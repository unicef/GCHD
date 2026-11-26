# Hazard exposure by ADM1, per hazard (roll-up)

Roll-up of adm2_hazard following each column's Aggregation Logic. Counts are summed, percentages recomputed, max/min kept, hazs_mean and severity indices population-weighted (provisional); medians, std and the exposure indices and classes are null. Same GEE provenance as adm2_hazard. Join to adm1 on adm1_ucode = ucode.

Source: UNICEF; release 2026-08-31; processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Source release | 2026-08-31 |
| Rows | 77682 |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | application/vnd.apache.parquet | 3.1 MB | [Hazard exposure by ADM1, per hazard (roll-up) (Parquet)](https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1_hazard/adm1_hazard.parquet) |
| `thumbnail` | image/jpeg | 29.2 KB | [Thumbnail (ADM1 administrative boundaries)](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/thumbnail.jpg) |

## Access

```sql
-- DuckDB reads the Parquet over HTTP (range requests): no download needed
INSTALL httpfs; LOAD httpfs;
SELECT iso3, adm1_name, hazard_code, u18_aexp, u18_rexp
FROM 'https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1_hazard/adm1_hazard.parquet'
WHERE hazard_code = 'river_flood_100yr' AND iso3 = 'BGD'
ORDER BY u18_aexp DESC LIMIT 10;
```
```python
import pandas as pd
df = pd.read_parquet("https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm1_hazard/adm1_hazard.parquet", filters=[("iso3", "==", "BGD")])
```

---
STAC: [`exposure/adm1_hazard/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/exposure/adm1_hazard/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/exposure/adm1_hazard/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
