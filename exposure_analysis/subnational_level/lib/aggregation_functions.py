# ============================================================
# Aggregation helpers: roll admin2 hazard-exposure indicators
# up to admin1 / admin0, recomputing exposure inputs so the
# existing IndicatorUtils.compute_* functions can be reused.
# ============================================================
# aggregation_functions.py
#
# Design notes
# ------------
# Counts (population, absolute exposure) are additive and can be summed
# across child admin2 units. Everything derived from them — relative
# exposure, the log transforms, and all indices/classes — must be
# RECOMPUTED from the summed counts, never averaged. hazs_min/max roll up
# via min/max; hazs_mean/std are pixel-count-weighted pooled statistics;
# hazs_median cannot be aggregated and is dropped.

from __future__ import annotations

import glob
import os
import warnings

import numpy as np
import pandas as pd

# Population classes and the compact column names they map to in the
# global CSVs (see IndicatorUtils.get_rename_map). Each class has an
# absolute-exposure column and a population column.
POPULATION_CLASSES = [
    "total", "total_female", "total_male",
    "under_18_total", "under_18_female", "under_18_male",
]

# class -> (absolute exposure column, population column) in the global CSV schema
CLASS_TO_COLS = {
    "total":          ("aexp",      "pop_total"),
    "total_female":   ("afexp",     "pop_total_f"),
    "total_male":     ("amexp",     "pop_total_m"),
    "under_18_total": ("u18_aexp",  "u18_pop_total"),
    "under_18_female":("u18_afexp", "u18_pop_f"),
    "under_18_male":  ("u18_amexp", "u18_pop_m"),
}

# All additive count columns (summed on aggregation).
COUNT_COLS = [c for pair in CLASS_TO_COLS.values() for c in pair]

# Nominal columns carried through, keyed per grouping level.
NOMINAL_ADM1 = ["iso3", "adm0_id", "adm0_name", "adm0_ucode",
                "adm1_name", "adm1_ucode", "unicef_region", "unicef_region_full"]
NOMINAL_ADM0 = ["iso3", "adm0_id", "adm0_name", "adm0_ucode",
                "unicef_region", "unicef_region_full"]


def load_hazard_global(hazard_code: str, prod_date: str, folder: str) -> pd.DataFrame:
    """Load a per-hazard global admin2 CSV, fixing the duplicated
    adm2_name / adm2_ucode columns (keep the populated copy) and coercing
    numeric columns.

    Global CSVs written before the s02 duplicate-column fix ship two
    `adm2_name` and two `adm2_ucode` columns; pandas de-dupes them to
    `adm2_name`/`adm2_name.1` etc. We keep whichever copy is populated and drop
    the other, so both old and newly regenerated files load identically.
    """
    path = os.path.join(folder, f"{hazard_code}_{prod_date}.csv")
    df = pd.read_csv(path, low_memory=False)

    for base in ("adm2_name", "adm2_ucode"):
        dup = f"{base}.1"
        if dup in df.columns:
            # Prefer whichever copy actually carries values: in practice the
            # first is populated and `.1` is empty, but do not assume either way.
            if df[dup].notna().sum() > df[base].notna().sum():
                df[base] = df[dup].where(df[dup].notna(), df[base])
            else:
                df[base] = df[base].where(df[base].notna(), df[dup])
            df = df.drop(columns=[dup])

    numeric = COUNT_COLS + ["hazs_mean", "hazs_std", "hazs_max", "hazs_min", "hazs_median"]
    for c in numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # normalise the status column: treat NaN / whitespace as blank ("usable")
    if "status" not in df.columns:
        df["status"] = ""
    df["status"] = df["status"].fillna("").astype(str).str.strip()

    return df


