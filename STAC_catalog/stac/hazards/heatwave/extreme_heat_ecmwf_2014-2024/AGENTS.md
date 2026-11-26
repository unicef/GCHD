# AGENTS.md: Extreme hot days (`extreme_heat_ecmwf_2014-2024`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Extremely high temperatures (extremely hot days) are estimated when a day exceeds 35 degrees Celsius.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif
- Period: 2014-01-01 – 2024-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 0 to 364.5, mean 38.4, valid pixels 32.1%
- Hazard (`GCHD:hazard`): Heatwaves
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): Number of days with extreme temperature (>35°C)
- Resolution (`GCHD:nominal_resolution`): 10km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): 35 days
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 365.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/high_temp_degree_days_return_level_100yr
- CRS: EPSG:4326
- Exposure rule `extreme_heat_days`: exposed where value > 35; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- Alternate sources: NOAA CDR, NASA MERRA2, MODIS for SIDS
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `extreme_heat_days`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `extreme_heat_days`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `extreme_heat_days`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
