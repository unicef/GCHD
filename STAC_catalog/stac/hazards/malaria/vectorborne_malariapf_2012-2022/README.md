# Malaria Plasmodium Falciparum

Malaria is a life-threatening disease caused by parasites transmitted to humans through the bites of infected female Anopheles mosquitoes. P. falciparum is the deadliest malaria parasite and the most prevalent on the African continent.

Source: MAP (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/malaria/vectorborne_malariapf_2012-2022.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2013-01-01 – 2022-12-31 |
| Hazard | Vector Borne Diseases |
| Phase | Preparedness/Planning |
| Data type | Modelled |
| Units | # per 1000 people |
| Resolution | 5km |
| Coverage | Global |
| Exposure threshold | > 0,001 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 1.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/Pf_average_2013_2022 |
| License | other |
| Providers | MAP (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 8.8 MB | [Malaria Plasmodium Falciparum (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif) |
| `thumbnail` | image/png | 60.2 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/malaria/vectorborne_malariapf_2012-2022/thumbnail.png) |
| `overview` | image/png | 130.5 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/malaria/vectorborne_malariapf_2012-2022/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `epidemics_malaria_pf` (UNICEF code ML_PF): value > 0.001 (pixels with data: value > 0)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/malaria/vectorborne_malariapf_2012-2022.tif`.

---
STAC: [`hazards/malaria/vectorborne_malariapf_2012-2022/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/malaria/vectorborne_malariapf_2012-2022/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/malaria/vectorborne_malariapf_2012-2022/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
