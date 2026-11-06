"""Step 1: read the "Hazard" sheet of the GCHD data catalog xlsx -> config/layers.yaml.

Source per layer:
  - river_flood_100yr_jrc_2024 -> raw JRC tiles in the private container ("Azure path (raw)")
  - every other layer          -> the public "Azure link" file

layers.yaml is meant to be hand-reviewed after generation, so it is not
overwritten unless --force is given. If Azure credentials are available, the
river flood tile folder is also listed to reports/river_flood_tiles.csv.

Usage:  python scripts/01_extract_catalog.py [--force]
"""
import argparse
import csv
import math
import re
import sys
from pathlib import PurePosixPath

import openpyxl
import yaml

from common import (LAYERS_YAML, RAW_CONTAINER, REPO_DIR, REPORTS_DIR, TILED_LAYER, XLSX,
                    container_client, has_credentials)

# Collections keyed by the folder under public/final_hazard_layers/.
# GLIDE codes from the "Hazard Codes" sheet of the same xlsx.
COLLECTIONS = {
    "flood":         {"id": "flood",           "title": "Floods",                 "glide": "FL"},
    "storm":         {"id": "tropical_storm",  "title": "Tropical Storm",         "glide": "TC"},
    "drought":       {"id": "drought",         "title": "Droughts",               "glide": "DR"},
    "heat_extreme":  {"id": "heatwave",        "title": "Heatwaves and Extreme Heat", "glide": "HW"},
    "fire":          {"id": "fire",            "title": "Fire",                   "glide": "FR"},
    "SDS":           {"id": "sand_dust_storm", "title": "Sand and Dust Storm",    "glide": None},
    "air_pollution": {"id": "air_pollution",   "title": "Air Pollution",          "glide": "AP"},
    "malaria":       {"id": "malaria",         "title": "Vector Borne Diseases (Malaria)", "glide": "EP"},
    "landslide":     {"id": "landslide",       "title": "Landslides",             "glide": "LS"},
    "earthquake":    {"id": "earthquake",      "title": "Earthquake",             "glide": "EQ"},
    "conflict":      {"id": "conflict",        "title": "Complex Emergencies (Conflict)", "glide": "CE"},
    "volcano":       {"id": "volcano",         "title": "Volcanoes",              "glide": "VO"},
}

TILE_RE = re.compile(r"ID(\d+)_([NS])(\d+)_([EW])(\d+)_RP(\d+)_depth\.tif$")

NAN = float("nan")
# Output nodata per layer (agreed 2026-11). Layers not listed use NaN.
# Where the source already has a different nodata, 03 remaps those pixels.
NODATA = {
    "river_flood_100yr_jrc_2024": -9999.0,       # JRC tiles already use -9999
    "coastal_flood_100yr_jrc_2024": 255,          # stored as uint8 (see DTYPE)
    "vectorborne_malariapv_2012-2022": -9999.0,
    "vectorborne_malariapf_2012-2022": -9999.0,
    "UNICEF_ACLED_CI_Sep2020_Aug2025": -9999.0,
    "sand_dust_storm_unccd_2024": -999000000.0,
    "landslides_trig_earthquakes": 0,
}
# Fill values in sources that do not tag them as nodata; 03 maps them to the output nodata.
SOURCE_NODATA = {
    "drought_spei_terraclimate_1958-2025": -9999.0,  # ocean = -9999, untagged
}
# Data period where the layer name (xlsx Naming Convention) differs from the actual period
YEARS = {
    "vectorborne_malariapv_2012-2022": (2013, 2022),  # MAP 2013-2022 average (confirmed 2026-11-06)
    "vectorborne_malariapf_2012-2022": (2013, 2022),
}
# Output dtype overrides. Coastal flood is binary 0/1 in a Float32 file (432k x 168k px):
# uint8 is lossless, 4x less data to process and a much smaller COG (agreed 2026-11-05).
DTYPE = {"coastal_flood_100yr_jrc_2024": "uint8"}
# Binary / classed layers: overviews must not average class values
MODE_RESAMPLING = {"coastal_flood_100yr_jrc_2024", "landslides_trig_earthquakes"}
# Hazard -> ColorCodes sheet name, for layers without a web app palette
COLORCODES_KEY = {"landslide": "Landslide", "earthquake": "Earthquake",
                  "volcano": "Volcanoes", "conflict": "Complex Emergencies"}


def web_app_config():
    """web_app/config.py has palettes and the 0-is-transparent list; it has no heavy imports."""
    sys.path.insert(0, str(REPO_DIR / "web_app"))
    import config
    return config


def colorcodes(wb) -> dict:
    out = {}
    for r in list(wb["ColorCodes"].iter_rows(values_only=True))[1:]:
        hazard, hexcode = clean(r[0]), clean(r[4])
        if hazard and hexcode:
            out.setdefault(hazard, []).append(hexcode)
    return out


def clean(v):
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, str):
        v = v.replace("\xa0", " ").strip()
        return v or None
    return v


