# AGENTS.md: Landslide (rainfall induced) (`ls_rf_mean_1980-2018`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Landslide exposure is estimated using the GFDRR rainfall-triggered Global Landslide Hazard Map (V2), based on the annual frequency of significant rainfall-induced landslides per km². Children and population exposed are identified using 0.1 and 0.01 landslides/km² thresholds (Medium–High and Moderate hazard). Indicators include absolute and relative exposed population and normalized scores ranging from 0–10.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif
- Period: 1980-01-01 – 2018-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 0 to 1.065, mean 0.0005633, valid pixels 100.0%
- Hazard (`GCHD:hazard`): Geophysical
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Modelled
- Units (`GCHD:units`): landslides per km² per year
- Resolution (`GCHD:nominal_resolution`): 1 km
- Coverage (`GCHD:coverage`): All land areas between 60°S and 72°N
- Exposure threshold (`GCHD:threshold`): ≥ 0.01 or ≥ 0.1
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 2.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/LS_RF_Mean_1980-2018_COG
- CRS: EPSG:4326
- Exposure rule `landslides_0p1`: exposed where value > 0.1; a pixel has data where value > -1000 (default variant)
- Exposure rule `landslides_0p01`: exposed where value > 0.01; a pixel has data where value > -1000

## Data quality & usage notes

- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `landslides_0p1`, `landslides_0p01`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `landslides_0p1`, `landslides_0p01`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `landslides_0p1`, `landslides_0p01`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
