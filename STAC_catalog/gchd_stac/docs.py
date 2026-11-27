"""README.md and AGENTS.md for every Catalog and Collection of the saved catalog (Portolan PTL-FIL-001).

Both are generated from the object's own metadata, so they never go stale:

  README.md   for people: what the collection is, its key facts, its files and how to open them
  AGENTS.md   for agents/LLMs: access code, field notes (bands, nodata, units, exposure rules, table
              columns), caveats and related collections with their join keys

Hand-written notes: put them in config/agents/<collection or catalog id>.md. They are appended to the
generated AGENTS.md under "## Additional notes" on every build, and never overwritten.
"""
import json
from pathlib import Path

PAGES_STAC = "https://unicef.github.io/GCHD/STAC_catalog/stac"
BROWSER = "https://unicef.github.io/GCHD/STAC_catalog/browser/"
REPO = "https://github.com/unicef/GCHD"

FACTS = [  # (field, label) shown in the README table, in order
    ("GCHD:hazard", "Hazard"), ("GCHD:hazard_phase", "Phase"), ("GCHD:data_type", "Data type"),
    ("GCHD:units", "Units"), ("GCHD:nominal_resolution", "Resolution"), ("GCHD:coverage", "Coverage"),
    ("GCHD:threshold", "Exposure threshold"), ("GCHD:classes", "Classes"), ("GCHD:value_range", "Value range"),
    ("GCHD:citation", "Citation"), ("GCHD:source_release", "Source release"), ("GCHD:gee_asset", "GEE asset"),
    ("table:row_count", "Rows"),
]


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def _abs_href(obj_path: Path, stac_root: Path, href: str) -> str:
    if "://" in href:
        return href
    rel = (obj_path.parent / href).resolve().relative_to(stac_root.resolve()).as_posix()
    return f"{PAGES_STAC}/{rel}"


def _size(n: int | None) -> str:
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024


def _bands(asset: dict) -> list:
    return asset.get("bands") or asset.get("raster:bands") or []


def kind(d: dict) -> str:
    a = d.get("assets", {}).get("data", {})
    t = a.get("type", "")
    if "parquet" in t:
        if not d.get("table:primary_geometry"):
            return "table"
        return "points" if "Point" in (d.get("GCHD:geometry_types") or []) else "boundaries"
    if t == "application/xml":
        return "mosaic"
    if "tiff" in t:
        return "raster"
    return "other"


def _period(d: dict) -> str:
    iv = d.get("extent", {}).get("temporal", {}).get("interval", [[None, None]])[0]
    if not any(iv):
        return ""
    return " – ".join((x or "…")[:10] for x in iv)


# --- access snippets ------------------------------------------------------------------------------

