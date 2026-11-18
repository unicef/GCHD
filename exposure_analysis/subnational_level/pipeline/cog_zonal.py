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
                GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE",
                GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="10", GDAL_HTTP_TIMEOUT="300",
                # a failed lookup (e.g. a DNS outage) must not be remembered as "file missing"
                CPL_VSIL_CURL_NON_CACHED=f"/vsicurl/{AZURE}/gchd_cog/")

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


def _session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()  # a dropped connection or DNS hiccup must not lose the country
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=6, backoff_factor=5,
                                                      status_forcelist=(429, 500, 502, 503, 504))))
    return s


def population_urls(iso3: str) -> dict[str, tuple[str, int]]:
    """(url, bytes) of the country's six population COGs; falls back to the
    2024 file, as the Azure upload did for FJI, GRL and RUS."""
    s, out = _session(), {}
    for cls in POP_LAYERS:
        for year in (2025, 2024):
            url = pop_url(iso3, cls, year)
            r = s.head(url, timeout=60)
            if r.status_code == 200:
                out[cls] = (url, int(r.headers.get("Content-Length", 0)))
                break
        else:
            raise FileNotFoundError(f"no {cls} population COG for {iso3}")
    return out


class DiskBudget:
    """Bytes the population cache may hold at once, shared by every worker: a
    country reserves its files' size before downloading and frees it once its
    partials are written, so the cache never exceeds the cap."""

    def __init__(self, max_gb: float):
        import threading
        self.cap, self.used = int(max_gb * 1e9), 0
        self.cond = threading.Condition()

    def reserve(self, nbytes: int, log=print) -> None:
        if nbytes > self.cap:
            raise MemoryError(f"needs {nbytes / 1e9:.1f} GB, above the {self.cap / 1e9:.0f} GB disk budget")
        with self.cond:
            if self.used + nbytes > self.cap:
                log(f"    waiting for disk budget ({self.used / 1e9:.1f} + {nbytes / 1e9:.1f} GB "
                    f"> {self.cap / 1e9:.0f} GB)")
            self.cond.wait_for(lambda: self.used + nbytes <= self.cap)
            self.used += nbytes

    def release(self, nbytes: int) -> None:
        with self.cond:
            self.used -= nbytes
            self.cond.notify_all()


def _download(url: str, size: int, dest: Path, parts: int) -> None:
    """Download ``url`` as ``parts`` byte ranges in parallel. Far from the
    storage region one connection is latency-bound (~0.3 MB/s measured), so
    parallel ranges, as AzCopy uses, give several times the throughput."""
    from concurrent.futures import ThreadPoolExecutor
    tmp = Path(f"{dest}.part")
    with open(tmp, "wb") as f:
        f.truncate(size)
    step = -(-size // parts)

    def one(start):
        end = min(start + step, size) - 1
        with _session().get(url, headers={"Range": f"bytes={start}-{end}"}, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "r+b") as f:
                f.seek(start)
                for c in r.iter_content(1 << 20):
                    f.write(c)

    with ThreadPoolExecutor(max_workers=parts) as pool:
        list(pool.map(one, range(0, size, step)))
    if tmp.stat().st_size != size:
        raise IOError(f"{dest.name}: got {tmp.stat().st_size} of {size} bytes")
    os.replace(tmp, dest)


def fetch_population(urls: dict[str, tuple[str, int]], dest_dir: Path, log=print,
                     parts: int = 4) -> dict[str, Path]:
    """Download the population COGs whole, all six at once and each in
    ``parts`` parallel byte ranges; files already in ``dest_dir`` are reused."""
    from concurrent.futures import ThreadPoolExecutor
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = {cls: dest_dir / url.rsplit("/", 1)[1] for cls, (url, _) in urls.items()}
    todo = [(urls[c][0], urls[c][1], d) for c, d in out.items() if not d.exists()]
    if todo:
        t = time.time()
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            list(pool.map(lambda a: _download(*a, parts), todo))
        mb = sum(n for _, n, _ in todo) / 1e6
        log(f"    {len(todo)} population files, {mb:.0f} MB in {time.time() - t:.0f}s "
            f"({mb / max(time.time() - t, 1e-6):.1f} MB/s)")
    return out


def hazard_window(path: str, grid):
    """The hazard at its native resolution over ``grid``'s extent, read in one
    request batch: (float32 array with NaN for no data, transform, crs), or None
    when the extent is outside the raster. This is the only network step."""
    import rasterio
    import rasterio._err
    import rasterio.errors
    from rasterio.warp import transform_bounds
    from rasterio.windows import Window, from_bounds
    for attempt in range(6):  # ride out a dropped connection (about 15 minutes in all)
        try:
            with rasterio.open(f"/vsicurl/{AZURE}/gchd_cog/{path}") as src:
                bounds = transform_bounds(grid.crs, src.crs, *grid.bounds, densify_pts=21)
                w = from_bounds(*bounds, transform=src.transform)
                c0, r0 = int(np.floor(w.col_off)) - 1, int(np.floor(w.row_off)) - 1
                c1, r1 = int(np.ceil(w.col_off + w.width)) + 1, int(np.ceil(w.row_off + w.height)) + 1
                win = Window(c0, r0, c1 - c0, r1 - r0)
                try:
                    win = win.intersection(Window(0, 0, src.width, src.height))
                except rasterio.errors.WindowError:
                    return None
                arr = src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
                return arr, src.window_transform(win), src.crs
        except (rasterio.errors.RasterioIOError, rasterio._err.CPLE_BaseError):  # mid-read drops raise the latter
            if attempt == 5:
                raise
            time.sleep(30 * (attempt + 1))


def window_on_grid(window, grid) -> np.ndarray:
    """The native window resampled (nearest) onto ``grid``'s pixels; NaN where it has no data."""
    from rasterio.enums import Resampling
    from rasterio.warp import reproject
    out = np.full((grid.height, grid.width), np.nan, dtype="float32")
    if window is not None:
        arr, transform, crs = window
        reproject(arr, out, src_transform=transform, src_crs=crs, src_nodata=np.nan,
                  dst_transform=grid.transform, dst_crs=grid.crs, dst_nodata=np.nan,
                  resampling=Resampling.nearest)
    return out


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


def country_stats(units, hazards, pop_files: dict[str, Path | str], log=print, timing: dict | None = None):
    """Per (unit, hazard) exposures and hazard statistics, shaped like
    ``pipeline.chunked.combine``'s output. ``timing`` accumulates ``read_s``
    (hazard windows over the network) and ``compute_s`` (everything else)."""
    import pandas as pd
    import rasterio
    from exactextract import exact_extract
    from exactextract.raster import NumPyRasterSource, RasterioRasterSource

    from contextlib import ExitStack
    rows = []
    with rasterio.Env(**GDAL_ENV), ExitStack() as stack:  # files closed even on failure
        pops = {c: stack.enter_context(rasterio.open(p)) for c, p in pop_files.items()}
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
            window = None
            if path not in cache:
                window = hazard_window(path, grid)
            t_read = time.time() - t
            if path not in cache:
                cache = {path: window_on_grid(window, grid)}  # keep one layer in memory (twins share it)
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
            t_comp = time.time() - t - t_read
            if timing is not None:
                timing["read_s"] = timing.get("read_s", 0) + t_read
                timing["compute_s"] = timing.get("compute_s", 0) + t_comp
            log(f"    {hazard.code}: read {t_read:.1f}s, compute {t_comp:.1f}s")
    return pd.concat(rows, ignore_index=True)
