# Landslide (earthquake induced)

The Global Landslide Hazard Map: Earthquake-Triggered Landslide Hazard presents an estimate of earthquake-triggered landslide hazard at a global scale which builds upon work by Nadim et al. (2006; 2013) and uses the NASA Global Landslide Susceptibility Map as a base.

Source: World Bank/GFDRR (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/landslide/landslides_trig_earthquakes.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2026-10-22 – 2026-10-22 |
| Hazard | Geophysical |
| Phase | Preparedness/Planning |
| Data type | Modelled |
| Units | Susceptibility (1-5) |
| Resolution | ~100m |
| Coverage | All land areas between 60°S and 72°N |
| License | other |
| Providers | World Bank/GFDRR (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 1.5 GB | [Landslide (earthquake induced) (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/landslides_trig_earthquakes.tif) |
| `thumbnail` | image/png | 54.3 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/landslides_trig_earthquakes/thumbnail.png) |
| `overview` | image/png | 51.9 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/landslides_trig_earthquakes/overview.png) |

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/landslides_trig_earthquakes.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/landslide/landslides_trig_earthquakes.tif`.

---
STAC: [`hazards/landslide/landslides_trig_earthquakes/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/landslide/landslides_trig_earthquakes/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/landslide/landslides_trig_earthquakes/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
