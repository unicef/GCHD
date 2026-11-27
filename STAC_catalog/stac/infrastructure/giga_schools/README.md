# School locations (Giga)

School point locations from Giga, the UNICEF-ITU initiative to connect every school to the Internet, for 180 countries (2,324,244 schools, snapshot of 2026-11-20). One row per school with its Giga identifier, name, education level and coordinates. The data come from governments, which share their school records with Giga, and from open sources such as OpenStreetMap, checked by Giga against satellite imagery.

`education_level` is free text as reported by each source, in several languages ('Primary', 'Primaria', 'Primaire', ...), and is 'Unknown' for about half of the schools. Coverage and completeness vary by country. A country missing from the table, or with few rows, does not mean it has no schools.

Source: Giga (UNICEF and ITU) (https://giga.global/); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2026-11-20 – 2026-11-20 |
| Rows | 2324244 |
| License | other |
| Providers | Giga (UNICEF and ITU) (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 164.9 MB | [School locations (Giga) (GeoParquet 1.1)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/infrastructure/giga_schools_global.parquet) |
| `thumbnail` | image/jpeg | 19.2 KB | [Thumbnail (point density)](https://unicef.github.io/GCHD/STAC_catalog/stac/infrastructure/giga_schools/thumbnail.jpg) |

## Access

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

---
STAC: [`infrastructure/giga_schools/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/infrastructure/giga_schools/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/infrastructure/giga_schools/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
