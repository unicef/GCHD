# PM 2.5

Air pollution refers to the presence of substances in the atmosphere that are harmful to human health and the environment.  Fine particle air pollution, or PM2 .5, refers to airborne particles measuring less than 2 .5 micrometers in diameter that could be emitted from vehicles, residential fuel use, coal-burning power plants, agricultural and industrial activities, waste burning, wildfires, and many other human and natural sources.

Source: ACAG (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/air_pollution/air_pollution_pm25_1998-2023.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2012-01-01 – 2022-12-31 |
| Hazard | Air pollution |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | μg/m3 |
| Resolution | 1km |
| Coverage | Global |
| Exposure threshold | >5 AQG |
| Classes | 5 - 10 - 15 - 25 - 35+ |
| Value range | [0.0, 300.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/pm25_p90_1998_2023 |
| License | other |
| Providers | ACAG (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 351.0 MB | [PM 2.5 (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif) |
| `thumbnail` | image/png | 108.6 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/air_pollution/air_pollution_pm25_2012-2022/thumbnail.png) |
| `overview` | image/png | 319.6 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/air_pollution/air_pollution_pm25_2012-2022/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `air_pollution_pm25` (UNICEF code AP): value > 5 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/air_pollution/air_pollution_pm25_2012-2022.tif`.

---
STAC: [`hazards/air_pollution/air_pollution_pm25_2012-2022/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/air_pollution/air_pollution_pm25_2012-2022/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/air_pollution/air_pollution_pm25_2012-2022/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
