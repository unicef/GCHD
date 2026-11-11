"""Step 05 — SDMX-CSV export (pure pandas, no EE).

Productionized form of ``notebooks/05_adm2_hazard_export_sdmx.ipynb``. Converts
the s02 global CSVs into SDMX-CSV long format for UN portals, in three streams:
hazard intensity, exposure, and population (population written once — identical
across hazards).

Fixes folded in vs the notebook:
  - reads the canonical ``base/global`` (was hardcoded ``output_CO_NA/global/CSV``)
  - ``prod_date`` / ``time_period`` / ``is_draft`` come from Settings (were
    hardcoded ``"2026-05-07"`` / ``"2026"`` / ``True``)
  - writes to the canonical ``export/sdmx/{stream}/CSV`` via ``io_paths``

The SDMX vocabulary (dimension lists, measure/unit maps, dataflow ids) is domain
metadata ported verbatim. ``build_stream_frames`` is a pure function returning
the three DataFrames, so it is unit-tested on a small fixture without any I/O.
"""

from __future__ import annotations

import csv

import os

import numpy as np
import pandas as pd

from ..settings import Settings
from ..hazards import load_hazards
from .. import io_paths

STEP = "s05"

# Population columns in the global CSV schema, and the names the independent
# admin2 reference (admin2_population.csv) uses for the same quantities.
_POPULATION_ALIASES = {
    "pop_total": ["pop_total"],
    "pop_total_f": ["pop_total_f", "pop_total_female"],
    "pop_total_m": ["pop_total_m", "pop_total_male"],
    "u18_pop_total": ["u18_pop_total", "pop_under_18_total"],
    "u18_pop_f": ["u18_pop_f", "pop_under_18_female"],
    "u18_pop_m": ["u18_pop_m", "pop_under_18_male"],
}