def recompute_exposure_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """(Re)build the per-class log/relative exposure inputs the exposure
    index consumes, from the absolute-exposure and population counts.

    Matches GEE_functions.add_ratios_pandas exactly:
      {class}_log_exposure    = ln(1 + aexp)
      {class}_log_total       = ln(1 + pop)
      {class}_relative_exposure = aexp / pop * 100   (0 when pop==0 & exp present, NA when missing)
    """
    df = df.copy()

    def log1p_offset(v):
        if pd.isna(v):
            return pd.NA
        return np.log(v + 1) if v > 0 else 0.0

    def percentage(exp, pop):
        if pd.notna(pop) and pd.notna(exp) and pop != 0:
            return exp / pop * 100
        if pd.notna(exp) and pop == 0:
            return 0.0
        return pd.NA

    for pop_class, (exp_col, pop_col) in CLASS_TO_COLS.items():
        exp = pd.to_numeric(df.get(exp_col), errors="coerce")
        pop = pd.to_numeric(df.get(pop_col), errors="coerce")
        df[f"{pop_class}_log_exposure"] = exp.apply(log1p_offset)
        df[f"{pop_class}_log_total"] = pop.apply(log1p_offset)
        df[f"{pop_class}_relative_exposure"] = [
            percentage(e, p) for e, p in zip(exp, pop)
        ]
    return df


def weight_table_join(df: pd.DataFrame, counts_df: pd.DataFrame | None,
                      hazard_code: str) -> pd.DataFrame:
    """Left-join a per-admin2 `hazs_count` weight onto df keyed on adm2_ucode.

    counts_df schema: adm2_ucode, hazard_code, hazs_count.
    When counts_df is None or a unit is missing, `hazs_count` is left NaN and
    the caller falls back to a population weight (with a warning).
    """
    df = df.copy()
    if counts_df is None:
        df["hazs_count"] = np.nan
        return df

    sub = counts_df[counts_df["hazard_code"] == hazard_code][["adm2_ucode", "hazs_count"]]
    df = df.merge(sub, on="adm2_ucode", how="left")
    n_missing = df["hazs_count"].isna().sum()
    if n_missing:
        warnings.warn(
            f"[{hazard_code}] {n_missing} admin2 units missing hazs_count; "
            f"falling back to pop_total weight for those.",
            stacklevel=2,
        )
    return df


def _weighted_mean_std(mean_i, std_i, w_i):
    """Pooled (weight-aggregated) mean and std from per-child mean/std/weight.

    var_agg = sum(w * (std^2 + mean^2)) / sum(w) - mean_agg^2
    Exact when w = pixel count; approximate when w = population.
    Returns (mean_agg, std_agg); NaN when total weight is 0.
    """
    mean_i = pd.to_numeric(mean_i, errors="coerce")
    std_i = pd.to_numeric(std_i, errors="coerce").fillna(0.0)
    w_i = pd.to_numeric(w_i, errors="coerce").fillna(0.0)

    valid = mean_i.notna() & (w_i > 0)
    W = w_i[valid].sum()
    if W <= 0:
        return np.nan, np.nan
    mean_agg = (mean_i[valid] * w_i[valid]).sum() / W
    ex2 = (w_i[valid] * (std_i[valid] ** 2 + mean_i[valid] ** 2)).sum() / W
    var_agg = max(ex2 - mean_agg ** 2, 0.0)
    return mean_agg, np.sqrt(var_agg)


# Status values that suppress a unit's hazard result. Their rows carry a NULL
# population in the hazard tables, so population for these units must come from
# the independent admin2 reference (see `population_reference`) rather than
# from the hazard table, or the denominator silently varies per hazard.
EXCLUDED_STATUSES = ("Insufficient Data", "Not Applicable")

# Countries that receive NO summary at all: non-official territories, disputed
# placeholders, and countries whose population is deliberately left blank in
# this product. Excluded before aggregation, so they never appear in any
# output — unlike EXCLUDED_STATUSES units, whose population IS still counted.
# The `x*_V1` codes are defensive: they are placeholders from an earlier
# boundary vintage and match nothing in the current dataset.
POP_BLANK_COUNTRIES = (
    ["ALA_V1", "CCK_V1", "CXR_V1", "ESH_V1", "GGY_V1", "JEY_V1", "NFK_V1",
     "PCN_V1", "SJM_V1"]
    + ["EGY1_V1", "SDN1_V1", "SSD1_V1", "xAB_V1", "xAC_V1", "xAP_V1", "xJK_V1",
       "xJL_V1", "xPI_V1", "xRI_V1", "xSI_V1", "xSK_V1", "xSR_V1", "xxx_V1"]
    + ["NIC_V1", "PSE_V1", "CUB_V2"]
)

