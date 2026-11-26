# AGENTS.md: Malaria Plasmodium Vivax (`vectorborne_malariapv_2012-2022`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

P. vivax is the dominant malaria parasite in most countries outside of sub-Saharan Africa. Malaria is a life-threatening disease caused by parasites transmitted to humans through the bites of infected female Anopheles mosquitoes.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapv_2012-2022.tif
- Period: 2013-01-01 – 2022-12-31
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapv_2012-2022.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapv_2012-2022.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `-9999.0`; observed range -666.6 to 0.1733, mean -0.0223, valid pixels 15.9%
- Hazard (`GCHD:hazard`): Vector Borne Diseases
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Modelled
- Units (`GCHD:units`): # per 1000 people
- Resolution (`GCHD:nominal_resolution`): 5km
- Coverage (`GCHD:coverage`): Global
- Exposure threshold (`GCHD:threshold`): > 0,001
- Classes (`GCHD:classes`): Use natural breaks/quantile
- Value range (`GCHD:value_range`): [0.0, 1.0]
- GEE asset (`GCHD:gee_asset`): projects/unicef-ccri/assets/hazards/Pv_average_2013_2022
- CRS: EPSG:4326
- Exposure rule `epidemics_malaria_pv`: exposed where value > 0.001; a pixel has data where value > 0 (default variant)

## Data quality & usage notes

- This layer map provides estimates of newly diagnosed Plasmodium falciparum cases per 1,000 population, on a given year. To produce these estimates, we apply geostatistical models to response datasets consisting of PR points and routine surveillance reports, and a rich set of geospatial covariates that characterise habitat for Anopheles mosquitos that spread the disease. The maps cover all malaria-endemic countries and are produced annually from year 2000 at a 5x5 km resolution. The rasters may be downloaded as a series of multi-band GeoTiffs. The first band consists of the modelled estimates as rates per person [0-1]. The second band is a mask consisting of the values zero and 1; the 1 values represent pixels that we mask out because they are sparsely populated. This masking is only applied to South America, and we define "sparsely populated" as areas that have a modelled estimate of >0 and a population of ≤5 people per pixel.
- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pv`
- [Hazard exposure by ADM1, per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) (`adm1_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pv`
- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics of this layer, rows with `hazard_code` in `epidemics_malaria_pv`
- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
