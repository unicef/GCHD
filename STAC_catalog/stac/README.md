# UNICEF Global Child Hazard Database

The **Global Child Hazard Database (GCHD)** brings together global, gridded layers of the climate, environmental, geophysical and conflict hazards that children are exposed to: floods, tropical storms, droughts, heatwaves, fire, sand and dust storms, air pollution, malaria, landslides, earthquakes, volcanoes and conflict. It adds the Multi-Hazard Intensity (MHI) index, WorldPop 2025 population grids (under 18 and all ages, female, male and total), harmonised administrative boundaries (ADM0/1/2), and hazard-exposure statistics per administrative unit.

Gridded layers are Cloud-Optimized GeoTIFFs that stream directly into GIS tools or analysis code; boundaries and exposure statistics are (Geo)Parquet tables that DuckDB, GeoPandas or Arrow read over HTTP. Processing scripts and documentation: https://github.com/unicef/GCHD

## Contents

- [Hazards](./hazards/README.md): `hazards`
- [Multi-hazard indicators](./multi_hazard/README.md): `multi_hazard`
- [Population](./population/README.md): `population`
- [Administrative boundaries](./boundaries/README.md): `boundaries`
- [Hazard exposure statistics](./exposure/README.md): `exposure`
- [Reference grids](./reference/README.md): `reference`

---
STAC: [`catalog.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
