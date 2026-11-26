# Conflict

Conflict Index generated from the geometric mean of normalized conflict events and fatalities recorded by ACLED between September 2020 and August 2025. The index ranges between 0 and 10.

Source: ACLED (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/conflict/conflict_grid_0p01_degree.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2020-01-01 – 2025-12-31 |
| Hazard | Complex Emergencies |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | Index |
| Resolution | 0.1 degree/11km |
| Coverage | Global |
| Exposure threshold | >=0.01 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 10.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/conflict_admin2_0p1_degree |
| License | other |
| Providers | ACLED (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 33.5 MB | [Conflict (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/conflict/UNICEF_ACLED_CI_Sep2020_Aug2025.tif) |
| `thumbnail` | image/png | 64.2 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/conflict/unicef_acled_ci_sep2020_aug2025/thumbnail.png) |
| `overview` | image/png | 93.8 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/conflict/unicef_acled_ci_sep2020_aug2025/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `complex_emergencies_acled_0p01_grid` (UNICEF code CE): value >= 0 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/conflict/UNICEF_ACLED_CI_Sep2020_Aug2025.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/conflict/UNICEF_ACLED_CI_Sep2020_Aug2025.tif`.

---
STAC: [`hazards/conflict/unicef_acled_ci_sep2020_aug2025/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/conflict/unicef_acled_ci_sep2020_aug2025/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/conflict/unicef_acled_ci_sep2020_aug2025/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