def _apply_population_reference(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Overwrite population columns from the independent admin2 reference.

    Mirrors ``lib.aggregation_functions.apply_population_reference``; kept here
    so the step has no dependency on ``lib`` (which needs a sys.path insert).
    """
    df = df.copy()
    ref = ref.drop_duplicates(subset=["adm2_ucode"], keep="first")
    for target, candidates in _POPULATION_ALIASES.items():
        src = next((c for c in candidates if c in ref.columns), None)
        if src is None or target not in df.columns:
            continue
        filled = df["adm2_ucode"].map(ref.set_index("adm2_ucode")[src])
        df[target] = pd.to_numeric(filled, errors="coerce").where(
            filled.notna(), pd.to_numeric(df[target], errors="coerce")
        )
    return df

# -- SDMX structure metadata (ported verbatim from NB05) -------------------

HAZARDS_VARIABLE = {
    "hazs_mean": {"unit": "NUMBER", "measure": "HAZARD_MEAN"},
    "hazs_std": {"unit": "NUMBER", "measure": "HAZARD_STD"},
    "hazs_max": {"unit": "NUMBER", "measure": "HAZARD_MAX"},
    "hazs_min": {"unit": "NUMBER", "measure": "HAZARD_MIN"},
    "hazs_median": {"unit": "NUMBER", "measure": "HAZARD_MEDIAN"},
    "cindex": {"unit": "IDX", "measure": "HAZARD_COUNTRY_INDEX"},
    "cexpi": {"unit": "IDX", "measure": "COUNTRY_EXPOSURE_INDEX"},
    "cexpc": {"unit": "NUMBER", "measure": "COUNTRY_EXPOSURE_CLASS"},
}
DIMS_HAZARDS = ["DATAFLOW", "REF_AREA", "INDICATOR", "MEASURE", "ADMIN_LEVEL",
                "ISO3_PARENT", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE", "REGION", "STATUS"]

EXPOSURE_VARIABLES = {
    "aexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "amexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "afexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "u18_aexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "u18_amexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "u18_afexp": {"unit": "NUMBER", "measure": "ABSOLUTE_EXPOSURE"},
    "rexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
    "rmexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
    "rfexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
    "u18_rexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
    "u18_rmexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
    "u18_rfexp": {"unit": "NUMBER", "measure": "RELATIVE_EXPOSURE"},
}
DIMS_EXPOSURE = ["DATAFLOW", "REF_AREA", "INDICATOR", "MEASURE", "SEX", "AGE", "ADMIN_LEVEL",
                 "ISO3_PARENT", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE", "REGION", "STATUS"]

POPULATION_VARIABLES = {
    "pop_total": {"unit": "PS", "measure": "POP_TOTAL"},
    "pop_total_m": {"unit": "PS", "measure": "POP_M"},
    "pop_total_f": {"unit": "PS", "measure": "POP_F"},
    "u18_pop_total": {"unit": "PS", "measure": "U18_POP_TOTAL"},
    "u18_pop_m": {"unit": "PS", "measure": "U18_POP_M"},
    "u18_pop_f": {"unit": "PS", "measure": "U18_POP_F"},
}
DIMS_POPULATION = ["DATAFLOW", "REF_AREA", "INDICATOR", "SEX", "AGE", "ADMIN_LEVEL",
                   "ISO3_PARENT", "TIME_PERIOD", "OBS_VALUE", "UNIT_MEASURE", "REGION", "STATUS"]


def _sex_age(col: str) -> tuple[str, str]:
    """Derive SEX / AGE dimension values from a column name (NB05 convention)."""
    sex = "F" if "f" in col else ("M" if "m" in col else "_T")
    age = "Y0T17" if "u18" in col else "_T"
    return sex, age


def build_stream_frames(hazard_df: pd.DataFrame, hazard, *, time_period: str,
                        is_draft: bool, with_population: bool) -> dict[str, pd.DataFrame]:
    """Build the SDMX hazard/exposure(/population) DataFrames for one hazard's
    global table. Pure function (no I/O). ``with_population`` controls whether the
    population stream is emitted (only for the first hazard in a run)."""
    draft = "_DRAFT" if is_draft else ""
    admin_level = "2"
    df = hazard_df.replace(np.nan, None)

    haz = {d: [] for d in DIMS_HAZARDS}
    exp = {d: [] for d in DIMS_EXPOSURE}
    pop = {d: [] for d in DIMS_POPULATION}

    for row in df.itertuples(index=False):
        adm2 = getattr(row, "adm2_ucode")
        iso3 = getattr(row, "iso3")
        region = getattr(row, "unicef_region")
        status = getattr(row, "status")

        for col, ind in HAZARDS_VARIABLE.items():
            haz["DATAFLOW"].append(f"UNICEF{draft}:HAZARD_INTENSITY(1.0)")
            haz["REF_AREA"].append(adm2)
            haz["INDICATOR"].append(f"HAZARD_{hazard.indicator}")
            haz["MEASURE"].append(ind["measure"])
            haz["ADMIN_LEVEL"].append(admin_level)
            haz["ISO3_PARENT"].append(iso3)
            haz["TIME_PERIOD"].append(time_period)
            haz["OBS_VALUE"].append(getattr(row, col, None))
            haz["UNIT_MEASURE"].append(ind["unit"])
            haz["REGION"].append(region)
            haz["STATUS"].append(status)

        for col, ind in EXPOSURE_VARIABLES.items():
            sex, age = _sex_age(col)
            exp["DATAFLOW"].append(f"UNICEF{draft}:HAZARD_EXPOSURE(1.0)")
            exp["REF_AREA"].append(adm2)
            exp["INDICATOR"].append(f"HAZARD_EXPOSURE_{hazard.indicator}")
            exp["MEASURE"].append(ind["measure"])
            exp["SEX"].append(sex)
            exp["AGE"].append(age)
            exp["ADMIN_LEVEL"].append(admin_level)
            exp["ISO3_PARENT"].append(iso3)
            exp["TIME_PERIOD"].append(time_period)
            exp["OBS_VALUE"].append(getattr(row, col, None))
            exp["UNIT_MEASURE"].append(ind["unit"])
            exp["REGION"].append(region)
            exp["STATUS"].append(status)

        if with_population:
            for col, ind in POPULATION_VARIABLES.items():
                sex, age = _sex_age(col)
                pop["DATAFLOW"].append(f"UNICEF{draft}:HAZARD_POPULATION(1.0)")
                pop["REF_AREA"].append(adm2)
                pop["INDICATOR"].append("HAZARD_POPULATION")
                pop["SEX"].append(sex)
                pop["AGE"].append(age)
                pop["ADMIN_LEVEL"].append(admin_level)
                pop["ISO3_PARENT"].append(iso3)
                pop["TIME_PERIOD"].append(time_period)
                pop["OBS_VALUE"].append(getattr(row, col, None))
                pop["UNIT_MEASURE"].append(ind["unit"])
                pop["REGION"].append(region)
                pop["STATUS"].append(status)

    out = {"hazard": pd.DataFrame(haz), "exposure": pd.DataFrame(exp)}
    if with_population:
        out["population"] = pd.DataFrame(pop)
    return out


def run(settings: Settings) -> dict:
    """Emit SDMX CSVs for every configured hazard. Population is written once.

    The population stream is emitted from the FIRST hazard processed, so that
    hazard's table decides the population values and their STATUS. That is only
    safe when population has been made hazard-independent: the per-hazard tables
    blank population for suppressed units and carry a per-hazard ``status``, so
    without the reference the SDMX population stream would inherit whichever
    units the first hazard happened to flag. ``population_reference_csv``
    overrides the population columns from the independent admin2 source (the
    same table notebook 06/07 use) and neutralizes the inherited status.
    """
    hazards = load_hazards(settings)
    time_period = str(settings.time_period)
    written = []
    population_done = False

    pop_ref = None
    ref_path = getattr(settings, "population_reference_csv", None)
    if ref_path and os.path.exists(ref_path):
        pop_ref = pd.read_csv(ref_path)
        print(f"  population reference: {len(pop_ref):,} admin2 rows from {ref_path}")
    else:
        print("  population reference: NOT SET -- SDMX population will be taken "
              "from the first hazard's table (varies with that hazard's flags)")

    for hazard in hazards:
        src = io_paths.base_global_csv(settings, hazard.code)
        try:
            hazard_df = pd.read_csv(src, index_col=None)
        except FileNotFoundError:
            print(f"  {hazard.code}: no global CSV; skipping SDMX")
            continue

        emit_population = not population_done
        if emit_population and pop_ref is not None:
            hazard_df = _apply_population_reference(hazard_df, pop_ref)

        frames = build_stream_frames(
            hazard_df, hazard, time_period=time_period,
            is_draft=settings.is_draft, with_population=emit_population,
        )
        if emit_population and pop_ref is not None and "population" in frames:
            # Population is a property of the place: it must not carry the
            # first hazard's per-hazard status into the population stream.
            frames["population"]["STATUS"] = ""
        for stream in ("hazard", "exposure"):
            out = io_paths.ensure_local_dir(io_paths.export_sdmx_csv(settings, stream, hazard.code))
            frames[stream].to_csv(out, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
            written.append(out)

        if not population_done and "population" in frames:
            out = io_paths.ensure_local_dir(io_paths.export_sdmx_csv(settings, "population"))
            frames["population"].to_csv(out, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)
            written.append(out)
            population_done = True
        print(f"  {hazard.code}: SDMX hazard+exposure written")

    print(f"s05 done: wrote {len(written)} SDMX CSVs")
    return {"written": written}
