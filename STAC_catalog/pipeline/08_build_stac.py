"""Step 8: build the static, Portolan-conformant STAC catalog -> stac/.

Layout (grouped; every leaf is a Collection with a collection-level `data` asset):

  stac/catalog.json                                     root (README.md, AGENTS.md alongside)
  stac/hazards/catalog.json
  stac/hazards/<theme>/catalog.json                     flood, drought, heatwave, ... (config/layers.yaml)
  stac/hazards/<theme>/<layer>/collection.json          one per hazard layer: data = COG
  stac/hazards/flood/river_flood_100yr_jrc_2024/        data = VRT mosaic, + 264 tile items + item index
  stac/multi_hazard/mhi_climate/  stac/reference/land_sea_mask/          (config/catalog.yaml layers)
  stac/population/worldpop_{u18_2025,2025}_{total,female,male}/          data = VRT, + country items
  stac/boundaries/adm{0,1,2}/  stac/exposure/adm{0,1,2}_hazard/          (Geo)Parquet on Azure

Hazard metadata comes from config/layers.yaml (the xlsx), exposure rules from config/hazard_map.yaml,
geometry / proj / raster bands from the COG itself (rio-stac), table schemas from the Parquet footers and
config/exposure_schema.json. Thumbnails (work/thumbnails/, steps 4 and 7) are copied next to the object
that uses them. Then gchd_stac.portolan.conform() applies the Portolan rules, and gchd_stac.docs writes
README.md + AGENTS.md everywhere.

The catalog is SELF_CONTAINED (relative links), so it works from GitHub Pages and from a local http
server alike. Data hrefs are absolute Azure URLs. Only data that are already published are included.

Usage:  python pipeline/08_build_stac.py [--workers 8]
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
from rio_stac import create_stac_item
from shapely.geometry import box, mapping, shape
from stac_geoparquet.arrow import parse_stac_items_to_arrow, to_parquet

import _path  # noqa: F401,E402  (STAC_catalog/ on sys.path)
from gchd_stac import docs, population, portolan
from gchd_stac.common import (CONFIG_DIR, COG_PREFIX, HAZARD_MAP_YAML, LAYERS_YAML, OVERVIEWS, PAGES_URL,
                              PUBLIC_CONTAINER, REPO_DIR, STAC_DIR, STAC_OUT, THUMB_DIR, WORK_DIR, clamp_world,
                              container_client, gdal_env, load_catalog_config, load_layers, stac_id)

COG_TYPE = pystac.MediaType.COG
VRT_TYPE = "application/xml"
PARQUET_TYPE = "application/vnd.apache.parquet"
PMTILES_TYPE = "application/vnd.pmtiles"
TILE_RE = re.compile(r"ID\d+_([NS]\d+_[EW]\d+)_RP\d+_depth")
EXT_RASTER = "https://stac-extensions.github.io/raster/v1.1.0/schema.json"
EXT_PROJ = "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
EXT_TABLE = "https://stac-extensions.github.io/table/v1.2.0/schema.json"
EXT_WEBMAP = "https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json"
PROJ_FIELDS = ("proj:epsg", "proj:code", "proj:shape", "proj:transform", "proj:bbox")

UNICEF = pystac.Provider(
    name="UNICEF", url="https://www.unicef.org/",
    roles=[pystac.ProviderRole.PROCESSOR, pystac.ProviderRole.HOST],
    description="Global Child Hazard Database (GCHD)")
UNICEF_PRODUCER = pystac.Provider(
    name="UNICEF", url="https://www.unicef.org/",
    roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.PROCESSOR, pystac.ProviderRole.HOST],
    description="Global Child Hazard Database (GCHD)")


def web_app_info() -> dict:
    sys.path.insert(0, str(REPO_DIR / "web_app"))
    import config
    return config.HAZARD_INFO


def source_provider(layer, info) -> list[pystac.Provider]:
    meta = info.get(layer["id"]) or info.get(Path(layer.get("source_filename") or "").stem) or {}
    if not layer.get("source_provider"):
        return [UNICEF]
    url = meta.get("source_url") or load_catalog_config().get("provider_urls", {}).get(layer["source_provider"])
    return [pystac.Provider(name=layer["source_provider"], url=url,
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


def make_item(layer, item_id, href, thumb: Path, info, extra=None, title=None, collection=None) -> pystac.Item:
    start, end, dt_source = time_range(layer)
    props = layer_properties(layer) | {"start_datetime": start.isoformat(), "end_datetime": end.isoformat()}
    if dt_source:
        props["GCHD:datetime_source"] = dt_source
    if title:
        props["title"] = title
    props |= extra or {}
    with rasterio.Env(**gdal_env()):
        item = create_stac_item(
            "/vsicurl/" + href, id=item_id, collection=collection or stac_id(layer), input_datetime=start,
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
    url = PAGES_URL + "stac/" + json_path.relative_to(STAC_OUT.resolve()).as_posix()
    d = json.loads(json_path.read_text())
    for a in d["assets"].values():
        a["href"] = urljoin(url, a["href"])
    d["links"] = [l | {"href": urljoin(url, l["href"])} for l in d["links"]] + \
                 [{"rel": "self", "href": url, "type": "application/geo+json"}]
    return d


# --- hazard / raster layers -------------------------------------------------------------------------

def exposure_rules(hm: dict, cid: str) -> list:
    """GCHD:exposure_rules of a collection, from config/hazard_map.yaml (stac_collection == cid)."""
    return [{"hazard_code": code, "app_name": h.get("app_name"), "unicef_code": h["unicef_code"],
             "valid": h["valid"], "op": h["op"], "threshold": h["threshold"],
             "default": h.get("app_name") is not None}
            for code, h in hm["hazards"].items() if h.get("stac_collection") == cid]


def layer_keywords(layer, theme: dict | None) -> list[str]:
    kw = ["GCHD", "UNICEF", "children"]
    if theme:
        kw += ["hazard", theme["title"], theme.get("glide_code")]
    else:
        kw += [layer.get("hazard"), layer["collection"].replace("_", " ")]
    return [k for k in kw if k]


def layer_collection(layer, item: pystac.Item, theme: dict | None, hm: dict) -> pystac.Collection:
    """A single-file layer as a Collection: the item's data asset, properties and footprint, lifted up.

    Portolan PTL-COL-001: a collection that holds one data file carries it at collection level.
    """
    p = item.properties
    start, end = p.get("start_datetime"), p.get("end_datetime")
    fields = {k: v for k, v in p.items() if k.startswith("GCHD:")} | (layer.get("extra_properties") or {})
    rules = exposure_rules(hm, stac_id(layer))
    if rules:
        fields["GCHD:exposure_rules"] = rules
    col = pystac.Collection(
        id=stac_id(layer), title=layer["title"], description=layer["description"] or layer["title"],
        extent=pystac.Extent(pystac.SpatialExtent([item.bbox]),
                             pystac.TemporalExtent([[pystac.utils.str_to_datetime(start) if start else None,
                                                     pystac.utils.str_to_datetime(end) if end else None]])),
        license="other", keywords=layer_keywords(layer, theme), providers=pystac.CommonMetadata(item).providers,
        extra_fields=fields)
    col.stac_extensions = [EXT_RASTER, EXT_PROJ]
    data = item.assets["data"]
    data.extra_fields |= {k: p[k] for k in PROJ_FIELDS if k in p}
    for key, asset in item.assets.items():
        col.add_asset(key, asset.clone())
    for link in item.links:
        if link.rel == "derived_from":
            col.add_link(link.clone())
    return col


def tiled_collection(layer, base, tiles, info, theme, hm, workers) -> pystac.Collection:
    """River flood: one item per JRC tile, the VRT mosaic as the collection's data asset."""
    col_dir = THUMB_DIR / layer["collection"]
    cid = stac_id(layer)
    rules = exposure_rules(hm, cid)
    sub = pystac.Collection(
        id=cid, title=f"{layer['title']} (original JRC tiles)",
        description=(f"{layer['description']}\n\nOriginal ~90 m (3 arc-second) JRC tiles of 10°x10°, one item per "
                     f"tile. The collection's `data` asset is a GDAL VRT over all tiles, for full-resolution access "
                     f"with a single URL; the `items_parquet` asset indexes the tiles for area-of-interest queries."),
        extent=pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]), pystac.TemporalExtent([[None, None]])),
        license="other", keywords=layer_keywords(layer, theme) + ["JRC"],
        providers=source_provider(layer, info),
        extra_fields={k: v for k, v in layer_properties(layer).items() if k.startswith("GCHD:")}
                     | ({"GCHD:exposure_rules": rules} if rules else {}))
    sub.add_asset("data", pystac.Asset(
        f"{base}/{COG_PREFIX}/{layer['collection']}/{layer['id']}/mosaic.vrt",
        title="Global mosaic (GDAL VRT over the tile COGs)", media_type=VRT_TYPE, roles=["data"]))
    thumb = col_dir / f"{layer['id']}.png"
    if thumb.exists():
        sub.add_asset("thumbnail", pystac.Asset(str(thumb), title="Thumbnail", media_type=pystac.MediaType.PNG,
                                                roles=["thumbnail"]))

    def tile_item(blob):
        stem = Path(blob).stem
        code = TILE_RE.search(stem).group(1)
        return make_item(layer, f"{layer['id']}_{code}", f"{base}/{blob}", col_dir / layer["id"] / f"{stem}.png",
                         info, extra={"GCHD:tile": stem}, title=f"{layer['title']} – tile {code.replace('_', ' ')}",
                         collection=cid)

    with ThreadPoolExecutor(workers) as ex:
        for item in ex.map(tile_item, tiles):
            sub.add_item(item)
    sub.update_extent_from_items()
    add_overview(sub, col_dir / f"{layer['id']}_overview.png", sub.extent.spatial.bboxes[0])
    return sub


