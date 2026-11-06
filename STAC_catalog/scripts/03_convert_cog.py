"""Step 3: convert sources to COGs and upload them to public/gchd_cog/.

  single-file layers: public/final_hazard_layers/... -> gchd_cog/<collection>/<id>.tif
  river flood tiles:  climate/CCRI/data/raw/...      -> gchd_cog/flood/<id>/tiles/<tile>.tif
                      plus gchd_cog/flood/<id>/mosaic.vrt over the public tile COGs (--vrt)

Each output is validated and compared pixel-by-pixel against its source (random
windows) before upload. Existing outputs are skipped unless --force.

Usage:
  python scripts/03_convert_cog.py --layers tropical_storm_100yr_giri_2024
  python scripts/03_convert_cog.py --layers river_flood_100yr_jrc_2024 --max-tiles 3
  python scripts/03_convert_cog.py --layers river_flood_100yr_jrc_2024 --vrt-only
  python scripts/03_convert_cog.py --all
"""
import argparse
import csv
import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from azure.storage.blob import ContentSettings
from rasterio.windows import Window
from rio_cogeo.cogeo import cog_translate, cog_validate
from rio_cogeo.profiles import cog_profiles

from common import (ACCOUNT_URL, COG_PREFIX, PUBLIC_CONTAINER, RAW_CONTAINER, REPORTS_DIR,
                    STAC_DIR, container_client, load_layers)

WORK_DIR = Path(os.getenv("GCHD_WORK_DIR", STAC_DIR / "work"))
GDAL_CFG = {"GDAL_NUM_THREADS": "ALL_CPUS", "GDAL_TIFF_OVR_BLOCKSIZE": "512",
            "BIGTIFF": "IF_SAFER", "GDAL_CACHEMAX": 1024}


def cog_blob_name(layer: dict, tile: str | None = None) -> str:
    if tile:
        return f"{COG_PREFIX}/{layer['collection']}/{layer['id']}/tiles/{tile}"
    return f"{COG_PREFIX}/{layer['collection']}/{layer['id']}.tif"


def public_url(blob_name: str) -> str:
    return f"{ACCOUNT_URL}/{PUBLIC_CONTAINER}/{blob_name}"


