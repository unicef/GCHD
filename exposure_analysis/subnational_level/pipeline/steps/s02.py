"""Step 02 — indices, classes, and NA/status rules (pure pandas, no EE).

Productionized form of ``notebooks/02_adm2_hazard_indices_NA.ipynb``. For each
hazard it concatenates the NB01 country partials into a global table, applies the
status rules, computes exposure indices/classes and the hazard index at global /
country / region scopes (only over "state" countries), renames to the compact
schema, and writes the MAIN deliverable to ``base/global/{code}_{date}.csv``.

Two agreed corrections vs the notebook (see na_rules NB02 section):
  - Dead-branch fix: per-hazard insufficient-data exclusions now key on the REAL
    config hazard codes, so they actually fire (Fiji/river_flood, coastal-flood
    island states, fire island states, air-pollution Nauru/Monaco).
  - s02 does NOT apply the SPEI/SPI drought exclusion (NB02 never had it).

Output-drift fix: writes to the canonical ``base/global`` (was ``global_NA/CSV``).

The math itself is untouched — it calls the frozen ``IndicatorUtils.compute_*``.
``apply_status_rules`` is factored out as a pure function so the status logic is
unit-tested without any Earth Engine or file I/O.
"""

from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

from ..settings import Settings
from ..hazards import load_hazards
from ..state_countries import STATE_COUNTRIES
from .. import na_rules
from .. import io_paths
from ..countries import resolve as resolve_countries

STEP = "s02"

COUNTRY_COLUMN_NAME = "adm0_ucode"
REGION_COLUMN_NAME = "Region_Code"


