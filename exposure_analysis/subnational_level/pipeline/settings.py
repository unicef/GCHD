"""The single configuration object for the pipeline.

Everything that was hardcoded across the notebooks lives here instead:
output roots, prod_date, production year / WorldPop release, GEE project,
SDMX metadata, and the export/throttle knobs. Values come from environment
variables (prefixed ``GCHD_``) with sensible defaults, so the *same code* runs
locally (``notebooks/output``) or on Azure (``abfs://...``) by changing env only.

Design choices
--------------
- Built on pydantic v2 ``BaseModel`` (already installed) rather than
  ``pydantic-settings`` to avoid adding a dependency mid-refactor. ``from_env``
  does the env-var loading that ``BaseSettings`` would; swapping to
  ``pydantic-settings`` later is a drop-in if desired.
- ``storage_root`` is a plain string (a local path OR an fsspec URL like
  ``abfs://container/prefix``). ``io_paths`` builds every artifact path off it,
  so no step ever hardcodes a folder again.
- Injected straight into ``GEEUtils`` — the fields mirror what its constructor
  already accepts (``unicef_data_source_path``, ``prod_date``, ``time_period``,
  ``dataflow``, ``population_paths_dict``), so **lib/ needs no changes**.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ENV_PREFIX = "GCHD_"

# subnational_level/ — the folder holding pipeline/, lib/ and notebooks/.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
# Absolute, so notebooks in any subfolder and the CLI from any cwd share one output.
DEFAULT_STORAGE_ROOT = (PACKAGE_ROOT / "notebooks" / "output").as_posix()

# The population classes the pipeline extracts, in canonical order. Mirrors
# aggregation_functions.POPULATION_CLASSES; kept here so a run can subset them.
DEFAULT_POPULATION_CLASSES = [
    "total", "total_female", "total_male",
    "under_18_total", "under_18_female", "under_18_male",
]


def _today() -> str:
    return dt.date.today().isoformat()


class Settings(BaseModel):
    """All run-level configuration. Construct via :meth:`from_env`."""

    model_config = {"frozen": False, "extra": "forbid"}

    # -- Earth Engine / asset namespace -----------------------------------
    gee_project: str = "unicef-ccri"
    unicef_data_source_path: str = "projects/unicef-ccri/assets"
    gee_service_account_key: Optional[str] = None  # path to SA JSON; Stage 2

    # -- Run identity -----------------------------------------------------
    prod_date: str = Field(default_factory=_today)  # ISO date stamped on outputs
    production_year: int = 2026                      # data vintage for this run
    # Reference year of the data, i.e. of the WorldPop population (2025 release).
    # Stamped on the partials and as SDMX TIME_PERIOD; move to 2026 with the data.
    time_period: int = 2025
    worldpop_release: str = "R2025A"                 # WorldPop dataset release tag

    # -- Storage ----------------------------------------------------------
    # A local path OR an fsspec URL (e.g. "abfs://gchd/prod"). io_paths builds
    # aux/base/export/upscale/_manifests paths off this single root.
    storage_root: str = DEFAULT_STORAGE_ROOT
    # Admin-2 boundaries as <adm0_ucode>.parquet (COG route); empty = fetch from Earth Engine.
    boundaries_url: str = "https://unidatadapmclimatechange.blob.core.windows.net/public/boundaries/adm2"

    # -- SDMX metadata ----------------------------------------------------
    is_draft: bool = True

    # -- Population reference (hazard-independent denominators) -----------
    # Independent admin2 population source. Population is a property of the
    # PLACE, not of the hazard: the per-hazard tables blank it for suppressed
    # units, and each hazard suppresses a different set, so reading it from
    # them makes the denominator drift per hazard. Used by s05 (SDMX population
    # stream) and by the notebook 06/07 admin1/admin0 rollups.
    population_reference_csv: Optional[str] = None
    # Per-admin2 total land-pixel count: denominator for pct_area_covered.
    land_pixels_csv: Optional[str] = None

    # -- Export staging / EE throttling ----------------------------------
    export_target: str = "drive"          # "drive" | "gcs" (Stage 2 prefers gcs)
    gcs_bucket: Optional[str] = None       # required when export_target == "gcs"
    drive_folder: str = "hazs_count_exports"
    ee_max_pending: int = 2800             # hold new batch submits above this
    batch_size: int = 50                   # tasks per country-batch before cooldown
    batch_cooldown_s: int = 30             # seconds to wait between batches
    tile_scale: int = 8                    # reduceRegions tileScale default

    # -- s01 extraction / gap-fill (NB01) --------------------------------
    run_missing_data_fill: bool = True     # Phase 2: fill missing admin2 via tiling
    bounds_folder: str = "bounds"          # cached local admin2 geometries (huge polys)
    fill_tile_deg: float = 1.0             # tiled-path grid size (degrees)
    fill_batch_size: int = 20              # tiled-path EE calls per batch
    fill_batch_cooldown_s: float = 5.0     # tiled-path seconds between batches
    fill_tile_scale: int = 4               # tiled-path reduceRegions tileScale

    # -- s04 raster export (NB04) ----------------------------------------
    raster_pop_classes: list[str] = Field(
        default_factory=lambda: ["total", "under_18_total"]
    )
    raster_drive_folder_pattern: str = "{ucode}"   # Drive folder per country
    raster_export_exposure: bool = True            # export exp_{class} bands too
    poll_seconds: int = 30                         # EE task poll interval (SharePoint phase)

    # -- Optional run filters (None = all) -------------------------------
    process_countries: Optional[list[str]] = None   # ucodes or ISO3, e.g. ["EGY_V1"] or ["EGY"]
    process_hazards: Optional[list[str]] = None      # hazard codes
    population_classes: list[str] = Field(
        default_factory=lambda: list(DEFAULT_POPULATION_CLASSES)
    )
    scale_override: Optional[float] = None           # metres; None = nominalScale

    # -- SharePoint (Stage 2, deferred) ----------------------------------
    sharepoint_host: str = "unicef.sharepoint.com"
    sharepoint_site_path: str = "teams/DAPM"
    sharepoint_library: str = "DocumentLibrary4"
    graph_tenant_id: Optional[str] = None
    graph_client_id: Optional[str] = None

    # ---------------------------------------------------------------------
    @property
    def dataflow(self) -> str:
        """SDMX dataflow id, draft-aware (used by GEEUtils / SDMX step)."""
        prefix = "UNICEF_DRAFT" if self.is_draft else "UNICEF"
        return f"{prefix}:DRAFT_HAZARD(1.0)" if self.is_draft else f"{prefix}:HAZARD(1.0)"

    @property
    def sharepoint_year_folder(self) -> str:
        """Year segment of the SharePoint target path (was hardcoded '2025')."""
        return str(self.production_year)

    @field_validator("export_target")
    @classmethod
    def _valid_target(cls, v: str) -> str:
        if v not in ("drive", "gcs"):
            raise ValueError(f"export_target must be 'drive' or 'gcs', got {v!r}")
        return v

    @field_validator("prod_date")
    @classmethod
    def _valid_date(cls, v: str) -> str:
        dt.date.fromisoformat(v)  # raises if not ISO YYYY-MM-DD
        return v

    # ---------------------------------------------------------------------
    @classmethod
    def from_env(cls, **overrides) -> "Settings":
        """Build Settings from ``GCHD_*`` environment variables, then apply any
        explicit keyword overrides (e.g. from CLI flags). CLI overrides win.

        List-valued fields accept comma-separated env values, e.g.
        ``GCHD_PROCESS_COUNTRIES=EGY_V1,DEU_V1``.
        """
        list_fields = {"process_countries", "process_hazards", "population_classes",
                       "raster_pop_classes"}
        bool_fields = {"is_draft", "run_missing_data_fill", "raster_export_exposure"}
        int_fields = {"production_year", "time_period", "ee_max_pending",
                      "batch_size", "batch_cooldown_s", "tile_scale",
                      "fill_batch_size", "fill_tile_scale", "poll_seconds"}
        float_fields = {"scale_override", "fill_tile_deg", "fill_batch_cooldown_s"}

        env_values: dict = {}
        for name in cls.model_fields:
            raw = os.environ.get(f"{ENV_PREFIX}{name.upper()}")
            if raw is None:
                continue
            if name in list_fields:
                env_values[name] = [s.strip() for s in raw.split(",") if s.strip()]
            elif name in bool_fields:
                env_values[name] = raw.strip().lower() in ("1", "true", "yes", "on")
            elif name in int_fields:
                env_values[name] = int(raw)
            elif name in float_fields:
                env_values[name] = float(raw)
            else:
                env_values[name] = raw

        env_values.update(overrides)
        return cls(**env_values)
