# AGENTS.md: Meteorological Drought (Standardized Precipitation Evapotranspiration Index) (`drought_spei_terraclimate_1958-2025`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

SPEI adds the effect of evapotranspiration and is better suited to assess droughts under climate change scenarios where temperature changes are important. Probability values are computed from the full 1958–2025 record (804 monthly time steps) dividing the numbers of months lower than TH (1.5) with total months

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif
- Period: 1958-01-01 – 2025-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range -33.85 to -1.822, mean -4.923, valid pixels 35.8%
- Hazard (`GCHD:hazard`): Droughts
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Probabilistic - empirical
- Units (`GCHD:units`): Index
- Resolution (`GCHD:nominal_resolution`): 5km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): >0.06 (global mean)
- Classes (`GCHD:classes`): Use quantile
- Value range (`GCHD:value_range`): [-10.0, 10.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/droughts/spi12_TerraClimate_1958-2025
- CRS: EPSG:4326
- Exposure rule `drought_spei_tc`: exposed where value > 0.0650162152126539; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- The SPEI is an extension of the SPI and incorporates potential evapotranspiration to capture the impact of temperature on drought -12-month time scale. More details: https://github.com/dohyung-kim/precip-index/blob/main/README.md
- Alternate sources: World Bank (GOST)
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_spei_tc`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_spei_tc`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_spei_tc`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
