# Extreme hot days

Extremely high temperatures (extremely hot days) are estimated when a day exceeds 35 degrees Celsius.

Source: ECMWF (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/heat_extreme/extreme_heat_ecmwf_2014-2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2014-01-01 – 2024-12-31 |
| Hazard | Heatwaves |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | Number of days with extreme temperature (>35°C) |
| Resolution | 10km |
| Coverage | Global |
| Exposure threshold | 35 days |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 365.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/high_temp_degree_days_return_level_100yr |
| License | other |
| Providers | ECMWF (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 3.9 MB | [Extreme hot days (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif) |
| `thumbnail` | image/png | 89.9 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/extreme_heat_ecmwf_2014-2024/thumbnail.png) |
| `overview` | image/png | 199.2 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/extreme_heat_ecmwf_2014-2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `extreme_heat_days` (UNICEF code ET): value > 35 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/extreme_heat_ecmwf_2014-2024.tif`.

---
STAC: [`hazards/heatwave/extreme_heat_ecmwf_2014-2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/extreme_heat_ecmwf_2014-2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/heatwave/extreme_heat_ecmwf_2014-2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
