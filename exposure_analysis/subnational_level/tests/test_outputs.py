"""Data-quality checks on produced admin1 summaries and count tables.

These validate real output files rather than pure functions, so they SKIP
cleanly when the files are absent (CI, a fresh clone, a country not yet run).
Point them at a run with:

    set GCHD_ADM1_LONG=<path to *_admin1_long_<date>.csv>
    set GCHD_COUNTS_TABLE=<path to hazs_count_<date>.csv>
    ..\\..\\.venv\\Scripts\\python.exe tests/test_outputs.py

With no env vars set they auto-discover the newest admin1 long CSV under the
default results tree.

These are the checks that would have caught the 2026-09 Egypt regressions in
the output rather than in the code: blank hazard means, and a weight table
whose counts have collapsed to near-zero.
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = ROOT / "notebooks" / "output" / "results_admin1"

# A hazard whose weights collapsed reads as a tiny national pixel total.
# Egypt's broken river-flood table summed to 20 across 411 districts.
MIN_PIXELS_PER_UNIT = 1.0
# genuinely sparse: the source raster has data in 1 of the country's units
SPARSE_COVERAGE = {
    ("TUV", "air_pollution_pm25"),  # PM2.5 raster misses the atolls: 2 pixels, 1 of 28 units
}


def _find_long_csv():
    p = os.environ.get("GCHD_ADM1_LONG")
    if p:
        return p if os.path.exists(p) else None
    hits = glob.glob(str(DEFAULT_RESULTS / "**" / "*_admin1_long_*.csv"),
                     recursive=True)
    return max(hits, key=os.path.getmtime) if hits else None


def _find_counts_table():
    p = os.environ.get("GCHD_COUNTS_TABLE")
    if p:
        return p if os.path.exists(p) else None
    hits = glob.glob(str(ROOT / "notebooks" / "output" / "aux" / "hazs_count_*.csv"))
    return max(hits, key=os.path.getmtime) if hits else None


def _skip(what):
    msg = f"no {what} found; set the env var to run this check"
    try:
        import pytest
        pytest.skip(msg)
    except ImportError:
        print(f"  SKIP  {msg}")
    return True


# -- admin1 long output ---------------------------------------------------

def test_no_blank_hazard_means_where_hazard_exists():
    """REGRESSION (2026-09): 44 Egypt admin1 means were blank while the unit
    had real exposure. A blank is only legitimate when there is no hazard at
    all (hazs_max == 0 and aexp == 0).
    """
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    if "hazs_mean" not in df.columns:
        return _skip("hazs_mean column")

    blank = df[df["hazs_mean"].isna()]
    suspicious = blank[(blank.get("hazs_max", 0).fillna(0) > 0)
                       | (blank.get("aexp", 0).fillna(0) > 0)]
    assert suspicious.empty, (
        f"{len(suspicious)} admin1 rows have a blank hazs_mean despite a "
        f"hazard footprint, in {os.path.basename(p)}:\n"
        + suspicious[["hazard_code", "adm1_name"]].head(10).to_string(index=False))


def test_mean_lies_within_min_and_max():
    """A mean outside [min, max] means the stats came from different pixel
    sets — the signature of a scale or join mismatch."""
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    need = {"hazs_mean", "hazs_min", "hazs_max"}
    if not need <= set(df.columns):
        return _skip("hazs_* columns")
    d = df.dropna(subset=list(need))
    bad = d[(d.hazs_mean < d.hazs_min - 1e-6)
            | (d.hazs_mean > d.hazs_max + 1e-6)]
    assert bad.empty, f"{len(bad)} rows have hazs_mean outside [min, max]"


def test_exposure_never_exceeds_population():
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    if not {"aexp", "pop_total"} <= set(df.columns):
        return _skip("exposure columns")
    d = df.dropna(subset=["aexp", "pop_total"])
    bad = d[d.aexp > d.pop_total + 1]
    assert bad.empty, f"{len(bad)} rows have exposed > total population"


def test_child_population_never_exceeds_total():
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    if not {"u18_pop_total", "pop_total"} <= set(df.columns):
        return _skip("population columns")
    d = df.dropna(subset=["u18_pop_total", "pop_total"])
    bad = d[d.u18_pop_total > d.pop_total + 1]
    assert bad.empty, f"{len(bad)} rows have child > total population"


def test_population_within_hazard_footprint_never_exceeds_governorate():
    """`pop_total` is scoped to each hazard's own footprint, so it VARIES by
    hazard for the same unit — this is by design, not a defect.

    (Port Said: 898,637 across the governorate, but 120,568 inside the PM2.5
    layer. Reading the footprint-scoped figure as a governorate total is what
    prompted the 2026-09 query from the Egypt CO.)

    The real invariant is that no hazard's footprint population may exceed the
    unit's own maximum across hazards.
    """
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    if not {"adm1_ucode", "pop_total"} <= set(df.columns):
        return _skip("population columns")
    full = df.groupby("adm1_ucode").pop_total.max()
    merged = df.join(full.rename("unit_max"), on="adm1_ucode")
    bad = merged[merged.pop_total > merged.unit_max + 1]
    assert bad.empty, (
        f"{len(bad)} rows report a footprint population above the unit total")


def test_landslide_thresholds_are_nested():
    """>0.01 is a superset of >0.1, so its exposure can never be smaller.

    REGRESSION: the 2026-08 Egypt file had >0.1 exposure of 605,959 against
    >0.01 of 0 — the column-shift symptom that first flagged the run.
    """
    p = _find_long_csv()
    if not p:
        return _skip("admin1 long CSV")
    df = pd.read_csv(p)
    if "hazard_code" not in df.columns or "aexp" not in df.columns:
        return _skip("hazard columns")
    strict = df[df.hazard_code == "landslides_0p1"].set_index("adm1_ucode").aexp
    loose = df[df.hazard_code == "landslides_0p01"].set_index("adm1_ucode").aexp
    if strict.empty or loose.empty:
        return _skip("landslide rows")
    common = strict.index.intersection(loose.index)
    bad = [u for u in common if loose[u] + 1 < strict[u]]
    assert not bad, (
        f"{len(bad)} units have landslide >0.01 exposure BELOW >0.1, which is "
        f"impossible: {bad[:5]}")


# -- counts table ---------------------------------------------------------

def test_counts_table_has_no_duplicate_keys():
    p = _find_counts_table()
    if not p:
        return _skip("counts table")
    t = pd.read_csv(p)
    dups = t.duplicated(subset=["adm2_ucode", "hazard_code"]).sum()
    assert dups == 0, (
        f"{dups} duplicate (adm2_ucode, hazard_code) rows in "
        f"{os.path.basename(p)} — these fan out the join and inflate sums")


def test_counts_are_not_degenerate_for_present_hazards():
    """REGRESSION: the mosaic scale bug left national pixel totals in the tens
    across hundreds of districts. Any hazard with SOME coverage should average
    at least ~1 pixel per admin2 unit.
    """
    p = _find_counts_table()
    if not p:
        return _skip("counts table")
    t = pd.read_csv(p)
    t["iso"] = t.adm2_ucode.str.split("_").str[0]

    degenerate = []
    for (iso, hz), g in t.groupby(["iso", "hazard_code"]):
        total = pd.to_numeric(g.hazs_count, errors="coerce").fillna(0).sum()
        if total == 0 or (iso, hz) in SPARSE_COVERAGE:
            continue           # genuinely absent or sparse hazard — legitimate
        if total / len(g) < MIN_PIXELS_PER_UNIT:
            degenerate.append((iso, hz, total, len(g)))

    assert not degenerate, (
        f"{len(degenerate)} country/hazard pairs have a non-zero but "
        f"implausibly small pixel count (<{MIN_PIXELS_PER_UNIT}/unit), the "
        f"signature of a wrong reduction scale. First few: {degenerate[:5]}")


if __name__ == "__main__":
    lp, cp = _find_long_csv(), _find_counts_table()
    print(f"admin1 long : {lp or '(none found)'}")
    print(f"counts table: {cp or '(none found)'}\n")
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}:\n        {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {name}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
