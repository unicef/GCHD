# Earthquake

Earthquake exposure is derived from the GEM Global Seismic Hazard Map (v2023.1, June 2023), which maps peak ground acceleration (PGA) on reference rock for a 10% probability of exceedance in 50 years (475-year return period; Vs30 = 760–800 m/s). Exposed children and population are identified using two thresholds linked to Mercalli intensities: Strong shaking (VI; PGA ≥ 0.09 g) and Severe shaking (VIII; PGA ≥ 0.34 g). Outputs include absolute and relative exposure and normalized scores (0–10).

Source: GEM (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2023-01-01 – 2023-12-31 |
| Hazard | Geophysical |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | PGA (g) |
| Resolution | 3 arc-minutes |
| Coverage | Global |
| Exposure threshold | >0.09 g or >0.34g |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 2.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/earthquake_v2023_1_pga_475_rock_3min |
| License | other |
| Providers | GEM (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 17.3 MB | [Earthquake (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif) |
| `thumbnail` | image/png | 97.7 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/earthquake/earthquake_v2023_1_pga_475_rock_3min/thumbnail.png) |
| `overview` | image/png | 250.7 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/earthquake/earthquake_v2023_1_pga_475_rock_3min/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `earthquake_pga_0p09` (UNICEF code EQ): value > 0.09 (pixels with data: value > -1000)
- `earthquake_pga_0p34` (UNICEF code EQ): value > 0.34 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/earthquake/earthquake_v2023_1_pga_475_rock_3min.tif`.

---
STAC: [`hazards/earthquake/earthquake_v2023_1_pga_475_rock_3min/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/earthquake/earthquake_v2023_1_pga_475_rock_3min/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/earthquake/earthquake_v2023_1_pga_475_rock_3min/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
