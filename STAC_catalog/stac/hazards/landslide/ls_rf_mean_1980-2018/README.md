# Landslide (rainfall induced)

Landslide exposure is estimated using the GFDRR rainfall-triggered Global Landslide Hazard Map (V2), based on the annual frequency of significant rainfall-induced landslides per km². Children and population exposed are identified using 0.1 and 0.01 landslides/km² thresholds (Medium–High and Moderate hazard). Indicators include absolute and relative exposed population and normalized scores ranging from 0–10.

Source: World Bank/GFDRR (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/landslide/LS_RF_Mean_1980-2018_COG.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 1980-01-01 – 2018-12-31 |
| Hazard | Geophysical |
| Phase | Preparedness/Planning |
| Data type | Modelled |
| Units | landslides per km² per year |
| Resolution | 1 km |
| Coverage | All land areas between 60°S and 72°N |
| Exposure threshold | ≥ 0.01 or ≥ 0.1 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 2.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/LS_RF_Mean_1980-2018_COG |
| License | other |
| Providers | World Bank/GFDRR (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 145.2 MB | [Landslide (rainfall induced) (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif) |
| `thumbnail` | image/png | 94.6 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/ls_rf_mean_1980-2018/thumbnail.png) |
| `overview` | image/png | 238.0 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/ls_rf_mean_1980-2018/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `landslides_0p1` (UNICEF code LS_RIN): value > 0.1 (pixels with data: value > -1000)
- `landslides_0p01` (UNICEF code LS_RIN): value > 0.01 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/LS_RF_Mean_1980-2018.tif`.

---
STAC: [`hazards/landslide/ls_rf_mean_1980-2018/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/ls_rf_mean_1980-2018/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/landslide/ls_rf_mean_1980-2018/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
