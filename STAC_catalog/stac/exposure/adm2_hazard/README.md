# Hazard exposure by district (ADM2), per hazard

One row per (adm2_ucode, hazard_code). Columns follow the ' Data Schema' sheet of Global Hazard Data catalog.xlsx. Computed by the GEE exposure pipeline (CSV release 2026-08-31); for some hazards (heatwave, extreme heat, ASI, malaria) GEE used a different version of the layer than the hazard COGs in this catalog, so the numbers can differ from a recomputation on the COGs. Join to adm2 on adm2_ucode = ucode.

Source: UNICEF; release 2026-08-31; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Source release | 2026-08-31 |
| Rows | 902506 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 48.2 MB | [Hazard exposure by district (ADM2), per hazard (Parquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2_hazard/adm2_hazard.parquet) |
| `thumbnail` | image/jpeg | 24.3 KB | [Thumbnail (ADM2 administrative boundaries)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/thumbnail.jpg) |

## Access

```sql
-- DuckDB reads the Parquet over HTTP (range requests): no download needed
INSTALL httpfs; LOAD httpfs;
SELECT iso3, adm2_name, hazard_code, u18_aexp, u18_rexp
FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2_hazard/adm2_hazard.parquet'
WHERE hazard_code = 'river_flood_100yr' AND iso3 = 'BGD'
ORDER BY u18_aexp DESC LIMIT 10;
```
```python
import pandas as pd
df = pd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2_hazard/adm2_hazard.parquet", filters=[("iso3", "==", "BGD")])
```

---
STAC: [`exposure/adm2_hazard/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm2_hazard/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/exposure/adm2_hazard/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
