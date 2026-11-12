"""Step 5: build the static STAC catalog -> stac/.

Only layers whose COG exists in public/gchd_cog/ are included, so the catalog
can be built incrementally. Item geometry, proj:* and raster:bands come from
the COG itself (rio-stac); everything descriptive comes from layers.yaml.

  stac/catalog.json
  stac/<collection>/collection.json
  stac/<collection>/<item>/<item>.json
  stac/flood/river_flood_100yr_jrc_2024/collection.json   (one item per JRC tile)
  stac/worldpop_u18_2025/worldpop_u18_2025_<group>/       (one item per country, see population.py)

The catalog is SELF_CONTAINED (relative links), so it works from GitHub Pages
and from a local http server alike. COG hrefs are absolute Azure URLs.

Usage:  python scripts/05_build_stac.py [--workers 8]
"""
import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pystac
import rasterio
import yaml

import population
from rio_stac import create_stac_item
from shapely.geometry import box, mapping, shape
from stac_geoparquet.arrow import parse_stac_items_to_arrow, to_parquet

from common import (COG_PREFIX, LAYERS_YAML, PAGES_URL, PUBLIC_CONTAINER, REPO_DIR, STAC_DIR,
                    clamp_world, container_client, gdal_env)

STAC_OUT = STAC_DIR / "stac"
THUMB_DIR = STAC_DIR / "thumbnails"
COG_TYPE = pystac.MediaType.COG
VRT_TYPE = "application/xml"
TILE_RE = re.compile(r"ID\d+_([NS]\d+_[EW]\d+)_RP\d+_depth")
OVERVIEWS = THUMB_DIR / "overviews.json"   # overlay PNG -> bbox it covers (written by 04)

UNICEF = pystac.Provider(
    name="UNICEF", url="https://www.unicef.org/",
    roles=[pystac.ProviderRole.PROCESSOR, pystac.ProviderRole.HOST],
    description="Global Children's Hazard Database (GCHD)")

ROOT_DESCRIPTION = (
    "The **Global Children's Hazard Database (GCHD)** brings together global, gridded layers of "
    "the climate, environmental, geophysical and conflict hazards that children are exposed to: "
    "floods, tropical storms, droughts, heatwaves, fire, sand and dust storms, air pollution, "
    "malaria, landslides, earthquakes, volcanoes and conflict. It also includes WorldPop gridded "
    "estimates of the population under 18 (female, male and total), the basis for exposure analysis.\n\n"
    "Every layer is a Cloud-Optimized GeoTIFF that can be streamed directly into GIS tools or "
    "analysis code. Processing scripts and documentation: https://github.com/unicef/GCHD")


def web_app_info() -> dict:
    sys.path.insert(0, str(REPO_DIR / "web_app"))
    import config
    return config.HAZARD_INFO


def source_provider(layer, info) -> list[pystac.Provider]:
    meta = info.get(layer["id"]) or info.get(Path(layer["source_filename"]).stem) or {}
    if not layer["source_provider"]:
        return [UNICEF]
    return [pystac.Provider(name=layer["source_provider"], url=meta.get("source_url"),
                            roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.LICENSOR]),
            UNICEF]


def time_range(layer):
    if layer["start_year"]:
        return (datetime(layer["start_year"], 1, 1, tzinfo=timezone.utc),
                datetime(layer["end_year"], 12, 31, 23, 59, 59, tzinfo=timezone.utc), None)
    # No period in the name: fall back to the source file's modification date
    blob = layer["source"]["href"].split(f"/{PUBLIC_CONTAINER}/", 1)[1]
    t = container_client(PUBLIC_CONTAINER).get_blob_client(blob).get_blob_properties().last_modified
    return t, t, "source file modified date"


def layer_properties(layer) -> dict:
    p = {
        "title": layer["title"],
        "description": layer["description"],
        "GCHD:hazard": layer["hazard"],
        "GCHD:hazard_phase": layer["hazard_phase"],
        "GCHD:data_type": layer["data_type"],
        "GCHD:nominal_resolution": layer["resolution"],
        "GCHD:coverage": layer["coverage"],
        "GCHD:units": layer["units"],
        "GCHD:threshold": layer["threshold"],
        "GCHD:classes": layer["classes"],
        "GCHD:value_range": layer["range"],
        "GCHD:notes": layer["notes"],
        "GCHD:alternate_sources": layer["alternate_sources"],
        "GCHD:gee_asset": layer["gee_asset"],
    }
    return {k: v for k, v in p.items() if v not in (None, "", "None", [None, None])}


