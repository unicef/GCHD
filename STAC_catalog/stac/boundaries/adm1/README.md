# Administrative boundaries - ADM1

UNICEF GeoRepo ADM1 (2025-10-14); Mali replaced by MLI_V2 dissolved from ADM2. `has_exposure` marks units present in the exposure tables.

Source: UNICEF; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Rows | 3578 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 232.6 MB | [Administrative boundaries - ADM1 (GeoParquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1/adm1.parquet) |
| `tiles` | application/vnd.pmtiles | 101.5 MB | [Administrative boundaries - ADM1 (PMTiles vector tiles)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1/adm1.pmtiles) |
| `style` | application/vnd.mapbox.style+json | 688 B | [Default MapLibre style (PMTiles)](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm1/style.json) |
| `thumbnail` | image/jpeg | 29.2 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm1/thumbnail.jpg) |

## Access

```python
import geopandas as gpd
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1/adm1.parquet", bbox=(west, south, east, north))   # GeoParquet 1.1 with bbox covering
gdf = gpd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1/adm1.parquet", filters=[("iso3", "==", "BGD")])
```
```sql
INSTALL spatial; LOAD spatial; INSTALL httpfs; LOAD httpfs;
SELECT ucode, name, iso3, ST_Area(geometry) FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1/adm1.parquet' WHERE iso3 = 'BGD';
```
For web maps use the `tiles` asset (PMTiles, vector tiles in one file).

---
STAC: [`boundaries/adm1/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm1/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/boundaries/adm1/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
