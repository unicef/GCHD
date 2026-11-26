# AGENTS.md: PM 2.5 (`air_pollution_pm25_2012-2022`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Air pollution refers to the presence of substances in the atmosphere that are harmful to human health and the environment.  Fine particle air pollution, or PM2 .5, refers to airborne particles measuring less than 2 .5 micrometers in diameter that could be emitted from vehicles, residential fuel use, coal-burning power plants, agricultural and industrial activities, waste burning, wildfires, and many other human and natural sources.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif
- Period: 2012-01-01 – 2022-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 1.065 to 268, mean 20.24, valid pixels 34.1%
- Hazard (`GCHD:hazard`): Air pollution
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): μg/m3
- Resolution (`GCHD:nominal_resolution`): 1km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): >5 AQG
- Classes (`GCHD:classes`): 5 - 10 - 15 - 25 - 35+
- Value range (`GCHD:value_range`): [0.0, 300.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/pm25_p90_1998_2023
- CRS: EPSG:4326
- Exposure rule `air_pollution_pm25`: exposed where value > 5; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- Threshold adopted from WHO guidelines -= https://worldhealthorg.shinyapps.io/Air_Quality_Standards_V2_1/
- Alternate sources: WMO
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `air_pollution_pm25`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `air_pollution_pm25`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `air_pollution_pm25`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
