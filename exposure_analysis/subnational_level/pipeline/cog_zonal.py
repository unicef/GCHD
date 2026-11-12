"""Admin-2 exposure from Cloud-Optimized GeoTIFFs, without Earth Engine (approach B).

Reads the WorldPop R2025A population and the GCHD hazard layers published as
COGs on the unit's Azure storage, and computes per admin-2 unit what s01
computes in Earth Engine:

    exposure  sum over population pixels of pop x hazard_mask
    hazard    mean, min, max, median, std, count of the hazard

The hazard is resampled (nearest) onto the population grid, as Earth Engine
does when it reduces at the population's scale, and exactextract weights each
pixel by the share of it inside the unit, as Earth Engine's weighted reducers
do. WorldPop marks unpopulated pixels as nodata, which counts as zero children.

Only hazards whose COG is the same raster as the GEE asset s01 reads are
listed in ``COG_LAYERS``, checked against s01 in Malawi (exposures within
0.08 %). Left out because the COG is a different product or version: the
heat layers (ECMWF 2014-2024 vs 100-year return levels), TerraClimate
SPI/SPEI, agricultural drought (FAO ASI vs ASI return level) and river flood
(JRC 2024 tiles; up to 68 % apart per unit).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np

AZURE = "https://unidatadapmclimatechange.blob.core.windows.net/public"
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.vrt",
                GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE")

# hazard code -> COG under public/gchd_cog/ (same raster as the GEE asset in hazard_info.json)
COG_LAYERS = {
    "coastal_flood_100yr": "flood/coastal_flood_100yr_jrc_2024.tif",
    "tropical_storm_100yr": "tropical_storm/tropical_storm_100yr_giri_2024.tif",
    "fire_intensity": "fire/fire_FRP_nasa_2001-2024.tif",
    "fire_frequency": "fire/fire_frequency_nasa_2001-2023.tif",
    "sand_dust_storm_susc": "sand_dust_storm/sand_dust_storm_unccd_2024.tif",
    "air_pollution_pm25": "air_pollution/air_pollution_pm25_2012-2022.tif",
    "epidemics_malaria_pv": "malaria/vectorborne_malariapv_2012-2022.tif",
    "epidemics_malaria_pf": "malaria/vectorborne_malariapf_2012-2022.tif",
    "earthquake_pga_0p09": "earthquake/earthquake_v2023_1_pga_475_rock_3min.tif",
    "earthquake_pga_0p34": "earthquake/earthquake_v2023_1_pga_475_rock_3min.tif",
    "volcano_100km_buff": "volcano/GVP_Hol_volcanoes_1800.tif",
    "landslides_0p1": "landslide/LS_RF_Mean_1980-2018.tif",
    "landslides_0p01": "landslide/LS_RF_Mean_1980-2018.tif",
    "complex_emergencies_acled_0p01_grid": "conflict/UNICEF_ACLED_CI_Sep2020_Aug2025.tif",
}

# population class -> (Azure folder, WorldPop file name pattern)
POP_LAYERS = {
    "total": ("T", "{iso}_pop_{year}_CN_100m_R2025A_v1.tif"),
    "total_female": ("T_F", "{iso}_T_F_{year}_CN_100m_R2025A_v1.tif"),
    "total_male": ("T_M", "{iso}_T_M_{year}_CN_100m_R2025A_v1.tif"),
    "under_18_total": ("T_U18", "{iso}_T_Under_18_{year}_CN_100m_R2025A_v1.tif"),
    "under_18_female": ("F_U18", "{iso}_F_Under_18_{year}_CN_100m_R2025A_v1.tif"),
    "under_18_male": ("M_U18", "{iso}_M_Under_18_{year}_CN_100m_R2025A_v1.tif"),
}
STATS = ["mean", "min", "max", "median", "stdev", "count"]


def pop_url(iso3: str, cls: str, year: int = 2025) -> str:
    folder, pattern = POP_LAYERS[cls]
    return f"{AZURE}/worldpop_2025/R2025A/2025/100m/{folder}/" + pattern.format(iso=iso3.lower(), year=year)


def fetch_population(iso3: str, cache_dir: Path, log=print) -> dict[str, Path]:
    """Download the country's six population COGs once (whole files: far faster
    than many range reads over a slow link). Falls back to the 2024 file, as the
    Azure upload did for FJI, GRL and RUS."""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    session = requests.Session()  # a dropped connection or DNS hiccup must not lose the country
    session.mount("https://", HTTPAdapter(max_retries=Retry(total=6, backoff_factor=5,
                                                            status_forcelist=(429, 500, 502, 503, 504))))
    out = {}
    for cls in POP_LAYERS:
        for year in (2025, 2024):
            url = pop_url(iso3, cls, year)
            dest = cache_dir / iso3.lower() / url.rsplit("/", 1)[1]
            if dest.exists():
                out[cls] = dest
                break
            r = session.get(url, stream=True, timeout=120)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            t = time.time()
            with open(f"{dest}.part", "wb") as f:
                for c in r.iter_content(1 << 22):
                    f.write(c)
            os.replace(f"{dest}.part", dest)
            log(f"    {dest.name}: {dest.stat().st_size / 1e6:.1f} MB in {time.time() - t:.0f}s")
            out[cls] = dest
            break
        else:
            raise FileNotFoundError(f"no {cls} population COG for {iso3}")
    return out


def hazard_on_grid(path: str, grid):
    """The hazard resampled (nearest) onto ``grid``'s pixels; NaN where it has no data."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT
    with rasterio.open(f"/vsicurl/{AZURE}/gchd_cog/{path}") as src, \
            WarpedVRT(src, crs=grid.crs, transform=grid.transform, width=grid.width, height=grid.height,
                      resampling=Resampling.nearest, src_nodata=src.nodata, nodata=np.nan,
                      dtype="float32") as vrt:
        return vrt.read(1)