def add_overview(obj, png: Path, bbox):
    """Add a map overlay PNG as the `overview` asset, if 04 rendered it for this exact bbox.

    STAC Browser places preview images over the object's bbox, so a mismatch would misplace it.
    """
    index = json.loads(OVERVIEWS.read_text()) if OVERVIEWS.exists() else {}
    key = str(png.relative_to(THUMB_DIR))
    if not png.exists() or key not in index:
        return
    if max(abs(a - b) for a, b in zip(index[key], bbox)) > 1e-3:
        print(f"WARN   {key}: overlay bbox {index[key]} != {list(bbox)}, not added")
        return
    obj.add_asset("overview", pystac.Asset(str(png), title="Map overlay (data only)",
                                           media_type=pystac.MediaType.PNG, roles=["overview"]))


def make_item(layer, item_id, href, thumb: Path, info, extra=None, title=None) -> pystac.Item:
    start, end, dt_source = time_range(layer)
    props = layer_properties(layer) | {"start_datetime": start.isoformat(), "end_datetime": end.isoformat()}
    if dt_source:
        props["GCHD:datetime_source"] = dt_source
    if title:
        props["title"] = title
    props |= extra or {}
    with rasterio.Env(**gdal_env()):
        item = create_stac_item(
            "/vsicurl/" + href, id=item_id, collection=layer["collection"], input_datetime=start,
            properties=props, asset_name="data", asset_href=href, asset_roles=["data"],
            asset_media_type=COG_TYPE, with_proj=True, with_raster=True, geom_densify_pts=21)
    item.datetime = None
    # half-pixel overhangs (e.g. -180.125) break map clients: clip footprint to the world
    item.bbox = list(clamp_world(item.bbox))
    item.geometry = mapping(shape(item.geometry).intersection(box(-180, -90, 180, 90)))
    item.assets["data"].title = f"{layer['title']} (Cloud-Optimized GeoTIFF)"
    if thumb.exists():
        item.add_asset("thumbnail", pystac.Asset(str(thumb), title="Thumbnail",
                                                 media_type=pystac.MediaType.PNG, roles=["thumbnail"]))
    add_overview(item, thumb.with_name(f"{thumb.stem}_overview.png"), item.bbox)
    pystac.CommonMetadata(item).providers = source_provider(layer, info)
    return item


def absolute_item(json_path: Path) -> dict:
    """Saved item JSON with every href made absolute (Pages URL), so it works outside the catalog tree."""
    url = PAGES_URL + json_path.relative_to(STAC_DIR).as_posix()
    d = json.loads(json_path.read_text())
    for a in d["assets"].values():
        a["href"] = urljoin(url, a["href"])
    d["links"] = [l | {"href": urljoin(url, l["href"])} for l in d["links"]] + \
                 [{"rel": "self", "href": url, "type": "application/geo+json"}]
    return d


def write_item_index(sub: pystac.Collection):
    """items.geojson + items.parquet next to the collection: one request finds the tiles for an AOI."""
    d = Path(sub.get_self_href()).parent
    items = [absolute_item(Path(i.get_self_href())) for i in sub.get_items()]
    with open(d / "items.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": items}, f)
    to_parquet(parse_stac_items_to_arrow(items), d / "items.parquet")
    print(f"index  {d.relative_to(STAC_DIR)}/items.geojson, items.parquet ({len(items)} items)")


