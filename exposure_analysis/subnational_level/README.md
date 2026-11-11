# Global Child Hazard Database — Hazard Exposure Pipeline

A cleaned, documented subset of UNICEF's Global Child Hazard Database processing pipeline.

This pipeline computes child population exposure to climate and environmental hazards at the admin2 level globally, then derives the exposure indices and classes used for CCRI scoring, and exports the results as tables, vector files, per-country rasters, and SDMX-CSV.
Each hazard layer (riverine/coastal flood, tropical storm, drought, heatwave, fire, sand & dust, PM2.5, malaria, earthquake, volcano, landslide, …) is intersected in Google Earth Engine with WorldPop child-population rasters to produce, per admin2 unit:

- **`aexp`** absolute exposure, **`rexp`** relative exposure,
- **`expi`** normalized exposure index (0–10), **`expc`** exposure class,
- hazard statistics (`mean`, `std`, `median`, `min`, `max`),

broken out by **total / male / female** and **under-18** subgroups, at **global / country / regional**
aggregation scopes. A final stage also exports **continuous raster surfaces (GeoTIFF) per country**
and attempts hand those rasters off to SharePoint automatically.

Everything runs from numbered Jupyter notebooks in `notebooks/`, backed by two shared Python
modules in `lib/` and canonical reference data in `config/`.

---

## Folder layout

```
handoff/
├── README.md                       # this file
├── notebooks/                      # numbered in execution order
│   ├── 01_adm2_hazard_exposure_updated.ipynb        # Phase 1 — exposure extraction
│   ├── 02_adm2_hazard_indices_NA.ipynb              # Phase 2 — indices & classes
│   ├── 03_adm2_hazard_export.ipynb                  # Phase 3 — Excel + GeoPackage export
│   ├── 04_adm2_hazard_exposure_raster_country.ipynb # Phase 4 — per-country rasters + SharePoint
│   └── 05_adm2_hazard_export_sdmx.ipynb             # Phase 5 — SDMX-CSV export
│
├── lib/                            # shared Python modules (imported by the notebooks)
│   ├── GEE_functions.py            # GEEUtils + Hazard: Earth Engine wrappers, exposure math, exports
│   ├── indicator_functions.py      # IndicatorUtils: index/class math + canonical column schema
│   └── sharepoint_sync.py          # Drive → SharePoint hand-off helpers (notebook 04)
│
├── config/                         # canonical reference data (single source of truth)
│   ├── hazard_info.json            # hazard definitions (asset, threshold, operation, nodata…)
│   ├── hazard_info.csv             # same, CSV form
│   ├── countries_info.csv          # ISO3 ↔ ucode ↔ country name lookup
│   ├── countries_NA_summary.csv    # countries marked "Not applicable" and why
│   └── deltares_hazard_info.json   # alternate Deltares coastal-flood layer config
│
├── bounds/                         # cached admin2 geometries for huge countries (skips slow getInfo)
│   ├── CAN_bounds.geojson
│   ├── GRL_bounds.geojson
│   ├── RUS_bounds.geojson
│   ├── USA_bounds.geojson
│   └── adm2_pop_geom_complete_update.csv
│
├── regions/
│   └── UNICEF_REP_REG_GLOBAL.csv   # region / regional-grouping mapping for output joins
│
└── credentials/                    # GEE service account + OAuth tokens — GITIGNORED, never commit
```

---

## Execution order

The notebooks are numbered to run in sequence; each consumes the previous stage's output.

| # | Notebook | Phase | What it does |
|---|----------|-------|--------------|
| 01 | `01_adm2_hazard_exposure_updated` | 1 — Exposure | Extracts per-country, per-hazard child-population exposure in GEE for every admin2 unit. Iterate until all ~40,900 admin2 units are covered for each hazard. |
| 02 | `02_adm2_hazard_indices_NA` | 2 — Indices | Concatenates the per-country results to global, then computes normalized indices (`expi`) and classes (`expc`), incl. the `Not applicable` handling for non-populated / non-official units. |
| 03 | `03_adm2_hazard_export` | 3 — Export | Writes the global and per-country deliverables to **Excel** and **GeoPackage**. |
| 04 | `04_adm2_hazard_exposure_raster_country` | 4 — Rasters | Exports continuous **GeoTIFF** raster surfaces per country (hazard + exposure bands) to Google Drive, then optionally hands them off to **SharePoint** automatically (see below). Independent of 02/03 — can run any time after the hazard assets exist. |
| 05 | `05_adm2_hazard_export_sdmx` | 5 — SDMX | Converts the results to **SDMX-CSV** for UN statistical portals. |

