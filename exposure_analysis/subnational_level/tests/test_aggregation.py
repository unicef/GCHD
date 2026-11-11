"""Tests for the admin2 -> admin1/admin0 aggregation stage (notebooks 06/07).

Pure, no Earth Engine / no network. Run from the subnational_level dir:
    ..\\..\\.venv\\Scripts\\python.exe -m pytest tests -q
or without pytest:
    ..\\..\\.venv\\Scripts\\python.exe tests/test_aggregation.py

Covers the weighted pooling maths, the weight-table join and its fallback, and
the conservation/containment invariants the admin1 summary must satisfy.

Includes regression tests for two production defects (2026-09):
  * zero total weight silently blanking hazs_mean at admin1
  * the counts table being missing, silently switching the whole run to
    population weighting
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import aggregation_functions as agg


# -- helpers --------------------------------------------------------------

def _adm2_frame(rows):
    """Build a minimal admin2 frame with the columns aggregate_counts needs."""
    base = dict(iso3="EGY", adm0_id=284, adm0_name="Egypt", adm0_ucode="EGY_V1",
                adm1_name="Test", unicef_region="UNICEF_MENARO",
                unicef_region_full="Middle East and North Africa", status="")
    out = []
    for r in rows:
        rec = dict(base)
        rec.update(r)
        for c in agg.COUNT_COLS:
            rec.setdefault(c, 0.0)
        out.append(rec)
    return pd.DataFrame(out)


# -- pooled mean / std ----------------------------------------------------

def test_weighted_mean_is_weight_weighted():
    """Two children, 3:1 weight -> mean pulled toward the heavier child."""
    m, _ = agg._weighted_mean_std(
        pd.Series([10.0, 20.0]), pd.Series([0.0, 0.0]), pd.Series([300, 100]))
    assert abs(m - 12.5) < 1e-9


def test_weighted_mean_equal_weights_is_simple_mean():
    m, _ = agg._weighted_mean_std(
        pd.Series([1.0, 2.0, 6.0]), pd.Series([0.0, 0.0, 0.0]),
        pd.Series([50, 50, 50]))
    assert abs(m - 3.0) < 1e-9


def test_pooled_std_recovers_known_variance():
    """Pooling two halves of a known sample reproduces its population std."""
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.array([10.0, 12.0])
    whole = np.concatenate([a, b])
    m, s = agg._weighted_mean_std(
        pd.Series([a.mean(), b.mean()]),
        pd.Series([a.std(ddof=0), b.std(ddof=0)]),
        pd.Series([len(a), len(b)]))
    assert abs(m - whole.mean()) < 1e-9
    assert abs(s - whole.std(ddof=0)) < 1e-9


def test_pooled_std_zero_when_children_identical():
    _, s = agg._weighted_mean_std(
        pd.Series([5.0, 5.0]), pd.Series([0.0, 0.0]), pd.Series([10, 90]))
    assert abs(s) < 1e-12


def test_zero_total_weight_yields_nan_not_zero():
    """REGRESSION: a zero-weight unit must be NaN, never a fabricated 0.0.

    A 0.0 would read as 'measured, and the hazard is absent', which is a
    different claim from 'no valid pixels to average over'.
    """
    m, s = agg._weighted_mean_std(
        pd.Series([3.0, 4.0]), pd.Series([0.1, 0.1]), pd.Series([0, 0]))
    assert np.isnan(m) and np.isnan(s)


def test_children_with_zero_weight_are_excluded():
    """A zero-weight child must not drag the mean toward its value."""
    m, _ = agg._weighted_mean_std(
        pd.Series([10.0, 999.0]), pd.Series([0.0, 0.0]), pd.Series([100, 0]))
    assert abs(m - 10.0) < 1e-9


def test_nan_mean_child_is_ignored():
    m, _ = agg._weighted_mean_std(
        pd.Series([10.0, np.nan]), pd.Series([0.0, 0.0]), pd.Series([100, 100]))
    assert abs(m - 10.0) < 1e-9


# -- weight table join ----------------------------------------------------

def test_weight_join_attaches_counts():
    df = pd.DataFrame({"adm2_ucode": ["A", "B"]})
    counts = pd.DataFrame({"adm2_ucode": ["A", "B"],
                           "hazard_code": ["h", "h"],
                           "hazs_count": [10, 20]})
    out = agg.weight_table_join(df, counts, "h")
    assert list(out["hazs_count"]) == [10, 20]


def test_weight_join_without_table_leaves_nan():
    """No counts table -> hazs_count all NaN, so the caller falls back to pop."""
    df = pd.DataFrame({"adm2_ucode": ["A", "B"]})
    out = agg.weight_table_join(df, None, "h")
    assert out["hazs_count"].isna().all()


def test_weight_join_only_matches_same_hazard():
    """Counts for another hazard must not leak into this one."""
    df = pd.DataFrame({"adm2_ucode": ["A"]})
    counts = pd.DataFrame({"adm2_ucode": ["A"], "hazard_code": ["other"],
                           "hazs_count": [99]})
    out = agg.weight_table_join(df, counts, "h")
    assert out["hazs_count"].isna().all()


# -- aggregate_counts -----------------------------------------------------

def test_aggregate_prefers_count_over_population():
    """With hazs_count present the mean is count-weighted, not pop-weighted.

    Counts and population are deliberately opposed here: pop weighting would
    give 15.0, count weighting 5.5.
    """
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=5.0, hazs_std=0.0,
             hazs_min=5.0, hazs_max=5.0, pop_total=10, hazs_count=900),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=55.0, hazs_std=0.0,
             hazs_min=55.0, hazs_max=55.0, pop_total=990, hazs_count=100),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert abs(out.loc[0, "hazs_mean"] - 10.0) < 1e-9


def test_aggregate_falls_back_to_population_per_row():
    """A row with no count uses its population; a row with a count uses that."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=10.0, hazs_std=0.0,
             hazs_min=10.0, hazs_max=10.0, pop_total=300, hazs_count=np.nan),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=20.0, hazs_std=0.0,
             hazs_min=20.0, hazs_max=20.0, pop_total=999, hazs_count=100),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert abs(out.loc[0, "hazs_mean"] - 12.5) < 1e-9


