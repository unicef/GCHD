# AGENTS.md: Coastal flood hazard (`coastal_flood_100yr_jrc_2024`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Coastal flooding is most frequently the result of storm surges and high winds coinciding with high tides

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif
- Period: 2024-01-01 – 2024-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif`.

## Schema & field notes

- Band: data type `uint8`, nodata `255.0`; observed range 0 to 1, mean 0.0007465, valid pixels 100.0%
- Hazard (`GCHD:hazard`): Floods
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Probabilistic - 100 year return period
- Units (`GCHD:units`): Binary
- Resolution (`GCHD:nominal_resolution`): 90m
- Coverage (`GCHD:coverage`): Global
- Value range (`GCHD:value_range`): [0.0, 1.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/coastal_flood_r100
- CRS: EPSG:4326
- Exposure rule `coastal_flood_100yr`: exposed where value > 0; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- While 1000 year return period is available, it might be easier to keep the same as floods. Note WRI coastal flood is average annual impact of storm surge (a good indicator to be considered for others as well with different return periods) and UNEP GRID is only available as a point layer; SIDS might not be well represented and more discussions needed on the added value
- Alternate sources: WRI, UNEP GRID 2023
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `coastal_flood_100yr`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `coastal_flood_100yr`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `coastal_flood_100yr`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
