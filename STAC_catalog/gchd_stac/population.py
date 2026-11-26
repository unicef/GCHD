"""WorldPop R2025A 2025 population (100 m): VRT mosaics, thumbnails and STAC collections.

Two datasets, three groups each. The source files are already valid COGs in public/worldpop_2025/
(checked with rio-cogeo), so they are referenced in place, not copied. One file per country and group:

  worldpop_u18_2025  children under 18   {F_U18,M_U18,T_U18}/<iso3>_<S>_Under_18_2025_CN_100m_R2025A_v1.tif
  worldpop_2025      all ages            {T,T_F,T_M}/<iso3>_..._2025_CN_100m_R2025A_v1.tif
                                         (T_F and T_M lack FJI, GRL and RUS)

Outputs:
  public/gchd_cog/<dataset>/<group>/mosaic_ovr.vrt   global GDAL VRT over the country COGs, with a virtual
                                                     <OverviewList> so low-zoom reads use the country
                                                     overviews (pipeline/04_population.py --vrt)
  work/thumbnails/<dataset>/<group>.png              global thumbnail (+ _overview.png map overlay)
  work/thumbnails/<dataset>/<group>/<iso3>.png       country thumbnail (+ _overview.png map overlay)

08_build_stac.py calls build_collections() and places the six collections under population/:
one Collection per group, a collection-level `data` asset (the VRT), one item per country.
"""
import csv
import hashlib
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import common
from .common import (ACCOUNT_URL, COG_PREFIX, PUBLIC_CONTAINER, REPO_DIR, clamp_world, container_client,
                     gdal_env)

SOURCE_PREFIX = "worldpop_2025/R2025A/2025/100m"
YEAR = 2025
NODATA = -99999.0
LICENSE = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
CITATION = "WorldPop (www.worldpop.org), R2025A"
SOURCE_URL = "https://www.worldpop.org/"
OVERVIEW_LIST = '  <OverviewList resampling="average">2 4 8 16 32 64 128 256 512</OverviewList>\n'
COUNTRIES_CSV = REPO_DIR / "exposure_analysis" / "subnational_level" / "config" / "countries_info.csv"
# Population is heavy-tailed (median ~1 person per cell, peaks of several hundred): log colour scale
PALETTE = ["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"]

_GEE = "projects/unicef-ccri/assets/population/worldpop_{}_2025_CN_100m"
DATASETS = {
    "worldpop_u18_2025": {
        "who": "children under 18", "short": "U18", "vrange": (0.1, 50.0),
        "legend": "children per 100 m cell (log)",
        "groups": {  # group -> source folder, title word, people word, GEE asset (exposure_analysis/population_data)
            "total": ("T_U18", "Total U18", "children", _GEE.format("T_U18")),
            "female": ("F_U18", "Female U18", "girls", _GEE.format("T_F_U18")),
            "male": ("M_U18", "Male U18", "boys", _GEE.format("T_M_U18")),
        },
        "title": "{gtitle} population 2025 (WorldPop R2025A)",
    },
    "worldpop_2025": {
        "who": "people (all ages)", "short": "all ages", "vrange": (0.1, 100.0),
        "legend": "people per 100 m cell (log)",
        "groups": {
            "total": ("T", "Total", "people", None),
            "female": ("T_F", "Female", "females", None),
            "male": ("T_M", "Male", "males", None),
        },
        "title": "{gtitle} population 2025, all ages (WorldPop R2025A)",
    },
}


def description(dataset: str) -> str:
    d = DATASETS[dataset]
    return (
        f"Estimated number of {d['who']} per ~100 m grid cell (3 arc-seconds) in {YEAR}, from the WorldPop "
        "R2025A constrained (`CN`) population estimates. Constrained means people are only allocated to "
        "cells mapped as built settlement; all other cells are nodata.\n\n"
        "The data are one Cloud-Optimized GeoTIFF per country, served from their original location on "
        "Azure, with one STAC item per country. The collection's `data` asset is a GDAL VRT over all "
        "country files, with virtual overviews, for global access with a single URL.\n\n"
        f"Units: people per grid cell. Nodata: {NODATA:g}. License: {LICENSE}. Citation: {CITATION}.")


