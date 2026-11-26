# Meteorological Drought (Standardized Precipitation Evapotranspiration Index)

SPEI adds the effect of evapotranspiration and is better suited to assess droughts under climate change scenarios where temperature changes are important. Probability values are computed from the full 1958–2025 record (804 monthly time steps) dividing the numbers of months lower than TH (1.5) with total months

Source: TerraClimate (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/drought/SPEI12_return_level_100yr.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 1958-01-01 – 2025-12-31 |
| Hazard | Droughts |
| Phase | Preparedness/Planning |
| Data type | Probabilistic - empirical |
| Units | Index |
| Resolution | 5km |
| Coverage | Global |
| Exposure threshold | >0.06 (global mean) |
| Classes | Use quantile |
| Value range | [-10.0, 10.0] |
| GEE asset | projects/unicef-ccri/assets/droughts/spi12_TerraClimate_1958-2025 |
| License | other |
| Providers | TerraClimate (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 1.4 MB | [Meteorological Drought (Standardized Precipitation Evapotranspiration Index) (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif) |
| `thumbnail` | image/png | 130.0 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/drought_spei_terraclimate_1958-2025/thumbnail.png) |
| `overview` | image/png | 509.2 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/drought_spei_terraclimate_1958-2025/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `drought_spei_tc` (UNICEF code DR_SPEI): value > 0.0650162152126539 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/drought/drought_spei_terraclimate_1958-2025.tif`.

---
STAC: [`hazards/drought/drought_spei_terraclimate_1958-2025/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/drought/drought_spei_terraclimate_1958-2025/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/drought/drought_spei_terraclimate_1958-2025/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
