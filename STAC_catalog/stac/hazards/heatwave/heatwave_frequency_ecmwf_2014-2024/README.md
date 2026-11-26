# Heatwave frequency

A heatwave can be defined as a period where local excess heat accumulates over a sequence of unusually hot days and nights. Heatwave frequency refers to the number of heatwaves per year.

Source: ECMWF (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/heat_extreme/heatwave_frequency_ecmwf_2014-2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2014-01-01 – 2024-12-31 |
| Hazard | Heatwaves |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | Number of heatwaves per year |
| Resolution | 10km |
| Coverage | Global |
| Exposure threshold | 16.02 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 50.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/heatwave_frequency_return_level_100yr |
| License | other |
| Providers | ECMWF (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 6.1 MB | [Heatwave frequency (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/heatwave_frequency_ecmwf_2014-2024.tif) |
| `thumbnail` | image/png | 114.7 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/heatwave_frequency_ecmwf_2014-2024/thumbnail.png) |
| `overview` | image/png | 338.7 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/heatwave_frequency_ecmwf_2014-2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `heatwave_frequency` (UNICEF code HW_FRQ): value > 16.02581287445288 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/heatwave_frequency_ecmwf_2014-2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/heatwave/heatwave_frequency_ecmwf_2014-2024.tif`.

---
STAC: [`hazards/heatwave/heatwave_frequency_ecmwf_2014-2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/heatwave/heatwave_frequency_ecmwf_2014-2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/heatwave/heatwave_frequency_ecmwf_2014-2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
