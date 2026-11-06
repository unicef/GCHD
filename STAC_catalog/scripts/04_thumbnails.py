"""Step 4: render PNG thumbnails from the published COGs -> thumbnails/.

  thumbnails/<collection>/<id>.png              600x300, global layers, with legend
  thumbnails/<collection>/<id>/<tile>.png       256x256, river flood tiles
  thumbnails/<collection>/<id>.png (tiled)      from mosaic.vrt over the tile COGs

Map overlays ("overview" assets, used by STAC Browser's map when the COG cannot be shown):
  thumbnails/<collection>/<id>_overview.png         data only (transparent nodata, no basemap/legend),
  thumbnails/<collection>/<id>/<tile>_overview.png  covering exactly the item's bbox
  thumbnails/<collection>/_collection_overview.png  first layer of the collection over the
                                                    collection's bbox (union of its layers)
  thumbnails/overviews.json                         bbox of every overlay, checked by 05

Colours: layers.yaml palette (web_app/config.py HAZARD_VIS_PALETTES, or the
xlsx ColorCodes sheet), stretched over thumb_range or the 2-98th percentile.
Only layers whose COG already exists in public/gchd_cog/ are rendered.

Usage:  python scripts/04_thumbnails.py [--layers id ...] [--force]
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from rasterio.enums import Resampling

from common import (COG_PREFIX, PUBLIC_CONTAINER, STAC_DIR, clamp_world, container_client, gdal_env,
                    gdal_path, load_layers)

THUMB_DIR = STAC_DIR / "thumbnails"
NE_DIR = STAC_DIR / "work" / "naturalearth"   # ne_110m_land / ne_50m_land GeoJSON
OCEAN, LAND, COAST, TEXT = "#eef2f6", "#dde1e6", "#b9c0c8", "#3a3f45"
TILE_RANGE_DEFAULT = (0.0, 3.0)  # river flood depth (m) when thumb_range is not set
# Return levels where lower = more severe: dark end of the palette goes to the low values
REVERSED_PALETTE = {"drought_spi_terraclimate_1958-2025", "drought_spei_terraclimate_1958-2025"}
# Sparse, thin features (1-px coastal strips, conflict points) vanish when subsampled: read a finer overview
# and keep the maximum of each block instead
MAX_POOL = {"coastal_flood_100yr_jrc_2024": 8, "UNICEF_ACLED_CI_Sep2020_Aug2025": 4}


def land_patches(scale: str):
    with open(NE_DIR / f"ne_{scale}_land.geojson") as f:
        gj = json.load(f)
    polys = []
    for feat in gj["features"]:
        g = feat["geometry"]
        rings = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        polys += [Polygon(np.asarray(r[0]), closed=True) for r in rings]
    return polys


def read_overview(url: str, width: int, pool: int = 1):
    with rasterio.Env(**gdal_env()), rasterio.open(gdal_path(url)) as src:
        h = max(1, round(src.height * width / src.width))
        a = src.read(1, out_shape=(h * pool, width * pool), resampling=Resampling.nearest, masked=True)
        bounds = src.bounds
    if pool > 1:
        a = a.reshape(h, pool, width, pool).max(axis=(1, 3))  # masked max: nodata only if all are
    return a, bounds


def prepare(a, layer):
    a = np.ma.masked_invalid(a.astype("float32"))
    if layer["transparent_zero"]:
        a = np.ma.masked_equal(a, 0)
    return a


def stretch(a, layer, default=None):
    if layer.get("thumb_range"):
        return layer["thumb_range"]
    if default:
        return default
    v = a.compressed()
    if v.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(v, [2, 98])
    return (float(lo), float(hi)) if hi > lo else (float(v.min()), float(v.max()) or 1.0)


def cmap(layer):
    colours = layer["palette"] or ["#fff5eb", "#7f2704"]
    if layer["id"] in REVERSED_PALETTE:
        colours = colours[::-1]
    cm = LinearSegmentedColormap.from_list(layer["id"], colours)
    cm.set_bad(alpha=0)
    return cm


def draw(a, bounds, layer, out: Path, size, extent, scale, vrange, legend=True):
    w, h = size
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(OCEAN)
    ax.add_collection(PatchCollection(land_patches(scale), facecolor=LAND, edgecolor="none", zorder=0))
    left, bottom, right, top = bounds
    im = ax.imshow(a, extent=(left, right, bottom, top), cmap=cmap(layer), vmin=vrange[0], vmax=vrange[1],
                   interpolation="nearest", zorder=1)
    ax.add_collection(PatchCollection(land_patches(scale), facecolor="none", edgecolor=COAST,
                                      linewidth=0.3, zorder=2))
    ax.set_xlim(extent[0], extent[2])
    ax.set_ylim(extent[1], extent[3])
    ax.set_aspect("auto")
    ax.axis("off")
    if legend:
        cax = fig.add_axes([0.05, 0.08, 0.28, 0.035])
        cb = fig.colorbar(im, cax=cax, orientation="horizontal")
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=6, length=2, colors=TEXT, pad=1)
        cb.set_ticks([vrange[0], vrange[1]], labels=[f"{v:.3g}" for v in vrange])
        cb.ax.set_title(layer.get("legend_label") or layer.get("units") or "", fontsize=6.5, color=TEXT,
                        loc="left", pad=2)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, facecolor=OCEAN)
    plt.close(fig)


def global_thumb(layer, url, out: Path):
    a, bounds = read_overview(url, 1200, MAX_POOL.get(layer["id"], 1))
    a = prepare(a, layer)
    # Show the inhabited latitudes so every thumbnail has the same framing
    extent = (-180, -60, 180, 85)
    draw(a, bounds, layer, out, (600, 300), extent, "110m", stretch(a, layer))


def read_bounds(url: str) -> tuple:
    """Layer bounds clipped to the world, the same bbox 05 gives the STAC object."""
    with rasterio.Env(**gdal_env()), rasterio.open(gdal_path(url)) as src:
        return clamp_world(tuple(src.bounds))


def overview_png(layer, url, out: Path, bbox, width: int, vrange):
    """Data-only RGBA overlay of `url` over `bbox`, nodata transparent.

    All layers are EPSG:4326, so this reads the COG overviews directly (no warping) and, when
    `bbox` is larger than the layer (collection overlays), pastes it into a transparent canvas.
    """
    pool = MAX_POOL.get(layer["id"], 1)
    res = (bbox[2] - bbox[0]) / width  # canvas pixel size (degrees)
    H = max(1, round((bbox[3] - bbox[1]) / res))
    with rasterio.Env(**gdal_env()), rasterio.open(gdal_path(url)) as src:
        assert src.crs.to_epsg() == 4326, f"{url}: overlays assume EPSG:4326"
        b = src.bounds
        w = max(1, round((b.right - b.left) / res))
        h = max(1, round((b.top - b.bottom) / res))
        a = src.read(1, out_shape=(h * pool, w * pool), resampling=Resampling.nearest, masked=True)
    if pool > 1:
        a = a.reshape(h, pool, w, pool).max(axis=(1, 3))
    a = prepare(a, layer)
    rgba = cmap(layer)(np.ma.clip((a - vrange[0]) / ((vrange[1] - vrange[0]) or 1), 0, 1), bytes=True)
    rgba[..., 3] = np.where(np.ma.getmaskarray(a), 0, 255)
    # paste at the layer's offset in the canvas, cropping any part outside bbox
    canvas = np.zeros((H, width, 4), np.uint8)
    x0, y0 = round((b.left - bbox[0]) / res), round((bbox[3] - b.top) / res)
    sx, sy = max(0, -x0), max(0, -y0)
    dx, dy = max(0, x0), max(0, y0)
    ww, hh = min(w - sx, width - dx), min(h - sy, H - dy)
    canvas[dy:dy + hh, dx:dx + ww] = rgba[sy:sy + hh, sx:sx + ww]
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(out, canvas)


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def tile_thumb(layer, url, out: Path):
    a, bounds = read_overview(url, 256)
    a = prepare(a, layer)
    draw(a, bounds, layer, out, (256, 256), tuple(bounds), "50m",
         stretch(a, layer, TILE_RANGE_DEFAULT), legend=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", nargs="+")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    published = {b.name for b in container_client(PUBLIC_CONTAINER).list_blobs(name_starts_with=COG_PREFIX + "/")}
    base = container_client(PUBLIC_CONTAINER).url

    index_path = THUMB_DIR / "overviews.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    col_layers = defaultdict(list)  # collection -> [(layer, url of COG or VRT, bounds)]

    def overlay(layer, url, out: Path, bbox, width, vrange):
        key = str(out.relative_to(THUMB_DIR))
        if args.force or not out.exists() or key not in index:
            overview_png(layer, url, out, bbox, width, vrange)
            print(f"ovr    {out.relative_to(STAC_DIR)}", flush=True)
        index[key] = [round(v, 9) for v in bbox]

    for layer in load_layers():
        col = layer["collection"]
        if layer["source"]["type"] == "file":
            blob = f"{COG_PREFIX}/{col}/{layer['id']}.tif"
            if blob not in published:
                continue
            url = f"{base}/{blob}"
            bounds = read_bounds(url)
            col_layers[col].append((layer, url, bounds))
            if args.layers and layer["id"] not in args.layers:
                continue
            out = THUMB_DIR / col / f"{layer['id']}.png"
            if args.force or not out.exists():
                global_thumb(layer, url, out)
                print(f"thumb  {out.relative_to(STAC_DIR)}", flush=True)
            a, _ = read_overview(url, 1200, MAX_POOL.get(layer["id"], 1))
            overlay(layer, url, THUMB_DIR / col / f"{layer['id']}_overview.png", bounds, 1440,
                    stretch(prepare(a, layer), layer))
        else:
            tiles = sorted(n for n in published if n.startswith(f"{COG_PREFIX}/{col}/{layer['id']}/tiles/"))
            if not tiles:
                continue
            tlayer = layer | {"thumb_range": layer.get("thumb_range") or TILE_RANGE_DEFAULT}
            vrt_url = f"{base}/{COG_PREFIX}/{col}/{layer['id']}/mosaic.vrt"
            bounds = read_bounds(vrt_url)
            col_layers[col].append((tlayer, vrt_url, bounds))
            if args.layers and layer["id"] not in args.layers:
                continue
            out = THUMB_DIR / col / f"{layer['id']}.png"
            if args.force or not out.exists():
                # collection-level preview: the VRT reads each tile COG's overviews
                global_thumb(tlayer, vrt_url, out)
                print(f"thumb  {out.relative_to(STAC_DIR)}", flush=True)
            overlay(tlayer, vrt_url, THUMB_DIR / col / f"{layer['id']}_overview.png", bounds, 1440,
                    tlayer["thumb_range"])
            for t in tiles:
                out = THUMB_DIR / col / layer["id"] / (Path(t).stem + ".png")
                if args.force or not out.exists():
                    tile_thumb(layer, f"{base}/{t}", out)
                    print(f"thumb  {out.relative_to(STAC_DIR)}", flush=True)
                overlay(tlayer, f"{base}/{t}", THUMB_DIR / col / layer["id"] / (Path(t).stem + "_overview.png"),
                        read_bounds(f"{base}/{t}"), 256, tlayer["thumb_range"])

    # Collection overlay: its first layer (layers.yaml order) over the union of its layers' bounds
    for col, entries in col_layers.items():
        layer, url, _ = entries[0]
        if args.layers and layer["id"] not in args.layers:
            continue
        a, _ = read_overview(url, 1200, MAX_POOL.get(layer["id"], 1))
        overlay(layer, url, THUMB_DIR / col / "_collection_overview.png", union([e[2] for e in entries]),
                1440, stretch(prepare(a, layer), layer))

    index_path.write_text(json.dumps(dict(sorted(index.items())), indent=1))


if __name__ == "__main__":
    main()