def country_names() -> dict:
    with open(COUNTRIES_CSV) as f:
        names = {r["ISO3"].lower(): r["name"] for r in csv.DictReader(f)}
    return names | {"xkx": "Kosovo"}


def list_sources(dataset: str) -> dict:
    """group -> sorted [(iso3, public URL)] of the country COGs."""
    cc = container_client(PUBLIC_CONTAINER)
    out = {}
    for g, (folder, *_) in DATASETS[dataset]["groups"].items():
        blobs = sorted(b.name for b in cc.list_blobs(name_starts_with=f"{SOURCE_PREFIX}/{folder}/")
                       if b.name.endswith(".tif"))
        out[g] = [(Path(b).name[:3], f"{ACCOUNT_URL}/{PUBLIC_CONTAINER}/{b}") for b in blobs]
    return out


def vrt_blob(dataset: str, group: str) -> str:
    return f"{COG_PREFIX}/{dataset}/{group}/mosaic_ovr.vrt"


def thumb_dir(dataset: str) -> Path:
    return common.THUMB_DIR / dataset


# --- VRT mosaics --------------------------------------------------------------------------------

def build_vrts(dataset: str, sources: dict, upload: bool):
    """Build mosaic_ovr.vrt per group in work/; upload only with `upload`, and never over an existing blob."""
    from azure.storage.blob import ContentSettings
    work = common.WORK_DIR / dataset
    work.mkdir(parents=True, exist_ok=True)
    cc = container_client(PUBLIC_CONTAINER)
    for g, files in sources.items():
        lst, vrt = work / f"{g}_files.txt", work / f"{g}_mosaic_ovr.vrt"
        lst.write_text("\n".join("/vsicurl/" + u for _, u in files))
        subprocess.run(["gdalbuildvrt", "-q", "-overwrite", "-srcnodata", f"{NODATA:g}", "-vrtnodata", f"{NODATA:g}",
                        "-input_file_list", str(lst), str(vrt)], check=True,
                       env=os.environ | {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"})
        vrt.write_text(vrt.read_text().replace("</VRTDataset>", OVERVIEW_LIST + "</VRTDataset>"))
        data = vrt.read_bytes()
        print(f"vrt    {dataset}/{g}: {len(files)} countries, {len(data):,} B -> {vrt}", flush=True)
        if upload:
            bc = cc.get_blob_client(vrt_blob(dataset, g))
            if bc.exists():
                print(f"skip   {vrt_blob(dataset, g)} (exists; delete it first to replace it)")
                continue
            bc.upload_blob(data, overwrite=False, content_settings=ContentSettings(
                content_type="application/xml", content_md5=hashlib.md5(data).digest()))
            print(f"done   {vrt_blob(dataset, g)}", flush=True)


# --- thumbnails ---------------------------------------------------------------------------------

def _render(url, out: Path, bbox, width: int, basemap: bool, legend: bool = False, max_h: int = None,
            pool: int = 4, vrange=(0.1, 50.0), legend_label: str = "people per 100 m cell (log)"):
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
    norm = LogNorm(*vrange, clip=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not basemap:
        rgba = cm(norm(np.ma.clip(a, vrange[0], vrange[1])), bytes=True)
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
    im = ax.imshow(np.ma.clip(a, vrange[0], None), extent=(rb[0], rb[2], rb[1], rb[3]), cmap=cm,
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
        ticks = [t for t in (0.1, 1, 10, 100, 1000) if t <= vrange[1]] + ([vrange[1]] if vrange[1] not in (0.1, 1, 10, 100, 1000) else [])
        cb.set_ticks(ticks, labels=[f"{t:g}" for t in ticks])
        cb.ax.minorticks_off()
        cb.ax.set_title(legend_label, fontsize=6.5, color="#3a3f45", loc="left", pad=2)
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
        gj = json.loads((common.WORK_DIR / "naturalearth" / f"ne_{scale}_land.geojson").read_text())
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


def render_thumbs(dataset: str, sources: dict, force: bool, workers: int):
    ds = DATASETS[dataset]
    td = thumb_dir(dataset)
    index = json.loads(common.OVERVIEWS.read_text()) if common.OVERVIEWS.exists() else {}
    base = container_client(PUBLIC_CONTAINER).url
    world = (-180.0, -60.0, 180.0, 85.0)
    style = {"vrange": ds["vrange"], "legend_label": ds["legend"]}

    def key(p: Path):
        return str(p.relative_to(common.THUMB_DIR))

    def todo(p: Path):
        return force or not p.exists() or (p.name.endswith("_overview.png") and key(p) not in index)

    def country(g, iso, url):
        bbox = file_bbox(url)
        thumb, ovr = td / g / f"{iso}.png", td / g / f"{iso}_overview.png"
        if todo(thumb):
            _render(url, thumb, bbox, 256, basemap=True, max_h=256, **style)
        if todo(ovr):
            _render(url, ovr, bbox, 256, basemap=False, max_h=512, **style)
        return key(ovr), [round(v, 9) for v in bbox]

    for g, files in sources.items():
        vrt = f"{base}/{vrt_blob(dataset, g)}"
        bbox = file_bbox(vrt)
        thumb, ovr = td / f"{g}.png", td / f"{g}_overview.png"
        if todo(thumb):
            _render(vrt, thumb, world, 600, basemap=True, legend=True, pool=8, **style)
        if todo(ovr):
            _render(vrt, ovr, bbox, 1440, basemap=False, pool=8, **style)
        index[key(ovr)] = [round(v, 9) for v in bbox]
        print(f"thumb  {dataset}/{g} (global)", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            for k, b in ex.map(lambda f: country(g, *f), files):
                index[k] = b
        print(f"thumb  {dataset}/{g} ({len(files)} countries)", flush=True)
        common.OVERVIEWS.write_text(json.dumps(dict(sorted(index.items())), indent=1))


# --- STAC ---------------------------------------------------------------------------------------

def build_collections(add_overview, unicef, workers: int = 8) -> list:
    """One pystac Collection per dataset group (six in all), each with one item per country.

    `add_overview(obj, png, bbox)` and the `unicef` host provider come from 08_build_stac.py.
    A dataset whose VRTs are not published is skipped with a message.
    """
    import pystac
    import rasterio
    from rio_stac import create_stac_item
    from shapely.geometry import box, mapping, shape

    cc = container_client(PUBLIC_CONTAINER)
    base, names = cc.url, country_names()
    start = datetime(YEAR, 1, 1, tzinfo=timezone.utc)
    end = datetime(YEAR, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    worldpop = pystac.Provider(name="WorldPop, University of Southampton", url=SOURCE_URL,
                               roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.LICENSOR])
    providers = [worldpop, unicef]
    common_props = {"GCHD:units": "people per grid cell", "GCHD:nominal_resolution": "100 m (3 arc-seconds)",
                    "GCHD:citation": CITATION, "GCHD:source_release": "R2025A"}
    world = pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]), pystac.TemporalExtent([[start, end]]))
    out = []
    for dataset, ds in DATASETS.items():
        if not all(cc.get_blob_client(vrt_blob(dataset, g)).exists() for g in ds["groups"]):
            print(f"skip   {dataset} (mosaic_ovr.vrt not published; run pipeline/04_population.py --vrt)")
            continue
        sources, td = list_sources(dataset), thumb_dir(dataset)
        all_iso = {iso for iso, _ in sources["total"]}
        keywords = ["GCHD", "UNICEF", "population", "WorldPop", "exposure"] + \
                   (["children", "under 18"] if ds["short"] == "U18" else ["all ages"])
        for g, (folder, gtitle, word, gee) in ds["groups"].items():
            cid = f"{dataset}_{g}"
            title = ds["title"].format(gtitle=gtitle)
            missing = sorted(all_iso - {iso for iso, _ in sources[g]})
            desc = (f"Estimated number of {word}{' under 18' if ds['short'] == 'U18' else ' (all ages)'} per "
                    f"~100 m grid cell in {YEAR} (WorldPop R2025A, constrained), one item per country.\n\n"
                    + description(dataset))
            props = common_props | {"GCHD:source_folder": f"{SOURCE_PREFIX}/{folder}/"}
            if gee:
                props["GCHD:gee_asset"] = gee
            if missing:
                props["GCHD:missing_countries"] = [m.upper() for m in missing]
                desc += (f"\n\nNot available for {', '.join(m.upper() for m in missing)}: WorldPop R2025A has no "
                         f"{gtitle.lower()} file for them (the total layer covers them).")
            sub = pystac.Collection(id=cid, title=title, description=desc, extent=world, license=LICENSE,
                                    keywords=keywords + [gtitle], providers=providers, extra_fields=dict(props))
            sub.add_asset("data", pystac.Asset(
                f"{base}/{vrt_blob(dataset, g)}", title=f"{title} – global mosaic (GDAL VRT)",
                description=("GDAL VRT mosaic of the per-country WorldPop R2025A COGs "
                             f"({SOURCE_PREFIX}/{folder}/), with virtual overviews (OverviewList 2-512) built "
                             "from the country COGs' own overviews"),
                media_type="application/xml", roles=["data"],
                extra_fields={"bands": [{"data_type": "float32", "nodata": NODATA, "raster:sampling": "area",
                                         "unit": "people per grid cell"}]}))
            thumb = td / f"{g}.png"
            if thumb.exists():
                sub.add_asset("thumbnail", pystac.Asset(str(thumb), title="Thumbnail",
                                                        media_type=pystac.MediaType.PNG, roles=["thumbnail"]))

            def item(f, cid=cid, gtitle=gtitle, g=g, props=props, title=title):
                iso, url = f
                name = names.get(iso, iso.upper())
                with rasterio.Env(**gdal_env()):
                    it = create_stac_item(
                        "/vsicurl/" + url, id=f"{cid}_{iso}", collection=cid, input_datetime=start,
                        properties={"title": f"{title.split(' (')[0]} – {name}",
                                    "start_datetime": start.isoformat(), "end_datetime": end.isoformat(),
                                    "GCHD:iso3": iso.upper(), "GCHD:country": name} | props,
                        asset_name="data", asset_href=url, asset_roles=["data"],
                        asset_media_type=pystac.MediaType.COG, with_proj=True, with_raster=True,
                        geom_densify_pts=21)
                it.datetime = None
                it.bbox = list(clamp_world(it.bbox))
                it.geometry = mapping(shape(it.geometry).intersection(box(-180, -90, 180, 90)))
                it.assets["data"].title = f"{gtitle} population 2025 – {name} (Cloud-Optimized GeoTIFF)"
                png = td / g / f"{iso}.png"
                if png.exists():
                    it.add_asset("thumbnail", pystac.Asset(str(png), title="Thumbnail",
                                                           media_type=pystac.MediaType.PNG, roles=["thumbnail"]))
                add_overview(it, td / g / f"{iso}_overview.png", it.bbox)
                pystac.CommonMetadata(it).providers = providers
                return it

            with ThreadPoolExecutor(workers) as ex:
                for it in ex.map(item, sources[g]):
                    sub.add_item(it)
            sub.update_extent_from_items()
            add_overview(sub, td / f"{g}_overview.png", sub.extent.spatial.bboxes[0])
            out.append(sub)
            print(f"coll   population/{cid} ({len(sources[g])} countries)", flush=True)
    return out
