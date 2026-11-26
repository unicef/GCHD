# AGENTS.md: Riverine flood hazard (original JRC tiles) (`river_flood_100yr_jrc_2024`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

A fluvial or riverine flood is a rise, usually brief, in the water level of a stream or water body to a peak from which the water level recedes at a slower rate.

- Layout: 264 files, one STAC item each, plus a global GDAL VRT mosaic as the collection-level `data` asset.
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/river_flood_100yr_jrc_2024/mosaic.vrt
- Item index: https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/river_flood_100yr_jrc_2024/items.parquet
- Period: 2024-01-01 – 2024-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

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

## Schema & field notes

- Hazard (`GCHD:hazard`): Floods
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Probabilistic - 100 year return period
- Units (`GCHD:units`): Depth in m
- Resolution (`GCHD:nominal_resolution`): 90m
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): 0.01
- Classes (`GCHD:classes`): 0.01 - 0.15 - 0.5 - 1.5 - 2+
- Value range (`GCHD:value_range`): [0.0, 50.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazrards/river_flood_r100
- Exposure rule `river_flood_100yr`: exposed where value > 0.01; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- JRC currently has 90m and plans to release 30 m in the coming years which could be useful for sub-national and localized analysis in the future - also includes SSP based projections. CCRI 2021 used GAR 2015 which is quite outdated. GRID 2023 has some inconsistencies (comment from CCRI-DRM team). WRI is also a good alternative with projections - but yet to identify the future update frequencies and resolutions; it might also be good to align with INFORM data sources. Highest return period chosen to capture the maximum exposure.
- Alternate sources: WRI, UNEP GRID 2023
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `river_flood_100yr`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `river_flood_100yr`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `river_flood_100yr`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
