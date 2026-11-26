# AGENTS.md: Female population 2025, all ages (WorldPop R2025A) (`worldpop_2025_female`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Estimated number of females (all ages) per ~100 m grid cell in 2025 (WorldPop R2025A, constrained), one item per country.

- Layout: 237 files, one STAC item each, plus a global GDAL VRT mosaic as the collection-level `data` asset.
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/worldpop_2025/female/mosaic_ovr.vrt
- Item index: https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_female/items.parquet
- Period: 2025-01-01 – 2025-12-31
- License: CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/); cite as: WorldPop (www.worldpop.org), R2025A

## Accessing the data

```python
import rasterio, rasterio.mask
vrt = "/vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/worldpop_2025/female/mosaic_ovr.vrt"   # GDAL VRT: one global raster over all files, reads only what you touch
with rasterio.open(vrt) as src:
    value = next(src.sample([(lon, lat)]))
    data, transform = rasterio.mask.mask(src, [aoi_geojson], crop=True)
```

The catalog is static (no `/search`). To find the files for an area of interest, filter the item index:

```python
import geopandas as gpd
items = gpd.read_parquet("https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_female/items.parquet")              # stac-geoparquet, one row per item
hits = items[items.intersects(aoi)]                  # shapely geometry in EPSG:4326
urls = hits["assets"].map(lambda a: a["data"]["href"]).tolist()
```

## Schema & field notes

- Band: data type `float32`, nodata `-99999.0`, unit people per grid cell
- Units (`GCHD:units`): people per grid cell
- Resolution (`GCHD:nominal_resolution`): 100 m (3 arc-seconds)
- Citation (`GCHD:citation`): WorldPop (www.worldpop.org), R2025A
- Source release (`GCHD:source_release`): R2025A

## Data quality & usage notes

- No data for FJI, GRL, RUS in this collection.
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics computed with these population grids
