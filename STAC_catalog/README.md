# GCHD STAC Catalog

The Global Child Hazard Database (GCHD) is published as a [SpatioTemporal Asset Catalog (STAC)](https://stacspec.org/). The catalog conforms to the [Portolan](https://portolan-sdi.org) profile v0.2.0. It covers:

- the gridded hazard layers;
- the Multi-Hazard Intensity (MHI) index;
- WorldPop 2025 population, for children under 18 and for all ages;
- harmonised administrative boundaries (ADM0/1/2);
- hazard-exposure statistics per administrative unit.

Every catalog and collection has a `README.md` for people and an `AGENTS.md` for AI agents. You can browse it with [STAC Browser](https://github.com/radiantearth/stac-browser).

- Browser: https://unicef.github.io/GCHD/STAC_catalog/browser/
- Catalog: https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json
- Data: `https://unidatadapmclimatechange.blob.core.windows.net/public/` (public, HTTP range requests, CORS)

## Layout

Every leaf is one Collection with a collection-level `data` asset. Collections made of many files also have STAC items and an `items_parquet` index. Those are the river flood tiles and the WorldPop countries.

```
stac/catalog.json
├─ hazards/                        one sub-catalog per theme
│  ├─ flood/   river_flood_100yr_jrc_2024 (264 tile items, VRT mosaic), coastal_flood_100yr_jrc_2024
│  ├─ tropical_storm/  drought/  heatwave/  fire/  sand_dust_storm/  air_pollution/
│  └─ malaria/  landslide/  earthquake/  conflict/  volcano/            21 hazard layers in all
├─ multi_hazard/    mhi_climate
├─ population/      worldpop_u18_2025_{total,female,male}  worldpop_2025_{total,female,male}   (country items)
├─ boundaries/      adm0  adm1  adm2                        GeoParquet + PMTiles
├─ exposure/        adm0_hazard  adm1_hazard  adm2_hazard   Parquet, one row per unit and hazard
└─ reference/       land_sea_mask
```

Collection ids are the layer ids in lower case, the same ids as in the earlier `GCHD_portolan` blob catalog. Each hazard collection carries its exposure rule (`GCHD:exposure_rules`: valid-pixel test, operator, threshold, hazard code). The exposure tables use the same hazard codes.

## Data sources

| Collection(s) | Data | Source |
|---|---|---|
| Hazard layers | `public/gchd_cog/<theme>/<layer>.tif` | The `Azure link` file in `public/final_hazard_layers/`, converted to a COG by step 3 |
| `river_flood_100yr_jrc_2024` | `public/gchd_cog/flood/river_flood_100yr_jrc_2024/tiles/*.tif` + `mosaic.vrt` | The original JRC 100-year return-period depth tiles (private container `climate`, `CCRI/data/raw/riverline_flood/2025_update/`) |
| `mhi_climate`, `land_sea_mask` | `public/gchd_cog/{multi_hazard,reference}/` | `multi_hazard_indicators/mhi/` (ERA5 0.1° grid) |
| `worldpop_*_2025_*` | Country COGs in `public/worldpop_2025/R2025A/2025/100m/{T,T_F,T_M,T_U18,F_U18,M_U18}/`, referenced in place; `mosaic_ovr.vrt` per group in `public/gchd_cog/<dataset>/<group>/` | WorldPop R2025A (CC-BY-4.0) |
| `adm0`–`adm2`, `adm*_hazard` | `public/GCHD_portolan/<id>/` (Parquet, PMTiles) | Steps 5 and 6; exposure CSVs from `exposure_analysis/subnational_level/` (release 2026-08-31) |

## Folder structure

```
STAC_catalog/
  README.md  requirements.txt  pytest.ini  .env.example
  config/      layers.yaml          hazard layers (from the xlsx, step 1; then hand-edited)
               catalog.yaml         root and group texts, MHI and land-mask layers, table collections
               hazard_map.yaml      exposure rules and the hazard-code mapping (GCHD:exposure_rules)
               exposure_schema.json column dictionary of the exposure tables (written by step 6)
               browser.config.mjs   STAC Browser settings
               agents/<id>.md       optional hand-written notes, appended to that collection's AGENTS.md
  gchd_stac/   shared code: common.py (paths, Azure), population.py (WorldPop), portolan.py (conformance),
               docs.py (README.md / AGENTS.md)
  pipeline/    the numbered steps below
  tests/       pytest: catalog structure and conformance, exposure tables
  reports/     audit and check outputs
  stac/        GENERATED catalog (published on GitHub Pages); do not edit by hand
  browser/     GENERATED STAC Browser build (published on GitHub Pages)
  work/        git-ignored scratch: thumbnails, logs, caches, Node, stac-browser clone
```

## Setup

```bash
uv pip install --python .venv -r STAC_catalog/requirements.txt
cp STAC_catalog/.env.example STAC_catalog/.env   # then add the storage connection string
```

`.env` is git-ignored. The connection string is used only to list blobs, to read the river flood tiles and to write under `public/gchd_cog/`.

## Pipeline

Run from `STAC_catalog/` with the repo venv (`../.venv/bin/python pipeline/<step>.py`):

| Step | What it does | Writes to Azure |
|---|---|---|
| `01_extract_catalog.py` | Converts the xlsx to `config/layers.yaml`, and lists the river flood tiles to `reports/river_flood_tiles.csv` | No |
| `02_audit_cog.py` | Read-only COG, nodata, dtype and resolution audit of all sources to `reports/cog_audit.csv` | No |
| `03_convert_cog.py` | Converts each source to a COG (flipping south-up rasters to north-up and casting Float64 to Float32), checks it against the source and uploads it to `public/gchd_cog/`. For river flood it also builds `mosaic.vrt` | Yes |
| `04_population.py` | WorldPop: `--vrt` builds `mosaic_ovr.vrt` per group (with `--upload`, it uploads only missing ones); `--thumbs` renders the thumbnails | `--vrt --upload` only |
| `05_boundaries.py` | Optional: rebuilds the ADM0/1/2 GeoParquet files from source into `work/out/boundaries/` | No |
| `06_exposure_tables.py` | Optional: converts the ADM2 exposure CSVs to Parquet with the ADM1/ADM0 roll-ups, and rewrites `config/exposure_schema.json` | No |
| `07_thumbnails.py` | Renders a thumbnail and a data-only map overlay for each raster layer and river flood tile into `work/thumbnails/` | No |
| `08_build_stac.py` | Builds `stac/`. It applies the Portolan rules (`gchd_stac/portolan.py`) and writes every README.md and AGENTS.md | No |
| `09_check.py` | `portolan check` (offline), pystac validation, and coverage of the hazard codes and the Portolan collections. Writes `reports/portolan_check.txt` and `reports/catalog_summary.csv` | No |
| `10_publish.py` | Checks that blob CORS allows GitHub Pages (read-only), then builds STAC Browser into `browser/`. Needs Node 22 or later; pass `--node-bin` if the system Node is older | No |
| `11_split_exposure.py` | Per-country copies of the ADM1/ADM2 exposure tables for the browser data assistant, at `public/gchd_cog/exposure_by_country/<table>/<sha>/<ISO3>.parquet`, where `<sha>` is the start of the table's STAC checksum. A new table version goes to a new folder and existing files are never overwritten. Run it again after the exposure tables change | Yes, with `--upload` |

Tests: `../.venv/bin/python -m pytest -q`. Add `-m "not network"` to stay offline.

`config/layers.yaml` is generated once and then edited by hand. Re-running step 1 does not overwrite it unless you pass `--force`. The extra layers in `config/catalog.yaml` are not affected by step 1.

## Using the data

### A hazard layer

Every single-file layer is one COG, the collection's `data` asset. Stream it with GDAL, rasterio or QGIS (Layer > Add Raster Layer > Protocol: HTTP):

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif"
with rasterio.open(url) as src:
    print(next(src.sample([(130, 20)])))   # wind speed (m/s) at 130°E, 20°N
```

Find a layer by id with pystac:

```python
import pystac
cat = pystac.Catalog.from_file("https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json")
col = next(c for c in cat.get_all_collections() if c.id == "tropical_storm_100yr_giri_2024")
col.assets["data"].href, col.extra_fields["GCHD:exposure_rules"]
```

### River flood tiles over an area of interest

The river flood layer is 264 tiles of 10°x10° at about 90 m resolution. There are three ways to get data for a polygon, and all three read only the tiles and pixels you need.

**1. The VRT mosaic: one URL, no STAC client.** GDAL opens the collection's `data` asset (`mosaic.vrt`) as a single global raster. It reads only the tiles your polygon touches, and it also works in QGIS.

```python
import rasterio, rasterio.mask
from shapely.geometry import box, mapping

aoi = box(-16.5, 25.0, -13.0, 28.0)   # any shapely polygon in EPSG:4326
vrt = ("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/"
       "flood/river_flood_100yr_jrc_2024/mosaic.vrt")
with rasterio.open("/vsicurl/" + vrt) as src:
    depth, transform = rasterio.mask.mask(src, [mapping(aoi)], crop=True)   # nodata = -9999
```

**2. Item index: find the tiles for a polygon in one request.** The collection publishes all its tile items in a single file, as `items.parquet` (stac-geoparquet) and `items.geojson`.

```python
import geopandas as gpd
idx = gpd.read_parquet("https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.parquet")
tiles = idx[idx.intersects(aoi)]
tiles["assets"].map(lambda a: a["data"]["href"]).tolist()   # COG URLs of the intersecting tiles
```

**3. STAC items to xarray with [odc-stac](https://odc-stac.readthedocs.io/).** This is the STAC equivalent of `ee.ImageCollection(...).filterBounds(aoi).mosaic().clip(aoi)`:

```python
import json, urllib.request, pystac, odc.stac
from shapely.geometry import shape

url = "https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.geojson"
features = json.load(urllib.request.urlopen(url))["features"]
items = [pystac.Item.from_dict(f) for f in features]
items = [i for i in items if shape(i.geometry).intersects(aoi)]

ds = odc.stac.load(items, bands=["data"], geopolygon=aoi, groupby="solar_day", chunks={})
depth = ds["data"].isel(time=0)   # all intersecting tiles mosaicked, clipped to the AOI's bounding box
```

The catalog is static, so there is no `/search` endpoint and `pystac-client` search does not apply. Use the item index (option 2) to filter by location.

### Exposure statistics and boundaries

The exposure tables are plain Parquet, and DuckDB queries them over HTTP without downloading them:

```sql
INSTALL httpfs; LOAD httpfs;
SELECT adm2_name, u18_aexp, u18_rexp
FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2_hazard/adm2_hazard.parquet'
WHERE hazard_code = 'river_flood_100yr' AND iso3 = 'BGD'
ORDER BY u18_aexp DESC LIMIT 10;
```

The boundaries are GeoParquet 1.1 with a bbox covering. Join them to the tables on `ucode` = `adm{0,1,2}_ucode`:

```python
import geopandas as gpd
adm2 = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet",
                        filters=[("iso3", "==", "BGD")])
```

## WorldPop population

The `population/` collections hold the WorldPop R2025A constrained estimates of people per ~100 m cell for 2025, in two datasets:

- `worldpop_u18_2025_{total,female,male}`: children under 18, 240 country items each;
- `worldpop_2025_{total,female,male}`: all ages, with 240, 237 and 237 items. FJI, GRL and RUS have no female or male file in R2025A.

- The data are the original WorldPop country files, which are already valid COGs (Float32, DEFLATE, 512 px tiles, nodata −99999). The items point to them where they are, in `public/worldpop_2025/R2025A/2025/100m/`.
- Each collection's `data` asset is `mosaic_ovr.vrt`, a GDAL VRT over its country files. A virtual `<OverviewList>` makes low-zoom reads use the country files' own overviews.
- Units are people per grid cell. Cells outside mapped settlements are nodata.
- License: CC-BY-4.0. Citation: WorldPop (www.worldpop.org), R2025A.

```python
import rasterio
vrt = ("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/"
       "worldpop_u18_2025/total/mosaic_ovr.vrt")
with rasterio.open("/vsicurl/" + vrt) as src:
    print(next(src.sample([(3.379, 6.524)])))   # children under 18 in the 100 m cell at Lagos
```

For an area of interest, each collection's `items.parquet` index finds the country files to read, in the same way as for the river flood tiles. An example is `stac/population/worldpop_u18_2025_total/items.parquet`.
