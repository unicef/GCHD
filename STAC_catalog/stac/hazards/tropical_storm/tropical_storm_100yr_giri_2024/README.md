# Wind speed

A tropical storm is a type of storm system characterized by a low-pressure center, a closed low-level atmospheric circulation, strong winds, and a spiral arrangement of thunderstorms that produce heavy rain.

Source: GIRI (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/storm/tropical_storm_100yr_giri_2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2024-01-01 – 2024-12-31 |
| Hazard | Tropical Storm |
| Phase | Preparedness/Planning |
| Data type | Probabilistic - 100 year return period |
| Units | m/s |
| Resolution | 10km |
| Coverage | Global |
| Exposure threshold | >17.5 m/s |
| Classes | 63 - 119 - 154 - 178 - 209+ |
| Value range | [0.0, 60.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/storm_giri_rp100 |
| License | other |
| Providers | GIRI (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 6.6 MB | [Wind speed (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif) |
| `thumbnail` | image/png | 114.1 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/tropical_storm/tropical_storm_100yr_giri_2024/thumbnail.png) |
| `overview` | image/png | 295.1 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/tropical_storm/tropical_storm_100yr_giri_2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `tropical_storm_100yr` (UNICEF code TC): value > 17.5 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/tropical_storm/tropical_storm_100yr_giri_2024.tif`.

---
STAC: [`hazards/tropical_storm/tropical_storm_100yr_giri_2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/tropical_storm/tropical_storm_100yr_giri_2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/tropical_storm/tropical_storm_100yr_giri_2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
