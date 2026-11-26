# AGENTS.md: Wind speed (`tropical_storm_100yr_giri_2024`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

A tropical storm is a type of storm system characterized by a low-pressure center, a closed low-level atmospheric circulation, strong winds, and a spiral arrangement of thunderstorms that produce heavy rain.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif
- Period: 2024-01-01 – 2024-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 0 to 51.59, mean 20.55, valid pixels 47.8%
- Hazard (`GCHD:hazard`): Tropical Storm
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Probabilistic - 100 year return period
- Units (`GCHD:units`): m/s
- Resolution (`GCHD:nominal_resolution`): 10km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): >17.5 m/s
- Classes (`GCHD:classes`): 63 - 119 - 154 - 178 - 209+
- Value range (`GCHD:value_range`): [0.0, 60.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/storm_giri_rp100
- CRS: EPSG:4326
- Exposure rule `tropical_storm_100yr`: exposed where value > 17.5; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- GIRI preferred over STORM following country level testing by CCRI DRM team and saffir simpson classification is used to establish thresholds.  Classification from WMO - https://wmo.int/content/classification-of-tropical-cyclones
- Alternate sources: STORM
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `tropical_storm_100yr`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `tropical_storm_100yr`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `tropical_storm_100yr`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