def num(v):
    v = clean(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def years(name: str):
    m = re.search(r"(?<!\d)(\d{4})[-_]\D{0,3}(\d{4})(?!\d)", name)  # 2014-2024, Sep2020_Aug2025
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"[_v](20\d{2})(?:_|$)", name)                    # _2024, v2023_
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def read_layers():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    cfg = web_app_config()
    codes = colorcodes(wb)
    rows = list(wb["Hazard"].iter_rows(values_only=True))
    header = [clean(h) for h in rows[0]]
    layers = []
    for r in rows[1:]:
        d = {h: clean(v) for h, v in zip(header, r) if h}
        link = d.get("Azure link")
        if not link:
            continue
        rel = PurePosixPath(link.split("/final_hazard_layers/", 1)[1])
        folder, stem = rel.parts[0], rel.stem
        naming = d.get("Naming Convention")
        # Outputs are named by the "Naming Convention" column; file stem if it is empty
        layer_id = naming or re.sub(r"_COG$", "", stem)
        collection = COLLECTIONS[folder]["id"]

        if naming == TILED_LAYER:
            source = {"type": "tiles", "container": RAW_CONTAINER,
                      "prefix": d.get("Azure path (raw)"), "legacy_href": link}
        else:
            source = {"type": "file", "href": link}

        palette = (cfg.HAZARD_VIS_PALETTES.get(layer_id) or cfg.HAZARD_VIS_PALETTES.get(stem)
                   or codes.get(COLORCODES_KEY.get(collection)))
        start, end = YEARS.get(layer_id) or years(layer_id)
        layers.append({
            "id": layer_id,
            "collection": collection,
            "source_filename": rel.name,
            "title": d.get("Type"),
            "hazard": d.get("Hazards"),
            "description": d.get("Description"),
            "notes": d.get("Notes"),
            "hazard_phase": d.get("Hazard Phase"),
            "data_type": d.get("Data type"),
            "resolution": d.get("Resolution"),
            "coverage": d.get("Coverage"),
            "units": d.get("Units"),
            "legend_label": d.get("Temparory column for legend"),
            "threshold": d.get("Overall Thresholds"),
            "classes": d.get("Classes"),
            "range": [num(d.get("Min range")), num(d.get("Max range"))],
            "actual_range": [num(d.get("Min (actual)")), num(d.get("Max (actual)"))],
            "nodata_note": d.get("No data value"),
            "source_provider": d.get("Standard Source"),
            "alternate_sources": d.get("Alternate Source"),
            "gee_asset": d.get("GEE Asset"),
            "naming_convention": naming,
            "start_year": start,
            "end_year": end,
            "source": source,
            "nodata": NODATA.get(layer_id, NAN),
            "source_nodata": SOURCE_NODATA.get(layer_id),  # null = use the source's nodata tag
            "dtype": DTYPE.get(layer_id),  # null = keep source dtype (Float64 -> Float32)
            "overview_resampling": "mode" if layer_id in MODE_RESAMPLING else "average",
            "palette": palette,
            "transparent_zero": layer_id in cfg.SELF_MASK_HAZARDS or stem in cfg.SELF_MASK_HAZARDS,
            "thumb_range": None,  # [min, max] override; default is the 2-98th percentile
        })
    return layers


def list_tiles(prefix: str):
    cc = container_client(RAW_CONTAINER)
    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / "river_flood_tiles.csv"
    n = 0
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blob", "tile_id", "lat", "lon", "return_period", "size_bytes", "last_modified"])
        for b in cc.list_blobs(name_starts_with=prefix):
            m = TILE_RE.search(b.name)
            if not m:
                print(f"  skipping non-tile blob: {b.name}")
                continue
            tid, ns, lat, ew, lon, rp = m.groups()
            lat = int(lat) * (1 if ns == "N" else -1)
            lon = int(lon) * (1 if ew == "E" else -1)
            w.writerow([b.name, int(tid), lat, lon, int(rp), b.size, b.last_modified.isoformat()])
            n += 1
    print(f"Listed {n} river flood tiles -> {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite an existing layers.yaml")
    args = ap.parse_args()

    layers = read_layers()
    print(f"Read {len(layers)} layers from {XLSX.name}")
    for l in layers:
        if PurePosixPath(l["source_filename"]).stem != l["id"]:
            print(f"  renamed: {l['source_filename']} -> {l['id']}")
        if not l["palette"]:
            print(f"  warning: no palette for {l['id']}")

    if LAYERS_YAML.exists() and not args.force:
        print(f"{LAYERS_YAML} exists, not overwriting (use --force)")
    else:
        LAYERS_YAML.parent.mkdir(exist_ok=True)
        collections = {c["id"]: {"title": c["title"], "glide_code": c["glide"]} for c in COLLECTIONS.values()}
        with open(LAYERS_YAML, "w") as f:
            yaml.safe_dump({"collections": collections, "layers": layers}, f,
                           sort_keys=False, allow_unicode=True, width=120)
        print(f"Wrote {LAYERS_YAML}")

    tiled = next(l for l in layers if l["id"] == TILED_LAYER)
    if has_credentials():
        list_tiles(tiled["source"]["prefix"])
    else:
        print("No Azure credentials in STAC_catalog/.env: skipping river flood tile listing")


if __name__ == "__main__":
    main()
