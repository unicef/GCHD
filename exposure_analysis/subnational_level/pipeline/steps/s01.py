"""Step 01 — admin2 hazard-exposure extraction (the heavy GEE stage).

Productionized form of ``notebooks/01_adm2_hazard_exposure_updated.ipynb``. Two
phases, both delegating to frozen ``lib`` logic:

  Phase 1 (main): for each (hazard, country), call
    ``GEEUtils.process_hazard_for_country`` and save a per-country partial via
    ``save_country_results`` → ``base/hazards/{code}/partials/{ucode}_{code}_admin2.csv``.
    Resumable: countries whose partial already exists are skipped.

  Phase 2 (gap-fill): detect admin2 units missing from the partials
    (``find_missing_adm2``) and fill them via the local-tiled huge-polygon path
    (``load_local_boundaries`` + ``process_missing_adm2_unit`` +
    ``merge_missing_results``). This path is intentionally wrapped AS-IS — it has
    delicate EE-call batching, cooldowns and a shapely tiling scheme we do not
    re-architect; we only feed its knobs from Settings.

The `output_folder` handed to lib is ``io_paths.base_root(settings)`` — lib then
appends ``hazards/{code}/partials/...`` and scans the same tree, so no lib change
is needed.

Prereqs for Phase 2: the ``bounds/`` folder of cached admin2 geometries must be
present (ship it into the container in Stage 6). ``settings.bounds_folder`` points
to it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..settings import Settings
from ..hazards import load_hazards
from .. import io_paths
from .. import auth
from ..countries import countries_to_process

STEP = "s01"


def partial_ucode(filename: str, hazard_code: str) -> str | None:
    """Country ucode of a partial named ``{ucode}_{code}_admin2.csv``, else None.
    Ucodes vary in length (CAN_V1, BES1_V2), so strip the known suffix."""
    suffix = f"_{hazard_code}_admin2.csv"
    return filename[: -len(suffix)] if filename.endswith(suffix) else None


def _filtered_countries(utils, base_root: str, hazard_code: str, countries: list[str]) -> list[str]:
    """Countries not yet processed for this hazard (resume support). Mirrors the
    notebook's get_filtered_countries: skip those with an existing partial and
    those with no population."""
    partials_dir = Path(base_root) / "hazards" / hazard_code / "partials"
    processed: set[str] = set()
    if partials_dir.exists():
        for f in partials_dir.iterdir():
            ucode = partial_ucode(f.name, hazard_code)
            if f.is_file() and ucode:
                processed.add(ucode)
    no_pop = set(utils.countries_no_population)
    return [c for c in countries if c not in processed and c not in no_pop]


def _define_hazard(utils, settings: Settings, hazard):
    """define_hazard also stamps the run metadata written into every partial;
    without these arguments it uses today's date and the draft dataflow."""
    return utils.define_hazard(hazard, production_date=settings.prod_date,
                               dataflow=settings.dataflow)


def _run_main(settings: Settings, ee, utils, hazards, countries, base_root: str) -> int:
    """Phase 1: main hazard x country extraction. Returns count of saved partials."""
    saved = 0
    for hazard in hazards:
        print(f"\n{'='*60}\nHazard: {hazard.name} ({hazard.code})\n{'='*60}")
        hazard_images = _define_hazard(utils, settings, hazard)
        todo = _filtered_countries(utils, base_root, hazard.code, countries)
        print(f"Countries to process: {len(todo)}")
        for ucode in todo:
            t0 = pd.Timestamp.now()
            try:
                results = utils.process_hazard_for_country(hazard_images, ucode, hazard.asset)
                utils.save_country_results(results, hazard.code, ucode, base_root)
                print(f"  {ucode}: {len(results)} rows in {pd.Timestamp.now() - t0}")
                saved += 1
            except Exception as e:
                print(f"  ERROR {ucode}: {e}")
    return saved


def _all_adm2_ucodes(settings: Settings, ee, utils) -> list[str]:
    fc = ee.FeatureCollection(f"{settings.unicef_data_source_path}/{utils.ADMIN2_ASSET}")
    return fc.aggregate_array("adm2_ucode").getInfo()


