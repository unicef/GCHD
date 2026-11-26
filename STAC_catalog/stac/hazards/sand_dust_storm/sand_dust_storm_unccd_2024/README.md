# SDS Susceptiblity

Sand and dust storms (SDS) are caused by intense winds over areas of arid soil that pick up large amounts of ground material into the atmosphere.

Source: UNCCD (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/SDS/sand_dust_storm_unccd_2024.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2024-01-01 – 2024-12-31 |
| Hazard | Sand and Dust Storm |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | Index |
| Resolution | 1km |
| Coverage | Global |
| Exposure threshold | All |
| Classes | 0-0.2-0.4-0.6-0.8-1 |
| Value range | [0.0, 1.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/sand_dust_storm_annual |
| License | other |
| Providers | UNCCD (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 209.3 MB | [SDS Susceptiblity (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif) |
| `thumbnail` | image/png | 88.6 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/sand_dust_storm/sand_dust_storm_unccd_2024/thumbnail.png) |
| `overview` | image/png | 213.7 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/sand_dust_storm/sand_dust_storm_unccd_2024/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `sand_dust_storm_susc` (UNICEF code SD): value > 0 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/sand_dust_storm/sand_dust_storm_unccd_2024.tif`.

---
STAC: [`hazards/sand_dust_storm/sand_dust_storm_unccd_2024/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/sand_dust_storm/sand_dust_storm_unccd_2024/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/sand_dust_storm/sand_dust_storm_unccd_2024/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
