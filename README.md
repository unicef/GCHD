# Global Children's Hazard Database (GCHD)

**UNICEF Data Science | Climate & Environment Data Unit**

The Global Children's Hazard Database (GCHD) is an open, spatially explicit database cataloguing children's exposure to climate, geophysical, and conflict hazards worldwide. It provides the foundational hazard data layer for UNICEF's [Children's Climate Risk Report (CCRR)](https://www.unicef.org/reports/climate-crisis-child-rights-crisis) and sub-national risk assessments.

---

## What is GCHD?

GCHD compiles globally consistent hazard datasets — each standardised, documented, and linked to a children's population exposure layer — to answer a single question:

> *How many children, and where, are exposed to each hazard?*

The database covers four hazard categories:

| Category | Hazards |
|---|---|
| **Climate** | River flood, coastal flood, tropical storm, agricultural drought, meteorological drought, heatwave, extreme heat, wildfire, sand & dust storm |
| **Climate-related** | Air pollution (PM2.5), malaria |
| **Geophysical** | Earthquake, volcano, landslide *(planned Q3 2026)* |
| **Environmental** | *(planned Q4 2026)* |
| **Conflict** | Armed conflict *(planned Q3 2026)* |

---

## Repository Structure

```
GCHD/
├── hazard_data/             # Per-hazard source documentation and processing scripts
├── multi_hazard_indicators/ # Multi-Hazard Count (MHC) and Multi-Hazard Intensity (MHI)
├── exposure_analysis/       # Population and boundary data for exposure computation
├── web_app/                 # Interactive dashboard (Python Dash + Google Earth Engine)
├── STAC_catalog/            # STAC catalog of the hazard layers (COGs) and its STAC Browser
└── index.html               # Public landing page
```

---

## Hazard Coverage

### Spatial Resolution
All hazard layers are processed at their original resolution (varying from 100 m to ~15 km depending on the source dataset) then overlaid with 100 m gridded children's population data for exposure computation.

### Population Reference
Children's exposure is computed using **WorldPop gridded population estimates for children under 18, 2025 baseline**, at 100 m spatial resolution.

### Exposure Computation
Population-weighted exposure is computed via Google Earth Engine using `reduceRegions` over country and sub-national boundaries. Results are expressed as:
- Absolute count of children exposed
- Share of the national/subnational child population exposed
- Separate estimates for girls and boys

---

## Multi-Hazard Indicators

Two composite indicators summarise multi-hazard exposure:

**Multi-Hazard Count (MHC)** — the number of distinct hazard categories a location is exposed to. Identifies hotspots where children face multiple simultaneous hazards.

**Multi-Hazard Intensity (MHI)** — a continuous 0–10 pixel-level score derived from Principal Component Analysis (PCA) across 13 climate hazard layers. Distinguishes areas with frequent mild events from those with infrequent but extreme events.

See [`multi_hazard_indicators/`](multi_hazard_indicators/) for methodology and scripts.

---

## Web Application

An interactive dashboard built in Python Dash with Google Earth Engine map tiles is available at **[gchd.unicef.org](https://gchd.unicef.org)**.

Source code is in [`web_app/`](web_app/).

---

## Data Catalog (STAC)

All hazard layers are published as Cloud-Optimized GeoTIFFs in a [STAC](https://stacspec.org/) catalog, with metadata, previews and direct download links:

- **Browse:** [unicef.github.io/GCHD/STAC_catalog/browser/](https://unicef.github.io/GCHD/STAC_catalog/browser/)
- **STAC root:** [`catalog.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json)

The COGs can be streamed straight into GIS tools or code without downloading whole files. See [`STAC_catalog/`](STAC_catalog/) for how the catalog is built and for Python examples, including how to read the ~90 m river flood tiles over an area of interest.

---

## Data Sources

| Hazard | Source | Return Period / Metric |
|---|---|---|
| River flood | JRC Global Flood Maps | 100-year return level|
| Coastal flood | JRC Global Flood Maps | 100-year return level|
| Tropical storm | GIRI | 100-year return level |
| Agricultural drought | FAO ASIS | 100-year return level|
| Meteorological drought | TerraClimate (SPI-12, SPEI-12) | emprical probability |
| Heatwave | ERA5 / ECMWF | Frequency, duration, severity  100-year return level|
| Extreme heat | ERA5 / ECMWF | Degree-days 100-year return level|
| Wildfire | NASA FIRMS | 90th percentile |
| Air pollution (PM2.5) | Satellite-derived | 90th percentile, 2012–2022 |
| Sand & dust storm | UNCCD | Occurrence frequency |
| Malaria | MAP (Malaria Atlas Project) | Multi-year average, 2013–2022 |
| Earthquake | GEM Global Seismic Hazard Map v2023.1 | PGA on rock, 475-year return period |
| Volcano | Smithsonian Global Volcanism Program | Population within 100 km of volcanoes active since 1800 |
| Landslide | World Bank / GFDRR | Earthquake-triggered susceptibility; rainfall-triggered frequency, 1980–2018 |
| Conflict | ACLED | Conflict index (events and fatalities), Sep 2020–Aug 2025 |

---

## Citing GCHD

> UNICEF (2025). *Global Children's Hazard Database (GCHD)*. UNICEF Office of Strategy and Evidence, Climate & Environment Data Team. https://github.com/unicef/GCHD

---

## Contact

**Dohyung Kim** — Data Science Specialist, UNICEF  
dokim@unicef.org