# --- tables (boundaries, exposure) ------------------------------------------------------------------

def parquet_meta(url: str) -> tuple[list[dict], int, dict]:
    """(columns [{name, type}], row count, GeoParquet `geo` metadata) from the remote file's footer only."""
    import fsspec
    import pyarrow.parquet as pq
    with fsspec.open(url, "rb", block_size=1 << 20) as f:
        pf = pq.ParquetFile(f)
        schema, rows = pf.schema_arrow, pf.metadata.num_rows
        geo = json.loads((schema.metadata or {}).get(b"geo", b"{}"))
    return [{"name": n, "type": str(t)} for n, t in zip(schema.names, schema.types)], rows, geo


def maplibre_style(layer: str, pmtiles_url: str, pm: dict) -> dict:
    """Minimal MapLibre style drawing the boundary PMTiles (Portolan PTL-VIZ-002)."""
    return {"version": 8, "name": f"{layer.upper()} boundaries",
            "sources": {"data": {"type": "vector", "url": f"pmtiles://{pmtiles_url}",
                                 "minzoom": pm["min_zoom"], "maxzoom": pm["max_zoom"]}},
            "layers": [{"id": f"{layer}-fill", "type": "fill", "source": "data", "source-layer": layer,
                        "paint": {"fill-color": "#1CABE2", "fill-opacity": 0.25}},
                       {"id": f"{layer}-line", "type": "line", "source": "data", "source-layer": layer,
                        "paint": {"line-color": "#0058AB", "line-width": 0.6}}]}


