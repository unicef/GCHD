# Fire Intensity

Wildfires are uncontrolled burns of vegetation, including forests, shrublands, grasslands, savannas, and croplands. Fire frequency is obtained from NASA’s Fire Information for Resource Management System (FIRMS) is used as a proxy for fire hazard.

Source: NASA FIRMS (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/fire/fire_FRP_nasa_2001-2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2001-01-01 – 2024-12-31 |
| Hazard | Fire |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | MW |
| Resolution | 250 m |
| Coverage | Global |
| Exposure threshold | 37.89 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 15000.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/FIRMS_FRP_90th_percentile |
| License | other |
| Providers | NASA FIRMS (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 14.8 MB | [Fire Intensity (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_FRP_nasa_2001-2024.tif) |
| `thumbnail` | image/png | 137.0 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frp_nasa_2001-2024/thumbnail.png) |
| `overview` | image/png | 480.4 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frp_nasa_2001-2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `fire_intensity` (UNICEF code FR_INT): value > 37.89412565331788 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_FRP_nasa_2001-2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_FRP_nasa_2001-2024.tif`.

---
STAC: [`hazards/fire/fire_frp_nasa_2001-2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frp_nasa_2001-2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/fire/fire_frp_nasa_2001-2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
