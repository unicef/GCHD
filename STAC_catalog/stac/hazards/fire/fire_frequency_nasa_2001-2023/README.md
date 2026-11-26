# Fire Frequency

Wildfires are uncontrolled burns of vegetation, including forests, shrublands, grasslands, savannas, and croplands. Fire Radiative Power (FRP) is a measure of the energy released by a fire in the form of radiation.

Source: NASA FIRMS (https://unidatadapmclimatechange.blob.core.windows.net/public/final_hazard_layers/fire/fire_frequency_nasa_2001-2023.tif); processed and hosted by UNICEF for the Global Child Hazard Database.

| | |
|---|---|
| Period | 2001-01-01 – 2023-12-31 |
| Hazard | Fire |
| Phase | Preparedness/Planning |
| Data type | Observed |
| Units | km⁻² · yr⁻¹ |
| Resolution | 250 m |
| Coverage | Global |
| Exposure threshold | 4.91 |
| Classes | Use natural breaks/quantile |
| Value range | [0.0, 1500.0] |
| GEE asset | projects/unicef-ccri/assets/hazards/FIRMS_count_90th_percentile |
| License | other |
| Providers | NASA FIRMS (producer, licensor), UNICEF (processor, host) |

## Files

| Asset | Type | Size | Link |
|---|---|---|---|
| `data` | image/tiff; application=geotiff; profile=cloud-optimized | 10.6 MB | [Fire Frequency (Cloud-Optimized GeoTIFF)](https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif) |
| `thumbnail` | image/png | 128.4 KB | [Thumbnail](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frequency_nasa_2001-2023/thumbnail.png) |
| `overview` | image/png | 408.9 KB | [Map overlay (data only)](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frequency_nasa_2001-2023/overview.png) |

## Exposure rule

A pixel counts as exposed when:

- `fire_frequency` (UNICEF code FR_FRQ): value > 4.9134115164042935 (pixels with data: value > -1000)

## Access

```python
import rasterio
url = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif"
with rasterio.open(url) as src:                      # streams only the bytes it needs (COG)
    print(src.profile)
    value = next(src.sample([(lon, lat)]))           # value at a point (EPSG:4326)
    window = src.read(1, window=src.window(*bbox))   # bbox = (west, south, east, north)
```
QGIS: Layer > Add Raster Layer > Protocol: HTTP(S), paste the URL. GDAL: `gdalinfo /vsicurl/https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/fire/fire_frequency_nasa_2001-2023.tif`.

---
STAC: [`hazards/fire/fire_frequency_nasa_2001-2023/collection.json`](https://unicef.github.io/GCHD/STAC_catalog/stac/hazards/fire/fire_frequency_nasa_2001-2023/collection.json) · Browse: [STAC Browser](https://unicef.github.io/GCHD/STAC_catalog/browser/#/hazards/fire/fire_frequency_nasa_2001-2023/collection.json) · Agent guide: [AGENTS.md](./AGENTS.md) · Processing: [https://github.com/unicef/GCHD](https://github.com/unicef/GCHD)