def test_aggregate_min_max_span_children():
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=3.0, hazs_std=0.0,
             hazs_min=1.0, hazs_max=4.0, pop_total=10, hazs_count=10),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=7.0, hazs_std=0.0,
             hazs_min=2.0, hazs_max=9.0, pop_total=10, hazs_count=10),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert out.loc[0, "hazs_min"] == 1.0
    assert out.loc[0, "hazs_max"] == 9.0


def test_aggregate_mean_within_child_range():
    """A weighted mean can never fall outside the children's own means."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=2.5, hazs_std=0.3,
             hazs_min=2.0, hazs_max=3.0, pop_total=100, hazs_count=1234),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=8.5, hazs_std=0.4,
             hazs_min=8.0, hazs_max=9.0, pop_total=100, hazs_count=99),
        dict(adm1_ucode="A1", adm2_ucode="c", hazs_mean=5.0, hazs_std=0.2,
             hazs_min=4.0, hazs_max=6.0, pop_total=100, hazs_count=500),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert 2.5 <= out.loc[0, "hazs_mean"] <= 8.5


def test_aggregate_conserves_population_and_exposure():
    """Summed children == parent, for every count column."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=1.0, hazs_std=0.0,
             hazs_min=1.0, hazs_max=1.0, pop_total=100, u18_pop_total=40,
             aexp=60, u18_aexp=25, hazs_count=10),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=1.0, hazs_std=0.0,
             hazs_min=1.0, hazs_max=1.0, pop_total=250, u18_pop_total=90,
             aexp=110, u18_aexp=44, hazs_count=10),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert out.loc[0, "pop_total"] == 350
    assert out.loc[0, "u18_pop_total"] == 130
    assert out.loc[0, "aexp"] == 170
    assert out.loc[0, "u18_aexp"] == 69


def test_flagged_rows_excluded_from_hazard_stats_only():
    """A flagged row must not pollute hazs_mean, but its people still count.

    REGRESSION (2026-09): the original filter was a single
    ``df[df.status == ""]``, which dropped flagged rows from the population
    sums too. That shrank the denominator per hazard — 10.2M people in Egypt
    for river flood, 16.2 billion person-rows globally — and inflated every
    relative-exposure and index value downstream. Population is a property of
    the PLACE, not of the hazard, so it must survive the flag.
    """
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=10.0, hazs_std=0.0,
             hazs_min=10.0, hazs_max=10.0, pop_total=100, aexp=50,
             hazs_count=10),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=999.0, hazs_std=0.0,
             hazs_min=999.0, hazs_max=999.0, pop_total=100, aexp=50,
             hazs_count=10, status=agg.NO_DATA_STATUS),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    # the flagged child's hazard value is ignored...
    assert abs(out.loc[0, "hazs_mean"] - 10.0) < 1e-9
    assert out.loc[0, "hazs_max"] == 10.0
    # ...but its population is NOT lost
    assert out.loc[0, "pop_total"] == 200


