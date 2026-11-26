# Riverine flood hazard (original JRC tiles)

A fluvial or riverine flood is a rise, usually brief, in the water level of a stream or water body to a peak from which the water level recedes at a slower rate.

Original ~90 m (3 arc-second) JRC tiles of 10°x10°, one item per tile. The collection's `data` asset is a GDAL VRT over all tiles, for full-resolution access with a single URL; the `items_parquet` asset indexes the tiles for area-of-interest queries.

Source: JRC (https://global-flood-maps.jrc.ec.europa.eu/); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2024-01-01 – 2024-12-31 |
| Hazard | Floods |
| Phase | Preparedness/Planning |
| Data type | Probabilistic - 100 year return period |
| Units | Depth in m |
| Resolution | 90m |
| Coverage | Global |
| Exposure threshold | 0.01 |
| Classes | 0.01 - 0.15 - 0.5 - 1.5 - 2+ |
| Value range | [0.0, 50.0] |
| GEE asset | projects/unicef-ccri/assets/hazrards/river_flood_r100 |
| License | other |
| Providers | JRC (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/xml | 146.6 KB | [Global mosaic (GDAL VRT over the tile COGs)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/river_flood_100yr_jrc_2024/mosaic.vrt) |
| `thumbnail` | image/png | 98.0 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/thumbnail.png) |
| `overview` | image/png | 211.6 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/overview.png) |
| `items_parquet` | application/vnd.apache.parquet | 143.9 KB | [Item index (stac-geoparquet, all items)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.parquet) |
| `items_geojson` | application/geo+json | 1.3 MB | [Item index (GeoJSON FeatureCollection, all items)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.geojson) |

The collection has **264 items** (one file each); the `items_parquet` asset lists them all in one stac-geoparquet file.

## Exposure rule

A pixel counts as exposed when:

- `river_flood_100yr` (UNICEF code FL_RIV): value > 0.01 (pixels with data: value > -1000)

## Access

```python
import rasterio, rasterio.mask
vrt = "/vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/river_flood_100yr_jrc_2024/mosaic.vrt"   # GDAL VRT: one global raster over all files, reads only what you touch
with rasterio.open(vrt) as src:
    value = next(src.sample([(lon, lat)]))
    data, transform = rasterio.mask.mask(src, [aoi_geojson], crop=True)
```

The catalog is static (no `/search`). To find the files for an area of interest, filter the item index:

```python
import geopandas as gpd
items = gpd.read_parquet("https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.parquet")              # stac-geoparquet, one row per item
hits = items[items.intersects(aoi)]                  # shapely geometry in EPSG:4326
urls = hits["assets"].map(lambda a: a["data"]["href"]).tolist()
```

---
STAC: [`hazards/flood/river_flood_100yr_jrc_2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/flood/river_flood_100yr_jrc_2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
