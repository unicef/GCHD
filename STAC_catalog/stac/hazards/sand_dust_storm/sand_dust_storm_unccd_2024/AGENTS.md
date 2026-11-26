# AGENTS.md: SDS Susceptiblity (`sand_dust_storm_unccd_2024`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Sand and dust storms (SDS) are caused by intense winds over areas of arid soil that pick up large amounts of ground material into the atmosphere.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif
- Period: 2024-01-01 – 2024-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `-999000000.0`; observed range 0 to 1, mean 0.08276, valid pixels 31.4%
- Hazard (`GCHD:hazard`): Sand and Dust Storm
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): Index
- Resolution (`GCHD:nominal_resolution`): 1km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): All
- Classes (`GCHD:classes`): 0-0.2-0.4-0.6-0.8-1
- Value range (`GCHD:value_range`): [0.0, 1.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/sand_dust_storm_annual
- CRS: EPSG:4326
- Exposure rule `sand_dust_storm_susc`: exposed where value > 0; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- SDS susceptibility only shows the areas of sds source and classes are consolidated from the UNCCD index -
- Alternate sources: WMO
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `sand_dust_storm_susc`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `sand_dust_storm_susc`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `sand_dust_storm_susc`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