def build(workers: int):
    with open(LAYERS_YAML) as f:
        cfg = yaml.safe_load(f)
    groups, layers = cfg["collections"], cfg["layers"]
    info = web_app_info()
    base = container_client(PUBLIC_CONTAINER).url
    published = {b.name for b in container_client(PUBLIC_CONTAINER).list_blobs(name_starts_with=COG_PREFIX + "/")}

    root = pystac.Catalog(id="GCHD", title="UNICEF Global Children's Hazard Database",
                          description=ROOT_DESCRIPTION)
    collections = {}
    tiled = []  # nested tile collections that get an items.geojson / items.parquet index
    first_thumb = {}  # collection -> thumbnail of its first layer (layers.yaml order), as 04 does

    def collection(cid) -> pystac.Collection:
        if cid not in collections:
            g = groups[cid]
            collections[cid] = pystac.Collection(
                id=cid, title=g["title"],
                description=f"{g['title']} hazard layers in the Global Children's Hazard Database.",
                extent=pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]),
                                     pystac.TemporalExtent([[None, None]])),
                license="other",
                keywords=[k for k in ["GCHD", "UNICEF", "children", "hazard", g["title"], g.get("glide_code")] if k],
                extra_fields={"GCHD:glide_code": g.get("glide_code")} if g.get("glide_code") else None)
        return collections[cid]

    for layer in layers:
        col = layer["collection"]
        if layer["source"]["type"] == "file":
            blob = f"{COG_PREFIX}/{col}/{layer['id']}.tif"
            if blob not in published:
                continue
            first_thumb.setdefault(col, THUMB_DIR / col / f"{layer['id']}.png")
            item = make_item(layer, layer["id"], f"{base}/{blob}", THUMB_DIR / col / f"{layer['id']}.png", info)
            item.add_link(pystac.Link("derived_from", layer["source"]["href"], media_type="image/tiff",
                                      title="Source file (pre-COG)"))
            collection(col).add_item(item)
            print(f"item   {col}/{item.id}", flush=True)
            continue

        # Tiled layer: nested collection, one item per tile
        prefix = f"{COG_PREFIX}/{col}/{layer['id']}/tiles/"
        tiles = sorted(n for n in published if n.startswith(prefix))
        if not tiles:
            continue
        first_thumb.setdefault(col, THUMB_DIR / col / f"{layer['id']}.png")
        sub = pystac.Collection(
            id=layer["id"], title=f"{layer['title']} (original JRC tiles)",
            description=(f"{layer['description']}\n\nOriginal ~90 m (3 arc-second) JRC tiles of "
                         f"10°x10°, one item per tile. The `mosaic` asset is a GDAL VRT over all tiles "
                         f"for full-resolution access with a single URL."),
            extent=pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]),
                                 pystac.TemporalExtent([[None, None]])),
            license="other", keywords=["GCHD", "UNICEF", "children", "hazard", "flood", "JRC"],
            providers=source_provider(layer, info))
        vrt = f"{COG_PREFIX}/{col}/{layer['id']}/mosaic.vrt"
        if vrt in published:
            sub.add_asset("mosaic", pystac.Asset(f"{base}/{vrt}", title="Global mosaic (GDAL VRT over tile COGs)",
                                                 media_type=VRT_TYPE, roles=["data"]))
        thumb = THUMB_DIR / col / f"{layer['id']}.png"
        if thumb.exists():
            sub.add_asset("thumbnail", pystac.Asset(str(thumb), media_type=pystac.MediaType.PNG, roles=["thumbnail"]))

        def tile_item(blob):
            stem = Path(blob).stem
            code = TILE_RE.search(stem).group(1)
            return make_item(layer, f"{layer['id']}_{code}", f"{base}/{blob}",
                             THUMB_DIR / col / layer["id"] / f"{stem}.png", info,
                             extra={"GCHD:tile": stem}, title=f"{layer['title']} – tile {code.replace('_', ' ')}")

        with ThreadPoolExecutor(workers) as ex:
            for item in ex.map(tile_item, tiles):
                item.collection_id = layer["id"]
                sub.add_item(item)
        sub.update_extent_from_items()
        add_overview(sub, THUMB_DIR / col / f"{layer['id']}_overview.png", sub.extent.spatial.bboxes[0])
        collection(col).add_child(sub)
        tiled.append(sub)
        print(f"coll   {col}/{layer['id']} ({len(tiles)} tiles)", flush=True)

    for cid, c in collections.items():
        items = list(c.get_items(recursive=True))
        c.extent = pystac.Extent.from_items(items)
        thumb = first_thumb.get(cid)
        if thumb and thumb.exists():
            c.add_asset("thumbnail", pystac.Asset(str(thumb), media_type=pystac.MediaType.PNG, roles=["thumbnail"]))
        add_overview(c, THUMB_DIR / cid / "_collection_overview.png", c.extent.spatial.bboxes[0])
        root.add_child(c)

    pop = population.build_collection(add_overview, UNICEF, workers)
    if pop:
        root.add_child(pop[0])
        tiled += pop[1]

    if STAC_OUT.exists():
        shutil.rmtree(STAC_OUT)
    root.normalize_hrefs(str(STAC_OUT))
    for sub in tiled:
        d = Path(sub.get_self_href()).parent
        sub.add_asset("items_geojson", pystac.Asset(
            str(d / "items.geojson"), title="Item index (GeoJSON FeatureCollection, all items)",
            media_type=pystac.MediaType.GEOJSON, roles=["metadata"]))
        sub.add_asset("items_parquet", pystac.Asset(
            str(d / "items.parquet"), title="Item index (stac-geoparquet, all items)",
            media_type="application/vnd.apache.parquet", roles=["metadata"]))
    root.make_all_asset_hrefs_relative()
    root.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    for sub in tiled:
        write_item_index(sub)
    n = root.validate_all()
    print(f"Saved {STAC_OUT}/catalog.json; {len(collections) + bool(pop)} collections, validated {n} STAC objects")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    build(ap.parse_args().workers)