def access_snippet(d: dict, url: str, index_url: str | None) -> str:
    k = kind(d)
    if k == "raster":
        return f'''```python
import rasterio
url = "{url}"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/{url}`.'''
    if k == "mosaic":
        s = f'''```python
import rasterio, rasterio.mask
vrt = "/vsicurl/{url}"   # GDAL VRT: one global raster over all files, reads only what you touch
with rasterio.open(vrt) as src:
    value = next(src.sample([(lon, lat)]))
    data, transform = rasterio.mask.mask(src, [aoi_geojson], crop=True)
```'''
        if index_url:
            s += f'''

The catalog is static (no `/search`). To find the files for an area of interest, filter the item index:

```python
import geopandas as gpd
items = gpd.read_parquet("{index_url}")              # stac-geoparquet, one row per item
hits = items[items.intersects(aoi)]                  # shapely geometry in EPSG:4326
urls = hits["assets"].map(lambda a: a["data"]["href"]).tolist()
```'''
        return s
    if k == "table":
        level = d["id"].split("_")[0]
        return f'''```sql
-- DuckDB reads the Parquet over HTTP (range requests): no download needed
INSTALL httpfs; LOAD httpfs;
SELECT iso3, {level}_name, hazard_code, u18_aexp, u18_rexp
FROM '{url}'
WHERE hazard_code = 'river_flood_100yr' AND iso3 = 'BGD'
ORDER BY u18_aexp DESC LIMIT 10;
```
```python
import pandas as pd
df = pd.read_parquet("{url}", filters=[("iso3", "==", "BGD")])
```'''
    if k == "points":
        return f'''```python
import geopandas as gpd
gdf = gpd.read_parquet("{url}", filters=[("iso3", "==", "BGD")])          # one country
gdf = gpd.read_parquet("{url}", bbox=(west, south, east, north))          # GeoParquet 1.1 bbox covering
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT iso3, count(*) AS n FROM '{url}' GROUP BY iso3 ORDER BY n DESC;
-- points in an area: the bbox column lets DuckDB skip row groups
SELECT name, education_level, longitude, latitude FROM '{url}'
WHERE bbox.xmin BETWEEN 88 AND 93 AND bbox.ymin BETWEEN 20.5 AND 26.7;
```
Hazard value at each point (sample a hazard COG of this catalog; GDAL streams only the blocks it needs):
```python
import rasterio
with rasterio.open(hazard_cog_url) as src:
    gdf["hazard"] = [v[0] for v in src.sample(zip(gdf.longitude, gdf.latitude))]
```'''
    if k == "boundaries":
        return f'''```python
import geopandas as gpd
gdf = gpd.read_parquet("{url}", bbox=(west, south, east, north))   # GeoParquet 1.1 with bbox covering
gdf = gpd.read_parquet("{url}", filters=[("iso3", "==", "BGD")])
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT ucode, name, iso3, ST_Area(geometry) FROM '{url}' WHERE iso3 = 'BGD';
```
For web maps use the `tiles` asset (PMTiles, vector tiles in one file).'''
    return f"Data: {url}"


# --- related collections --------------------------------------------------------------------------

def related(d: dict, index: dict) -> list[str]:
    k, cid, out = kind(d), d["id"], []

    def ref(other: str, why: str):
        if other in index:
            out.append(f"- [{index[other]['title']}]({index[other]['url']}) (`{other}`): {why}")

    rules = d.get("GCHD:exposure_rules", [])
    if rules:
        codes = ", ".join(f"`{r['hazard_code']}`" for r in rules)
        for t in ("adm2_hazard", "adm1_hazard", "adm0_hazard"):
            ref(t, f"exposure statistics of this layer, rows with `hazard_code` in {codes}")
    if k in ("raster", "mosaic") and not cid.startswith("worldpop"):
        ref("worldpop_u18_2025_total", "children under 18 per ~100 m cell, the exposure denominator")
        ref("worldpop_2025_total", "people of all ages per ~100 m cell")
    if cid.startswith("worldpop"):
        for t in ("adm2_hazard",):
            ref(t, "exposure statistics computed with these population grids")
    if k == "table":
        level = cid.split("_")[0]
        ref(level, f"boundaries of the units: join `{level}_ucode` = `ucode`")
        ref("adm2", "ADM2 boundaries: join `adm2_ucode` = `ucode`") if level != "adm2" else None
        out.append("- Hazard layers: each hazard collection lists its `hazard_code`s in `GCHD:exposure_rules`.")
    if k == "boundaries":
        ref(f"{cid}_hazard", f"exposure statistics per unit: join `ucode` = `{cid}_ucode`")
    if k == "points":
        ref("adm2", "ADM2 boundaries: assign each point to its district with a spatial join")
        out.append("- Hazard layers: sample any hazard COG at the points to find facilities in hazard zones; "
                   "each hazard collection's `GCHD:exposure_rules` give the threshold for 'exposed'.")
    if cid == "mhi_climate":
        ref("land_sea_mask", "the land/sea mask of the same ERA5 0.1° grid")
    if cid == "land_sea_mask":
        ref("mhi_climate", "the MHI index on the same grid")
    return out


# --- writers --------------------------------------------------------------------------------------

def _assets_table(d: dict, path: Path, stac_root: Path) -> str:
    rows = ["| Asset | Type | Size | Link |", "|---|---|---|---|"]
    for key, a in d.get("assets", {}).items():
        rows.append(f"| `{key}` | {a.get('type', '')} | {_size(a.get('file:size'))} | "
                    f"[{a.get('title') or key}]({_abs_href(path, stac_root, a['href'])}) |")
    return "\n".join(rows)


