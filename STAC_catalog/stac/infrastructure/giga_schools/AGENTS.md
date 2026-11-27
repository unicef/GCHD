# AGENTS.md: School locations (Giga) (`giga_schools`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

School point locations from Giga, the UNICEF-ITU initiative to connect every school to the Internet, for 180 countries (2,324,244 schools, snapshot of 2026-11-20). One row per school with its Giga identifier, name, education level and coordinates. The data come from governments, which share their school records with Giga, and from open sources such as OpenStreetMap, checked by Giga against satellite imagery.

- Layout: one GeoParquet 1.1 point table (collection-level `data` asset), sorted by `iso3`.
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet
- Period: 2026-11-20 – 2026-11-20
- License: other (https://giga.global/)

## Accessing the data

```python
import geopandas as gpd
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet", filters=[("iso3", "==", "BGD")])          # one country
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet", bbox=(west, south, east, north))          # GeoParquet 1.1 bbox covering
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT iso3, count(*) AS n FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet' GROUP BY iso3 ORDER BY n DESC;
-- points in an area: the bbox column lets DuckDB skip row groups
SELECT name, education_level, longitude, latitude FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet'
WHERE bbox.xmin BETWEEN 88 AND 93 AND bbox.ymin BETWEEN 20.5 AND 26.7;
```
Hazard value at each point (sample a hazard COG of this catalog; GDAL streams only the blocks it needs):
```python
import rasterio
with rasterio.open(hazard_cog_url) as src:
    gdf["hazard"] = [v[0] for v in src.sample(zip(gdf.longitude, gdf.latitude))]
```

## Schema & field notes


| Column | Type | Unit | Description |
|---|---|---|---|
| `facility_id` | large_string |  | Giga school identifier (unique) |
| `name` | large_string |  | School name as reported by the source ('Name unknown' when missing) |
| `education_level` | large_string |  | Education level, free text as reported by the source (not harmonised; 'Unknown' for about half the rows) |
| `iso3` | large_string |  | ISO 3166-1 alpha-3 country code; the file is sorted by iso3, so a filter on it reads only a few row groups |
| `country_name` | large_string |  | Country name |
| `longitude` | double |  | Longitude, WGS84 |
| `latitude` | double |  | Latitude, WGS84 |
| `geometry` | binary |  | Point geometry, EPSG:4326 (WKB) |
| `bbox` | struct<xmin: double, ymin: double, xmax: double, ymax: double> |  | GeoParquet 1.1 bbox covering of the geometry (xmin, ymin, xmax, ymax), for spatial filters |

## Data quality & usage notes

- The terms are those of Giga and of the governments that share the data; check them at https://giga.global/ before redistributing.

## Related collections

- [Administrative boundaries - ADM2 (districts)](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm2/collection.json) (`adm2`): ADM2 boundaries: assign each point to its district with a spatial join
- Hazard layers: sample any hazard COG at the points to find facilities in hazard zones; each hazard collection's `GCHD:exposure_rules` give the threshold for 'exposed'.
