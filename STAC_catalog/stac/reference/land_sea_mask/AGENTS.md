# AGENTS.md: Land/sea mask (ERA5 0.1 deg grid) (`land_sea_mask`)

Guidance for AI agents and LLMs working with this collection. Generated from the collection's metadata by STAC_catalog/gchd_stac/docs.py; see README.md for the human-readable summary.

## Overview

1 = land (painted from ADM0 boundaries), 0 = sea, on the ERA5 0.1 deg reference grid shared with MHI_climate. Built by multi_hazard_indicators/mhi/MHI_input_gee.js.

- Layout: one global Cloud-Optimized GeoTIFF (collection-level `data` asset).
- Data URL: https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif
- Period: 2026-11-13 – 2026-11-13
- License: other (https://github.com/unicef/GCHD)

## Accessing the data

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif`.

## Schema & field notes

- Band: data type `uint8`, nodata `None`; observed range 0 to 1, mean 0.3274, valid pixels 0.0%
- Data type (`GCHD:data_type`): Mask
- Units (`GCHD:units`): 1 = land, 0 = sea
- Resolution (`GCHD:nominal_resolution`): 0.1 deg (~10km)
- Coverage (`GCHD:coverage`): Global
- Value range (`GCHD:value_range`): [0, 1]
- CRS: EPSG:4326

## Data quality & usage notes

- Read with masked=True (or check the band's nodata) before computing statistics.

## Related collections

- [Total U18 population 2025 (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_u18_2025_total/collection.json) (`worldpop_u18_2025_total`): children under 18 per ~100 m cell, the exposure denominator
- [Total population 2025, all ages (WorldPop R2025A)](https://unicef.github.io/GCHD/STAC_catalog/stac/population/worldpop_2025_total/collection.json) (`worldpop_2025_total`): people of all ages per ~100 m cell
- [Multi-Hazard Intensity (MHI) - climate](https://unicef.github.io/GCHD/STAC_catalog/stac/multi_hazard/mhi_climate/collection.json) (`mhi_climate`): the MHI index on the same grid
