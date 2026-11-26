# AGENTS.md: Agricultural Drought (Agricultural Stress Index) (`agricultural_drought_fao_1984-2023`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Agricultural drought occurs when there is insufficient soil moisture to meet the needs of a particular crop at a particular time

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif
- Period: 1984-01-01 – 2023-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 14.85 to 100, mean 57.45, valid pixels 16.0%
- Hazard (`GCHD:hazard`): Droughts
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): %
- Resolution (`GCHD:nominal_resolution`): 1km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): >30% cropland affected
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 100.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/ASI_return_level_100yr
- CRS: EPSG:4326
- Exposure rule `drought_asi`: exposed where value > 30; a pixel has data where value <= 100 (default variant)

## Data quality & usage notes

- Drought is a complicated phenomena - GRID's drought layer is not useful to be considered as it predominantly caters to the location of hydro-electric power generation. JRC doesnt have any immediate plans to release global drought layer and WFP is working on one - yet to be generated.
- Alternate sources: WFP, JRC - yet to be published
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_asi`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_asi`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `drought_asi`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