def _run_fill(settings: Settings, ee, utils, hazards, base_root: str) -> int:
    """Phase 2: detect + fill missing admin2 units via the tiled path. Returns
    number of units filled."""
    all_ucodes = _all_adm2_ucodes(settings, ee, utils)
    print(f"Reference admin2 units in asset: {len(all_ucodes)}")
    errors = utils.find_missing_adm2(base_root, all_ucodes)

    total_missing = sum(len(m) for fe in errors.values() for _, m in fe)
    print(f"Total missing admin2 units: {total_missing}")
    if total_missing == 0:
        return 0

    geojson_cache, properties_cache = type(utils).load_local_boundaries(settings.bounds_folder)
    hazards_by_code = {h.code: h for h in hazards}
    filled = 0

    for haz_code, file_errors in errors.items():
        hazard_obj = hazards_by_code.get(haz_code)
        if hazard_obj is None:  # hazard filtered out of this run
            continue
        if sum(len(m) for _, m in file_errors) == 0:
            continue
        print(f"\n{'='*60}\nFilling missing units for: {hazard_obj.name}\n{'='*60}")
        hazard_images = _define_hazard(utils, settings, hazard_obj)

        for filename, missing_list in file_errors:
            if not missing_list:
                continue
            parts = filename.split("_")
            country_ucode = f"{parts[0]}_{parts[1]}"
            print(f"\n  {filename}: {len(missing_list)} missing")
            country_df = None
            for idx, adm2_ucode in enumerate(missing_list):
                try:
                    stats_df = utils.process_missing_adm2_unit(
                        hazard_images=hazard_images,
                        hazard_obj=hazard_obj,
                        country_ucode=country_ucode,
                        adm2_ucode=adm2_ucode,
                        geojson_cache=geojson_cache,
                        properties_cache=properties_cache,
                        tile_deg=settings.fill_tile_deg,
                        batch_size=settings.fill_batch_size,
                        batch_cooldown=settings.fill_batch_cooldown_s,
                        tileScale=settings.fill_tile_scale,
                    )
                except Exception as e:
                    print(f"    [{idx+1}/{len(missing_list)}] {adm2_ucode}: ERROR {e}")
                    continue
                if len(stats_df) > 0:
                    country_df = stats_df if country_df is None else pd.concat([country_df, stats_df])
                    filled += 1

            if country_df is None:
                continue
            # Merge into the REAL on-disk file that find_missing_adm2 reported
            # (its `filename` is authoritative — the partial to overwrite in place),
            # not the canonical builder, in case the two ever diverge.
            existing = f"{base_root}/hazards/{hazard_obj.code}/partials/{filename}"
            utils.merge_missing_results(new_df=country_df, existing_file_path=existing, output_path=existing)
            print(f"  merged {len(country_df)} rows into {existing}")

    return filled


def run(settings: Settings, *, allow_interactive: bool = False,
        fill_missing: bool | None = None) -> dict:
    """Run the extraction. ``fill_missing`` overrides
    ``settings.run_missing_data_fill`` when given. Returns a small summary dict."""
    ee, utils = auth.ee_and_utils(settings, allow_interactive=allow_interactive)
    base_root = io_paths.base_root(settings)
    io_paths.ensure_local_dir(f"{base_root}/hazards/.keep")  # create base tree locally

    hazards = load_hazards(settings)
    countries = countries_to_process(utils, settings.process_countries)
    print(f"s01: {len(hazards)} hazards x {len(countries)} countries -> {base_root}")

    saved = _run_main(settings, ee, utils, hazards, countries, base_root)

    do_fill = settings.run_missing_data_fill if fill_missing is None else fill_missing
    filled = _run_fill(settings, ee, utils, hazards, base_root) if do_fill else 0

    # Post-fill validation: report any still-missing units (does not raise).
    remaining = 0
    if do_fill:
        all_ucodes = _all_adm2_ucodes(settings, ee, utils)
        rem = utils.find_missing_adm2(base_root, all_ucodes)
        remaining = sum(len(m) for fe in rem.values() for _, m in fe)
        print(f"\ns01: {remaining} admin2 units still missing after fill")

    summary = {"partials_saved": saved, "units_filled": filled, "units_remaining": remaining}
    print(f"s01 done: {summary}")
    return summary
