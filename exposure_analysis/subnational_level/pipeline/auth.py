"""Authentication and Earth Engine bootstrap for the pipeline.

Single place that turns a :class:`Settings` into an authenticated ``ee`` module
and a ready ``GEEUtils``. This replaces the notebooks' inline
``ee.Authenticate()`` / ``ee.Initialize(...)`` calls.

Auth precedence (non-interactive first — the production path):
  1. ``settings.gee_service_account_key`` → ``ee.ServiceAccountCredentials``
     (the unattended path; key JSON comes from Key Vault in Azure, Stage 2).
  2. Cached user credentials from a prior ``earthengine authenticate`` →
     ``ee.Initialize(project=...)`` alone.
  3. As a LOCAL DEV convenience only, if ``allow_interactive=True`` and both
     above fail, fall back to ``ee.Authenticate()``. Never enabled in Azure.

``ee`` is imported lazily inside functions so importing this module (and any
step that imports it) does not require Earth Engine to be installed/authed —
keeps the foundation unit-testable.

Storage / Graph auth (Stage 2) will also live here:
  - ``storage_options(settings)`` → fsspec kwargs for abfs:// (DefaultAzureCredential)
  - ``graph_token(settings)``     → app-only MS Graph token (deferred; needs the
    UNICEF AAD app registration)
Both are stubbed with clear NotImplementedError until Stage 2/3 land.
"""

from __future__ import annotations

import json
from typing import Any, Tuple

from .settings import Settings


def init_ee(settings: Settings, *, allow_interactive: bool = False) -> Any:
    """Initialize Earth Engine per the precedence above and return the ``ee``
    module (already initialized). Raises if EE cannot be initialized
    non-interactively and ``allow_interactive`` is False."""
    import ee

    key = settings.gee_service_account_key
    if key:
        with open(key, encoding="utf-8") as fh:
            info = json.load(fh)
        creds = ee.ServiceAccountCredentials(email=info["client_email"], key_file=key)
        ee.Initialize(credentials=creds, project=settings.gee_project)
        return ee

    # No SA key: try cached user credentials (from a prior `earthengine authenticate`).
    try:
        ee.Initialize(project=settings.gee_project)
        return ee
    except Exception:
        if not allow_interactive:
            raise RuntimeError(
                "Earth Engine could not initialize non-interactively. Provide a "
                "service-account key via settings.gee_service_account_key "
                "(GCHD_GEE_SERVICE_ACCOUNT_KEY), or run "
                "`earthengine authenticate` once in a terminal, or pass "
                "allow_interactive=True for local dev."
            )
        ee.Authenticate()
        ee.Initialize(project=settings.gee_project)
        return ee


def make_utils(settings: Settings, ee_module: Any):
    """Construct a ``GEEUtils`` wired from Settings. Injects the run identity
    fields GEEUtils already accepts, so no lib/ change is needed."""
    import sys
    from pathlib import Path

    lib_dir = str(Path(__file__).resolve().parent.parent / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from GEE_functions import GEEUtils  # noqa: E402

    return GEEUtils(
        ee=ee_module,
        unicef_data_source_path=settings.unicef_data_source_path,
        prod_date=settings.prod_date,
        time_period=settings.time_period,
        dataflow=settings.dataflow,
    )


def ee_and_utils(settings: Settings, *, allow_interactive: bool = False) -> Tuple[Any, Any]:
    """Convenience: initialize EE and build GEEUtils in one call.
    Returns ``(ee_module, utils)``."""
    ee_module = init_ee(settings, allow_interactive=allow_interactive)
    return ee_module, make_utils(settings, ee_module)


# -- Stage 2/3 stubs (kept here so the surface is discoverable) ------------

def storage_options(settings: Settings) -> dict:
    """fsspec storage_options for the storage backend. Local paths need none;
    ``abfs://`` needs Azure credentials (DefaultAzureCredential) — wired in Stage 3."""
    if "://" not in settings.storage_root:
        return {}
    raise NotImplementedError(
        "abfs:// storage options are added in Stage 3 (DefaultAzureCredential). "
        "For now use a local storage_root."
    )


def graph_token(settings: Settings) -> str:
    """App-only Microsoft Graph token for the SharePoint push (Stage 2, deferred
    until the UNICEF AAD app registration exists)."""
    raise NotImplementedError(
        "SharePoint app-only auth is deferred pending the UNICEF AAD app "
        "registration (Sites.Selected). NB04 runs in stage-only mode until then."
    )
