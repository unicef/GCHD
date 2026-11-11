"""Smoke tests for the Stage-1 foundation modules.

Pure, no Earth Engine / no network. Run from the subnational_level dir:
    ..\..\.venv\Scripts\python.exe -m pytest tests -q
or without pytest:
    ..\..\.venv\Scripts\python.exe tests/test_foundation.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make `pipeline` importable when run directly (pytest handles this via rootdir).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import io_paths, hazards, na_rules
from pipeline.settings import DEFAULT_STORAGE_ROOT, Settings


# -- settings -------------------------------------------------------------

def test_settings_defaults():
    s = Settings()
    assert s.gee_project == "unicef-ccri"
    assert s.time_period == 2025  # data year of the WorldPop population
    assert s.storage_root == DEFAULT_STORAGE_ROOT
    assert DEFAULT_STORAGE_ROOT.endswith("subnational_level/notebooks/output")
    # prod_date is a valid ISO date
    assert len(s.prod_date) == 10 and s.prod_date[4] == "-"
    assert s.export_target in ("drive", "gcs")


def test_settings_dataflow_draft_toggle():
    assert "DRAFT" in Settings(is_draft=True).dataflow
    assert "DRAFT" not in Settings(is_draft=False).dataflow


def test_settings_year_folder():
    assert Settings(production_year=2027).sharepoint_year_folder == "2027"


def test_settings_from_env(monkeypatch=None):
    os.environ["GCHD_STORAGE_ROOT"] = "abfs://gchd/prod"
    os.environ["GCHD_PROCESS_COUNTRIES"] = "EGY_V1,DEU_V1"
    os.environ["GCHD_PRODUCTION_YEAR"] = "2027"
    os.environ["GCHD_IS_DRAFT"] = "false"
    try:
        s = Settings.from_env()
        assert s.storage_root == "abfs://gchd/prod"
        assert s.process_countries == ["EGY_V1", "DEU_V1"]
        assert s.production_year == 2027
        assert s.is_draft is False
        # explicit override beats env
        s2 = Settings.from_env(production_year=2030)
        assert s2.production_year == 2030
    finally:
        for k in ("GCHD_STORAGE_ROOT", "GCHD_PROCESS_COUNTRIES",
                  "GCHD_PRODUCTION_YEAR", "GCHD_IS_DRAFT"):
            os.environ.pop(k, None)


def test_settings_rejects_bad_export_target():
    try:
        Settings(export_target="s3")
    except Exception:
        return
    raise AssertionError("expected validation error for export_target='s3'")


# -- io_paths -------------------------------------------------------------

def test_io_paths_local():
    s = Settings(storage_root="output", prod_date="2026-07-28")
    assert io_paths.base_global_csv(s, "river_flood_100yr") == \
        "output/base/global/river_flood_100yr_2026-07-28.csv"
    assert io_paths.base_partial_csv(s, "fire_intensity", "EGY_V1") == \
        "output/base/hazards/fire_intensity/partials/EGY_V1_fire_intensity_admin2.csv"
    assert io_paths.hazs_count_csv(s) == "output/aux/hazs_count_2026-07-28.csv"


def test_io_paths_stage_roots():
    s = Settings(storage_root="output", prod_date="2026-07-28")
    # Both save_country_results and save_global_results take base_root() as output_folder.
    assert io_paths.base_root(s) == "output/base"
    assert io_paths.export_excel(s, "fire_intensity", "EGY_V1") == \
        "output/export/results/EGY_V1/excel/EGY_V1_fire_intensity_2026-07-28.xlsx"
    assert io_paths.upscale_admin0_csv(s, "river_flood_100yr") == \
        "output/upscale/global_admin0/river_flood_100yr_2026-07-28.csv"
    assert io_paths.upscale_country_admin1(s, "EGY_V1", "wide") == \
        "output/upscale/results_admin1/EGY_V1/EGY_V1_admin1_wide_2026-07-28.csv"


def test_io_paths_remote_preserves_scheme():
    s = Settings(storage_root="abfs://gchd/prod", prod_date="2026-07-28")
    p = io_paths.base_global_csv(s, "river_flood_100yr")
    assert p == "abfs://gchd/prod/base/global/river_flood_100yr_2026-07-28.csv"
    assert io_paths.is_remote(s) is True
    assert io_paths.is_remote(Settings(storage_root="output")) is False


def test_io_paths_sdmx_streams():
    s = Settings(storage_root="output", prod_date="2026-07-28")
    assert io_paths.export_sdmx_csv(s, "population").endswith("HAZARD_SDMX_2026-07-28.csv")
    assert "exposure_river_flood_100yr" in io_paths.export_sdmx_csv(s, "exposure", "river_flood_100yr")
    try:
        io_paths.export_sdmx_csv(s, "bogus")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown SDMX stream")


# -- hazards --------------------------------------------------------------

def test_hazards_load_all():
    s = Settings()
    hz = hazards.load_hazards(s)
    codes = [h.code for h in hz]
    assert "river_flood_100yr" in codes
    assert len(codes) == len(set(codes)), "duplicate hazard codes in list"
    # asset prefix applied
    riv = next(h for h in hz if h.code == "river_flood_100yr")
    assert "projects/unicef-ccri" in riv.asset


def test_hazards_filter_and_missing():
    s = Settings(process_hazards=["river_flood_100yr"])
    hz = hazards.load_hazards(s)
    assert [h.code for h in hz] == ["river_flood_100yr"]
    try:
        hazards.load_hazards(Settings(process_hazards=["does_not_exist"]))
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown hazard code")


def test_hazards_dedup_drops_twins():
    s = Settings()
    full = {h.code for h in hazards.load_hazards(s)}
    unique = {h.code for h in hazards.unique_count_hazards(s)}
    assert "earthquake_pga_0p34" in full
    assert "earthquake_pga_0p34" not in unique  # twin dropped
    assert "earthquake_pga_0p09" in unique       # source kept
    assert len(full) - len(unique) == len(hazards.DUPLICATE_COUNT_OF)


# -- na_rules -------------------------------------------------------------

def test_na_rules_categories_populated():
    r = na_rules.load_na_rules()
    assert "ALA_V1" in r.non_official
    assert len(r.non_official) > 0
    assert len(r.sovereignty_unsettled) > 0


def test_na_rules_spei_spi_only_for_drought():
    r = na_rules.load_na_rules()
    base = r.excluded_for("river_flood_100yr")
    drought = r.excluded_for("drought_spi_tc")
    # drought adds the SPEI/SPI-specific exclusions on top
    assert r.spei_spi_insufficient <= drought
    assert (drought - base) == (r.spei_spi_insufficient - base)


def test_na_rules_status_precedence():
    r = na_rules.load_na_rules()
    assert r.status_for("ALA_V1", "river_flood_100yr") == "Non-official"
    # a normal state ucode returns None
    assert r.status_for("__definitely_not_a_ucode__", "river_flood_100yr") is None


if __name__ == "__main__":
    # Minimal runner so this works without pytest installed.
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} foundation tests passed.")