def collection_readme(d: dict, path: Path, stac_root: Path, n_items: int) -> str:
    facts = [(label, d[f]) for f, label in FACTS if d.get(f) not in (None, "", [])]
    if _period(d):
        facts.insert(0, ("Period", _period(d)))
    facts.append(("License", d.get("license")))
    facts.append(("Providers", ", ".join(f"{p['name']} ({', '.join(p.get('roles', []))})"
                                         for p in d.get("providers", []))))
    producers = [p["name"] for p in d.get("providers", []) if "producer" in p.get("roles", [])]
    derived = [l["href"] for l in d["links"] if l["rel"] in ("derived_from", "via")]
    source = f"Source: {', '.join(producers) or 'UNICEF'}" + (f" ({derived[0]})" if derived else "") + \
             (f"; release {d['GCHD:source_release']}" if d.get("GCHD:source_release") else "") + \
             "; processed and hosted by UNICEF for the Global Child Hazard Database."
    lines = [f"# {d['title']}", "", d["description"], "", source, "", "| | |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in facts]
    lines += ["", "## Files", "", _assets_table(d, path, stac_root)]
    if n_items:
        lines += ["", f"The collection has **{n_items} items** (one file each); the `items_parquet` asset lists them all "
                      "in one stac-geoparquet file."]
    rules = d.get("GCHD:exposure_rules")
    if rules:
        lines += ["", "## Exposure rule", "", "A pixel counts as exposed when:", ""]
        lines += [f"- `{r['hazard_code']}` (UNICEF code {r.get('unicef_code')}): value {r['op']} {r['threshold']} "
                  f"(pixels with data: value {r['valid']})" for r in rules]
    url = _abs_href(path, stac_root, d["assets"]["data"]["href"]) if "data" in d.get("assets", {}) else None
    idx = d.get("assets", {}).get("items_parquet")
    if url:
        lines += ["", "## Access", "", access_snippet(d, url, _abs_href(path, stac_root, idx["href"]) if idx else None)]
    rel = path.relative_to(stac_root).as_posix()
    lines += ["", "---", f"STAC: [`{rel}`]({PAGES_STAC}/{rel}) · Browse: [STAC Browser]({BROWSER}#/{rel}) · "
                         f"Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [{REPO}]({REPO})", ""]
    return "\n".join(lines)


def collection_agents(d: dict, path: Path, stac_root: Path, index: dict, n_items: int) -> str:
    k = kind(d)
    data = d.get("assets", {}).get("data", {})
    url = _abs_href(path, stac_root, data["href"]) if data else None
    idx = d.get("assets", {}).get("items_parquet")
    lines = [f"# AGENTS.md: {d['title']} (`{d['id']}`)", "",
             "Guidance for AI agents and LLMs working with this collection. Generated from the collection's "
             "metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.", "",
             "## Overview", "", d["description"].split("\n\n")[0], ""]
    what = {"raster": "one global Cloud-Optimized GeoTIFF (collection-level `data` asset)",
            "mosaic": f"{n_items} files, one STAC item each, plus a global GDAL VRT mosaic as the collection-level "
                      "`data` asset",
            "table": "one Parquet table (collection-level `data` asset)",
            "boundaries": "one GeoParquet file (`data`) plus PMTiles vector tiles (`tiles`)",
            "points": "one GeoParquet 1.1 point table (collection-level `data` asset), sorted by `iso3`"}.get(k, "see assets")
    lic_link = next((l["href"] for l in d["links"] if l["rel"] == "license"), None)
    facts = [f"- Layout: {what}.", f"- Data URL: {url}" if url else "",
             f"- Item index: {_abs_href(path, stac_root, idx['href'])}" if idx else "",
             f"- Period: {_period(d)}" if _period(d) else "",
             f"- License: {d.get('license')}" + (f" ({lic_link})" if lic_link else "")
             + (f"; cite as: {d['GCHD:citation']}" if d.get("GCHD:citation") else "")]
    lines += [x for x in facts if x] + [""]
    lines += ["## Accessing the data", "", access_snippet(d, url, _abs_href(path, stac_root, idx["href"]) if idx else None)
              if url else "No data asset.", ""]

    lines += ["## Schema & field notes", ""]
    for b in _bands(data):
        stats = b.get("statistics", {})
        lines.append(f"- Band: data type `{b.get('data_type')}`, nodata `{b.get('nodata')}`"
                     + (f", unit {b['unit']}" if b.get("unit") else "")
                     + (f"; observed range {stats.get('minimum'):.4g} to {stats.get('maximum'):.4g}, mean "
                        f"{stats.get('mean'):.4g}, valid pixels {stats.get('valid_percent', 0):.1f}%"
                        if stats.get("minimum") is not None else ""))
    for f, label in FACTS:
        if d.get(f) not in (None, "", []) and f.startswith("GCHD:"):
            lines.append(f"- {label} (`{f}`): {d[f]}")
    if d.get("proj:code") or data.get("proj:code"):
        lines.append(f"- CRS: {d.get('proj:code') or data.get('proj:code')}")
    for r in d.get("GCHD:exposure_rules", []):
        lines.append(f"- Exposure rule `{r['hazard_code']}`: exposed where value {r['op']} {r['threshold']}; "
                     f"a pixel has data where value {r['valid']}" + (" (default variant)" if r.get("default") else ""))
    if d.get("GCHD:mhi_percentiles"):
        lines.append(f"- `GCHD:mhi_percentiles` (global land percentiles of MHI): {d['GCHD:mhi_percentiles']}")
    cols = d.get("table:columns", [])
    if cols:
        lines += ["", "| Column | Type | Unit | Description |", "|---|---|---|---|"]
        lines += [f"| `{c['name']}` | {c.get('type', '')} | {c.get('unit', '')} | "
                  f"{(c.get('description') or '').replace('|', '/')} |" for c in cols]
    lines.append("")

    notes = [d.get("GCHD:notes"), d.get("GCHD:alternate_sources") and f"Alternate sources: {d['GCHD:alternate_sources']}"]
    if d.get("GCHD:missing_countries"):
        notes.append(f"No data for {', '.join(d['GCHD:missing_countries'])} in this collection.")
    if k == "table":
        notes.append("Rows with a non-empty `status` ('No Data', 'Insufficient Data', 'Not Applicable') carry no "
                     "valid statistics; filter `status IS NULL OR status = ''` before aggregating.")
        notes.append("The exposure numbers come from the GEE exposure pipeline. For some hazards GEE used a different "
                     "version of the layer than the COG in this catalog, so a recomputation on the COG can differ.")
    if k in ("raster", "mosaic"):
        notes.append("Read with masked=True (or check the band's nodata) before computing statistics.")
    notes = [n for n in notes if n]
    lines += ["## Data quality & usage notes", ""] + [f"- {n}" for n in notes] + [""]
    rel = related(d, index)
    if rel:
        lines += ["## Related collections", ""] + rel + [""]
    return "\n".join(x for x in lines if x is not None)


def catalog_readme(d: dict, path: Path, stac_root: Path, children: list[tuple[str, str, str]]) -> str:
    lines = [f"# {d['title']}", "", d["description"], "", "## Contents", ""]
    lines += [f"- [{t}](./{rel}/README.md): `{cid}`" for cid, t, rel in children]
    rel = path.relative_to(stac_root).as_posix()
    lines += ["", "---", f"STAC: [`{rel}`]({PAGES_STAC}/{rel}) · Browse: [STAC Browser]({BROWSER}) · "
                         f"Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [{REPO}]({REPO})", ""]
    return "\n".join(lines)


def catalog_agents(d: dict, path: Path, stac_root: Path, index: dict, is_root: bool) -> str:
    here = path.parent.resolve()
    order = ["hazards", "multi_hazard", "population", "boundaries", "exposure", "infrastructure", "reference"]

    def key(row):
        rel = Path(row[1]["path"]).resolve().relative_to(stac_root.resolve()).parts
        return (order.index(rel[0]) if rel[0] in order else len(order), rel)

    rows = sorted(((cid, v) for cid, v in index.items() if here in Path(v["path"]).resolve().parents), key=key)
    lines = [f"# AGENTS.md: {d['title']}", "",
             "Guidance for AI agents and LLMs working with this catalog. Generated by STAC_catalog/gchd_stac/docs.py.", "",
             "## Overview", "", d["description"].split("\n\n")[0], ""]
    if is_root:
        lines += [
            "## How the catalog is organised", "",
            "- Static STAC 1.1 catalog conforming to the Portolan profile v0.2.0, served from GitHub Pages: "
            f"{PAGES_STAC}/catalog.json",
            "- Root -> sub-catalogs (`hazards/<theme>`, `multi_hazard`, `population`, `boundaries`, `exposure`, "
            "`infrastructure`, `reference`) -> one Collection per dataset. Every Collection has a `data` asset; collections made of "
            "many files (river flood tiles, WorldPop countries) also have items and an `items_parquet` index.",
            "- Data files are on Azure Blob Storage (https://unidatadapmclimatechange.blob.core.windows.net/public/), "
            "public, with HTTP range requests and CORS: stream them, no download or credentials needed.",
            "- No `/search` endpoint (static catalog): walk `child` links, use the table below, or filter an "
            "`items_parquet` index.",
            "- CRS: EPSG:4326 everywhere. Rasters are COGs (or GDAL VRTs over COGs); tables are (Geo)Parquet.",
            "- Each Collection has its own AGENTS.md with access code, field notes and join keys.", "",
            "## Finding a collection", "",
            "```python",
            "import pystac",
            f'cat = pystac.Catalog.from_file("{PAGES_STAC}/catalog.json")',
            'col = next(c for c in cat.get_all_collections() if c.id == "tropical_storm_100yr_giri_2024")',
            'url = col.assets["data"].href',
            "```", ""]
    lines += ["## Collections", "", "| id | Title | Kind | Data |", "|---|---|---|---|"]
    lines += [f"| [`{cid}`]({v['url']}) | {v['title']} | {v['kind']} | {v.get('data', '')} |" for cid, v in rows]
    lines += ["", "## License", "",
              "Each collection states its license and providers (hazard data from external producers keep their "
              "original terms; WorldPop is CC-BY-4.0). The UNICEF processing code is in " + REPO + ".", ""]
    return "\n".join(lines)


def write_docs(stac_root: Path, notes_dir: Path):
    """Write README.md and AGENTS.md next to every catalog.json / collection.json under stac_root."""
    objs = {p: _load(p) for p in sorted(stac_root.rglob("*.json"))
            if p.name in ("catalog.json", "collection.json")}
    index = {}
    for p, d in objs.items():
        if d["type"] == "Collection":
            data = d.get("assets", {}).get("data")
            index[d["id"]] = {"path": str(p), "title": d["title"], "kind": kind(d),
                              "url": f"{PAGES_STAC}/{p.relative_to(stac_root).as_posix()}",
                              "data": _abs_href(p, stac_root, data["href"]) if data else ""}
    for p, d in objs.items():
        n_items = sum(1 for link in d["links"] if link["rel"] == "item")
        if d["type"] == "Collection":
            readme = collection_readme(d, p, stac_root, n_items)
            agents = collection_agents(d, p, stac_root, index, n_items)
        else:
            children = []
            for link in d["links"]:
                if link["rel"] == "child":
                    cp = (p.parent / link["href"]).resolve()
                    cd = objs.get(cp) or _load(cp)
                    children.append((cd["id"], cd["title"], cp.parent.relative_to(p.parent.resolve()).as_posix()))
            readme = catalog_readme(d, p, stac_root, children)
            agents = catalog_agents(d, p, stac_root, index, is_root=p.parent.resolve() == stac_root.resolve())
        extra = notes_dir / f"{d['id']}.md"
        if extra.exists():
            agents += "\n## Additional notes\n\n" + extra.read_text().strip() + "\n"
        (p.parent / "README.md").write_text(readme)
        (p.parent / "AGENTS.md").write_text(agents)
    print(f"docs   README.md + AGENTS.md for {len(objs)} catalogs/collections")
