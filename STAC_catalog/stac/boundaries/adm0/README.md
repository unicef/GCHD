# Administrative boundaries - ADM0 (countries and territories)

UNICEF GeoRepo ADM0 (2025-10-14); Mali replaced by MLI_V2 dissolved from ADM2. `has_exposure` marks units present in the exposure tables.

Source: UNICEF; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Rows | 289 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 104.1 MB | [Administrative boundaries - ADM0 (countries and territories) (GeoParquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.parquet) |
| `tiles` | application/vnd.pmtiles | 55.3 MB | [Administrative boundaries - ADM0 (countries and territories) (PMTiles vector tiles)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0/adm0.pmtiles) |
| `style` | application/vnd.mapbox.style+json | 688 B | [Default MapLibre style (PMTiles)](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm0/style.json) |
| `thumbnail` | image/jpeg | 31.3 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm0/thumbnail.jpg) |

## Access

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

---
STAC: [`boundaries/adm0/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm0/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/boundaries/adm0/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
