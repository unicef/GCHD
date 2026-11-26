# AGENTS.md: Administrative boundaries - ADM2 (districts) (`adm2`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

GEE admin2_pop_geom export (2026-06-04), the geometry the ADM2 exposure statistics were computed on (41,023 units), with WorldPop 2025 population totals.

- Layout: one GeoParquet file (`data`) plus PMTiles vector tiles (`tiles`).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import geopandas as gpd
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet", bbox=(west, south, east, north))   # GeoParquet 1.1 with bbox covering
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet", filters=[("iso3", "==", "BGD")])
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT ucode, name, iso3, ST_Area(geometry) FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet' WHERE iso3 = 'BGD';
```
For web maps use the `tiles` asset (PMTiles, vector tiles in one file).

## Schema & field notes


| Column | Type | Unit | Description |
|---|---|---|---|
| `ucode` | string |  |  |
| `name` | string |  |  |
| `name_en` | string |  |  |
| `name_fr` | string |  |  |
| `adm1_ucode` | string |  |  |
| `adm1_name` | string |  |  |
| `adm0_ucode` | string |  |  |
| `adm0_name` | string |  |  |
| `iso3` | string |  |  |
| `adm0_type` | string |  |  |
| `pcode` | string |  |  |
| `unicef_region` | string |  |  |
| `unicef_region_full` | string |  |  |
| `pop_total` | int64 |  |  |
| `pop_total_male` | int64 |  |  |
| `pop_total_female` | int64 |  |  |
| `pop_under_18_total` | int64 |  |  |
| `pop_under_18_male` | int64 |  |  |
| `pop_under_18_female` | int64 |  |  |
| `source` | string |  |  |
| `geometry` | binary |  |  |
| `has_exposure` | bool |  |  |
| `bbox` | struct<xmin: double, ymin: double, xmax: double, ymax: double> |  |  |

## Data quality & usage notes


## Related collections

- [Hazard exposure by district (ADM2), per hazard](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) (`adm2_hazard`): exposure statistics per unit: join `ucode` = `adm2_ucode`