def hazard_arrays(raw: np.ndarray, hazard) -> tuple[np.ndarray, np.ndarray]:
    """(raw, mask) with define_hazard's rules: values under th_min dropped when
    apply_nodata is set; the mask is 1 where the threshold test passes."""
    raw = raw.astype("float32", copy=True)
    if hazard.apply_nodata:
        raw[raw < hazard.th_min] = np.nan
    op = {"gt": np.greater, "gte": np.greater_equal, "lt": np.less, "lte": np.less_equal}.get(
        hazard.threshold_operation, np.greater)
    with np.errstate(invalid="ignore"):
        mask = np.where(np.isnan(raw), np.nan, op(raw, float(hazard.threshold)).astype("float32"))
    return raw, mask.astype("float32")


def country_stats(units, hazards, pop_files: dict[str, Path], log=print):
    """Per (unit, hazard) exposures and hazard statistics, shaped like
    ``pipeline.chunked.combine``'s output."""
    import pandas as pd
    import rasterio
    from exactextract import exact_extract
    from exactextract.raster import NumPyRasterSource, RasterioRasterSource

    rows = []
    with rasterio.Env(**GDAL_ENV):
        pops = {c: rasterio.open(p) for c, p in pop_files.items()}
        grid = pops["total"]
        b = grid.bounds
        weights = [RasterioRasterSource(ds, name=c) for c, ds in pops.items()]
        cache: dict[str, np.ndarray] = {}
        for h, hazard in enumerate(hazards):
            path = COG_LAYERS.get(hazard.code)
            if path is None:
                log(f"    {hazard.code}: no matching COG, skipped")
                continue
            t = time.time()
            if path not in cache:
                cache = {path: hazard_on_grid(path, grid)}  # keep one layer in memory (twins share it)
            raw, mask = hazard_arrays(cache[path], hazard)
            src = dict(xmin=b.left, ymin=b.bottom, xmax=b.right, ymax=b.top, nodata=np.nan,
                       srs_wkt=grid.crs.to_wkt())
            ex = exact_extract(NumPyRasterSource(mask, name="mask", **src), units,
                               ["weighted_sum(default_weight=0)"], weights=weights,
                               include_cols=["adm2_ucode"], output="pandas")
            st = exact_extract(NumPyRasterSource(raw, name="h", **src), units, STATS,
                               include_cols=["adm2_ucode"], output="pandas")
            df = ex.merge(st, on="adm2_ucode")
            df = df.rename(columns={f"mask_{c}_weighted_sum": f"exp_{c}" for c in POP_LAYERS})
            df = df.rename(columns={s: f"hazs_{'std' if s == 'stdev' else s}" for s in STATS})
            df["hazard_index"] = h
            df["n_chunks"] = 1
            rows.append(df)
            log(f"    {hazard.code}: {time.time() - t:.1f}s")
        for ds in pops.values():
            ds.close()
    return pd.concat(rows, ignore_index=True)
