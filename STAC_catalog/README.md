# GCHD STAC Catalog

A [SpatioTemporal Asset Catalog (STAC)](https://stacspec.org/) for the hazard layers of the Global Children's Hazard Database. Each layer is published as a Cloud-Optimized GeoTIFF (COG) with a thumbnail and the metadata from `docs/Global Hazard Data catalog.xlsx`. The catalog also includes the WorldPop under-18 population for 2025 (see [WorldPop U18 population](#worldpop-u18-population)). The catalog can be browsed with [STAC Browser](https://github.com/radiantearth/stac-browser).

- Browser: https://unicef.github.io/GCHD/STAC_catalog/browser/
- Catalog: https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json
- COGs: `https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/<collection>/<layer>.tif`

## Data sources

| Layer | Source |
|---|---|
| `river_flood_100yr_jrc_2024` | Original JRC 100-year return-period depth tiles (private container `climate`, `CCRI/data/raw/riverline_flood/2025_update/`). Each tile becomes its own STAC item, and a VRT mosaic is published alongside. |
| All other layers | The `Azure link` file in `public/final_hazard_layers/` |
| `worldpop_u18_2025` | WorldPop R2025A country COGs in `public/worldpop_2025/R2025A/2025/100m/{F_U18,M_U18,T_U18}/`, referenced in place (already valid COGs, not copied) |

## Setup

```bash
uv pip install --python .venv -r STAC_catalog/requirements.txt
cp STAC_catalog/.env.example STAC_catalog/.env   # then add the storage connection string
```

`.env` is git-ignored. The connection string is used only to read the river flood tiles and to write to `public/gchd_cog/`.

## Pipeline

Run from `STAC_catalog/` with the repo venv (`../.venv/bin/python`):

| Script | What it does | Writes to Azure |
|---|---|---|
| `scripts/01_extract_catalog.py` | xlsx to `config/layers.yaml`, and lists the river flood tiles to `reports/river_flood_tiles.csv` | No |
| `scripts/02_audit_cog.py` | Read-only COG, nodata, dtype and resolution audit of all sources to `reports/cog_audit.csv` | No |
| `scripts/03_convert_cog.py` | Converts each source to a COG (flipping south-up rasters to north-up and casting Float64 to Float32), checks it against the source and uploads it to `public/gchd_cog/`. For river flood it also builds `mosaic.vrt` | Yes |
| `scripts/04_thumbnails.py` | Renders a colourised PNG thumbnail per item (cards) and a data-only `_overview.png` map overlay per item and collection into `thumbnails/` | No |
| `scripts/05_build_stac.py` | Builds the catalog, collections and items into `stac/`, plus `items.geojson` and `items.parquet` indexes for the tiled collection | No |
| `scripts/population.py` | WorldPop U18 population: `--vrt` builds a global `mosaic.vrt` per group into `public/gchd_cog/worldpop_u18_2025/<group>/`, `--thumbs` renders the thumbnails and map overlays. Step 5 adds the collections | `--vrt` only |
| `scripts/06_publish.py` | Checks that blob CORS allows GitHub Pages (read-only), then builds STAC Browser into `browser/`. Needs Node 22 or later; pass `--node-bin` if the system Node is older | No |

`config/layers.yaml` is generated once and then edited by hand. Re-running step 1 does not overwrite it unless you pass `--force`.

## Using the data

Every single-file layer is one COG. Stream it with GDAL, rasterio or QGIS (Layer > Add Raster Layer > Protocol: HTTP):

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif"
with rasterio.open(url) as src:
    print(next(src.sample([(130, 20)])))   # wind speed (m/s) at 130°E, 20°N
```

### River flood tiles over an area of interest

The river flood layer is 264 tiles of 10°x10° at about 90 m resolution. There are three ways to get data for a polygon. All three read only the tiles and pixels you need.

**1. The VRT mosaic: one URL, no STAC client.** GDAL opens `mosaic.vrt` as a single global raster and reads only the tiles your polygon touches. It also works in QGIS.

```python
import rasterio, rasterio.mask
from shapely.geometry import box, mapping

aoi = box(-16.5, 25.0, -13.0, 28.0)   # any shapely polygon in EPSG:4326
vrt = ("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/"
       "flood/river_flood_100yr_jrc_2024/mosaic.vrt")
with rasterio.open("/vsicurl/" + vrt) as src:
    depth, transform = rasterio.mask.mask(src, [mapping(aoi)], crop=True)   # nodata = -9999
```

**2. Item index: find the tiles for a polygon in one request.** The collection publishes every tile item in a single file, as `items.parquet` (stac-geoparquet) and `items.geojson`.

```python
import geopandas as gpd
idx = gpd.read_parquet("https://unicef.github.io/GCHD/STAC_catalog/stac/flood/river_flood_100yr_jrc_2024/items.parquet")
tiles = idx[idx.intersects(aoi)]
tiles["assets"].map(lambda a: a["data"]["href"]).tolist()   # COG URLs of the intersecting tiles
```

**3. STAC items to xarray with [odc-stac](https://odc-stac.readthedocs.io/).** This is the STAC equivalent of `ee.ImageCollection(...).filterBounds(aoi).mosaic().clip(aoi)`:

```python
import json, urllib.request, pystac, odc.stac
from shapely.geometry import shape

url = "https://unicef.github.io/GCHD/STAC_catalog/stac/flood/river_flood_100yr_jrc_2024/items.geojson"
features = json.load(urllib.request.urlopen(url))["features"]
items = [pystac.Item.from_dict(f) for f in features]
items = [i for i in items if shape(i.geometry).intersects(aoi)]

ds = odc.stac.load(items, bands=["data"], geopolygon=aoi, groupby="solar_day", chunks={})
depth = ds["data"].isel(time=0)   # all intersecting tiles mosaicked, clipped to the AOI's bounding box
```

The catalog is static, so there is no `/search` endpoint and `pystac-client` search does not apply. Use the item index (option 2) to filter by location.

## WorldPop U18 population

The `worldpop_u18_2025` collection holds the WorldPop R2025A constrained estimates of children under 18 per ~100 m cell for 2025. It has three sub-collections, **Female U18**, **Male U18** and **Total U18**, with one item per country (240 each).

- The data are the original WorldPop country files, which are already valid COGs (Float32, DEFLATE, 512 px tiles, nodata −99999). The items point to them where they are, in `public/worldpop_2025/R2025A/2025/100m/`.
- Each sub-collection has a `mosaic` asset: a GDAL VRT over its 240 country files, for global access with one URL.
- Units are people per grid cell. Cells outside mapped settlements are nodata.
- License: CC-BY-4.0. Citation: WorldPop (www.worldpop.org), R2025A.

```python
import rasterio
vrt = ("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/"
       "worldpop_u18_2025/total/mosaic.vrt")
with rasterio.open("/vsicurl/" + vrt) as src:
    print(next(src.sample([(3.379, 6.524)])))   # children under 18 in the 100 m cell at Lagos
```

For an area of interest, the `items.parquet` index of each sub-collection (for example `stac/worldpop_u18_2025/worldpop_u18_2025_total/items.parquet`) finds the country files to read, in the same way as for the river flood tiles. Reading global extents through the VRT is slow, because GDAL has to open all 240 files.