# Status meaning "the hazard raster does not cover this unit". The unit is a
# real, populated place: its population MUST be counted, and its exposure is 0
# (nobody here is known to be exposed). Only the hazard STATISTICS are absent.
NO_DATA_STATUS = "No Data"


def apply_population_reference(df: pd.DataFrame,
                               population_reference: pd.DataFrame) -> pd.DataFrame:
    """Overwrite the hazard table's population columns from the independent
    admin2 population source, keyed on adm2_ucode.

    Population is a property of the PLACE, not of the hazard. The hazard tables
    blank it for ``Insufficient Data`` / ``Not Applicable`` units, and since
    each hazard flags a different set, sourcing population from them makes the
    denominator drift per hazard (24.2M globally). Taking it from one reference
    instead makes every hazard report identical totals — the same approach
    notebook 05 already uses to keep the SDMX population stream collision-free.

    Only population columns are touched; exposure columns are left alone, so a
    suppressed unit keeps its blank exposure while contributing its people.

    `population_reference` schema: ``adm2_ucode`` + the pop columns of
    CLASS_TO_COLS (``pop_total``, ``pop_total_f``, ...). ``admin2_population.csv``
    ships the GEE-native names (``pop_total_female``); both spellings are read.
    """
    df = df.copy()
    ref = population_reference.drop_duplicates(subset=["adm2_ucode"], keep="first")

    # admin2_population.csv uses the GEE-native class names; the global hazard
    # CSVs use the compact schema. Map one onto the other.
    alias = {
        "pop_total": ["pop_total"],
        "pop_total_f": ["pop_total_f", "pop_total_female"],
        "pop_total_m": ["pop_total_m", "pop_total_male"],
        "u18_pop_total": ["u18_pop_total", "pop_under_18_total"],
        "u18_pop_f": ["u18_pop_f", "pop_under_18_female"],
        "u18_pop_m": ["u18_pop_m", "pop_under_18_male"],
    }
    for target, candidates in alias.items():
        src = next((c for c in candidates if c in ref.columns), None)
        if src is None or target not in df.columns:
            continue
        mapping = ref.set_index("adm2_ucode")[src]
        filled = df["adm2_ucode"].map(mapping)
        # Reference wins wherever it has a value; keep the hazard table's value
        # only where the reference is silent (so a unit is never blanked).
        df[target] = pd.to_numeric(filled, errors="coerce").where(
            filled.notna(), pd.to_numeric(df[target], errors="coerce")
        )
    return df


