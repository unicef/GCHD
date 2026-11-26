# Multi-Hazard Intensity (MHI) - climate

Pixel-based multi-hazard intensity score (0-10) combining the climate hazard layers (PCA, min-max scaled), on the ERA5 0.1 deg grid. NoData (NaN) over sea. Global land percentiles for the mhi_pNN exposure metrics are in GCHD:mhi_percentiles. Built by multi_hazard_indicators/mhi/.

Source: UNICEF (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/multi_hazard/MHI_climate.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2026-05-27 – 2026-05-27 |
| Hazard | Multi-hazard |
| Phase | Preparedness/Planning |
| Data type | Index |
| Units | index (0-10) |
| Resolution | 0.1 deg (~10km) |
| Coverage | Global (land) |
| Value range | [0.0, 10.0] |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 8.3 MB | [Multi-Hazard Intensity (MHI) - climate (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif) |
| `thumbnail` | image/png | 148.4 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/multi_hazard/mhi_climate/thumbnail.png) |
| `overview` | image/png | 563.2 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/multi_hazard/mhi_climate/overview.png) |

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/multi_hazard/MHI_climate.tif`.

---
STAC: [`multi_hazard/mhi_climate/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/multi_hazard/mhi_climate/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/multi_hazard/mhi_climate/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
