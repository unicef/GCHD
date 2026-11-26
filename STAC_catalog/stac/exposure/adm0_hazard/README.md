# Hazard exposure by country (ADM0), per hazard (roll-up)

Roll-up of adm2_hazard to country level, with the same rules and GEE provenance as adm1_hazard. Join to adm0 on adm0_ucode = ucode.

Source: UNICEF; release 2026-08-31; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Source release | 2026-08-31 |
| Rows | 5610 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 305.5 KB | [Hazard exposure by country (ADM0), per hazard (roll-up) (Parquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0_hazard/adm0_hazard.parquet) |
| `thumbnail` | image/jpeg | 31.3 KB | [Thumbnail (ADM0 administrative boundaries)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/thumbnail.jpg) |

## Access

```sql
-- DuckDB reads the Parquet over HTTP (range requests): no download needed
INSTALL httpfs; LOAD httpfs;
SELECT iso3, adm0_name, hazard_code, u18_aexp, u18_rexp
FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0_hazard/adm0_hazard.parquet'
WHERE hazard_code = 'river_flood_100yr' AND iso3 = 'BGD'
ORDER BY u18_aexp DESC LIMIT 10;
```
```python
import pandas as pd
df = pd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm0_hazard/adm0_hazard.parquet", filters=[("iso3", "==", "BGD")])
```

---
STAC: [`exposure/adm0_hazard/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm0_hazard/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/exposure/adm0_hazard/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