def aggregate_counts(df: pd.DataFrame, group_col: str,
                     exclude_countries: list[str] | None = None) -> pd.DataFrame:
    """Aggregate admin2 rows to `group_col` (adm1_ucode or adm0_ucode).

    Two-tier row selection — this distinction is the whole point of this
    function, and collapsing it is a correctness bug (see below):

    * ``Insufficient Data`` / ``Not Applicable`` rows are dropped entirely.
      These carry no population (verified: 0 across all 22 hazards), so they
      contribute to neither numerator nor denominator.
    * ``No Data`` rows are KEPT for every count column. The hazard raster does
      not cover the unit, but people live there: their population belongs in
      the denominator and their exposure is a true 0. These rows are excluded
      only from the hazard-statistic pooling (hazs_mean/std/min/max), because
      they have no hazard value to contribute.

    Why this matters: a single ``df[df.status == ""]`` filter drops No Data
    rows from the population sums too, which silently shrinks the denominator
    per hazard. That defect removed 16.2 billion person-rows globally — 10.2M
    in Egypt for river flood alone (117,477,477 -> 107,276,368), inflating
    every relative-exposure and index value, and making 821 admin1 units
    vanish outright. Regression-guarded by ``validate_population_totals`` and
    ``tests/test_aggregation.py``.

    Counts (pop_*, *exp*) are summed over kept rows; hazs_min/max via min/max
    and hazs_mean/std via count-weighted pooling over COVERED rows only
    (weight priority: hazs_count -> pop_total); hazs_median is dropped.

    Coverage is reported as a COUNT OF UNITS, so a consumer can judge whether
    hazs_mean/std/min/max rest on enough of the parent:

    ``n_admin2_covered``   admin2 children that have hazard data
    ``n_children``         admin2 children counted (covered + No Data). NB06/07
                           rename this to ``n_admin2``, the name the display
                           layer (config/column_labels.json) knows.

    Read them together — "21 of 47". They must sit ADJACENT in every output;
    ``n_admin2_covered`` alone is meaningless without its total.

    No area-share percentage is emitted, deliberately. A "% of land covered"
    figure cannot be read the same way for two hazards, because each raster is
    defined over a different footprint: wall-to-wall layers (heatwave, PM2.5,
    earthquake) sit near 100%, while ``river_flood_100yr`` has a median of
    ~1.8% simply because a 100-year floodplain IS a small part of a region, and
    ``volcano_100km_buff`` is near 0% because the raster exists only near
    volcanoes. Publishing 1.8% next to 100% invites a reader to dismiss a
    perfectly sound flood statistic as "poorly covered". A unit either has
    hazard data or it does not, and that is unambiguous for every hazard.

    The covered/total pair is deliberately TWO numeric columns rather than one
    "3/7" string: Excel silently autoconverts such text to a date on open
    ("5/12" -> 05-Dec), corrupting the value in every workbook a CO touches.
    Two integers survive any spreadsheet round-trip. The denominator is the
    existing ``n_children``/``n_admin2`` column — no second total is emitted.

    Assumes `recompute_exposure_inputs` will be called AFTER on the result.
    """
    df = df.copy()

    # Countries excluded from the product entirely (no summary at any level).
    blocked = POP_BLANK_COUNTRIES if exclude_countries is None else exclude_countries
    if blocked and "adm0_ucode" in df.columns:
        df = df[~df["adm0_ucode"].isin(blocked)]

    status = df["status"].fillna("").astype(str).str.strip()

    # Tier 1: suppressed units contribute population (already sourced from the
    # reference by `apply_population_reference`) but no hazard result. They are
    # kept in the count sums so the denominator does not vary per hazard, and
    # excluded from hazard pooling exactly like No Data.
    kept = df.copy()
    kept_status = status

    # Tier 2: within the kept rows, mark which ones have hazard coverage.
    # No Data <-> hazs_count == 0 is a 1:1 correspondence in the production
    # data, so either signal identifies the same rows; we use status as the
    # authority and fall back to the pixel count when status is absent.
    kept["_covered"] = ~kept_status.isin((NO_DATA_STATUS,) + EXCLUDED_STATUSES)

    nominal = NOMINAL_ADM1 if group_col == "adm1_ucode" else NOMINAL_ADM0
    nominal = [c for c in nominal if c in kept.columns]

    # weight column: prefer hazs_count, fall back to pop_total per row
    if "hazs_count" in kept.columns:
        w = pd.to_numeric(kept["hazs_count"], errors="coerce")
    else:
        w = pd.Series(np.nan, index=kept.index)
    pop = pd.to_numeric(kept["pop_total"], errors="coerce")
    kept["_weight"] = w.where(w.notna(), pop)
    kept["_hazs_count"] = w

    rows = []
    for key, g in kept.groupby(group_col, dropna=True):
        cov = g[g["_covered"]]

        rec = {c: g[c].iloc[0] for c in nominal}
        rec[group_col] = key

        # Counts: summed over ALL kept rows (covered + No Data / suppressed).
        # Such a unit contributes its population and 0 exposure: the hazard
        # table stores exposure as NULL there (no raster coverage), but the
        # agreed semantics are "nobody here is known to be exposed", so the
        # exposure columns are treated as 0 before summing. Population is NOT
        # coerced this way — a null population means genuinely unknown, and
        # `apply_population_reference` is what fills it.
        exposure_cols = {e for e, _ in CLASS_TO_COLS.values()}
        for c in COUNT_COLS:
            series = pd.to_numeric(g[c], errors="coerce")
            if c in exposure_cols:
                series = series.fillna(0.0)
            rec[c] = series.sum(min_count=1)

        # Hazard statistics: COVERED rows only — a unit with no raster
        # coverage has no hazard value to pool.
        rec["hazs_min"] = pd.to_numeric(cov["hazs_min"], errors="coerce").min()
        rec["hazs_max"] = pd.to_numeric(cov["hazs_max"], errors="coerce").max()
        m, s = _weighted_mean_std(cov["hazs_mean"], cov.get("hazs_std"), cov["_weight"])
        rec["hazs_mean"], rec["hazs_std"] = m, s

        # Coverage: how many admin2 children carried hazard data, out of how
        # many were counted. Emitted adjacent so they are always read as a
        # pair ("21 of 47"); n_admin2_covered alone means nothing.
        rec["n_admin2_covered"] = int(len(cov))
        rec["n_children"] = len(g)
        rec["status"] = "" if len(cov) else NO_DATA_STATUS
        rows.append(rec)

    return pd.DataFrame(rows)


