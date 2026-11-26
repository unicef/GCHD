# AGENTS.md: Administrative boundaries - ADM0 (countries and territories) (`adm0`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

UNICEF GeoRepo ADM0 (2025-10-14); Mali replaced by MLI_V2 dissolved from ADM2. `has_exposure` marks units present in the exposure tables.

- Layout: one GeoParquet file (`data`) plus PMTiles vector tiles (`tiles`).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.parquet
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import geopandas as gpd
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.parquet", bbox=(west, south, east, north))   # GeoParquet 1.1 with bbox covering
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.parquet", filters=[("iso3", "==", "BGD")])
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT ucode, name, iso3, ST_Area(geometry) FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.parquet' WHERE iso3 = 'BGD';
```
For web maps use the `tiles` asset (PMTiles, vector tiles in one file).

## Schema & field notes


| Column | Type | Unit | Description |
|---|---|---|---|
| `ucode` | string |  |  |
| `name` | string |  |  |
| `name_en` | string |  |  |
| `iso3` | string |  |  |
| `adm0_type` | string |  |  |
| `source` | string |  |  |
| `geometry` | binary |  |  |
| `has_exposure` | bool |  |  |
| `bbox` | struct<xmin: double, ymin: double, xmax: double, ymax: double> |  |  |

## Data quality & usage notes


## Related collections

- [Hazard exposure by country (ADM0), per hazard (roll-up)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) (`adm0_hazard`): exposure statistics per unit: join `ucode` = `adm0_ucode`
