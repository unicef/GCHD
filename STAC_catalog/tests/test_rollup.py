"""Roll-up checks for the exposure tables (adm{0,1,2}_hazard), read from the published copies on Azure.

1. Internal: ADM1 / ADM0 sum columns equal the sum of their ADM2 rows (exact).
2. External: ADM0 U18 numbers agree with the GEE country asset the current app shows
   (work/src/gee_adm0_exposure.parquet from pipeline/00_export_gee_adm0.py), for hazards whose
   GEE layer is the same source as the published ADM2 CSVs. This is a guard against roll-up
   bugs, not a parity study: globally within 1%, per country within max(5%, 1,000 children).
   Per-hazard source differences are out of scope for now (2026-11-16).

Run: .venv/bin/python -m pytest tests/test_rollup.py -q
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXP = "https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan"   # <table>/<table>.parquet
GEE = ROOT / "work" / "src" / "gee_adm0_exposure.parquet"
SUM_COLS = ["pop_total", "pop_total_m", "pop_total_f", "u18_pop_total", "u18_pop_m", "u18_pop_f",
            "aexp", "amexp", "afexp", "u18_aexp", "u18_amexp", "u18_afexp"]
SAME_SOURCE = {   # hazard_code -> GEE adm0 asset field (same layer as the published CSVs)
    "river_flood_100yr": "pop_exposed_river_flood_100yr_jrc_2024",
    "coastal_flood_100yr": "pop_exposed_coastal_flood_100yr_jrc_2024",
    "tropical_storm_100yr": "pop_exposed_tropical_storm_100yr_giri_2024",
    "sand_dust_storm_susc": "pop_exposed_sand_dust_storm_unccd_2024",
    "fire_intensity": "pop_exposed_fire_FRP_nasa_2001-2024",
    "fire_frequency": "pop_exposed_fire_frequency_nasa_2001-2023",
}


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    for t in ("adm2_hazard", "adm1_hazard", "adm0_hazard"):
        c.sql(f"CREATE VIEW {t} AS SELECT * FROM '{EXP}/{t}/{t}.parquet'")
    return c


@pytest.mark.parametrize("level", ["adm1", "adm0"])
def test_rollup_equals_adm2_sum(con, level):
    key = f"{level}_ucode"
    cols = ", ".join(f"sum({c}) AS {c}" for c in SUM_COLS)
    diff = " OR ".join(f"abs(coalesce(r.{c},0) - coalesce(s.{c},0)) > 0.5" for c in SUM_COLS)
    bad = con.sql(f"""
        WITH s AS (SELECT hazard_code, {key}, {cols} FROM adm2_hazard GROUP BY ALL)
        SELECT r.hazard_code, r.{key} FROM {level}_hazard r JOIN s USING (hazard_code, {key})
        WHERE {diff} LIMIT 20""").fetchall()
    assert not bad, bad
    n_missing = con.sql(f"""SELECT count(*) FROM (SELECT DISTINCT hazard_code, {key} FROM adm2_hazard)
                            ANTI JOIN {level}_hazard USING (hazard_code, {key})""").fetchone()[0]
    assert n_missing == 0


@pytest.mark.skipif(not GEE.exists(), reason="needs work/src/gee_adm0_exposure.parquet (GCHD_portolan pipeline/00_export_gee_adm0.py)")
@pytest.mark.parametrize("code,field", [("river_flood_100yr", "pop_child_total"), *SAME_SOURCE.items()])
def test_adm0_matches_gee_asset(con, code, field):
    col = "u18_pop_total" if field == "pop_child_total" else "u18_aexp"
    q = f"""SELECT t.adm0_ucode, t.{col} AS ours, g."{field}" AS gee
            FROM adm0_hazard t JOIN '{GEE}' g ON t.adm0_ucode = g.ucode WHERE t.hazard_code = '{code}'"""
    ours, gee = con.sql(f"SELECT sum(ours), sum(gee) FROM ({q})").fetchone()
    assert abs(ours - gee) <= 0.01 * gee, (ours, gee)
    bad = con.sql(f"SELECT * FROM ({q}) WHERE abs(ours - gee) > greatest(0.05 * gee, 1000)").fetchall()
    assert not bad, bad