def validate_population_totals(long: pd.DataFrame, reference: pd.DataFrame,
                               group_col: str = "adm1_ucode",
                               tolerance: float = 1.0) -> pd.DataFrame:
    """Assert population is invariant across hazards and matches the admin2 source.

    This is the guard for the defect described in :func:`aggregate_counts`:
    population is a property of the PLACE, not of the hazard, so every hazard
    must report an identical total for a given unit. Any variation means rows
    were dropped from a denominator.

    Parameters
    ----------
    long
        The aggregated long frame (one row per unit x hazard).
    reference
        Admin2-level source of truth with ``adm2_ucode`` + population columns,
        plus the grouping key (e.g. ``admin2_population.csv`` joined to bounds).
        Population is summed from here independently of any hazard table.
    group_col
        Unit key to validate at (``adm1_ucode`` or ``adm0_ucode``).
    tolerance
        Allowed absolute difference, in people, to absorb float rounding.

    Returns a DataFrame of discrepancies — EMPTY means everything reconciles.
    Columns: unit, population class, expected, per-hazard observed, diff.
    """
    pop_cols = [p for _, p in CLASS_TO_COLS.values() if p in long.columns]
    problems = []

    # 1. population must not vary across hazards within a unit
    for pc in pop_cols:
        spread = (long.groupby(group_col)[pc]
                      .agg(["min", "max", "nunique"])
                      .query("nunique > 1"))
        for unit, r in spread.iterrows():
            worst = long.loc[long[group_col] == unit, ["hazard_code", pc]]
            problems.append({
                "check": "varies_by_hazard", "unit": unit, "column": pc,
                "expected": r["max"], "observed": r["min"],
                "diff": r["max"] - r["min"],
                "detail": f"{int(r['nunique'])} distinct values across hazards; "
                          f"lowest at {worst.loc[worst[pc].idxmin(), 'hazard_code']}",
            })

    # 2. the per-unit total must match the admin2 reference
    if reference is not None and group_col in reference.columns:
        ref_map = {p: reference.groupby(group_col)[p].sum()
                   for p in pop_cols if p in reference.columns}
        for pc, ref_totals in ref_map.items():
            obs = long.groupby([group_col, "hazard_code"])[pc].sum()
            for (unit, haz), value in obs.items():
                expected = ref_totals.get(unit)
                if expected is None or pd.isna(expected):
                    continue
                if abs(value - expected) > tolerance:
                    problems.append({
                        "check": "mismatch_vs_admin2", "unit": unit, "column": pc,
                        "expected": expected, "observed": value,
                        "diff": value - expected, "detail": haz,
                    })

    return pd.DataFrame(problems)