def same_nodata(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return (math.isnan(a) and math.isnan(b)) or a == b


def nodata_mask(a, nodata):
    """True where `a` is missing: non-finite, or equal to a (non-NaN) nodata value."""
    m = ~np.isfinite(a)
    if nodata is not None and not math.isnan(nodata):
        m |= a == nodata
    return m


def download(container: str, blob_name: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    bc = container_client(container).get_blob_client(blob_name)
    size = bc.get_blob_properties().size
    if dest.exists() and dest.stat().st_size == size:
        return dest
    with open(dest, "wb") as f:
        bc.download_blob(max_concurrency=8).readinto(f)
    return dest


def remap(src_path: Path, dst_path: Path, nodata: float, dtype: str = "float32", src_nodata=None):
    """Rewrite as `dtype`, north-up, with the target nodata (source nodata / non-finite -> nodata).

    src_nodata overrides the source's nodata tag (for untagged fill values, e.g. SPEI -9999).
    Casting to an integer dtype must be lossless: every valid value has to be a whole
    number that fits the dtype and (if the dtype changes) differs from nodata, otherwise
    this raises. A same-dtype source keeps its values, so e.g. 0 in a uint8 layer with
    nodata 0 is nodata by convention.
    """
    integer = np.issubdtype(np.dtype(dtype), np.integer)
    info = np.iinfo(dtype) if integer else None
    with rasterio.open(src_path) as src:
        t = src.transform
        fill = src.nodata if src_nodata is None else src_nodata
        south_up = t.e > 0  # e.g. GIRI storm: origin at -90, rows run northwards
        transform = Affine(t.a, t.b, t.c, t.d, -t.e, t.f + t.e * src.height) if south_up else t
        profile = src.profile | {"driver": "GTiff", "dtype": dtype, "nodata": nodata,
                                 "transform": transform,
                                 "tiled": True, "blockxsize": 512, "blockysize": 512,
                                 "compress": "DEFLATE", "BIGTIFF": "IF_SAFER"}
        with rasterio.open(dst_path, "w", **profile) as dst:
            # Full-width bands of 512 rows: strip-organised sources (e.g. coastal flood, one
            # 432k-px row per strip) are then decompressed once, not once per 512-px block.
            for row in range(0, src.height, 512):
                h = min(512, src.height - row)
                win = Window(0, row, src.width, h)
                if south_up:
                    a = src.read(1, window=Window(0, src.height - row - h, src.width, h))[::-1]
                else:
                    a = src.read(1, window=win)
                bad = ~np.isfinite(a) if np.issubdtype(a.dtype, np.floating) else np.zeros(a.shape, bool)
                if fill is not None and not math.isnan(fill):
                    bad |= a == fill
                if integer:
                    v = a[~bad]
                    if v.size and (np.any(v != np.round(v)) or v.min() < info.min or v.max() > info.max
                                   or (src.dtypes[0] != dtype and np.any(v == nodata))):
                        raise RuntimeError(f"{src_path.name}: values in {win} do not fit {dtype} losslessly")
                dst.write(np.where(bad, nodata, a).astype(dtype), 1, window=win)


def to_cog(src_path: Path, dst_path: Path, nodata, resampling: str):
    with rasterio.open(src_path) as src:
        dtype = src.dtypes[0]
    profile = cog_profiles.get("deflate") | {
        "blockxsize": 512, "blockysize": 512,
        "predictor": 3 if dtype.startswith("float") else 2,
    }
    cog_translate(src_path, dst_path, profile, nodata=nodata, overview_resampling=resampling,
                  config=GDAL_CFG, in_memory=False, quiet=True)
    valid, errors, _ = cog_validate(dst_path, quiet=True)
    if not valid:
        raise RuntimeError(f"{dst_path.name} is not a valid COG: {errors}")


def verify(src_path: Path, cog_path: Path, nodata, n: int = 12, size: int = 256):
    """Compare random full-resolution windows; nodata (tagged, or the target value) is compared as a mask."""
    rng = np.random.default_rng(0)
    with rasterio.open(src_path) as a, rasterio.open(cog_path) as b:
        assert (a.width, a.height, a.transform) == (b.width, b.height, b.transform), "grid differs"
        for _ in range(n):
            w = Window(int(rng.integers(0, max(1, a.width - size))),
                       int(rng.integers(0, max(1, a.height - size))),
                       min(size, a.width), min(size, a.height))
            x = a.read(1, window=w, masked=True).astype("float64")
            y = b.read(1, window=w, masked=True).astype("float64")
            xm = np.ma.getmaskarray(x) | nodata_mask(x.data, nodata)
            ym = np.ma.getmaskarray(y) | nodata_mask(y.data, nodata)
            if not np.array_equal(xm, ym):
                raise RuntimeError(f"nodata mask differs in window {w}")
            if not np.allclose(x.data[~xm], y.data[~ym], rtol=1e-6, atol=0):
                raise RuntimeError(f"values differ in window {w}")


def upload(path: Path, blob_name: str, content_type: str = "image/tiff"):
    bc = container_client(PUBLIC_CONTAINER).get_blob_client(blob_name)
    with open(path, "rb") as f:
        bc.upload_blob(f, overwrite=True, max_concurrency=8,
                       content_settings=ContentSettings(content_type=content_type))


def exists(blob_name: str) -> bool:
    return container_client(PUBLIC_CONTAINER).get_blob_client(blob_name).exists()


def process(layer: dict, src_container: str, src_blob: str, dst_blob: str, force: bool, keep: bool) -> str:
    if not force and exists(dst_blob):
        return f"skip   {dst_blob} (exists)"
    work = WORK_DIR / layer["id"]
    src = download(src_container, src_blob, work / "src" / Path(src_blob).name)
    nodata = layer["nodata"]

    with rasterio.open(src) as ds:
        # layers.yaml "dtype" overrides (e.g. binary coastal flood -> uint8); Float64 -> Float32
        dtype = layer.get("dtype") or ("float32" if ds.dtypes[0] == "float64" else ds.dtypes[0])
        # an untagged source (nodata None) is remapped too, so its NaNs/fill values get the target nodata
        src_nodata = layer.get("source_nodata")
        needs_remap = (dtype != ds.dtypes[0] or ds.transform.e > 0 or src_nodata is not None
                       or not same_nodata(ds.nodata, nodata))
    staged = src
    if needs_remap:
        staged = work / "staged" / src.name
        staged.parent.mkdir(exist_ok=True)
        remap(src, staged, nodata, dtype, src_nodata)

    out = work / "cog" / Path(dst_blob).name
    out.parent.mkdir(exist_ok=True)
    to_cog(staged, out, nodata, layer["overview_resampling"])
    verify(staged, out, nodata)
    upload(out, dst_blob)
    if not keep:
        for p in {src, staged, out}:
            p.unlink(missing_ok=True)
    return f"done   {dst_blob}"


def build_vrt(layer: dict):
    prefix = f"{COG_PREFIX}/{layer['collection']}/{layer['id']}/tiles/"
    urls = ["/vsicurl/" + public_url(b.name)
            for b in container_client(PUBLIC_CONTAINER).list_blobs(name_starts_with=prefix)]
    if not urls:
        raise SystemExit(f"No tile COGs under {prefix}")
    work = WORK_DIR / layer["id"]
    work.mkdir(parents=True, exist_ok=True)
    lst, vrt = work / "tiles.txt", work / "mosaic.vrt"
    lst.write_text("\n".join(sorted(urls)))
    subprocess.run(["gdalbuildvrt", "-input_file_list", str(lst), str(vrt)], check=True,
                   env=os.environ | {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"})
    dst = f"{COG_PREFIX}/{layer['collection']}/{layer['id']}/mosaic.vrt"
    upload(vrt, dst, content_type="application/xml")
    print(f"done   {dst} ({len(urls)} tiles)")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--layers", nargs="+", help="layer ids from layers.yaml")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--max-tiles", type=int, help="tiled layer: only the first N tiles (pilot)")
    ap.add_argument("--workers", type=int, default=3, help="parallel tiles")
    ap.add_argument("--vrt-only", action="store_true", help="tiled layer: only rebuild mosaic.vrt")
    ap.add_argument("--force", action="store_true", help="redo outputs that already exist")
    ap.add_argument("--keep", action="store_true", help="keep local work files")
    args = ap.parse_args()

    layers = load_layers()
    if args.layers:
        unknown = set(args.layers) - {l["id"] for l in layers}
        if unknown:
            raise SystemExit(f"Unknown layer ids: {unknown}")
        layers = [l for l in layers if l["id"] in args.layers]

    for layer in layers:
        src = layer["source"]
        if src["type"] == "file":
            blob = src["href"].split(f"/{PUBLIC_CONTAINER}/", 1)[1]
            print(process(layer, PUBLIC_CONTAINER, blob, cog_blob_name(layer), args.force, args.keep), flush=True)
            continue

        if not args.vrt_only:
            with open(REPORTS_DIR / "river_flood_tiles.csv") as f:
                tiles = [t["blob"] for t in csv.DictReader(f)][: args.max_tiles]
            print(f"{layer['id']}: {len(tiles)} tiles")
            with ProcessPoolExecutor(args.workers) as ex:
                futs = [ex.submit(process, layer, RAW_CONTAINER, t,
                                  cog_blob_name(layer, Path(t).name), args.force, args.keep) for t in tiles]
                for fu in futs:
                    print(fu.result(), flush=True)
        build_vrt(layer)


if __name__ == "__main__":
    main()
