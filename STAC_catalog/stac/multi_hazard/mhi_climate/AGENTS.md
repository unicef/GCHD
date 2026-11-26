# AGENTS.md: Multi-Hazard Intensity (MHI) - climate (`mhi_climate`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

Pixel-based multi-hazard intensity score (0-10) combining the climate hazard layers (PCA, min-max scaled), on the ERA5 0.1 deg grid. NoData (NaN) over sea. Global land percentiles for the mhi_pNN exposure metrics are in GCHD:mhi_percentiles. Built by multi_hazard_indicators/mhi/.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif
- Period: 2026-05-27 – 2026-05-27
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif`.

## Schema & field notes

- Band: data type `float32`, nodata `nan`; observed range 0.06221 to 8.715, mean 3.154, valid pixels 34.8%
- Hazard (`GCHD:hazard`): Multi-hazard
- Phase (`GCHD:hazard_phase`): Preparedness/Planning
- Data type (`GCHD:data_type`): Index
- Units (`GCHD:units`): index (0-10)
- Resolution (`GCHD:nominal_resolution`): 0.1 deg (~10km)
- Coverage (`GCHD:coverage`): Global (land)
- Value range (`GCHD:value_range`): [0.0, 10.0]
- CRS: EPSG:4326
- `GCHD:mhi_percentiles` (global land percentiles of MHI): {'p75': 5.202352, 'p80': 5.56949, 'p85': 5.935779, 'p90': 6.362279, 'p95': 6.890319, 'n_land_pixels': 2123439, 'method': 'unweighted pixel percentile over landSeaMask==1 on the native ERA5 0.1deg grid'}

## Data quality & usage notes

- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
- [Land/sea mask (ERA5 0.1 deg grid)](https://unicef.github.io/GCHD/STAC_catalog/stac/reference/land_sea_mask/collection.json) (`land_sea_mask`): the land/sea mask of the same ERA5 0.1° grid
