# AGENTS.md: Volcanoes (`gvp_hol_volcanoes_1800`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Number of people and children within 100km2 radius of an active volcano. A volcano is considered active if it had vlocanic activity after 1800. The 100km radius was selected as the maximum distance where children could be affected by emissions from volcanoes.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif
- Period: 2026-10-22 – 2026-10-22
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 7025 to 1e+05, mean 7.175e+04, valid pixels 2.7%
- Hazard (`GCHD:hazard`): Geophysical
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Observed
- Units (`GCHD:units`): people per 100 km²
- Resolution (`GCHD:nominal_resolution`): 0.1 degree/11km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): <=100km
- Classes (`GCHD:classes`): 0, 30, 50, 80, 100, >100
- Value range (`GCHD:value_range`): [0.0, 100000.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/hol_volcanoes_1800_100kmbuff
- CRS: EPSG:4326
- Exposure rule `volcano_100km_buff`: exposed where value > 0; a pixel has data where value > -1000 (default variant)

## Data quality & usage notes

- This layer was produced using records of active volcanoes since 1800 from the Smithsonian Institute-Global Volcanism Program. The Hazard layer has ranks from 0 to 5 with 0 being not within 100km of an active volcano. 0 - 10km: 5, 10 - 30km: 4, 30 - 50km: 3, 50 - 80km: 2, 80 to 100km: 1, > 100km: 0. This layer was developed with significant input from UNICEF's PG Climate team, Prof. Claire Horwell of Durham University and Assoc. Prof. Carol Stewart of the Massey University, New Zealand. Data Source: https://volcano.si.edu/
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `volcano_100km_buff`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `volcano_100km_buff`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `volcano_100km_buff`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
