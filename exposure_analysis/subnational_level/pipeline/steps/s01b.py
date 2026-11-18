"""Step 01b — admin-2 hazard exposure from COGs on Azure, without Earth Engine (prototype).

Same partials as s01/s01c, from ``pipeline.cog_zonal``: the WorldPop R2025A
population and the GCHD hazard COGs are read from the unit's Azure storage
and reduced per admin-2 unit with exactextract. Only hazards whose COG is the
same raster as the GEE asset are computed (``cog_zonal.COG_LAYERS``).

Per country: the admin-2 boundaries are cached as GeoParquet (fetched from
Earth Engine once), the six population COGs are downloaded once or read in
place (``population="remote"``), and every hazard is read for the country's
extent only. Several countries can run at once (``workers``). Runs anywhere Python runs: on a
laptop it is bound by the download speed; in Databricks, next to the storage,
reads are fast and free of egress.

Special population rasters (Alaska, Aaland, Kosovo) are not handled yet.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .. import auth, io_paths
from ..cog_zonal import COG_LAYERS, DiskBudget, country_stats, fetch_population, population_urls
from ..countries import resolve
from ..hazards import load_hazards
from ..settings import Settings
from .s01c import log, write_country

BOUNDARY_ASSET = "global_boundary/admin2_pop_geom"


def boundaries(settings: Settings, ucode: str, cache: Path):
    """The country's admin-2 units (all asset properties), cached as GeoParquet:
    downloaded from ``settings.boundaries_url``, else fetched from Earth Engine."""
    import geopandas as gpd
    import os
    from ..cog_zonal import _session
    path = cache / "boundaries" / f"{ucode}.parquet"
    if not path.exists() and settings.boundaries_url:
        r = _session().get(f"{settings.boundaries_url.rstrip('/')}/{ucode}.parquet", timeout=300)
        if r.status_code == 200:
            path.parent.mkdir(parents=True, exist_ok=True)
            Path(f"{path}.part").write_bytes(r.content)
            os.replace(f"{path}.part", path)
        elif r.status_code != 404:
            r.raise_for_status()
    if not path.exists():
        import ee
        auth.init_ee(settings)
        fc = (ee.FeatureCollection(f"{settings.unicef_data_source_path}/{BOUNDARY_ASSET}")
              .filter(ee.Filter.eq("adm0_ucode", ucode)).distinct("adm2_ucode"))
        g = gpd.GeoDataFrame.from_features(fc.getInfo()["features"], crs="EPSG:4326")
        path.parent.mkdir(parents=True, exist_ok=True)
        g.to_parquet(path)
    return gpd.read_parquet(path)


def as_multipolygons(units):
    """Every unit as a MultiPolygon: exactextract rejects a layer that mixes
    Polygon and MultiPolygon, and Earth Engine returns both (sometimes inside a
    GeometryCollection with stray lines, which carry no area)."""
    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

    def fix(g):
        if isinstance(g, Polygon):
            return MultiPolygon([g])
        if isinstance(g, GeometryCollection) and not isinstance(g, MultiPolygon):
            parts = [p for q in g.geoms for p in (q.geoms if isinstance(q, MultiPolygon) else [q])
                     if isinstance(p, Polygon)]
            return MultiPolygon(parts)
        return g

    units = units.copy()
    units["geometry"] = units.geometry.apply(fix)
    return units


def one_country(settings: Settings, utils, hazards, ucode: str, cache: Path, population: str,
                budget: DiskBudget, keep_cache: bool) -> dict:
    t0 = time.time()
    units = boundaries(settings, ucode, cache)
    t1 = time.time()
    urls = population_urls(ucode[:3])
    nbytes = sum(n for _, n in urls.values())
    pop_dir = cache / "worldpop" / ucode[:3].lower()
    remote = population == "remote"
    if remote:
        pop = {c: f"/vsicurl/{u}" for c, (u, _) in urls.items()}
    else:
        budget.reserve(nbytes, log=log)
    try:
        if not remote:
            pop = fetch_population(urls, pop_dir, log=log)
        t2 = time.time()
        tm: dict = {}
        stats = country_stats(as_multipolygons(units[["adm2_ucode", "geometry"]]), hazards, pop, log=log, timing=tm)
        write_country(settings, utils, hazards, ucode, stats, pd.DataFrame(units.drop(columns="geometry")))
        if not remote and not keep_cache:  # free the disk once the country is done; a failed one keeps its cache
            for f in pop_dir.glob("*.tif*"):
                f.unlink()
    finally:
        if not remote:
            budget.release(nbytes)
    return dict(ucode=ucode, n_units=len(units), hazards=len(hazards), population=population,
                population_gb=round(nbytes / 1e9, 2), boundaries_s=round(t1 - t0, 1),
                population_s=round(t2 - t1, 1), hazard_read_s=round(tm.get("read_s", 0), 1),
                compute_s=round(tm.get("compute_s", 0), 1), total_s=round(time.time() - t0, 1))


def run(settings: Settings, *, cache_dir: str | None = None, population: str = "download",
        workers: int = 1, max_cache_gb: float = 20, keep_cache: bool = False) -> dict:
    """``population``: "download" (cache each country's COGs locally; best on a
    slow link) or "remote" (read them in place; best next to the storage).
    ``workers``: countries processed at once. Downloaded population never holds
    more than ``max_cache_gb`` on disk, and a country's files are deleted once it
    is done unless ``keep_cache``."""
    import ee
    from concurrent.futures import ThreadPoolExecutor, as_completed
    hazards = [h for h in load_hazards(settings) if h.code in COG_LAYERS]
    countries = resolve(settings.process_countries) or []
    if not countries:
        raise ValueError("s01b is a prototype: pass --countries")
    cache = Path(cache_dir or Path(io_paths.aux_root(settings)).parent / "cache")
    utils = auth.make_utils(settings, ee)
    timing = Path(io_paths.manifest_root(settings)) / "s01b_timing.csv"
    timing.parent.mkdir(parents=True, exist_ok=True)
    rows, failed = [], []
    log(f"s01b: {len(hazards)} hazards with matching COGs x {len(countries)} countries; "
        f"population {population}, {workers} workers; cache {cache}")
    t_all = time.time()
    budget = DiskBudget(max_cache_gb)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one_country, settings, auth.make_utils(settings, ee), hazards, u, cache,
                               population, budget, keep_cache): u for u in countries}
        for fut in as_completed(futures):
            u = futures[fut]
            try:
                rows.append(fut.result())
                log(f"  {u}: {rows[-1]}")
            except Exception as e:
                failed.append(u)
                log(f"  ERROR {u}: {str(e)[:300]}")
    if rows:
        pd.DataFrame(rows).to_csv(timing, mode="a", header=not timing.exists(), index=False)
    return {"countries_done": len(rows), "failed": failed, "seconds": round(time.time() - t_all, 1)}
