# AGENTS.md: Fire Frequency (`fire_frequency_nasa_2001-2023`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Wildfires are uncontrolled burns of vegetation, including forests, shrublands, grasslands, savannas, and croplands. Fire Radiative Power (FRP) is a measure of the energy released by a fire in the form of radiation.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif
- Period: 2001-01-01 – 2023-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 1 to 165.4, mean 3.881, valid pixels 18.8%
- Hazard (`GCHD:hazard`): Fire
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): km⁻² · yr⁻¹
- Resolution (`GCHD:nominal_resolution`): 250 m
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): 4.91
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 1500.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/FIRMS_count_90th_percentile
- CRS: EPSG:4326
- Exposure rule `fire_frequency`: exposed where value > 4.9134115164042935; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- *World Bank's modelled data link is not up-to-date; FIRMS data of average Fire count  between 2014-2024 >1
- Alternate sources: JRC Global Wildfire Information System, NASA FIRMS, World Bank
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `fire_frequency`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `fire_frequency`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `fire_frequency`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
