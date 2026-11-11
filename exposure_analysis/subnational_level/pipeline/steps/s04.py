"""Step 04 — per-country hazard/exposure GeoTIFF export (+ optional SharePoint push).

Productionized form of ``notebooks/04_adm2_hazard_exposure_raster_country.ipynb``.
Independent branch of the pipeline.

Phase A (always runs): for each (hazard, country), export the clipped raw-hazard
band and, optionally, ``exp_{class}`` exposure bands to Google Drive via
``GEEUtils.export_singleband_to_drive``. Tasks are collected and returned.

Phases B-D (DEFERRED): wait for the EE tasks, download the TIFFs from Drive, and
upload them to SharePoint. These require app-only Microsoft Graph credentials
(the UNICEF AAD app registration, ``settings.graph_tenant_id`` +
``graph_client_id``) which are not yet provisioned. Until they are, s04 runs
Phase A and stops, printing where to collect the Drive outputs. When the creds
exist, the notebook's device-code flow must ALSO be swapped for client-
credentials in ``sharepoint_sync`` (Stage 2) — this step will call the deferred
``auth.graph_token`` which currently raises with that explanation.

Note: Phase A still uses interactive Drive OAuth today (the notebook's
``sharepoint_sync.get_drive_service``). The EE export itself is
service-account-drivable; moving the Drive dependency to a service account or
EE->GCS is part of Stage 2. For now Phase A submits the EE tasks (which land in
Drive by folder name) and does not require the Drive client just to submit.
"""

from __future__ import annotations

from ..settings import Settings
from ..hazards import load_hazards
from .. import auth
from ..countries import countries_to_process

STEP = "s04"


def _submit_country_rasters(settings: Settings, ee, utils, hazard, ucode: str) -> list:
    """Submit raw-hazard (+ optional exposure) raster exports for one
    (hazard, country). Returns list of (task, description) started."""
    started = []
    hazard_images = utils.define_hazard(hazard)
    country_adm2_fc = utils.get_admin2_boundaries(ucode)
    country_fc = utils.get_country_boundaries(ucode)
    utils.set_population_dicts(ucode, country_adm2_fc)

    folder = settings.raster_drive_folder_pattern.format(ucode=ucode)

    raw_clipped = hazard_images["hazard_raw_image"].clip(country_fc)
    task = utils.export_singleband_to_drive(
        image=raw_clipped, band_name="hazard_raw", region_fc=country_fc,
        country_ucode=ucode, hazard_code=hazard.code, folder=folder, return_task=True,
    )
    started.append((task, f"{ucode}_{hazard.code}_hazard_raw"))

    if settings.raster_export_exposure:
        pop_info = utils.get_population_classes(include_classes=settings.raster_pop_classes)
        for cls, img in pop_info["valid_population_classes"].items():
            exp_img = img.multiply(hazard_images["hazard_masked_image"])
            task = utils.export_singleband_to_drive(
                image=exp_img, band_name=f"exp_{cls}", region_fc=country_fc,
                country_ucode=ucode, hazard_code=hazard.code, folder=folder, return_task=True,
            )
            started.append((task, f"{ucode}_{hazard.code}_exp_{cls}"))
    return started


def run(settings: Settings, *, allow_interactive: bool = False,
        push_sharepoint: bool = False) -> dict:
    """Phase A raster export. If ``push_sharepoint`` and Graph creds are present,
    also run the (deferred) SharePoint hand-off — otherwise stop after export."""
    ee, utils = auth.ee_and_utils(settings, allow_interactive=allow_interactive)
    hazards = load_hazards(settings)
    countries = countries_to_process(utils, settings.process_countries)
    print(f"s04: {len(hazards)} hazards x {len(countries)} countries -> Drive")

    submitted = []  # (task, description)
    for hazard in hazards:
        for ucode in countries:
            try:
                submitted += _submit_country_rasters(settings, ee, utils, hazard, ucode)
            except Exception as e:
                print(f"  ERROR {hazard.code} / {ucode}: {e}")
    print(f"s04: submitted {len(submitted)} raster export task(s) to Drive "
          f"(folder pattern '{settings.raster_drive_folder_pattern}').")

    if not push_sharepoint:
        print("s04: SharePoint push not requested; stopping after export. "
              "Collect TIFFs from Drive when tasks complete.")
        return {"tasks_submitted": len(submitted), "sharepoint": "skipped"}

    # Deferred path: requires the AAD app registration. auth.graph_token raises
    # a clear NotImplementedError until Stage 2 wires client-credentials.
    if not (settings.graph_tenant_id and settings.graph_client_id):
        print("s04: push_sharepoint requested but graph_tenant_id/graph_client_id "
              "are unset (AAD app registration pending). Skipping SharePoint.")
        return {"tasks_submitted": len(submitted), "sharepoint": "unconfigured"}

    auth.graph_token(settings)  # raises NotImplementedError (deferred) by design
    return {"tasks_submitted": len(submitted), "sharepoint": "attempted"}
