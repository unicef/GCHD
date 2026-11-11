"""Country filter resolution and the s01 resume key. No Earth Engine. Run:
    ..\..\.venv\Scripts\python.exe tests/test_countries.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.countries import resolve
from pipeline.steps.s01 import partial_ucode

AVAILABLE = ["AUS1_V1", "AUS_V1", "BES1_V2", "BES2_V2", "BES3_V2", "EGY1_V1", "EGY_V1", "MWI_V1"]


def test_no_filter_means_all():
    assert resolve(None) is None
    assert resolve(None, AVAILABLE) == AVAILABLE


def test_ucodes_pass_through_in_available_order():
    assert resolve(["MWI_V1", "EGY_V1"], AVAILABLE) == ["EGY_V1", "MWI_V1"]


def test_iso3_expands_to_every_ucode():
    assert resolve(["EGY"]) == ["EGY1_V1", "EGY_V1"]
    assert resolve(["BES"], AVAILABLE) == ["BES1_V2", "BES2_V2", "BES3_V2"]


def test_mixed_iso3_and_ucode():
    assert resolve(["AUS", "MWI_V1"], AVAILABLE) == ["AUS1_V1", "AUS_V1", "MWI_V1"]


def test_unavailable_ucode_is_dropped_against_the_ee_list():
    # e.g. a no-population country removed by get_countries_to_process
    assert resolve(["ATA_V1"], AVAILABLE) == []


def test_unknown_code_raises():
    try:
        resolve(["EGYPT"])
    except ValueError as e:
        assert "EGYPT" in str(e)
        return
    raise AssertionError("expected ValueError for an unknown code")


def test_partial_ucode_handles_long_ucodes():
    # The old key, name[:6], gave "BES1_V" and "AUS1_V", so these were never resumed.
    assert partial_ucode("CAN_V1_landslides_0p1_admin2.csv", "landslides_0p1") == "CAN_V1"
    assert partial_ucode("BES1_V2_landslides_0p1_admin2.csv", "landslides_0p1") == "BES1_V2"
    assert partial_ucode("AUS1_V1_river_flood_100yr_admin2.csv", "river_flood_100yr") == "AUS1_V1"


def test_partial_ucode_ignores_other_files():
    assert partial_ucode("CAN_V1_other_hazard_admin2.csv", "landslides_0p1") is None
    assert partial_ucode("notes.txt", "landslides_0p1") is None


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} country tests passed.")
