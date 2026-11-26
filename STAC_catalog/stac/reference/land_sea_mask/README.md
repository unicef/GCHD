# Land/sea mask (ERA5 0.1 deg grid)

1 = land (painted from ADM0 boundaries), 0 = sea, on the ERA5 0.1 deg reference grid shared with MHI_climate. Built by multi_hazard_indicators/mhi/MHI_input_gee.js.

Source: UNICEF (https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2026-11-13 – 2026-11-13 |
| Data type | Mask |
| Units | 1 = land, 0 = sea |
| Resolution | 0.1 deg (~10km) |
| Coverage | Global |
| Value range | [0, 1] |
| License | other |
| Providers | UNICEF (producer, processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 160.2 KB | [Land/sea mask (ERA5 0.1 deg grid) (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif) |
| `thumbnail` | image/png | 48.3 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/reference/land_sea_mask/thumbnail.png) |
| `overview` | image/png | 27.1 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/reference/land_sea_mask/overview.png) |

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/reference/landSeaMask.tif`.

---
STAC: [`reference/land_sea_mask/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/reference/land_sea_mask/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/reference/land_sea_mask/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
