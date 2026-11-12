"""WorldPop under-18 population (R2025A, 2025, 100 m): VRT mosaics, thumbnails and STAC collections.

The source files are already valid COGs in public/worldpop_2025/ (checked with rio-cogeo), so
they are referenced in place, not copied. One file per country and sex group:

  public/worldpop_2025/R2025A/2025/100m/{F_U18,M_U18,T_U18}/<iso3>_<S>_Under_18_2025_CN_100m_R2025A_v1.tif

Outputs:
  public/gchd_cog/worldpop_u18_2025/<group>/mosaic.vrt     global GDAL VRT over the country COGs (--vrt)
  thumbnails/worldpop_u18_2025/<group>.png                 global thumbnail (+ _overview.png overlay)
  thumbnails/worldpop_u18_2025/<group>/<iso3>.png          country thumbnail (+ _overview.png overlay)
  thumbnails/worldpop_u18_2025/_collection_overview.png    total U18 overlay for the parent collection

05_build_stac.py calls build_collection() to add the collection tree to the catalog:

  WorldPop U18 population 2025 (worldpop_u18_2025)
  ├─ Female U18 (worldpop_u18_2025_female)  240 country items
  ├─ Male U18   (worldpop_u18_2025_male)    240 country items
  └─ Total U18  (worldpop_u18_2025_total)   240 country items

Usage:  python scripts/population.py [--vrt] [--thumbs] [--force] [--workers 8]
"""
import argparse
import csv
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from common import (ACCOUNT_URL, COG_PREFIX, PUBLIC_CONTAINER, REPO_DIR, STAC_DIR, clamp_world,
                    container_client, gdal_env)

COLLECTION = "worldpop_u18_2025"
SOURCE_PREFIX = "worldpop_2025/R2025A/2025/100m"
YEAR = 2025
NODATA = -99999.0
GROUPS = {  # group id -> source folder, title, sex word, GEE asset (exposure_analysis/population_data)
    "female": ("F_U18", "Female U18", "girls", "projects/unicef-ccri/assets/population/worldpop_T_F_U18_2025_CN_100m"),
    "male": ("M_U18", "Male U18", "boys", "projects/unicef-ccri/assets/population/worldpop_T_M_U18_2025_CN_100m"),
    "total": ("T_U18", "Total U18", "children", "projects/unicef-ccri/assets/population/worldpop_T_U18_2025_CN_100m"),
}
TITLE = "WorldPop U18 population 2025"
LICENSE = "CC-BY-4.0"
CITATION = "WorldPop (www.worldpop.org), R2025A"
SOURCE_URL = "https://www.worldpop.org/"
DESCRIPTION = (
    "Estimated number of children under 18 per ~100 m grid cell (3 arc-seconds) in 2025, from the "
    "WorldPop R2025A constrained (`CN`) population estimates. Constrained means people are only "
    "allocated to cells mapped as built settlement; all other cells are nodata.\n\n"
    "The data are one Cloud-Optimized GeoTIFF per country, served from their original location on "
    "Azure, with one STAC item per country. The `mosaic` asset of each group is a GDAL VRT over all "
    "country files, for global access with a single URL.\n\n"
    f"Units: people per grid cell. Nodata: {NODATA:g}. License: {LICENSE}. Citation: {CITATION}.")

THUMB_DIR = STAC_DIR / "thumbnails" / COLLECTION
OVERVIEWS = STAC_DIR / "thumbnails" / "overviews.json"
COUNTRIES_CSV = REPO_DIR / "exposure_analysis" / "subnational_level" / "config" / "countries_info.csv"
WORK_DIR = Path(os.getenv("GCHD_WORK_DIR", STAC_DIR / "work")) / COLLECTION

# Population is heavy-tailed (median ~1 child per cell, peaks of several hundred): log colour scale
PALETTE = ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"]
VRANGE = (0.1, 50.0)
LEGEND = "children per 100 m cell (log)"


def country_names() -> dict:
    with open(COUNTRIES_CSV) as f:
        names = {r["ISO3"].lower(): r["name"] for r in csv.DictReader(f)}
    return names | {"xkx": "Kosovo"}


def list_sources() -> dict:
    """group -> sorted [(iso3, public URL)] of the country COGs."""
    cc = container_client(PUBLIC_CONTAINER)
    out = {}
    for g, (folder, *_) in GROUPS.items():
        blobs = sorted(b.name for b in cc.list_blobs(name_starts_with=f"{SOURCE_PREFIX}/{folder}/")
                       if b.name.endswith(".tif"))
        out[g] = [(Path(b).name[:3], f"{ACCOUNT_URL}/{PUBLIC_CONTAINER}/{b}") for b in blobs]
    return out


def vrt_blob(group: str) -> str:
    return f"{COG_PREFIX}/{COLLECTION}/{group}/mosaic.vrt"