def _indicator_utils():
    """Import IndicatorUtils lazily from lib/ (no EE needed)."""
    import sys

    lib_dir = str(Path(__file__).resolve().parent.parent.parent / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from indicator_functions import IndicatorUtils  # noqa: E402

    return IndicatorUtils()



def _collapse_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse same-named duplicate columns, keeping the most populated copy.

    Renaming `name`/`ucode` onto `adm2_name`/`adm2_ucode` leaves two columns
    sharing each name. Selecting by that name then returns both, so the written
    CSV carries a duplicate (empty) copy of each. Combine them instead: for each
    duplicated label keep the copy with the most non-null values, backfilling
    from the others so no populated value is lost.
    """
    if not df.columns.duplicated().any():
        return df

    out = {}
    for name in df.columns.unique():
        block = df.loc[:, df.columns == name]
        if block.shape[1] == 1:
            out[name] = block.iloc[:, 0]
            continue
        cols = [block.iloc[:, i] for i in range(block.shape[1])]
        cols.sort(key=lambda s: s.notna().sum(), reverse=True)
        merged = cols[0]
        for other in cols[1:]:
            merged = merged.where(merged.notna(), other)
        out[name] = merged
    return pd.DataFrame(out, index=df.index)


def apply_status_rules(df: pd.DataFrame, hazard_code: str, indicator_columns: list[str]) -> pd.DataFrame:
    """Set the ``status`` column and blank the indicator columns for excluded
    units, per the NB02 rules (with the dead-branch fix). Pure function: takes a
    per-country (or already-concatenated) DataFrame with an ``adm0_ucode`` column
    and returns it modified in place.

    Precedence (matches the notebook's if/elif):
      Not Applicable (non-official/sovereignty) > Insufficient Data (all-hazard)
      > Insufficient Data (per-hazard) > No Data (missing hazs_mean & exp_total)
      > '' (normal).
    """
    if "status" not in df.columns:
        df["status"] = ""
    present = [c for c in indicator_columns if c in df.columns]

    for ucode, sub_idx in df.groupby(COUNTRY_COLUMN_NAME, dropna=False).groups.items():
        status = na_rules.nb02_status_for(str(ucode), hazard_code)
        if status is not None:
            df.loc[sub_idx, present] = np.nan
            df.loc[sub_idx, "status"] = status

    # "No Data" for otherwise-normal units with no hazard mean and no exposure.
    normal = df["status"] == ""
    if "hazs_mean" in df.columns and "exp_total" in df.columns:
        nodata = normal & df["hazs_mean"].isnull() & df["exp_total"].isnull()
        df.loc[nodata, "status"] = "No Data"
    return df


def _load_hazard_global(settings: Settings, hazard_code: str, countries: list[str],
                        indicator_columns: list[str]) -> pd.DataFrame:
    """Read this hazard's country partials, apply status rules, concat to global."""
    frames = []
    seen: set[str] = set()
    for ucode in countries:
        # A country listed twice would concatenate its partial twice; guard here
        # so the global table cannot inherit duplicate rows from the caller.
        if ucode in seen:
            continue
        seen.add(ucode)
        path = io_paths.base_partial_csv(settings, hazard_code, ucode)
        try:
            cdf = pd.read_csv(path)
        except FileNotFoundError:
            continue
        cdf = apply_status_rules(cdf, hazard_code, indicator_columns)
        frames.append(cdf)
    if not frames:
        raise FileNotFoundError(
            f"no partials found for hazard {hazard_code} under "
            f"{io_paths.base_root(settings)}/hazards/{hazard_code}/partials/"
        )
    return pd.concat(frames, ignore_index=True)


def _compute_scope_indices(iu, df_global: pd.DataFrame, state_mask, pop_classes: list[str]) -> pd.DataFrame:
    """Compute global (g), country (c), and region (r) indices/classes over the
    state-country subset, writing them back onto df_global. Faithful port of the
    notebook's three index blocks."""
    df_f = df_global.loc[state_mask].copy()

    # -- GLOBAL (gexpi/gexpc/gindex) --------------------------------------
    gexpi = [f"gexpi_{p}" for p in pop_classes]
    gexpc = [f"gexpc_{p}" for p in pop_classes]
    df_global = df_global.assign(**{c: np.nan for c in gexpi + gexpc + ["gindex"]})
    for p in pop_classes:
        df_f = iu.compute_exposure_index(df=df_f, log_aexp_col=f"{p}_log_exposure",
                                         rexp_col=f"{p}_relative_exposure", output_col=f"gexpi_{p}")
        df_f = iu.compute_exposure_class(df=df_f, expi_col=f"gexpi_{p}",
                                         aexp_col=f"{p}_log_exposure", k=5, output_col=f"gexpc_{p}")
    df_f = iu.compute_hazard_index(df_f, hazs_max_col="hazs_max", output_col="gindex")
    df_global.loc[state_mask, gexpi + gexpc + ["gindex"]] = df_f[gexpi + gexpc + ["gindex"]].values

    # -- COUNTRY (cexpi/cexpc/cindex) -------------------------------------
    cexpi = [f"cexpi_{p}" for p in pop_classes]
    cexpc = [f"cexpc_{p}" for p in pop_classes]
    df_global = df_global.assign(cindex=np.nan, **{c: 0.0 for c in cexpi}, **{c: np.nan for c in cexpc})
    for country_code, idx in df_f.groupby(COUNTRY_COLUMN_NAME, dropna=False).groups.items():
        if country_code not in STATE_COUNTRIES:
            continue
        n = len(idx)
        df_c = df_f.loc[idx].copy()
        df_c = iu.compute_hazard_index(df_c, hazs_max_col="hazs_max", output_col="cindex")
        df_f.loc[idx, "cindex"] = df_c["cindex"]
        for p in pop_classes:
            df_c = iu.compute_exposure_index(df_c, log_aexp_col=f"{p}_log_exposure",
                                             rexp_col=f"{p}_relative_exposure", output_col=f"cexpi_{p}")
            df_f.loc[idx, f"cexpi_{p}"] = df_c[f"cexpi_{p}"]
            if df_c[f"cexpi_{p}"].max() == 0:
                df_f.loc[idx, f"cexpc_{p}"] = 0
            elif n <= 2:
                df_f.loc[idx, f"cexpc_{p}"] = df_f.loc[idx, f"gexpc_{p}"].values
            else:
                k = min(5, max(3, n))
                df_c = iu.compute_exposure_class(df_c, expi_col=f"cexpi_{p}",
                                                 aexp_col=f"{p}_log_exposure", k=k, output_col=f"cexpc_{p}")
                df_f.loc[idx, f"cexpc_{p}"] = df_c[f"cexpc_{p}"]
    df_global.loc[state_mask, cexpi + cexpc + ["cindex"]] = df_f[cexpi + cexpc + ["cindex"]].values

    # -- REGION (rexpi/rexpc/rindex) --------------------------------------
    rexpi = [f"rexpi_{p}" for p in pop_classes]
    rexpc = [f"rexpc_{p}" for p in pop_classes]
    df_global = df_global.assign(rindex=np.nan, **{c: 0.0 for c in rexpi}, **{c: np.nan for c in rexpc})
    has_region_mask = state_mask & ~df_global[REGION_COLUMN_NAME].isna()
    df_r_all = df_global.loc[has_region_mask].copy()
    for region_code, idx in df_r_all.groupby(REGION_COLUMN_NAME, dropna=False).groups.items():
        n = len(idx)
        df_r = df_r_all.loc[idx].copy()
        df_r = iu.compute_hazard_index(df_r, hazs_max_col="hazs_max", output_col="rindex")
        df_r_all.loc[idx, "rindex"] = df_r["rindex"]
        for p in pop_classes:
            df_r = iu.compute_exposure_index(df_r, log_aexp_col=f"{p}_log_exposure",
                                             rexp_col=f"{p}_relative_exposure", output_col=f"rexpi_{p}")
            df_r_all.loc[idx, f"rexpi_{p}"] = df_r[f"rexpi_{p}"]
            if df_r[f"rexpi_{p}"].max() == 0:
                df_r_all.loc[idx, f"rexpc_{p}"] = 0
            elif n <= 2:
                df_r_all.loc[idx, f"rexpc_{p}"] = df_r_all.loc[idx, f"gexpc_{p}"].values
            else:
                k = min(5, max(3, n))
                df_r = iu.compute_exposure_class(df_r, expi_col=f"rexpi_{p}",
                                                 aexp_col=f"{p}_log_exposure", k=k, output_col=f"rexpc_{p}")
                df_r_all.loc[idx, f"rexpc_{p}"] = df_r[f"rexpc_{p}"]
    df_global.loc[has_region_mask, rexpi + rexpc + ["rindex"]] = df_r_all[rexpi + rexpc + ["rindex"]].values

    return df_global


def run(settings: Settings) -> dict:
    """Process every configured hazard: partials -> global CSV with indices/NA."""
    iu = _indicator_utils()
    indicator_columns = iu.get_numeric_columns_for_NA()
    hazards = load_hazards(settings)

    # Countries whose partials to read. If not filtered, read whatever partials
    # exist on disk (pure-pandas step has no EE to enumerate the world).
    countries = resolve_countries(settings.process_countries)
    written = []
    for hazard in hazards:
        code = hazard.code
        try:
            if countries is None:
                # Discover countries from the partial filenames on disk.
                files = glob.glob(io_paths.base_partials_glob(settings, code))
                disc = sorted({Path(f).name.split(f"_{code}_admin2.csv")[0] for f in files})
                use_countries = disc
            else:
                use_countries = countries

            df_global = _load_hazard_global(settings, code, use_countries, indicator_columns)
            state_mask = (df_global[COUNTRY_COLUMN_NAME].isin(STATE_COUNTRIES)
                          & (df_global["status"] == ""))
            df_global = _compute_scope_indices(iu, df_global, state_mask, settings.population_classes)

            df_global = df_global.rename(columns=iu.get_rename_map())
            # The partials carry both populated `adm2_name`/`adm2_ucode` and empty
            # `name`/`ucode`; the rename maps the latter onto the former, leaving two
            # same-named columns. Keep the populated copy so the selection below does
            # not emit each column twice.
            df_global = _collapse_duplicate_columns(df_global)
            df_global = iu.round_cols(df_global)
            df_global = df_global[iu.get_all_indicator_columns()]

            out = io_paths.ensure_local_dir(io_paths.base_global_csv(settings, code))
            df_global.to_csv(out, index=False)
            written.append(out)
            print(f"  {code}: {len(df_global)} rows -> {out}")
        except Exception as e:
            print(f"  ERROR {code}: {e}")

    print(f"s02 done: wrote {len(written)} global hazard CSVs")
    return {"written": written}
