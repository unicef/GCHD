# AGENTS.md: Hazard exposure by district (ADM2), per hazard (`adm2_hazard`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

One row per (adm2_ucode, hazard_code). Columns follow the ' Data Schema' sheet of Global Hazard Data catalog.xlsx. Computed by the GEE exposure pipeline (CSV release 2026-08-31); for some hazards (heatwave, extreme heat, ASI, malaria, SPI/SPEI drought) GEE used a different version of the layer than the hazard COGs in this catalog, so the numbers can differ from a recomputation on the COGs. Join to adm2 on adm2_ucode = ucode.

- Layout: one Parquet table (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/adm2_hazard/adm2_hazard.parquet
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

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

## Schema & field notes

- Source release (`GCHD:source_release`): 2026-08-31

| Column | Type | Unit | Description |
|---|---|---|---|
| `hazard_code` | string |  | GCHD pipeline hazard code (CSV file stem); see config/hazard_map.yaml. |
| `unicef_code` | string |  | UNICEF proposed / GLIDE code from the 'Hazard Codes' tab. |
| `source_release` | string |  | Release date of the source CSVs. |
| `geo_level` | string |  | Determines at what geographic level (global, country, region, etc). |
| `hazard` | string |  | The hazard type that is being assessed. |
| `source` | string |  | GEE asset from  which hazard data was obtained. |
| `prod_date` | date32[day] |  | The date when the data was produced. |
| `dataflow` | string |  | Data flow code according to UNICEF. |
| `time_period` | int16 |  | Year or time period for which the data is produced. |
| `iso3` | string |  | ISO 3 code of the country |
| `adm0_id` | int64 |  | Administrative level 0 (national level) unique ID. |
| `adm0_name` | string |  | Administrative level 0 (national level) readable name. |
| `adm0_ucode` | string |  | Administrative level 0 (national level) unique code. |
| `adm1_name` | string |  | Administrative level 1 (regional level) readable name. |
| `adm1_ucode` | string |  | Administrative level 1 (regional level) unique code. |
| `adm2_name` | string |  | Administrative level 2 (district level) readable name. |
| `adm2_ucode` | string |  | Administrative level 2 (district level) unique code. |
| `unicef_region` | string |  | UNICEF region acronym. |
| `unicef_region_full` | string |  | Complete name of the UNICEF region. |
| `hazs_mean` | double |  | Average intensity value of the hazard across the assessed administrative area. Higher numbers mean the physical danger is generally greater. |
| `hazs_std` | double |  | How much the intensity varies within the assessed administrative area. A large value means some locations are much riskier than others. |
| `hazs_max` | double |  | Highest hazard intensity within the administrative area. Higher values indicate severe localized impacts. |
| `hazs_min` | double |  | Lowest hazard intensity within the administrative area. Lower values represent minimal hazard intensity. |
| `hazs_median` | double |  | Middle value of hazard intensity when ranked from lowest to highest within the administrative area. Higher median refers to moderate–high intensity. |
| `gindex` | double | Index (0–10) | A 0–10 index scaled using global minimum and maximum hazard intensity values. Higher values indicate more severe global hazard levels. |
| `cindex` | double | Index (0–10) | A 0–10 index scaled using country-specific minimum and maximum hazard intensity values. Higher values indicate severe national-level hazard conditions. |
| `rindex` | double | Index (0–10) | A 0–10 index scaled using regional intensity extremes. Higher values reflect more severe regional hazard conditions. |
| `pop_total` | int64 | Persons | Estimated number of people residing in an admin unit. |
| `pop_total_m` | int64 | Persons | Estimated number of male population residing in an admin unit. |
| `pop_total_f` | int64 | Persons | Estimated number of  female population residing in an admin unit. |
| `u18_pop_total` | int64 | Persons | Estimated number of children residing in an admin unit. |
| `u18_pop_m` | int64 | Persons | Estimated number of boys under 18 residing in an admin unit. |
| `u18_pop_f` | int64 | Persons | Estimated number of girls under 18 residing in an admin unit. |
| `aexp` | int64 | Persons | Estimated number of people residing in hazard-exposed areas. |
| `amexp` | int64 | Persons | Estimated number of males residing in hazard-exposed areas. |
| `afexp` | int64 | Persons | Estimated number of females residing in hazard-exposed areas. |
| `u18_aexp` | int64 | Persons | Estimated number of children (under 18 years) residing in hazard-exposed areas. |
| `u18_amexp` | int64 | Persons | Estimated number of male children (under 18 years) residing in hazard-exposed areas. |
| `u18_afexp` | int64 | Persons | Estimated number of female children (under 18 years) residing in hazard-exposed areas. |
| `rexp` | double | Percent (%) | Estimated proportion of the total population of the administrative area residing in hazard-exposed areas. |
| `rmexp` | double | Percent (%) | Estimated proportion of all males in the administrative area residing in hazard-exposed areas. |
| `rfexp` | double | Percent (%) | Estimated proportion of all females in the administrative area residing in hazard-exposed areas. |
| `u18_rexp` | double | Percent (%) | Estimated proportion of all children (under 18) in the administrative area residing in hazard-exposed areas. |
| `u18_rmexp` | double | Percent (%) | Estimated proportion of male children (under 18) in the administrative area residing in hazard-exposed areas. |
| `u18_rfexp` | double | Percent (%) | Estimated proportion of female children (under 18) in the administrative area residing in hazard-exposed areas. |
| `gexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. |
| `cexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. |
| `rexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. |
| `gmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `cmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `rmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `gfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `cfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `rfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `u18_gexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. |
| `u18_cexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. |
| `u18_rexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. |
| `u18_gmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `u18_cmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `u18_rmexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. Male population only. |
| `u18_gfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `u18_cfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a country where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `u18_rfexpi` | double | Index (0–10) | A 0–10 index that combines log-scaled absolute exposure and percentage-based relative children exposure (each robust min–max normalised) via the geometric mean, identifying locations within a region where both the number and proportion of people exposed are simultaneously high. Female population only. |
| `gexpc` | int8 | Class label (1-5) | Categorisation of global exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. |
| `cexpc` | int8 | Class label (1-5) | Categorisation of country-specific exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. |
| `rexpc` | int8 | Class label (1-5) | Categorisation of regional exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. |
| `gmexpc` | int8 | Class label (1-5) | Categorisation of global exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. Male population only. |
| `cmexpc` | int8 | Class label (1-5) | Categorisation of country-specific exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. Male population only. |
| `rmexpc` | int8 | Class label (1-5) | Categorisation of regional exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. Male population only. |
| `gfexpc` | int8 | Class label (1-5) | Categorisation of global exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. Female population only. |
| `cfexpc` | int8 | Class label (1-5) | Categorisation of country-specific exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. Female population only. |
| `rfexpc` | int8 | Class label (1-5) | Categorisation of regional exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. Female population only. |
| `u18_gexpc` | int8 | Class label (1-5) | Categorisation of global children exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. |
| `u18_cexpc` | int8 | Class label (1-5) | Categorisation of country-specific children exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. |
| `u18_rexpc` | int8 | Class label (1-5) | Categorisation of regional children exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. |
| `u18_gmexpc` | int8 | Class label (1-5) | Categorisation of global children exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. Male population only. |
| `u18_cmexpc` | int8 | Class label (1-5) | Categorisation of country-specific children exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. Male population only. |
| `u18_rmexpc` | int8 | Class label (1-5) | Categorisation of regional children exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. Male population only. |
| `u18_gfexpc` | int8 | Class label (1-5) | Categorisation of global children exposure index scores into five classes indicating relative levels of population exposure, from Very low to Very high. Female population only. |
| `u18_cfexpc` | int8 | Class label (1-5) | Categorisation of country-specific children exposure index scores into five classes, clearly conveying relative exposure levels at the national scale. Female population only. |
| `u18_rfexpc` | int8 | Class label (1-5) | Categorisation of regional children exposure index scores into five classes, providing clear and actionable relative exposure levels within regional contexts. Female population only. |
| `status` | string |  | Data availability flag: empty = valid, 'No Data', 'Insufficient Data', 'Not Applicable'. |

## Data quality & usage notes

- Rows with a non-empty `status` ('No Data', 'Insufficient Data', 'Not Applicable') carry no valid statistics; filter `status IS NULL OR status = ''` before aggregating.
- The exposure numbers come from the GEE exposure pipeline. For some hazards GEE used a different version of the layer than the COG in this catalog, so a recomputation on the COG can differ.

## Related collections

- [Administrative boundaries - ADM2 (districts)](https://unicef.github.io/GCHD/STAC_catalog/stac/boundaries/adm2/collection.json) (`adm2`): boundaries of the units: join `adm2_ucode` = `ucode`
- Hazard layers: each hazard collection lists its `hazard_code`s in `GCHD:exposure_rules`.
