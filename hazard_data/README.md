# Hazard Data

This folder contains per-hazard documentation and processing scripts for all hazard layers in the Global Child Hazard Database.

Each subfolder corresponds to one hazard and contains:
- A `README.md` describing the data source, processing methodology, output format, and update cadence
- Processing script(s) (Jupyter notebooks or GEE JavaScript) used to prepare the hazard layer

Raw source data is not stored in this repository (files are too large). Final processed layers are hosted as Google Earth Engine assets under `projects/unicef-ccri/assets/hazards/`.

---

## Hazard Inventory

| Folder | Hazard | Source | Spatial Resolution | Processing Script |
|---|---|---|---|---|
| `flood/river_flood/` | River flood | JRC | 90 m | `flood_download.ipynb` |
| `flood/coastal_flood/` | Coastal flood | JRC | 90 m | `flood_download.ipynb` |
| `drought/agricultural_drought/` | Agricultural drought | FAO | 1 km | `ASI_RP.ipynb` |
| `drought/meteorological_drought/` | Meteorological drought (SPI-12, SPEI-12) | TerraClimate | 5 km | `compute_SPI_SPEI.ipynb` |
| `heatwave/` | Heatwave (frequency, duration, severity, extreme heat) | ECMWF | 10 km | `heatwave_RP.ipynb` |
| `tropical_storm/` | Tropical storm | GIRI | 10 km | Direct download |
| `fire/` | Wildfire (frequency, radiative power) | NASA FIRMS | 250 m | `Fire_90th_percentile.ipynb` |
| `air_pollution/` | PM2.5 air pollution | ACAG | 1 km | `PM25_90th_percentile.ipynb` |
| `sand_dust_storm/` | Sand and dust storm | UNCCD | 1 km | Direct download |
| `malaria/` | Malaria (Pf, Pv) | MAP | 5 km | `malaria_average.ipynb` |
| `earthquake/` | Earthquake | *(planned Q3 2026)* | — | — |
| `volcano/` | Volcano | *(planned Q3 2026)* | — | — |
| `landslide/` | Landslide | *(planned Q3 2026)* | — | — |
| `conflict/` | Armed conflict | *(planned Q3 2026)* | — | — |

---

## Adding a New Hazard

1. Create a subfolder with a descriptive name (lowercase, underscores)
2. Add a `README.md` following the template used in existing hazard folders
3. Include or link the processing script used to prepare the GEE asset
4. Update this table
