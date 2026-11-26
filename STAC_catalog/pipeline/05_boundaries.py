"""Step 5 (optional): rebuild the administrative boundary GeoParquet files (ADM0/1/2) from source.

The catalog (08_build_stac.py) references the published copies on Azure
(public/GCHD_portolan/adm{0,1,2}/adm{0,1,2}.parquet + .pmtiles); this step only matters when the
boundaries change. Ported from the GCHD_portolan project (pipeline/03_boundaries.py).

Sources
  ADM2  public/boundaries/adm2/<ADM0_UCODE>.parquet  (GEE admin2_pop_geom export, 2026-06-04)
        - authoritative: ucodes match the ADM2 exposure CSVs 1:1 (41,023 units).
  ADM1/ADM0  GeoRepo GeoJSON (climate/georepo_bnd_file_FINAL.../Adm{0,1}_Latest.zip, 2025-10-14)
        - match the CSV codes except Mali (V1 in GeoRepo, V2 in the CSVs), so MLI_V1 is
          replaced by a dissolve of the MLI_V2 ADM2 units. Extra units with no exposure data
          (territories, sovereignty-unsettled areas, Antarctica, VAT) are kept for the map,
          flagged has_exposure = false.

Outputs  work/out/boundaries/adm{0,1,2}/adm{0,1,2}.parquet  - GeoParquet 1.1, ZSTD, bbox covering,
         Hilbert-ordered (written by geoparquet-io).

Inputs are expected in work/src/ (boundaries_adm2_v2/) and work/out/gchd_tables/boundaries/
(GeoRepo GeoJSON converted with gpio), and the ADM2 exposure table from step 6.

Usage: ../.venv/bin/python pipeline/05_boundaries.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC_ADM2 = ROOT / "work" / "src" / "boundaries_adm2_v2"
SRC_GEOREPO = ROOT / "work" / "out" / "gchd_tables" / "boundaries" / "georepo_2025-10-14"  # gpio-converted GeoJSON
CATALOG = ROOT / "work" / "out" / "boundaries"
TMP = ROOT / "work" / "tmp"
GPIO = ROOT.parent / ".venv" / "bin" / "gpio"
RELEASE = yaml.safe_load((ROOT / "config" / "hazard_map.yaml").read_text())["release"]
EXPOSURE = ROOT / "work" / "out" / "gchd_tables" / "exposure" / RELEASE / "adm2_hazard.parquet"

ADM2_SOURCE = "GEE admin2_pop_geom export 2026-06-04 (public/boundaries/adm2)"
GEOREPO_SOURCE = "UNICEF GeoRepo Global Administrative Boundaries, extracted 2025-10-14"
MALI_SOURCE = "dissolved from MLI_V2 ADM2 units (GEE admin2_pop_geom export 2026-06-04)"


def gpio_convert(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(GPIO), "convert", "geoparquet", str(src), str(dst)], check=True,
                   stdout=subprocess.DEVNULL)


def fix_extent(con, tbl: str) -> None:
    """Bring geometries into [-180,180]x[-90,90].

    The GEE export unwraps a few dateline-crossing ADM2 units past 180 deg (FJI Cakaudrove /
    Macuata, RUS Chukot up to 190.35); the part east of 180 is cut and shifted by -360.
    Antarctica overshoots -180 by 5e-6 deg; everything is clipped to the world box.
    """
    from shapely import affinity, box, make_valid, wkb
    from shapely.ops import unary_union

    rows = con.sql(f"""SELECT ucode, ST_AsWKB(geometry) FROM {tbl}
                       WHERE ST_XMin(geometry) < -180 OR ST_XMax(geometry) > 180
                          OR ST_YMin(geometry) < -90 OR ST_YMax(geometry) > 90""").fetchall()
    world = box(-180, -90, 180, 90)
    for ucode, g in rows:
        geom = wkb.loads(bytes(g))
        parts = [geom.intersection(world)]
        east = geom.intersection(box(180, -90, 540, 90))
        if not east.is_empty:
            parts.append(affinity.translate(east, xoff=-360).intersection(world))
        west = geom.intersection(box(-540, -90, -180, 90))
        if not west.is_empty and west.area > 1e-9:
            parts.append(affinity.translate(west, xoff=360).intersection(world))
        fixed = make_valid(unary_union([p for p in parts if not p.is_empty]))
        if fixed.geom_type == "GeometryCollection":
            fixed = unary_union([p for p in fixed.geoms if p.geom_type in ("Polygon", "MultiPolygon")])
        con.execute(f"UPDATE {tbl} SET geometry = ST_GeomFromWKB(?) WHERE ucode = ?", [fixed.wkb, ucode])
        print(f"  {tbl}: fixed extent of {ucode}")


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial; SET preserve_insertion_order=false")
    con.sql(f"CREATE TABLE exp AS SELECT DISTINCT adm0_ucode, adm1_ucode, adm2_ucode FROM '{EXPOSURE}'")

    # ---------------------------------------------------------------- ADM2
    con.sql(f"""
        CREATE TABLE adm2 AS
        SELECT adm2_ucode AS ucode, adm2_name AS name, name_en, name_fr,
               adm1_ucode, adm1_name, adm0_ucode, adm0_name, ISO3 AS iso3, adm0_type,
               PCode AS pcode, Region_Code AS unicef_region, Region AS unicef_region_full,
               pop_total, pop_total_male, pop_total_female,
               pop_under_18_total, pop_under_18_male, pop_under_18_female,
               '{ADM2_SOURCE}' AS source,
               ST_GeomFromWKB(ST_AsWKB(geometry)) AS geometry
        FROM read_parquet('{SRC_ADM2}/*_V*.parquet', union_by_name=true)
    """)
    n2, u2 = con.sql("SELECT count(*), count(DISTINCT ucode) FROM adm2").fetchone()
    miss = con.sql("SELECT count(*) FROM exp WHERE adm2_ucode NOT IN (SELECT ucode FROM adm2)").fetchone()[0]
    assert n2 == u2 and miss == 0, (n2, u2, miss)
    con.sql("ALTER TABLE adm2 ADD COLUMN has_exposure BOOLEAN DEFAULT true")
    con.sql("UPDATE adm2 SET has_exposure = ucode IN (SELECT adm2_ucode FROM exp)")

    # ---------------------------------------------------------------- Mali V2 dissolves
    con.sql("""
        CREATE TABLE mli1 AS
        SELECT adm1_ucode AS ucode, any_value(adm1_name) AS name, any_value(adm0_ucode) AS adm0_ucode,
               ST_MakeValid(ST_Union_Agg(geometry)) AS geometry
        FROM adm2 WHERE adm0_ucode = 'MLI_V2' GROUP BY adm1_ucode
    """)
    con.sql("""
        CREATE TABLE mli0 AS
        SELECT 'MLI_V2' AS ucode, ST_MakeValid(ST_Union_Agg(geometry)) AS geometry FROM mli1
    """)

    # ---------------------------------------------------------------- ADM1
    con.sql(f"""
        CREATE TABLE adm1 AS
        SELECT ucode, name, name_en, adm0_ucode, adm0_type, PCode AS pcode,
               '{GEOREPO_SOURCE}' AS source, ST_GeomFromWKB(ST_AsWKB(geom)) AS geometry
        FROM '{SRC_GEOREPO}/adm1.parquet' WHERE adm0_ucode <> 'MLI_V1'
        UNION ALL
        SELECT m.ucode, m.name, m.name, 'MLI_V2', 'State', NULL, '{MALI_SOURCE}', m.geometry FROM mli1 m
    """)
    # iso3 + names from the ADM0 layer / exposure
    con.sql(f"""
        CREATE TABLE adm0 AS
        SELECT ucode, name, name_en, ISO3 AS iso3, "type" AS adm0_type,
               '{GEOREPO_SOURCE}' AS source, ST_GeomFromWKB(ST_AsWKB(geom)) AS geometry
        FROM '{SRC_GEOREPO}/adm0.parquet' WHERE ucode <> 'MLI_V1'
        UNION ALL
        SELECT 'MLI_V2', 'Mali', 'Mali', 'MLI', 'State', '{MALI_SOURCE}', geometry FROM mli0
    """)
    con.sql("""
        CREATE TABLE adm1_full AS
        SELECT a.*, z.iso3, z.name AS adm0_name,
               a.ucode IN (SELECT adm1_ucode FROM exp) AS has_exposure
        FROM adm1 a LEFT JOIN adm0 z ON z.ucode = a.adm0_ucode
    """)
    con.sql("""
        CREATE TABLE adm0_full AS
        SELECT *, ucode IN (SELECT adm0_ucode FROM exp) AS has_exposure FROM adm0
    """)
    for lvl, tbl, key in ((1, "adm1_full", "adm1_ucode"), (0, "adm0_full", "adm0_ucode")):
        miss = con.sql(f"SELECT list(DISTINCT {key}) FROM exp WHERE {key} NOT IN (SELECT ucode FROM {tbl})").fetchone()[0]
        dup = con.sql(f"SELECT count(*) - count(DISTINCT ucode) FROM {tbl}").fetchone()[0]
        assert not miss and dup == 0, (lvl, miss, dup)

    # ---------------------------------------------------------------- antimeridian / extent
    for tbl in ("adm0_full", "adm1_full", "adm2"):
        fix_extent(con, tbl)

    # ---------------------------------------------------------------- write
    for lvl, tbl in ((0, "adm0_full"), (1, "adm1_full"), (2, "adm2")):
        tmp = TMP / f"adm{lvl}_raw.parquet"
        con.sql(f"COPY (SELECT * FROM {tbl} ORDER BY ucode) TO '{tmp}' (FORMAT parquet, COMPRESSION zstd)")
        out = CATALOG / f"adm{lvl}" / f"adm{lvl}.parquet"
        gpio_convert(tmp, out)
        n, ne = con.sql(f"SELECT count(*), count_if(has_exposure) FROM '{out}'").fetchone()
        print(f"adm{lvl}: {n:>6,} units ({ne:,} with exposure data)  {out.stat().st_size/1e6:7.1f} MB  -> {out.relative_to(ROOT)}")
        tmp.unlink()


if __name__ == "__main__":
    main()
