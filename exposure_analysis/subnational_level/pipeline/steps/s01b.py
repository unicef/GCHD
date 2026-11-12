"""Step 01b — admin-2 hazard exposure from COGs on Azure, without Earth Engine (prototype).

Same partials as s01/s01c, from ``pipeline.cog_zonal``: the WorldPop R2025A
population and the GCHD hazard COGs are read from the unit's Azure storage
and reduced per admin-2 unit with exactextract. Only hazards whose COG is the
same raster as the GEE asset are computed (``cog_zonal.COG_LAYERS``).

Per country: the admin-2 boundaries are cached as GeoParquet (fetched from
Earth Engine once), the six population COGs are downloaded once, and every
hazard is read for the country's extent only. Runs anywhere Python runs: on a
laptop it is bound by the download speed; in Databricks, next to the storage,
reads are fast and free of egress.

Special population rasters (Alaska, Aaland, Kosovo) are not handled yet.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .. import auth, io_paths
from ..cog_zonal import COG_LAYERS, country_stats, fetch_population
from ..countries import resolve
from ..hazards import load_hazards
from ..settings import Settings
from .s01c import log, write_country

BOUNDARY_ASSET = "global_boundary/admin2_pop_geom"


def boundaries(settings: Settings, ucode: str, cache: Path):
    """The country's admin-2 units (all asset properties), cached as GeoParquet."""
    import geopandas as gpd
    path = cache / "boundaries" / f"{ucode}.parquet"
    if not path.exists():
        import ee
        auth.init_ee(settings)
        fc = (ee.FeatureCollection(f"{settings.unicef_data_source_path}/{BOUNDARY_ASSET}")
              .filter(ee.Filter.eq("adm0_ucode", ucode)).distinct("adm2_ucode"))
        g = gpd.GeoDataFrame.from_features(fc.getInfo()["features"], crs="EPSG:4326")
        path.parent.mkdir(parents=True, exist_ok=True)
        g.to_parquet(path)
    return gpd.read_parquet(path)


def run(settings: Settings, *, cache_dir: str | None = None) -> dict:
    import ee
    hazards = [h for h in load_hazards(settings) if h.code in COG_LAYERS]
    countries = resolve(settings.process_countries) or []
    if not countries:
        raise ValueError("s01b is a prototype: pass --countries")
    cache = Path(cache_dir or Path(io_paths.aux_root(settings)).parent / "cache")
    utils = auth.make_utils(settings, ee)
    timing = Path(io_paths.manifest_root(settings)) / "s01b_timing.csv"
    timing.parent.mkdir(parents=True, exist_ok=True)
    rows, failed = [], []
    log(f"s01b: {len(hazards)} hazards with matching COGs x {len(countries)} countries; cache {cache}")
    for ucode in countries:
        try:
            t0 = time.time()
            units = boundaries(settings, ucode, cache)
            t1 = time.time()
            pop = fetch_population(ucode[:3], cache / "worldpop", log=log)
            t2 = time.time()
            stats = country_stats(units[["adm2_ucode", "geometry"]], hazards, pop, log=log)
            t3 = time.time()
            write_country(settings, utils, hazards, ucode, stats, pd.DataFrame(units.drop(columns="geometry")))
            rows.append(dict(ucode=ucode, n_units=len(units), hazards=len(hazards),
                             boundaries_s=round(t1 - t0, 1), population_download_s=round(t2 - t1, 1),
                             compute_s=round(t3 - t2, 1), total_s=round(time.time() - t0, 1)))
            log(f"  {ucode}: {rows[-1]}")
        except Exception as e:
            failed.append(ucode)
            log(f"  ERROR {ucode}: {str(e)[:300]}")
    pd.DataFrame(rows).to_csv(timing, mode="a", header=not timing.exists(), index=False)
    return {"countries_done": len(rows), "failed": failed}
