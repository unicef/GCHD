# Agricultural Drought (Agricultural Stress Index)

Agricultural drought occurs when there is insufficient soil moisture to meet the needs of a particular crop at a particular time

Source: FAO (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/drought/agricultural_drought_fao_1984-2023.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 1984-01-01 – 2023-12-31 |
| Hazard | Droughts |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | % |
| Resolution | 1km |
| Coverage | Global |
| Exposure threshold | >30% cropland affected |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 100.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/ASI_return_level_100yr |
| License | other |
| Providers | FAO (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 61.1 MB | [Agricultural Drought (Agricultural Stress Index) (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif) |
| `thumbnail` | image/png | 100.6 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/agricultural_drought_fao_1984-2023/thumbnail.png) |
| `overview` | image/png | 217.1 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/agricultural_drought_fao_1984-2023/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `drought_asi` (UNICEF code DR_AGR): value > 30 (pixels with data: value <= 100)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/agricultural_drought_fao_1984-2023.tif`.

---
STAC: [`hazards/drought/agricultural_drought_fao_1984-2023/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/agricultural_drought_fao_1984-2023/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/drought/agricultural_drought_fao_1984-2023/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
