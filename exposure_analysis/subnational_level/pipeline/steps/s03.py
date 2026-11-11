"""Step 03 — delivery formats: per-country + global Excel and GeoPackage.

Productionized form of ``notebooks/03_adm2_hazard_export.ipynb``. Reads the s02
global CSVs, writes:
  - Excel  : per-country and global, per hazard         -> export/...
  - GPKG   : per-country (geometry fetched from GEE) and merged global, per hazard

Needs Earth Engine only to fetch admin2 geometries for the GeoPackage; the Excel
export is pure pandas.

Fixes folded in vs the notebook:
  - reads the canonical ``base/global`` (was ``global/CSV``)
  - loads hazards via ``pipeline.hazards`` (was a bare ``pd.read_json("hazard_info.json")``)
  - writes to the canonical ``export/`` layout via ``io_paths``

GeoPackage note: geopandas ``to_file`` needs a LOCAL path; when storage_root is
remote (abfs://) this step must run against a local root (Stage 3 adds a
local-tmp-then-put wrapper). We guard for that.
"""

from __future__ import annotations

import os

import pandas as pd

from ..settings import Settings
from ..hazards import load_hazards
from .. import io_paths
from .. import auth

STEP = "s03"
ADM0_COL = "adm0_ucode"


def _read_global(settings: Settings, hazard_code: str) -> pd.DataFrame:
    """Read one hazard's s02 global CSV (index_col=0 drops the written index)."""
    path = io_paths.base_global_csv(settings, hazard_code)
    return pd.read_csv(path, index_col=0)


def _polygons_only(geom):
    """Reduce a GeometryCollection to its polygonal parts (ported from NB03)."""
    if geom.geom_type != "GeometryCollection":
        return geom
    import shapely

    polys = []
    for g in geom.geoms:
        if g.geom_type == "Polygon":
            polys.append(g)
        elif g.geom_type == "MultiPolygon":
            polys.extend(list(g.geoms))
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else shapely.geometry.MultiPolygon(polys)


def export_excel(settings: Settings, utils, hazards, countries) -> int:
    """Per-country and global Excel per hazard. Pure pandas."""
    n = 0
    for hazard in hazards:
        try:
            df_global = _read_global(settings, hazard.code)
        except FileNotFoundError:
            print(f"  {hazard.code}: no global CSV; skipping excel")
            continue
        # global excel
        gout = io_paths.ensure_local_dir(io_paths.export_excel(settings, hazard.code))
        df_global.to_excel(gout, index=False)
        n += 1
        # per-country excel
        for ucode in countries:
            df_c = df_global.loc[df_global[ADM0_COL] == ucode].reset_index(drop=True)
            if df_c.empty:
                continue
            cout = io_paths.ensure_local_dir(io_paths.export_excel(settings, hazard.code, ucode))
            df_c.to_excel(cout, index=False)
            n += 1
    print(f"  excel: wrote {n} files")
    return n


def export_geopackage(settings: Settings, ee, utils, hazards, countries) -> int:
    """Per-country GeoPackage (geometry from GEE) + merged global, per hazard."""
    if io_paths.is_remote(settings):
        raise RuntimeError(
            "s03 GeoPackage export needs a local storage_root (geopandas.to_file "
            "cannot write abfs:// directly). Stage 3 will add a local-tmp-then-put "
            "wrapper; for now run s03 with a local --storage-root."
        )
    import geopandas as geopd
    import shapely

    adm2_asset = ee.FeatureCollection(f"{settings.unicef_data_source_path}/{utils.ADMIN2_ASSET}")
    n = 0
    for ucode in countries:
        geom_cache = None  # fetched once per country, reused across hazards
        for hazard in hazards:
            try:
                df_global = _read_global(settings, hazard.code)
            except FileNotFoundError:
                continue
            df_c = df_global.loc[df_global[ADM0_COL] == ucode].reset_index(drop=True)
            if df_c.empty:
                continue

            if geom_cache is None:
                rows = []
                for adm1 in df_c["adm1_ucode"].unique():
                    feats = adm2_asset.filter(ee.Filter.eq("adm1_ucode", adm1)).getInfo()["features"]
                    for f in feats:
                        g = _polygons_only(shapely.geometry.shape(f["geometry"]))
                        rows.append({"geometry": g, **f["properties"]})
                geom_cache = pd.DataFrame(rows)

            cols = list(df_c.columns) + ["geometry"]
            merged = pd.merge(df_c, geom_cache, how="right")[cols]
            gdf = geopd.GeoDataFrame(merged, geometry="geometry").set_crs(epsg=4326)

            out = io_paths.ensure_local_dir(io_paths.export_geopackage(settings, hazard.code, ucode))
            gdf.to_file(out, index=False, driver="GPKG", layer=hazard.code)
            n += 1
    print(f"  geopackage (per-country): wrote {n} files")

    # merged global gpkg per hazard, from the per-country files just written
    for hazard in hazards:
        frames = []
        for ucode in countries:
            p = io_paths.export_geopackage(settings, hazard.code, ucode)
            if os.path.exists(p):
                frames.append(geopd.read_file(p, layer=hazard.code))
        if not frames:
            continue
        gdf_g = geopd.GeoDataFrame(pd.concat(frames, ignore_index=True),
                                   geometry="geometry").set_crs(epsg=4326)
        gout = io_paths.ensure_local_dir(io_paths.export_geopackage(settings, hazard.code))
        gdf_g.to_file(gout, index=False, driver="GPKG", layer=hazard.code)
        n += 1
    print(f"  geopackage (incl. global): {n} files total")
    return n


def run(settings: Settings, *, allow_interactive: bool = False,
        excel: bool = True, geopackage: bool = True) -> dict:
    """Export delivery formats. GeoPackage needs EE (geometry); Excel does not,
    but we init EE once up front so both share the session."""
    ee, utils = auth.ee_and_utils(settings, allow_interactive=allow_interactive)
    hazards = load_hazards(settings)
    countries = utils.get_countries_to_process(settings.process_countries)
    print(f"s03: {len(hazards)} hazards x {len(countries)} countries")

    n_xlsx = export_excel(settings, utils, hazards, countries) if excel else 0
    n_gpkg = export_geopackage(settings, ee, utils, hazards, countries) if geopackage else 0

    summary = {"excel_files": n_xlsx, "gpkg_files": n_gpkg}
    print(f"s03 done: {summary}")
    return summary