def test_no_data_row_contributes_zero_exposure_not_null():
    """A No Data unit has null exposure in the source; it aggregates as 0."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=np.nan, hazs_std=np.nan,
             hazs_min=np.nan, hazs_max=np.nan, pop_total=500, aexp=np.nan,
             hazs_count=0, status=agg.NO_DATA_STATUS),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert out.loc[0, "pop_total"] == 500
    assert out.loc[0, "aexp"] == 0.0
    assert pd.isna(out.loc[0, "hazs_mean"])


def test_population_is_invariant_across_hazards():
    """The core invariant: the same unit reports the same population for every
    hazard, regardless of how many of its children are flagged."""
    totals = set()
    for n_flagged in (0, 1, 2, 3):
        rows = []
        for i in range(4):
            flagged = i < n_flagged
            rows.append(dict(
                adm1_ucode="A1", adm2_ucode=f"a{i}",
                hazs_mean=np.nan if flagged else 5.0,
                hazs_std=0.0, hazs_min=np.nan if flagged else 5.0,
                hazs_max=np.nan if flagged else 5.0,
                pop_total=100, aexp=np.nan if flagged else 10,
                hazs_count=0 if flagged else 10,
                status=agg.NO_DATA_STATUS if flagged else "",
            ))
        out = agg.aggregate_counts(_adm2_frame(rows), "adm1_ucode")
        totals.add(float(out.loc[0, "pop_total"]))
    assert totals == {400.0}, f"population varied by flag count: {totals}"


def test_admin1_never_vanishes_when_all_children_flagged():
    """An admin1 whose children are all No Data must still appear, carrying its
    population — it must not drop out of the output entirely (821 admin1 units
    disappeared from river flood under the original filter)."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=np.nan, hazs_std=np.nan,
             hazs_min=np.nan, hazs_max=np.nan, pop_total=7000, aexp=np.nan,
             hazs_count=0, status=agg.NO_DATA_STATUS),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert len(out) == 1
    assert out.loc[0, "pop_total"] == 7000
    assert out.loc[0, "n_admin2_covered"] == 0
    assert out.loc[0, "n_children"] == 1


def test_coverage_is_two_adjacent_unit_counts():
    """Coverage is n_admin2_covered out of n_children -- counts, not an area %.

    No area-share percentage is emitted: it cannot be read the same way for
    two hazards (river flood's floodplain is ~1.8% of land by nature, heatwave
    is ~100%), so publishing them side by side invites a reader to dismiss a
    sound flood statistic as "poorly covered". The two counts must also sit
    ADJACENT -- n_admin2_covered alone is meaningless without its total.
    """
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=5.0, hazs_std=0.0,
             hazs_min=5.0, hazs_max=5.0, pop_total=100, aexp=10, hazs_count=25),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=np.nan, hazs_std=np.nan,
             hazs_min=np.nan, hazs_max=np.nan, pop_total=100, aexp=np.nan,
             hazs_count=0, status=agg.NO_DATA_STATUS),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert out.loc[0, "n_admin2_covered"] == 1
    assert out.loc[0, "n_children"] == 2
    for gone in ("pct_area_covered", "hazs_pixels", "land_pixels",
                 "admin2_coverage", "n_admin2_total", "hazard_extent_type"):
        assert gone not in out.columns, gone
    cols = list(out.columns)
    assert abs(cols.index("n_admin2_covered") - cols.index("n_children")) == 1,         "coverage count and its total must be adjacent"


def test_blocked_countries_produce_no_rows():
    """POP_BLANK_COUNTRIES get no summary at any level."""
    blocked = agg.POP_BLANK_COUNTRIES[0]
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=5.0, hazs_std=0.0,
             hazs_min=5.0, hazs_max=5.0, pop_total=100, hazs_count=10),
    ])
    df["adm0_ucode"] = blocked
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert out.empty


def test_population_reference_overrides_blanked_population():
    """apply_population_reference fills population the hazard table blanked."""
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=5.0, hazs_std=0.0,
             hazs_min=5.0, hazs_max=5.0, pop_total=np.nan, aexp=np.nan,
             hazs_count=0, status="Insufficient Data"),
    ])
    ref = pd.DataFrame({"adm2_ucode": ["a"], "pop_total": [1234.0]})
    filled = agg.apply_population_reference(df, ref)
    assert filled.loc[0, "pop_total"] == 1234.0
    out = agg.aggregate_counts(filled, "adm1_ucode")
    assert out.loc[0, "pop_total"] == 1234.0
    # suppressed unit still yields no hazard statistic
    assert pd.isna(out.loc[0, "hazs_mean"])