def discover_hazard_codes(folder: str, prod_date: str) -> list[str]:
    """List hazard codes available in a global/CSV folder for a given date."""
    suffix = f"_{prod_date}.csv"
    codes = []
    for p in glob.glob(os.path.join(folder, f"*{suffix}")):
        codes.append(os.path.basename(p)[: -len(suffix)])
    return sorted(codes)


def load_counts_table(path: str | None) -> pd.DataFrame | None:
    """Load the standalone hazs_count lookup table if it exists, else None."""
    if path and os.path.exists(path):
        t = pd.read_csv(path)
        t["hazs_count"] = pd.to_numeric(t["hazs_count"], errors="coerce")
        # The counts table was built from a boundary source that stores some
        # adm2 units more than once (NGA, SLE), so it carries exact-duplicate
        # (adm2_ucode, hazard_code) rows. Joining on it would fan those admin2
        # rows out and inflate every summed count (aexp, pop_*) downstream.
        n_before = len(t)
        t = t.drop_duplicates(subset=["adm2_ucode", "hazard_code"], keep="first")
        if len(t) != n_before:
            print(f"  counts table: dropped {n_before - len(t)} duplicate "
                  f"(adm2_ucode, hazard_code) row(s)")
        return t
    return None


def compute_scope(iu, df: pd.DataFrame, prefix: str, group_col: str | None) -> pd.DataFrame:
    """Compute one normalisation scope (global / country / regional) on an
    already-aggregated frame, reusing IndicatorUtils.compute_* verbatim.

    Mirrors notebook 02's logic exactly:
      - hazard index over hazs_max (`{prefix}index`)
      - exposure index per population class (`{prefix}expi_{class}`)
      - exposure class per population class (`{prefix}expc_{class}`), with the
        small-group rules: max index==0 -> class 0; group with <=2 units borrows
        the GLOBAL class (`gexpc_{class}`, must be computed first); else
        k = min(5, max(3, n_units)).

    Args:
        iu: an IndicatorUtils instance.
        df: aggregated admin1 or admin0 frame (one row per unit).
        prefix: "g" (global), "c" (country), or "r" (regional).
        group_col: None for global (one group), else the column to group by
                   (adm0_ucode for country scope, unicef_region for regional).
    Returns a copy of df with the scope's index/class columns filled.
    """
    df = df.copy()
    idx_col = f"{prefix}index"
    df[idx_col] = np.nan
    for pc in POPULATION_CLASSES:
        df[f"{prefix}expi_{pc}"] = 0.0
        df[f"{prefix}expc_{pc}"] = np.nan

    def _fill(sub_idx):
        sub = df.loc[sub_idx].copy()
        n = len(sub)
        sub = iu.compute_hazard_index(sub, hazs_max_col="hazs_max", output_col=idx_col)
        df.loc[sub_idx, idx_col] = sub[idx_col].values
        for pc in POPULATION_CLASSES:
            sub = iu.compute_exposure_index(
                sub, f"{pc}_log_exposure", f"{pc}_relative_exposure", output_col=f"{prefix}expi_{pc}")
            df.loc[sub_idx, f"{prefix}expi_{pc}"] = sub[f"{prefix}expi_{pc}"].values
            if sub[f"{prefix}expi_{pc}"].max() == 0:
                df.loc[sub_idx, f"{prefix}expc_{pc}"] = 0
            elif n <= 2 and prefix != "g" and f"gexpc_{pc}" in df.columns:
                df.loc[sub_idx, f"{prefix}expc_{pc}"] = df.loc[sub_idx, f"gexpc_{pc}"].values
            else:
                k = min(5, max(3, n))
                sub = iu.compute_exposure_class(
                    sub, f"{prefix}expi_{pc}", f"{pc}_log_exposure", k=k, output_col=f"{prefix}expc_{pc}")
                df.loc[sub_idx, f"{prefix}expc_{pc}"] = sub[f"{prefix}expc_{pc}"].values

    if group_col is None:
        _fill(df.index)
    else:
        for _, grp in df.groupby(group_col, dropna=True).groups.items():
            _fill(grp)
    return df
