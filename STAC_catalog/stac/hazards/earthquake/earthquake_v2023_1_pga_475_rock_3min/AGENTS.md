# AGENTS.md: Earthquake (`earthquake_v2023_1_pga_475_rock_3min`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Earthquake exposure is derived from the GEM Global Seismic Hazard Map (v2023.1, June 2023), which maps peak ground acceleration (PGA) on reference rock for a 10% probability of exceedance in 50 years (475-year return period; Vs30 = 760–800 m/s). Exposed children and population are identified using two thresholds linked to Mercalli intensities: Strong shaking (VI; PGA ≥ 0.09 g) and Severe shaking (VIII; PGA ≥ 0.34 g). Outputs include absolute and relative exposure and normalized scores (0–10).

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif
- Period: 2023-01-01 – 2023-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 0 to 1.716, mean 0.07592, valid pixels 30.2%
- Hazard (`GCHD:hazard`): Geophysical
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): PGA (g)
- Resolution (`GCHD:nominal_resolution`): 3 arc-minutes
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): >0.09 g or >0.34g
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 2.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/earthquake_v2023_1_pga_475_rock_3min
- CRS: EPSG:4326
- Exposure rule `earthquake_pga_0p09`: exposed where value > 0.09; a pixel has data where value > -1000 (default variant)
- Exposure rule `earthquake_pga_0p34`: exposed where value > 0.34; a pixel has data where value > -1000

## Data quality & usage notes

- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `earthquake_pga_0p09`, `earthquake_pga_0p34`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `earthquake_pga_0p09`, `earthquake_pga_0p34`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `earthquake_pga_0p09`, `earthquake_pga_0p34`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