def table_collections(cfg: dict) -> tuple[list, list, dict[str, str]]:
    """(boundary collections, exposure collections, {url: sha256 multihash}) from config/catalog.yaml."""
    t = cfg["tables"]
    schema = {c["name"]: c for c in json.loads((CONFIG_DIR / "exposure_schema.json").read_text())["columns"]}
    known, thumbs = {}, THUMB_DIR / "boundaries"
    bounds, expo = [], []
    for spec in t["boundaries"]:
        cid = spec["id"]
        url, tiles = f"{t['base']}/{cid}/{cid}.parquet", f"{t['base']}/{cid}/{cid}.pmtiles"
        known[url], known[tiles] = spec["checksum"]["parquet"], spec["checksum"]["pmtiles"]
        cols, rows, geo = parquet_meta(url)
        gcol = geo.get("columns", {}).get(geo.get("primary_column", "geometry"), {})
        bbox = list(clamp_world(gcol["bbox"])) if gcol.get("bbox") else [-180, -90, 180, 90]
        col = pystac.Collection(
            id=cid, title=spec["title"], description=spec["description"],
            extent=pystac.Extent(pystac.SpatialExtent([bbox]), pystac.TemporalExtent([[None, None]])),
            license="other", keywords=["GCHD", "UNICEF", "administrative boundaries", cid.upper()],
            providers=[UNICEF_PRODUCER],
            extra_fields={"table:columns": cols, "table:row_count": rows, "table:primary_geometry": "geometry",
                          "GCHD:geometry_types": gcol.get("geometry_types"),
                          "pmtiles:min_zoom": spec["pmtiles"]["min_zoom"], "pmtiles:max_zoom": spec["pmtiles"]["max_zoom"],
                          "pmtiles:layers": [cid]})
        col.stac_extensions = [EXT_TABLE, EXT_WEBMAP]
        col.add_asset("data", pystac.Asset(url, title=f"{spec['title']} (GeoParquet)", media_type=PARQUET_TYPE,
                                           roles=["data"]))
        col.add_asset("tiles", pystac.Asset(tiles, title=f"{spec['title']} (PMTiles vector tiles)",
                                            media_type=PMTILES_TYPE, roles=["visual"]))
        style = WORK_DIR / "styles" / f"{cid}.json"
        style.parent.mkdir(parents=True, exist_ok=True)
        style.write_text(json.dumps(maplibre_style(cid, tiles, spec["pmtiles"]), indent=2))
        col.add_asset("style", pystac.Asset(str(style), title="Default MapLibre style (PMTiles)",
                                            media_type="application/vnd.mapbox.style+json", roles=["style"]))
        if (thumbs / f"{cid}.jpg").exists():
            col.add_asset("thumbnail", pystac.Asset(str(thumbs / f"{cid}.jpg"), title="Thumbnail",
                                                    media_type=pystac.MediaType.JPEG, roles=["thumbnail"]))
        col.add_link(pystac.Link("pmtiles", tiles, media_type=PMTILES_TYPE, title=f"{cid.upper()} vector tiles",
                                 extra_fields={"pmtiles:layers": [cid]}))
        bounds.append(col)
        print(f"coll   boundaries/{cid} ({rows:,} units)", flush=True)
    for spec in t["exposure"]:
        cid, lvl = spec["id"], spec["level"]
        url = f"{t['base']}/{cid}/{cid}.parquet"
        known[url] = spec["checksum"]["parquet"]
        cols, rows, _ = parquet_meta(url)
        for c in cols:
            s = schema.get(c["name"])
            if s:
                c["description"] = s.get("description") or s.get("title")
                if s.get("unit"):
                    c["unit"] = s["unit"]
        col = pystac.Collection(
            id=cid, title=spec["title"], description=spec["description"],
            extent=pystac.Extent(pystac.SpatialExtent([[-180, -90, 180, 90]]), pystac.TemporalExtent([[None, None]])),
            license="other", keywords=["GCHD", "UNICEF", "children", "exposure", "hazard", lvl.upper()],
            providers=[UNICEF_PRODUCER],
            extra_fields={"table:columns": cols, "table:row_count": rows, "GCHD:source_release": t["release"],
                          "GCHD:boundaries": lvl})
        col.stac_extensions = [EXT_TABLE]
        col.add_asset("data", pystac.Asset(url, title=f"{spec['title']} (Parquet)", media_type=PARQUET_TYPE,
                                           roles=["data"]))
        if (thumbs / f"{lvl}.jpg").exists():
            col.add_asset("thumbnail", pystac.Asset(str(thumbs / f"{lvl}.jpg"),
                                                    title=f"Thumbnail ({lvl.upper()} administrative boundaries)",
                                                    media_type=pystac.MediaType.JPEG, roles=["thumbnail"]))
        expo.append(col)
        print(f"coll   exposure/{cid} ({rows:,} rows)", flush=True)
    # extents of the exposure tables follow their boundaries
    bb = {c.id: c.extent.spatial.bboxes[0] for c in bounds}
    for c in expo:
        c.extent.spatial.bboxes = [bb.get(c.extra_fields["GCHD:boundaries"], [-180, -90, 180, 90])]
    return bounds, expo, known