# --- VRT mosaics --------------------------------------------------------------------------------

def build_vrts(sources: dict):
    from azure.storage.blob import ContentSettings
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    for g, files in sources.items():
        lst, vrt = WORK_DIR / f"{g}_files.txt", WORK_DIR / f"{g}_mosaic.vrt"
        lst.write_text("\n".join("/vsicurl/" + u for _, u in files))
        subprocess.run(["gdalbuildvrt", "-overwrite", "-srcnodata", f"{NODATA:g}", "-vrtnodata", f"{NODATA:g}",
                        "-input_file_list", str(lst), str(vrt)], check=True,
                       env=os.environ | {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"})
        bc = container_client(PUBLIC_CONTAINER).get_blob_client(vrt_blob(g))
        with open(vrt, "rb") as f:
            bc.upload_blob(f, overwrite=True, content_settings=ContentSettings(content_type="application/xml"))
        print(f"done   {vrt_blob(g)} ({len(files)} countries)", flush=True)


# --- thumbnails ---------------------------------------------------------------------------------

def _render(url, out: Path, bbox, width: int, basemap: bool, legend: bool = False, max_h: int = None,
            pool: int = 4):
    """Log-scaled PNG of `url` over `bbox` (EPSG:4326, read from the COG overviews).

    basemap=False gives a data-only RGBA overlay (nodata transparent) for STAC Browser's map.
    Reads `pool` times finer and averages each block: a single coarse overview pixel would
    otherwise show one dense cell as a dark speck in an empty area.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from matplotlib.collections import PatchCollection
    from matplotlib.colors import LinearSegmentedColormap, LogNorm
    from rasterio.enums import Resampling
    from rasterio.windows import from_bounds

    res = (bbox[2] - bbox[0]) / width
    H = max(1, round((bbox[3] - bbox[1]) / res))
    if max_h and H > max_h:  # very tall country bbox: shrink the width instead
        width, H = max(1, round(width * max_h / H)), max_h
        res = (bbox[2] - bbox[0]) / width
    with rasterio.Env(**gdal_env()), rasterio.open("/vsicurl/" + url) as src:
        # read only where bbox overlaps the data (boundless reads go through a slow WarpedVRT)
        b = src.bounds
        rb = (max(bbox[0], b.left), max(bbox[1], b.bottom), min(bbox[2], b.right), min(bbox[3], b.top))
        rh, rw = max(1, round((rb[3] - rb[1]) / res)), max(1, round((rb[2] - rb[0]) / res))
        a = src.read(1, window=from_bounds(*rb, transform=src.transform), out_shape=(rh * pool, rw * pool),
                     resampling=Resampling.nearest, masked=True)
    a = np.ma.masked_where(np.ma.getmaskarray(a) | (a.filled(NODATA) == NODATA), a)
    a = a.reshape(rh, pool, rw, pool).mean(axis=(1, 3))  # masked mean: nodata only if the whole block is
    cm = LinearSegmentedColormap.from_list("pop", PALETTE)
    cm.set_bad(alpha=0)
    cm.set_under(PALETTE[0])
    norm = LogNorm(*VRANGE, clip=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not basemap:
        rgba = cm(norm(np.ma.clip(a, VRANGE[0], VRANGE[1])), bytes=True)
        rgba[..., 3] = np.where(np.ma.getmaskarray(a), 0, 255)
        canvas = np.zeros((H, width, 4), np.uint8)  # overlays use bbox == data bounds; paste in case not
        x0, y0 = round((rb[0] - bbox[0]) / res), round((bbox[3] - rb[3]) / res)
        hh, ww = min(rh, H - y0), min(rw, width - x0)
        canvas[y0:y0 + hh, x0:x0 + ww] = rgba[:hh, :ww]
        plt.imsave(out, canvas)
        _quantize(out)
        return
    land = _land_patches("110m" if (bbox[2] - bbox[0]) > 60 else "50m")
    fig = plt.figure(figsize=(width / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#eef2f6")
    ax.add_collection(PatchCollection(land, facecolor="#dde1e6", edgecolor="none", zorder=0))
    im = ax.imshow(np.ma.clip(a, VRANGE[0], None), extent=(rb[0], rb[2], rb[1], rb[3]), cmap=cm,
                   norm=norm, interpolation="nearest", zorder=1)
    ax.add_collection(PatchCollection(land, facecolor="none", edgecolor="#b9c0c8", linewidth=0.3, zorder=2))
    ax.set_xlim(bbox[0], bbox[2])
    ax.set_ylim(bbox[1], bbox[3])
    ax.set_aspect("auto")
    ax.axis("off")
    if legend:
        cax = fig.add_axes([0.05, 0.08, 0.28, 0.035])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=6, length=2, colors="#3a3f45", pad=1, which="both")
        cb.set_ticks([0.1, 1, 10, 50], labels=["0.1", "1", "10", "50"])
        cb.ax.minorticks_off()
        cb.ax.set_title(LEGEND, fontsize=6.5, color="#3a3f45", loc="left", pad=2)
    fig.savefig(out, dpi=100, facecolor="#eef2f6")
    plt.close(fig)
    _quantize(out)


def _quantize(png: Path, colours: int = 64):
    """Palette PNG (keeps transparency): ~4x smaller than RGBA, enough for a 5-colour ramp."""
    from PIL import Image
    Image.open(png).quantize(colours, method=Image.Quantize.FASTOCTREE).save(png, optimize=True)


_LAND = {}


def _land_patches(scale):
    if scale not in _LAND:
        import numpy as np
        from matplotlib.patches import Polygon
        gj = json.loads((STAC_DIR / "work" / "naturalearth" / f"ne_{scale}_land.geojson").read_text())
        polys = []
        for feat in gj["features"]:
            g = feat["geometry"]
            rings = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            polys += [Polygon(np.asarray(r[0]), closed=True) for r in rings]
        _LAND[scale] = polys
    # fresh copies: a matplotlib artist can only belong to one figure
    from matplotlib.patches import Polygon
    return [Polygon(p.get_xy(), closed=True) for p in _LAND[scale]]


def file_bbox(url) -> tuple:
    import rasterio
    with rasterio.Env(**gdal_env()), rasterio.open("/vsicurl/" + url) as src:
        return clamp_world(tuple(src.bounds))


def render_thumbs(sources: dict, force: bool, workers: int):
    index = json.loads(OVERVIEWS.read_text()) if OVERVIEWS.exists() else {}
    base = container_client(PUBLIC_CONTAINER).url
    world = (-180.0, -60.0, 180.0, 85.0)

    def todo(p: Path):
        return force or not p.exists() or (p.name.endswith("_overview.png") and key(p) not in index)

    def key(p: Path):
        return str(p.relative_to(OVERVIEWS.parent))

    def country(g, iso, url):
        bbox = file_bbox(url)
        thumb, ovr = THUMB_DIR / g / f"{iso}.png", THUMB_DIR / g / f"{iso}_overview.png"
        if todo(thumb):
            _render(url, thumb, bbox, 256, basemap=True, max_h=256)
        if todo(ovr):
            _render(url, ovr, bbox, 256, basemap=False, max_h=512)
        return key(ovr), [round(v, 9) for v in bbox]

    for g, files in sources.items():
        vrt = f"{base}/{vrt_blob(g)}"
        bbox = file_bbox(vrt)
        thumb, ovr = THUMB_DIR / f"{g}.png", THUMB_DIR / f"{g}_overview.png"
        if todo(thumb):
            _render(vrt, thumb, world, 600, basemap=True, legend=True, pool=8)
        if todo(ovr):
            _render(vrt, ovr, bbox, 1440, basemap=False, pool=8)
        index[key(ovr)] = [round(v, 9) for v in bbox]
        print(f"thumb  {g} (global)", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            for k, b in ex.map(lambda f: country(g, *f), files):
                index[k] = b
        print(f"thumb  {g} ({len(files)} countries)", flush=True)
        if g == "total":  # parent collection overlay
            index[key(THUMB_DIR / "_collection_overview.png")] = [round(v, 9) for v in bbox]
            if todo(THUMB_DIR / "_collection_overview.png"):
                (THUMB_DIR / "_collection_overview.png").write_bytes(ovr.read_bytes())
    OVERVIEWS.write_text(json.dumps(dict(sorted(index.items())), indent=1))


# --- STAC ---------------------------------------------------------------------------------------

def build_collection(add_overview, unicef, workers: int = 8):
    """Parent collection with one child collection per group; None if the VRTs are not published.

    `add_overview(obj, png, bbox)` and the `unicef` provider come from 05_build_stac.py.
    Returns (parent, [child collections]) so 05 can write the item indexes.
    """
    import pystac
    import rasterio
    from rio_stac import create_stac_item
    from shapely.geometry import box, mapping, shape

    cc = container_client(PUBLIC_CONTAINER)
    if not all(cc.get_blob_client(vrt_blob(g)).exists() for g in GROUPS):
        print(f"skip   {COLLECTION} (mosaic.vrt not published; run scripts/population.py --vrt)")
        return None
    base, names, sources = cc.url, country_names(), list_sources()
    start = datetime(YEAR, 1, 1, tzinfo=timezone.utc)
    end = datetime(YEAR, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    worldpop = pystac.Provider(name="WorldPop, University of Southampton", url=SOURCE_URL,
                               roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.LICENSOR])
    providers = [worldpop, unicef]
    keywords = ["GCHD", "UNICEF", "children", "population", "under 18", "WorldPop", "exposure"]
    world = pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]), pystac.TemporalExtent([[start, end]]))
    common = {"GCHD:units": "people per grid cell", "GCHD:nominal_resolution": "100 m (3 arc-seconds)",
              "GCHD:citation": CITATION, "GCHD:source_release": "R2025A"}

    parent = pystac.Collection(id=COLLECTION, title=TITLE, description=DESCRIPTION, extent=world,
                               license=LICENSE, keywords=keywords, providers=providers, extra_fields=dict(common))
    parent.add_link(pystac.Link("license", "https://creativecommons.org/licenses/by/4.0/",
                                media_type="text/html", title="CC BY 4.0"))
    parent.add_link(pystac.Link("about", SOURCE_URL, media_type="text/html", title="WorldPop"))
    children = []
    for g, (folder, gtitle, word, gee) in GROUPS.items():
        cid = f"{COLLECTION}_{g}"
        sub = pystac.Collection(
            id=cid, title=f"{gtitle} population 2025 (WorldPop R2025A)",
            description=(f"Estimated number of {word} under 18 per ~100 m grid cell in {YEAR} "
                         f"(WorldPop R2025A, constrained), one item per country.\n\n" + DESCRIPTION),
            extent=world, license=LICENSE, keywords=keywords + [gtitle], providers=providers,
            extra_fields=common | {"GCHD:gee_asset": gee, "GCHD:source_folder": f"{SOURCE_PREFIX}/{folder}/"})
        sub.add_asset("mosaic", pystac.Asset(f"{base}/{vrt_blob(g)}", title="Global mosaic (GDAL VRT over country COGs)",
                                             media_type="application/xml", roles=["data"]))
        thumb = THUMB_DIR / f"{g}.png"
        if thumb.exists():
            sub.add_asset("thumbnail", pystac.Asset(str(thumb), media_type=pystac.MediaType.PNG, roles=["thumbnail"]))

        def item(f, g=g, gtitle=gtitle, cid=cid):
            iso, url = f
            name = names.get(iso, iso.upper())
            with rasterio.Env(**gdal_env()):
                it = create_stac_item(
                    "/vsicurl/" + url, id=f"{cid}_{iso}", collection=cid, input_datetime=start,
                    properties={"title": f"{gtitle} population 2025 – {name}", "start_datetime": start.isoformat(),
                                "end_datetime": end.isoformat(), "GCHD:iso3": iso.upper(), "GCHD:country": name}
                               | common,
                    asset_name="data", asset_href=url, asset_roles=["data"], asset_media_type=pystac.MediaType.COG,
                    with_proj=True, with_raster=True, geom_densify_pts=21)
            it.datetime = None
            it.bbox = list(clamp_world(it.bbox))
            it.geometry = mapping(shape(it.geometry).intersection(box(-180, -90, 180, 90)))
            it.assets["data"].title = f"{gtitle} population 2025 – {name} (Cloud-Optimized GeoTIFF)"
            png = THUMB_DIR / g / f"{iso}.png"
            if png.exists():
                it.add_asset("thumbnail", pystac.Asset(str(png), title="Thumbnail", media_type=pystac.MediaType.PNG,
                                                       roles=["thumbnail"]))
            add_overview(it, THUMB_DIR / g / f"{iso}_overview.png", it.bbox)
            pystac.CommonMetadata(it).providers = providers
            return it

        with ThreadPoolExecutor(workers) as ex:
            for it in ex.map(item, sources[g]):
                sub.add_item(it)
        sub.update_extent_from_items()
        add_overview(sub, THUMB_DIR / f"{g}_overview.png", sub.extent.spatial.bboxes[0])
        parent.add_child(sub)
        children.append(sub)
        print(f"coll   {COLLECTION}/{cid} ({len(sources[g])} countries)", flush=True)

    parent.extent = pystac.Extent.from_items(list(parent.get_items(recursive=True)))
    thumb = THUMB_DIR / "total.png"
    if thumb.exists():
        parent.add_asset("thumbnail", pystac.Asset(str(thumb), media_type=pystac.MediaType.PNG, roles=["thumbnail"]))
    add_overview(parent, THUMB_DIR / "_collection_overview.png", parent.extent.spatial.bboxes[0])
    return parent, children


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vrt", action="store_true", help="build and upload the global mosaic.vrt per group")
    ap.add_argument("--thumbs", action="store_true", help="render thumbnails and map overlays")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    sources = list_sources()
    missing = set(iso for iso, _ in sources["total"]) - set(country_names())
    if missing:
        print(f"WARN   no country name for {sorted(missing)}")
    if args.vrt:
        build_vrts(sources)
    if args.thumbs:
        render_thumbs(sources, args.force, args.workers)


if __name__ == "__main__":
    main()