---

## Prerequisites

### Python environment

```bash
conda create -n ccri python=3.10
conda activate ccri
pip install geopandas rasterio earthengine-api xarray numpy pandas matplotlib seaborn plotly sdmx1 mapclassify openpyxl pyogrio

# Extra deps used only by the notebook-04 Drive → SharePoint hand-off:
pip install google-api-python-client google-auth-oauthlib msal requests
```

### Google Earth Engine

Most notebooks call `ee.Initialize(project='unicef-ccri')`. Authenticate once per machine:

```bash
earthengine authenticate
earthengine set_project unicef-ccri
```

Service-account use additionally requires `credentials/unicef-ccri.json` (gitignored).

---

## The Drive → SharePoint hand-off (notebook 04)

The per-country raster export writes GeoTIFFs to Google Drive via Earth Engine batch tasks.
Historically these were then **manually downloaded from Drive and re-uploaded to SharePoint**.
Notebook 04 now automates that hand-off end-to-end; the logic lives in `lib/sharepoint_sync.py`.

**Flow:**

1. **Stage 0** — pre-create the root-level Drive folder named by each `ucode` (via the Drive API),
   so the many concurrent EE export tasks don't race and spawn duplicate same-name folders.
2. **Export** — EE exports each country's hazard + exposure bands into its `ucode` Drive folder.
3. **Stage B** — poll the EE tasks until every export is `COMPLETED` / `FAILED`.
4. **Stage C1** — download the finished TIFFs from Drive into a local temp dir.
5. **Stage C2** — upload them to SharePoint at
   `…/Country engagement/2025/<Country Name>/rasters/`, creating the per-country folder and
   `rasters/` subfolder if missing. `<Country Name>` comes from `config/countries_info.csv`.
6. **Stage D** — delete the local temp copies (the Drive folder is kept as a backup).

---

## Key concepts

- **ucode** — country/admin key (e.g. `CAN_V1`, `BES1_V2`). One ISO3 can map to multiple ucodes.
  See `config/countries_info.csv`, which also provides the human-readable country `name` used for
  the SharePoint folders.
- **admin1 processing path** — large countries (CAN, USA, BRA, IND, CHN, AUS, AUS1, DZA, RUS, FIN,
  SRB, KAZ, GRL) are processed one admin1 at a time to avoid GEE memory limits. See
  `admin1_process_countries` in `lib/GEE_functions.py`.
- **tiled path** — very large admin2 polygons (mainly RUS, CAN) are intersected with a 1° grid via
  Shapely and processed in batches, avoiding costly `ee.Image.clip()` on complex geometries.
  Cached geometries for the worst offenders live in `bounds/`.
- **hazard config** — `config/hazard_info.json` is the single source of truth, loaded into the
  `Hazard` dataclass. Each entry carries `asset, band, threshold, threshold_operation (gt/gte/lt/lte), 
  apply_nodata, nodata, mosaic`; pixels passing `value <op> threshold` are counted as exposed.
- **indicator prefixes** — `g/c/r` = global/country/regional aggregation; `m/f` = male/female;
  `u18_` = under-18. The canonical output column order is `IndicatorUtils.indicator_cols` in
  `lib/indicator_functions.py`.

---

## What is NOT included 
- `output_*/` — derived deliverables; regenerate them from the notebooks rather than hand-editing.
- One-time ingestion (`ingestion/`, WorldPop processing) and hazard-specific sandboxes. The resulting assets already live in GEE under `projects/unicef-ccri/assets`.
