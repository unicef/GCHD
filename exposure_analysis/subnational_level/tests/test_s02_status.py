"""Unit tests for s02 status-rule logic — the two agreed correctness fixes.

Pure pandas, no Earth Engine, no file I/O. Run:
    ..\..\.venv\Scripts\python.exe tests/test_s02_status.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import na_rules
from pipeline.steps.s02 import apply_status_rules

INDICATORS = ["gexpi_total", "cexpi_total", "gindex", "hazs_mean"]


def _row(ucode, **kw):
    base = {"adm0_ucode": ucode, "adm2_ucode": f"{ucode}_0001",
            "hazs_mean": 1.0, "exp_total": 10.0,
            "gexpi_total": 5.0, "cexpi_total": 5.0, "gindex": 5.0}
    base.update(kw)
    return base


# -- nb02_status_for precedence -------------------------------------------

def test_status_non_official_is_not_applicable():
    assert na_rules.nb02_status_for("ALA_V1", "river_flood_100yr") == "Not Applicable"


def test_status_sovereignty_is_not_applicable():
    assert na_rules.nb02_status_for("xJK_V1", "fire_intensity") == "Not Applicable"


def test_status_all_hazard_insufficient_includes_cuba():
    # CUB_V2 is in the notebook's all-hazard list (was missing from the CSV).
    assert na_rules.nb02_status_for("CUB_V2", "river_flood_100yr") == "Insufficient Data"
    assert na_rules.nb02_status_for("NIC_V1", "heatwave_frequency") == "Insufficient Data"


def test_status_normal_country_is_none():
    assert na_rules.nb02_status_for("DEU_V1", "river_flood_100yr") is None


# -- THE DEAD-BRANCH FIX --------------------------------------------------

def test_deadbranch_fix_fiji_river_flood_now_fires():
    # Notebook keyed on 'riverine_flood' (never matched real code) → Fiji slipped
    # through. With the real code it MUST be flagged now.
    assert na_rules.nb02_status_for("FJI_V2", "river_flood_100yr") == "Insufficient Data"
    # ...but NOT for an unrelated hazard.
    assert na_rules.nb02_status_for("FJI_V2", "heatwave_frequency") is None


def test_deadbranch_fix_coastal_island_states():
    for u in ["CPV_V2", "MDV_V2", "TUV_V2"]:
        assert na_rules.nb02_status_for(u, "coastal_flood_100yr") == "Insufficient Data"


def test_deadbranch_fix_fire_applies_to_both_fire_hazards():
    assert na_rules.nb02_status_for("MHL_V2", "fire_intensity") == "Insufficient Data"
    assert na_rules.nb02_status_for("MHL_V2", "fire_frequency") == "Insufficient Data"


def test_air_pollution_rule():
    assert na_rules.nb02_status_for("MCO_V1", "air_pollution_pm25") == "Insufficient Data"


# -- s02 does NOT apply SPEI/SPI (agreed scope) ---------------------------

def test_spei_spi_not_applied_by_s02():
    # KIR_V2 is in the CSV's id_countries_spei_spi, but s02 must NOT flag it for
    # the drought hazards (NB02 never had that rule).
    assert na_rules.nb02_status_for("KIR_V2", "drought_spei_tc") is None
    assert na_rules.nb02_status_for("KIR_V2", "drought_spi_tc") is None


# -- apply_status_rules on a DataFrame ------------------------------------

def test_apply_blanks_indicators_and_sets_status():
    df = pd.DataFrame([
        _row("DEU_V1"),                    # normal → status '' kept, numbers intact
        _row("ALA_V1"),                    # non-official → Not Applicable, blanked
        _row("FJI_V2"),                    # dead-branch fix → Insufficient Data, blanked
        _row("CUB_V2"),                    # all-hazard ID → Insufficient Data, blanked
    ])
    out = apply_status_rules(df.copy(), "river_flood_100yr", INDICATORS)

    deu = out[out.adm0_ucode == "DEU_V1"].iloc[0]
    assert deu["status"] == "" and deu["gexpi_total"] == 5.0

    for u, expect in [("ALA_V1", "Not Applicable"),
                      ("FJI_V2", "Insufficient Data"),
                      ("CUB_V2", "Insufficient Data")]:
        r = out[out.adm0_ucode == u].iloc[0]
        assert r["status"] == expect, f"{u}: {r['status']}"
        assert np.isnan(r["gexpi_total"]) and np.isnan(r["gindex"]), f"{u} not blanked"


def test_apply_sets_no_data_for_empty_normal_units():
    df = pd.DataFrame([_row("DEU_V1", hazs_mean=np.nan, exp_total=np.nan)])
    out = apply_status_rules(df.copy(), "river_flood_100yr", INDICATORS)
    assert out.iloc[0]["status"] == "No Data"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} s02 status tests passed.")
