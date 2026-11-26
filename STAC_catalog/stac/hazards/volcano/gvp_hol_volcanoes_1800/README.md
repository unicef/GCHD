# Volcanoes

Number of people and children within 100km2 radius of an active volcano. A volcano is considered active if it had vlocanic activity after 1800. The 100km radius was selected as the maximum distance where children could be affected by emissions from volcanoes.

Source: Smithsonian Institution - Global Volcanism Program (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/volcano/hol_volcanoes_buffer_100km.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2026-10-22 – 2026-10-22 |
| Hazard | Geophysical |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | people per 100 km² |
| Resolution | 0.1 degree/11km |
| Coverage | Global |
| Exposure threshold | <=100km |
| Classes | 0, 30, 50, 80, 100, >100 |
| Value range | [0.0, 100000.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/hol_volcanoes_1800_100kmbuff |
| License | other |
| Providers | Smithsonian Institution - Global Volcanism Program (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 6.2 MB | [Volcanoes (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif) |
| `thumbnail` | image/png | 60.7 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/volcano/gvp_hol_volcanoes_1800/thumbnail.png) |
| `overview` | image/png | 90.2 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/volcano/gvp_hol_volcanoes_1800/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `volcano_100km_buff` (UNICEF code VO): value > 0 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/volcano/GVP_Hol_volcanoes_1800.tif`.

---
STAC: [`hazards/volcano/gvp_hol_volcanoes_1800/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/volcano/gvp_hol_volcanoes_1800/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/volcano/gvp_hol_volcanoes_1800/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
