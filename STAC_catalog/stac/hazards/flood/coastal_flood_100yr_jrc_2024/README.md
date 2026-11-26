# Coastal flood hazard

Coastal flooding is most frequently the result of storm surges and high winds coinciding with high tides

Source: JRC (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/flood/coastal_flood_100yr_jrc_2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2024-01-01 – 2024-12-31 |
| Hazard | Floods |
| Phase | Preparedness/Planning |
| Data type | Probabilistic - 100 year return period |
| Units | Binary |
| Resolution | 90m |
| Coverage | Global |
| Value range | [0.0, 1.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/coastal_flood_r100 |
| License | other |
| Providers | JRC (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 126.5 MB | [Coastal flood hazard (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif) |
| `thumbnail` | image/png | 44.4 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/coastal_flood_100yr_jrc_2024/thumbnail.png) |
| `overview` | image/png | 14.6 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/coastal_flood_100yr_jrc_2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `coastal_flood_100yr` (UNICEF code FL_COA): value > 0 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/flood/coastal_flood_100yr_jrc_2024.tif`.

---
STAC: [`hazards/flood/coastal_flood_100yr_jrc_2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/flood/coastal_flood_100yr_jrc_2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/flood/coastal_flood_100yr_jrc_2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