def test_aggregate_returns_units_in_pcode_order():
    """Rows come back ordered by the grouping ucode.

    COs read the long CSV and both workbooks side by side, so the admin1
    sequence must be identical in every output and stable across production
    dates. groupby() sorts by key, which gives pcode order for free — this test
    pins that guarantee so a future refactor cannot quietly reorder the rows.
    """
    df = _adm2_frame([
        dict(adm1_ucode="A_0003_V1", adm2_ucode="c", hazs_mean=1.0, hazs_std=0.0,
             hazs_min=1.0, hazs_max=1.0, pop_total=10, hazs_count=1),
        dict(adm1_ucode="A_0001_V1", adm2_ucode="a", hazs_mean=9.0, hazs_std=0.0,
             hazs_min=9.0, hazs_max=9.0, pop_total=10, hazs_count=1),
        dict(adm1_ucode="A_0002_V1", adm2_ucode="b", hazs_mean=5.0, hazs_std=0.0,
             hazs_min=5.0, hazs_max=5.0, pop_total=10, hazs_count=1),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    got = list(out["adm1_ucode"])
    assert got == sorted(got) == ["A_0001_V1", "A_0002_V1", "A_0003_V1"], got


def test_validate_population_totals_catches_hazard_variation():
    """The validator must flag a frame where population differs by hazard."""
    long = pd.DataFrame([
        dict(adm1_ucode="A1", hazard_code="h1", pop_total=100.0),
        dict(adm1_ucode="A1", hazard_code="h2", pop_total=90.0),
    ])
    problems = agg.validate_population_totals(long, reference=None)
    assert not problems.empty
    assert (problems["check"] == "varies_by_hazard").any()


def test_validate_population_totals_passes_when_consistent():
    long = pd.DataFrame([
        dict(adm1_ucode="A1", hazard_code="h1", pop_total=100.0),
        dict(adm1_ucode="A1", hazard_code="h2", pop_total=100.0),
    ])
    ref = pd.DataFrame([dict(adm1_ucode="A1", adm2_ucode="a", pop_total=100.0)])
    assert agg.validate_population_totals(long, reference=ref).empty


def test_aggregate_groups_are_independent():
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=10.0, hazs_std=0.0,
             hazs_min=10.0, hazs_max=10.0, pop_total=100, hazs_count=10),
        dict(adm1_ucode="A2", adm2_ucode="b", hazs_mean=20.0, hazs_std=0.0,
             hazs_min=20.0, hazs_max=20.0, pop_total=100, hazs_count=10),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode").set_index("adm1_ucode")
    assert abs(out.loc["A1", "hazs_mean"] - 10.0) < 1e-9
    assert abs(out.loc["A2", "hazs_mean"] - 20.0) < 1e-9


def test_all_children_zero_weight_blanks_the_parent():
    """REGRESSION (2026-09, Egypt): the mosaic nominalScale() bug zeroed every
    hazs_count in a governorate, and the admin1 mean silently went blank.

    The blank itself is correct behaviour given zero weight — this pins it so a
    future change cannot turn it into a fabricated 0.0, and documents the shape
    of the failure the pixel-count fix removes upstream.
    """
    df = _adm2_frame([
        dict(adm1_ucode="A1", adm2_ucode="a", hazs_mean=4.2, hazs_std=0.5,
             hazs_min=0.1, hazs_max=15.4, pop_total=0, aexp=1_036_180,
             hazs_count=0),
        dict(adm1_ucode="A1", adm2_ucode="b", hazs_mean=3.9, hazs_std=0.4,
             hazs_min=0.1, hazs_max=12.9, pop_total=0, aexp=2_499_106,
             hazs_count=0),
    ])
    out = agg.aggregate_counts(df, "adm1_ucode")
    assert np.isnan(out.loc[0, "hazs_mean"])
    # Exposure still aggregates: it is summed, not weighted.
    assert out.loc[0, "aexp"] == 3_535_286


# -- counts table loading -------------------------------------------------

def test_load_counts_table_missing_path_returns_none():
    """REGRESSION: COUNTS_TABLE is a relative path. When it does not resolve,
    load_counts_table returns None and the whole run silently falls back to
    population weighting — the July 2026 failure. Callers must check.
    """
    assert agg.load_counts_table("output/aux/does_not_exist.csv") is None
    assert agg.load_counts_table(None) is None


def test_load_counts_table_drops_duplicate_rows(tmp_path=None):
    """Duplicate (adm2_ucode, hazard_code) rows would fan out the join and
    inflate every summed count downstream."""
    import tempfile, os
    d = tempfile.mkdtemp()
    p = os.path.join(d, "counts.csv")
    pd.DataFrame({
        "adm2_ucode": ["A", "A", "B"],
        "hazard_code": ["h", "h", "h"],
        "hazs_count": [5, 5, 7],
    }).to_csv(p, index=False)
    try:
        t = agg.load_counts_table(p)
        assert len(t) == 2
        assert not t.duplicated(subset=["adm2_ucode", "hazard_code"]).any()
    finally:
        os.remove(p)
        os.rmdir(d)


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
