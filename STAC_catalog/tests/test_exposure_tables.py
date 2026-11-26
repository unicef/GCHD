"""Checks for pipeline/04_exposure_tables.py outputs.

Run: .venv/bin/python -m pytest tests/test_exposure_tables.py -q
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import duckdb
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HM = yaml.safe_load((ROOT / "config" / "hazard_map.yaml").read_text())
REL = HM["release"]
OUT = ROOT / "work" / "out" / "gchd_tables" / "exposure" / REL
CSV_DIR = ROOT / "work" / "src" / "csv"
SCHEMA = json.loads((ROOT / "config" / "exposure_schema.json").read_text())

pytestmark = pytest.mark.skipif(not (OUT / "adm2_hazard.parquet").exists(), reason="run pipeline/06_exposure_tables.py first")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    for t in ("adm2_hazard", "adm1_hazard", "adm0_hazard"):
        c.sql(f"CREATE VIEW {t} AS SELECT * FROM '{OUT / (t + '.parquet')}'")
    return c


def test_columns_match_schema_and_csv(con):
    cols = con.sql("SELECT * FROM adm2_hazard LIMIT 0").columns
    assert cols == [c["name"] for c in SCHEMA["columns"] if c["name"] not in ("n_adm2", "n_adm2_with_data")]
    header = next(csv.reader(open(CSV_DIR / f"river_flood_100yr_{REL}.csv")))
    assert cols[3:] == header          # workbook/CSV columns verbatim after the 3 key columns


def test_types_follow_schema(con):
    want = {c["name"]: c["parquet_type"] for c in SCHEMA["columns"]}
    got = dict(con.sql("SELECT column_name, column_type FROM (DESCRIBE adm2_hazard)").fetchall())
    for name, t in got.items():
        assert t == want[name], f"{name}: {t} != {want[name]}"


def test_row_counts_match_csv(con):
    for code in HM["hazards"]:
        n_csv = con.sql(f"SELECT count(*) FROM read_csv('{CSV_DIR / f'{code}_{REL}.csv'}', all_varchar=true)").fetchone()[0]
        n_pq = con.sql(f"SELECT count(*) FROM adm2_hazard WHERE hazard_code='{code}'").fetchone()[0]
        assert n_csv == n_pq, code


def test_unique_keys(con):
    assert con.sql("SELECT count(*) FROM (SELECT 1 FROM adm2_hazard GROUP BY hazard_code, adm2_ucode HAVING count(*)>1)").fetchone()[0] == 0
    assert con.sql("SELECT count(*) FROM (SELECT 1 FROM adm1_hazard GROUP BY hazard_code, adm1_ucode HAVING count(*)>1)").fetchone()[0] == 0
    assert con.sql("SELECT count(*) FROM (SELECT 1 FROM adm0_hazard GROUP BY hazard_code, adm0_ucode HAVING count(*)>1)").fetchone()[0] == 0


@pytest.mark.parametrize("code", ["river_flood_100yr", "heatwave_frequency", "landslides_0p1"])
def test_values_equal_csv(con, code):
    """Every numeric cell equals the CSV value; nulls stay nulls (never 0)."""
    p = CSV_DIR / f"{code}_{REL}.csv"
    cols = ["u18_aexp", "aexp", "pop_total", "u18_rexp", "hazs_mean", "gindex", "u18_cexpc"]
    diff = con.sql(f"""
        SELECT count(*) FROM read_csv('{p}', all_varchar=true) c
        JOIN adm2_hazard a ON a.adm2_ucode = c.adm2_ucode AND a.hazard_code = '{code}'
        WHERE {' OR '.join(f"(TRY_CAST(c.{x} AS DOUBLE) IS DISTINCT FROM a.{x}::DOUBLE)" for x in cols)}
    """).fetchone()[0]
    assert diff == 0


def test_prod_date_normalised(con):
    assert con.sql("SELECT count(*) FROM adm2_hazard WHERE prod_date IS NULL").fetchone()[0] == 0
    lo, hi = con.sql("SELECT min(prod_date), max(prod_date) FROM adm2_hazard").fetchone()
    assert str(lo) >= "2026-01-01" and str(hi) <= "2026-12-31"


def test_rollup_sums_preserved(con):
    for col in ("u18_aexp", "aexp", "u18_pop_total", "pop_total"):
        for lvl in ("adm1_hazard", "adm0_hazard"):
            bad = con.sql(f"""
                SELECT count(*) FROM (SELECT hazard_code, sum({col}) s FROM adm2_hazard GROUP BY 1) a
                JOIN (SELECT hazard_code, sum({col}) s FROM {lvl} GROUP BY 1) b USING (hazard_code)
                WHERE a.s IS DISTINCT FROM b.s""").fetchone()[0]
            assert bad == 0, (col, lvl)


def test_rollup_relative_exposure_recomputed(con):
    bad = con.sql("""SELECT count(*) FROM adm0_hazard WHERE u18_aexp IS NOT NULL
        AND abs(u18_rexp - 100.0*u18_aexp/u18_pop_total) > 0.06 AND n_adm2 = n_adm2_with_data""").fetchone()[0]
    assert bad == 0
    assert con.sql("SELECT count(*) FROM adm0_hazard WHERE u18_rexp > 100.05").fetchone()[0] == 0


def test_rollup_non_aggregable_are_null(con):
    for col in ("hazs_median", "hazs_std", "cexpi", "u18_gexpc"):
        assert con.sql(f"SELECT count({col}) FROM adm1_hazard").fetchone()[0] == 0, col


def test_exposed_exceeds_population_only_known_source_rows(con):
    """Source CSVs have a few rows with exposure > population; they must all be in the QA report."""
    qa = json.loads((OUT / "qa_report.json").read_text())
    known = {(r["hazard_code"], r["adm2_ucode"]) for r in qa["exposed_exceeds_population"]["rows"]}
    found = set(con.sql("SELECT hazard_code, adm2_ucode FROM adm2_hazard "
                        "WHERE u18_aexp > u18_pop_total OR aexp > pop_total").fetchall())
    assert found == known
