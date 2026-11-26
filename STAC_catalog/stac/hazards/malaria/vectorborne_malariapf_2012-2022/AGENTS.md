# AGENTS.md: Malaria Plasmodium Falciparum (`vectorborne_malariapf_2012-2022`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Malaria is a life-threatening disease caused by parasites transmitted to humans through the bites of infected female Anopheles mosquitoes. P. falciparum is the deadliest malaria parasite and the most prevalent on the African continent.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif
- Period: 2013-01-01 – 2022-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `-9999.0`; observed range -4312 to 0.5765, mean -0.418, valid pixels 21.7%
- Hazard (`GCHD:hazard`): Vector Borne Diseases
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Modelled
- Units (`GCHD:units`): # per 1000 people
- Resolution (`GCHD:nominal_resolution`): 5km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): > 0,001
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 1.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/Pf_average_2013_2022
- CRS: EPSG:4326
- Exposure rule `epidemics_malaria_pf`: exposed where value > 0.001; a pixel has data where value > 0 (default variant)

## Data quality & usage notes

- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pf`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pf`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pf`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
