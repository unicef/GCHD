"""Unit tests for s05 SDMX frame building — pure pandas, no EE, no I/O.

Run:  ..\..\.venv\Scripts\python.exe tests/test_s05_sdmx.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.steps.s05 import (
    build_stream_frames, _sex_age,
    HAZARDS_VARIABLE, EXPOSURE_VARIABLES, POPULATION_VARIABLES,
)

HAZARD = SimpleNamespace(code="river_flood_100yr", indicator="RIVER_FLOOD", name="Riverine flood")


def _fixture(n=3):
    """A tiny global-CSV-like frame with the columns s05 reads."""
    cols = {
        "adm2_ucode": [f"EGY_{i:04d}" for i in range(n)],
        "iso3": ["EGY"] * n,
        "unicef_region": ["MENA"] * n,
        "status": [""] * n,
    }
    # every hazard/exposure/population value column referenced by the maps
    for c in list(HAZARDS_VARIABLE) + list(EXPOSURE_VARIABLES) + list(POPULATION_VARIABLES):
        cols[c] = list(np.arange(n, dtype=float))
    return pd.DataFrame(cols)


def test_sex_age_derivation():
    assert _sex_age("aexp") == ("_T", "_T")
    assert _sex_age("afexp") == ("F", "_T")
    assert _sex_age("amexp") == ("M", "_T")
    assert _sex_age("u18_aexp") == ("_T", "Y0T17")
    assert _sex_age("u18_afexp") == ("F", "Y0T17")


def test_streams_shapes_and_population_toggle():
    df = _fixture(n=3)
    frames = build_stream_frames(df, HAZARD, time_period="2026", is_draft=True, with_population=True)
    # hazard rows = n * #hazard vars
    assert len(frames["hazard"]) == 3 * len(HAZARDS_VARIABLE)
    assert len(frames["exposure"]) == 3 * len(EXPOSURE_VARIABLES)
    assert len(frames["population"]) == 3 * len(POPULATION_VARIABLES)

    # without population
    frames2 = build_stream_frames(df, HAZARD, time_period="2026", is_draft=True, with_population=False)
    assert "population" not in frames2


def test_draft_dataflow_and_indicator():
    df = _fixture(n=1)
    draft = build_stream_frames(df, HAZARD, time_period="2026", is_draft=True, with_population=False)
    live = build_stream_frames(df, HAZARD, time_period="2027", is_draft=False, with_population=False)
    assert draft["hazard"]["DATAFLOW"].iloc[0] == "UNICEF_DRAFT:HAZARD_INTENSITY(1.0)"
    assert live["hazard"]["DATAFLOW"].iloc[0] == "UNICEF:HAZARD_INTENSITY(1.0)"
    assert draft["hazard"]["INDICATOR"].iloc[0] == "HAZARD_RIVER_FLOOD"
    assert draft["exposure"]["INDICATOR"].iloc[0] == "HAZARD_EXPOSURE_RIVER_FLOOD"
    assert live["hazard"]["TIME_PERIOD"].iloc[0] == "2027"


def test_status_and_region_carried_through():
    df = _fixture(n=2)
    df.loc[0, "status"] = "Insufficient Data"
    frames = build_stream_frames(df, HAZARD, time_period="2026", is_draft=True, with_population=False)
    # the first adm2's rows should all carry its status
    first_area = frames["hazard"][frames["hazard"]["REF_AREA"] == "EGY_0000"]
    assert (first_area["STATUS"] == "Insufficient Data").all()
    assert (first_area["REGION"] == "MENA").all()


def test_nan_serializes_to_empty_obs_value():
    # A missing hazs_mean must produce an EMPTY OBS_VALUE in the SDMX CSV (the
    # contract downstream cares about), regardless of whether pandas holds it as
    # None or NaN in memory — building pd.DataFrame from the list re-coerces a
    # None-in-numeric-column back to NaN, and both serialize to "".
    import csv as _csv
    import io as _io

    df = _fixture(n=1)
    df.loc[0, "hazs_mean"] = np.nan
    frames = build_stream_frames(df, HAZARD, time_period="2026", is_draft=True, with_population=False)
    buf = _io.StringIO()
    frames["hazard"].to_csv(buf, index=False, quoting=_csv.QUOTE_MINIMAL)
    buf.seek(0)
    rows = list(_csv.DictReader(buf))
    mean_row = next(r for r in rows if r["MEASURE"] == "HAZARD_MEAN")
    assert mean_row["OBS_VALUE"] == "", f"expected empty, got {mean_row['OBS_VALUE']!r}"


def test_population_reference_overrides_blanked_population():
    """The SDMX population stream must not inherit the first hazard's blanks.

    Population is emitted once, from whichever hazard is processed first. That
    hazard blanks population for the units IT suppresses, so without the
    independent reference the population stream would vary depending on which
    hazard happened to run first.
    """
    from pipeline.steps.s05 import _apply_population_reference

    df = _fixture(n=2)
    df.loc[0, "pop_total"] = np.nan          # blanked by this hazard's status
    df.loc[0, "u18_pop_total"] = np.nan
    ref = pd.DataFrame({
        "adm2_ucode": [df.loc[0, "adm2_ucode"], df.loc[1, "adm2_ucode"]],
        "pop_total": [4321.0, 999.0],
        "pop_under_18_total": [1234.0, 111.0],
    })
    out = _apply_population_reference(df, ref)
    assert out.loc[0, "pop_total"] == 4321.0
    assert out.loc[0, "u18_pop_total"] == 1234.0


def test_population_reference_leaves_exposure_untouched():
    """Only population columns are overridden; exposure must not change."""
    from pipeline.steps.s05 import _apply_population_reference

    df = _fixture(n=1)
    before = {c: df.loc[0, c] for c in df.columns if "exp" in c}
    ref = pd.DataFrame({"adm2_ucode": [df.loc[0, "adm2_ucode"]], "pop_total": [7.0]})
    out = _apply_population_reference(df, ref)
    for c, v in before.items():
        assert (pd.isna(v) and pd.isna(out.loc[0, c])) or out.loc[0, c] == v, c


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} s05 SDMX tests passed.")