# --- after normalize_hrefs ----------------------------------------------------------------------

def localize_assets(root: pystac.Catalog):
    """Copy local files (thumbnails, overlays in work/) next to the object that uses them."""
    objs = [*root.get_all_collections(), *root.get_items(recursive=True)]
    seen = set()
    for obj in objs:
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        for key, a in obj.assets.items():
            src = Path(a.href)
            if "://" in a.href or not src.is_absolute() or STAC_OUT in src.parents:
                continue
            dst = Path(obj.get_self_href()).parent / f"{key}{src.suffix}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            a.href = str(dst)


def write_item_index(col_json: Path):
    """items.geojson + items.parquet next to a collection with items: one request finds the items for an AOI."""
    d = json.loads(col_json.read_text())
    items = [absolute_item((col_json.parent / l["href"]).resolve()) for l in d["links"] if l["rel"] == "item"]
    with open(col_json.parent / "items.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": items}, f)
    to_parquet(parse_stac_items_to_arrow(items), col_json.parent / "items.parquet")
    print(f"index  {col_json.parent.relative_to(STAC_OUT)}/items.parquet ({len(items)} items)")


# --- build ----------------------------------------------------------------------------------------

def build(workers: int, hash_remote: bool = False):
    cfg = load_catalog_config()
    with open(LAYERS_YAML) as f:
        themes = yaml.safe_load(f)["collections"]
    hm = yaml.safe_load(HAZARD_MAP_YAML.read_text())
    info = web_app_info()
    cc = container_client(PUBLIC_CONTAINER)
    base = cc.url
    published = {b.name for b in cc.list_blobs(name_starts_with=COG_PREFIX + "/")}

    rc = cfg["root"]
    root = pystac.Catalog(id=rc["id"], title=rc["title"], description=rc["description"],
                          extra_fields={"keywords": rc["keywords"]})
    groups = {g: pystac.Catalog(id=g, title=v["title"], description=v["description"])
              for g, v in cfg["groups"].items()}
    theme_cat = {t: pystac.Catalog(id=t, title=v["title"],
                                   description=f"{v['title']} hazard layers of the Global Child Hazard Database."
                                               + (f" GLIDE code: {v['glide_code']}." if v.get("glide_code") else ""),
                                   extra_fields={"GCHD:glide_code": v["glide_code"]} if v.get("glide_code") else None)
                 for t, v in themes.items()}
    with_items = []

    for layer in load_layers():
        grp = layer["collection"]
        theme = themes.get(grp)
        parent = theme_cat[grp] if theme else groups[grp]
        if layer["source"]["type"] == "file":
            blob = f"{COG_PREFIX}/{grp}/{layer['id']}.tif"
            if blob not in published:
                print(f"skip   {stac_id(layer)} ({blob} not published)")
                continue
            item = make_item(layer, stac_id(layer), f"{base}/{blob}", THUMB_DIR / grp / f"{layer['id']}.png", info)
            item.add_link(pystac.Link("derived_from", layer["source"]["href"], media_type="image/tiff",
                                      title="Source file (pre-COG)"))
            parent.add_child(layer_collection(layer, item, theme, hm))
            print(f"coll   {grp}/{stac_id(layer)}", flush=True)
            continue
        tiles = sorted(n for n in published if n.startswith(f"{COG_PREFIX}/{grp}/{layer['id']}/tiles/"))
        if not tiles:
            continue
        sub = tiled_collection(layer, base, tiles, info, theme, hm, workers)
        parent.add_child(sub)
        with_items.append(sub)
        print(f"coll   {grp}/{sub.id} ({len(tiles)} tiles)", flush=True)

    for col in population.build_collections(add_overview, UNICEF, workers):
        groups["population"].add_child(col)
        with_items.append(col)
    bounds, expo, known = table_collections(cfg)
    for col in bounds:
        groups["boundaries"].add_child(col)
    for col in expo:
        groups["exposure"].add_child(col)

    for t, cat in theme_cat.items():
        if list(cat.get_children()):
            groups["hazards"].add_child(cat)
    for g, cat in groups.items():
        if list(cat.get_children()):
            root.add_child(cat)

    if STAC_OUT.exists():
        shutil.rmtree(STAC_OUT)
    root.normalize_hrefs(str(STAC_OUT))
    localize_assets(root)
    for sub in with_items:
        d = Path(sub.get_self_href()).parent
        sub.add_asset("items_parquet", pystac.Asset(
            str(d / "items.parquet"), title="Item index (stac-geoparquet, all items)",
            media_type=PARQUET_TYPE, roles=["collection-mirror"]))
        sub.add_asset("items_geojson", pystac.Asset(
            str(d / "items.geojson"), title="Item index (GeoJSON FeatureCollection, all items)",
            media_type=pystac.MediaType.GEOJSON, roles=["metadata"]))
    root.make_all_asset_hrefs_relative()
    root.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    n = root.validate_all()
    print(f"saved  {STAC_OUT}/catalog.json; validated {n} STAC objects (pystac)")

    cache = WORK_DIR / "file_info.json"
    portolan.conform(STAC_OUT, cfg["license_url"], cache, known_checksums=known, hash_remote=hash_remote)
    for sub in with_items:
        write_item_index(Path(sub.get_self_href()))
    portolan.conform(STAC_OUT, cfg["license_url"], cache, known_checksums=known)   # file info of the indexes
    docs.write_docs(STAC_OUT, CONFIG_DIR / "agents")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--hash-remote", action="store_true",
                    help="stream-hash (sha256) remote data files that have no Content-MD5; cached in work/file_info.json")
    args = ap.parse_args()
    build(args.workers, args.hash_remote)
