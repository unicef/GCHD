# Male population 2025, all ages (WorldPop R2025A)

Estimated number of males (all ages) per ~100 m grid cell in 2025 (WorldPop R2025A, constrained), one item per country.

Estimated number of people (all ages) per ~100 m grid cell (3 arc-seconds) in 2025, from the WorldPop R2025A constrained (`CN`) population estimates. Constrained means people are only allocated to cells mapped as built settlement; all other cells are nodata.

The data are one Cloud-Optimized GeoTIFF per country, served from their original location on Azure, with one STAC item per country. The collection's `data` asset is a GDAL VRT over all country files, with virtual overviews, for global access with a single URL.

Units: people per grid cell. Nodata: -99999. License: CC-BY-4.0. Citation: WorldPop (www.worldpop.org), R2025A.

Not available for FJI, GRL, RUS: WorldPop R2025A has no male file for them (the total layer covers them).

Source: WorldPop, University of Southampton (https://www.worldpop.org/); release R2025A; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2025-01-01 – 2025-12-31 |
| Units | people per grid cell |
| Resolution | 100 m (3 arc-seconds) |
| Citation | WorldPop (www.worldpop.org), R2025A |
| Source release | R2025A |
| License | CC-BY-4.0 |
| Providers | WorldPop, University of Southampton (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/xml | 129.0 KB | [Male population 2025, all ages (WorldPop R2025A) – global mosaic (GDAL VRT)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/worldpop_2025/male/mosaic_ovr.vrt) |
| `thumbnail` | image/png | 21.5 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/thumbnail.png) |
| `overview` | image/png | 76.1 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/overview.png) |
| `items_parquet` | application/vnd.apache.parquet | 162.6 KB | [Item index (stac-geoparquet, all items)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/items.parquet) |
| `items_geojson` | application/geo+json | 976.9 KB | [Item index (GeoJSON FeatureCollection, all items)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/items.geojson) |

The collection has **237 items** (one file each); the `items_parquet` asset lists them all in one stac-geoparquet file.

## Access

```python
import rasterio, rasterio.mask
vrt = "/vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/worldpop_2025/male/mosaic_ovr.vrt"   # GDAL VRT: one global raster over all files, reads only what you touch
with rasterio.open(vrt) as src:
    value = next(src.sample([(lon, lat)]))
    data, transform = rasterio.mask.mask(src, [aoi_geojson], crop=True)
```

The catalog is static (no `/search`). To find the files for an area of interest, filter the item index:

```python
import geopandas as gpd
items = gpd.read_parquet("https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/items.parquet")              # stac-geoparquet, one row per item
hits = items[items.intersects(aoi)]                  # shapely geometry in EPSG:4326
urls = hits["assets"].map(lambda a: a["data"]["href"]).tolist()
```

---
STAC: [`population/worldpop_2025_male/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_male/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/population/worldpop_2025_male/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
