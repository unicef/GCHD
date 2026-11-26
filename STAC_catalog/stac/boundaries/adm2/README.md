# Administrative boundaries - ADM2 (districts)

GEE admin2_pop_geom export (2026-06-04), the geometry the ADM2 exposure statistics were computed on (41,023 units), with WorldPop 2025 population totals.

Source: UNICEF; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Rows | 41023 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 545.6 MB | [Administrative boundaries - ADM2 (districts) (GeoParquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.parquet) |
| `tiles` | application/vnd.pmtiles | 266.1 MB | [Administrative boundaries - ADM2 (districts) (PMTiles vector tiles)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2/adm2.pmtiles) |
| `style` | application/vnd.mapbox.style+json | 688 B | [Default MapLibre style (PMTiles)](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm2/style.json) |
| `thumbnail` | image/jpeg | 24.3 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm2/thumbnail.jpg) |

## Access

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

---
STAC: [`boundaries/adm2/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm2/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/boundaries/adm2/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
