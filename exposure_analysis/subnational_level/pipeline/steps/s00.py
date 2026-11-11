"""Step 00 — admin2 x hazard valid-pixel counts (the aggregation weight table).

Productionized form of ``notebooks/00_adm2_hazard_pixel_counts.ipynb``. Submits
one non-blocking ``Export.table.toDrive`` task per (country, hazard) counting
valid raw-hazard pixels per admin2 unit — the weight NB06/07 use to pool
hazs_mean/std. Duplicate-count twins (earthquake/landslide) are skipped and
reconstructed at assembly.

Design vs the notebook:
  - Config comes from :class:`Settings` (countries/hazards/scale/tile_scale/drive
    folder), not inline literals.
  - Submission is throttled: before each submit we hold if EE pending tasks
    exceed ``settings.ee_max_pending`` (admission control), so a full ~200-country
    run never trips the ~3000 pending-task cap.
  - The manifest is written through :mod:`pipeline.io_paths` to the canonical
    ``aux/`` location.

This step SUBMITS and records tasks. Downloading the Drive CSVs and assembling
``aux/hazs_count_{date}.csv`` (reconstructing the twins) is a separate action —
see :func:`assemble_from_local_csvs`, run after the tasks complete.
"""

from __future__ import annotations

import time

import pandas as pd

from ..settings import Settings
from ..hazards import load_hazards, DUPLICATE_COUNT_OF
from .. import io_paths
from .. import auth
from ..countries import countries_to_process

STEP = "s00"


def _pending_count(ee) -> int:
    """Number of EE batch tasks currently READY or RUNNING."""
    active = 0
    for t in ee.batch.Task.list():
        state = t.state if hasattr(t, "state") else t.status().get("state")
        if state in ("READY", "RUNNING"):
            active += 1
    return active


def _await_admission(ee, settings: Settings) -> None:
    """Block until EE pending tasks drop below the configured ceiling."""
    while _pending_count(ee) >= settings.ee_max_pending:
        print(f"  [admission] pending >= {settings.ee_max_pending}; "
              f"waiting {settings.batch_cooldown_s}s...")
        time.sleep(settings.batch_cooldown_s)


_ANALYSIS_SCALE: dict[str, object] = {}


def _analysis_scale(utils, ucode: str):
    """The country's population scale (WorldPop, ~92.77 m): the scale s01 reduces
    hazs_mean/std at, so the counts weight exactly the pixels behind those means.
    Cached per country; None for countries without population."""
    if ucode not in _ANALYSIS_SCALE:
        if utils.check_country_no_population(ucode):
            _ANALYSIS_SCALE[ucode] = None
        else:
            utils.set_population_dicts(ucode, utils.get_admin2_boundaries(ucode, admin_level="adm0_ucode"))
            utils.get_population_classes()
            _ANALYSIS_SCALE[ucode] = utils.analysis_scale
    return _ANALYSIS_SCALE[ucode]


def _native_scale(ee, hazard):
    """Fallback for no-population countries. A mosaic has no projection, so its
    nominalScale() is the ~111 km WGS84 default; read a member image instead."""
    if hazard.mosaic:
        return ee.Image(ee.ImageCollection(hazard.asset).first()).projection().nominalScale()
    return ee.Image(hazard.asset).projection().nominalScale()


def _submit_one(ee, utils, settings: Settings, hazard, ucode: str):
    """Submit ONE count export for (hazard, ucode). Returns the started task, or
    None if this hazard is a duplicate-count twin (skipped)."""
    if hazard.code in DUPLICATE_COUNT_OF:
        return None

    images = utils.define_hazard(hazard)
    raw = images["hazard_raw_image"].rename("haz").toFloat()
    adm2_fc = utils.get_admin2_boundaries(ucode, admin_level="adm0_ucode")
    scale = settings.scale_override or _analysis_scale(utils, ucode) or _native_scale(ee, hazard)

    reduced = raw.reduceRegions(
        collection=adm2_fc,
        reducer=ee.Reducer.count().setOutputs(["hazs_count"]),
        scale=scale,
        tileScale=settings.tile_scale,
    ).select(["adm2_ucode", "hazs_count"], None, False)
    reduced = reduced.map(lambda f: f.set("hazard_code", hazard.code))

    desc = f"cnt_{ucode}_{hazard.code}"[:100]
    task = ee.batch.Export.table.toDrive(
        collection=reduced,
        description=desc,
        folder=settings.drive_folder,
        fileNamePrefix=f"{ucode}__{hazard.code}",
        fileFormat="CSV",
        selectors=["adm2_ucode", "hazard_code", "hazs_count"],
    )
    task.start()
    return task


def run(settings: Settings, *, allow_interactive: bool = False) -> pd.DataFrame:
    """Submit count-export tasks for the configured countries x hazards.

    Loops COUNTRY -> HAZARD so a single country's set can be run and collected
    first. Returns (and writes) the manifest DataFrame
    [country, hazard_code, task_id].
    """
    ee, utils = auth.ee_and_utils(settings, allow_interactive=allow_interactive)

    hazards = load_hazards(settings)  # honors settings.process_hazards
    countries = countries_to_process(utils, settings.process_countries)
    print(f"s00: {len(hazards)} hazards x {len(countries)} countries "
          f"(twins skipped: {sorted(set(h.code for h in hazards) & set(DUPLICATE_COUNT_OF))})")

    submitted: list[tuple[str, str, str]] = []
    for ucode in countries:
        print(f"\n=== {ucode} ===")
        for hazard in hazards:
            try:
                _await_admission(ee, settings)
                task = _submit_one(ee, utils, settings, hazard, ucode)
                if task is None:
                    print(f"  {hazard.code}: skipped (twin of {DUPLICATE_COUNT_OF[hazard.code]})")
                    continue
                submitted.append((ucode, hazard.code, task.id))
                print(f"  {hazard.code}: task {task.id}")
            except Exception as e:  # keep going; one bad hazard/country shouldn't halt the run
                print(f"  ERROR {hazard.code} / {ucode}: {e}")

    manifest = pd.DataFrame(submitted, columns=["country", "hazard_code", "task_id"])
    out = io_paths.ensure_local_dir(io_paths.export_manifest_csv(settings))
    manifest.to_csv(out, index=False)
    print(f"\ns00: submitted {len(manifest)} tasks; manifest -> {out}")
    return manifest


def assemble_from_local_csvs(settings: Settings, csv_dir: str) -> pd.DataFrame:
    """Assemble the weight table from already-downloaded Drive CSVs in ``csv_dir``,
    reconstructing the duplicate-count twins, and write
    ``aux/hazs_count_{date}.csv``. Run after the s00 tasks complete and the Drive
    folder has been downloaded locally."""
    import glob

    files = glob.glob(f"{csv_dir}/*.csv")
    if not files:
        raise FileNotFoundError(f"no CSVs in {csv_dir}; download the "
                                f"'{settings.drive_folder}' Drive folder there first")
    table = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

    for dup, src in DUPLICATE_COUNT_OF.items():
        twin = table[table.hazard_code == src].copy()
        if twin.empty:
            print(f"  WARNING: source '{src}' absent; cannot build twin '{dup}'")
            continue
        twin["hazard_code"] = dup
        table = pd.concat([table, twin], ignore_index=True)

    table = table[["adm2_ucode", "hazard_code", "hazs_count"]]
    out = io_paths.ensure_local_dir(io_paths.hazs_count_csv(settings))
    table.to_csv(out, index=False)
    print(f"s00 assemble: {len(table)} rows ({table.hazard_code.nunique()} hazards) -> {out}")
    return table
