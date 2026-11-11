"""Canonical artifact layout for the pipeline.

Every path a step reads or writes is built here, off ``settings.storage_root``.
This is what kills the notebooks' output-folder drift (NB02 ``global_NA/CSV``,
NB03/05 ``global/CSV``, NB05 ``output_CO_NA``, NB06/07 absolute ``output_mali``):
they all collapse to the ``base/global`` layer defined below.

Layers (named by pipeline STAGE, matching how the team reasons about 00-07)
---------------------------------------------------------------------------
    aux      : hazs_count weight table                         (NB00)
    base     : the extraction+indices stage                    (NB01-02)
                 base/partials : per-(hazard, country) partials (NB01)
                 base/global   : global per-hazard CSV with indices/classes/NA
                                 (NB02, the MAIN deliverable everything reads)
    export   : delivery formats — Excel, GeoPackage, SDMX       (NB03, NB05)
    upscale  : admin1 / admin0 rollups                          (NB06, NB07)
    _manifests: per-run lineage json                            (Stage 5)

We deliberately do NOT use the bronze/silver/gold "medallion" convention: it
encodes refinement tiers, whereas 06-07 produce deliverables derived from other
deliverables (a case medallion has no clean slot for). Stage names keep the
01-02 vs 03-05 vs 06-07 distinctions the team already thinks in.

Local vs remote
---------------
``storage_root`` may be a local path (``output``) or an fsspec URL
(``abfs://container/prefix``). Paths are joined with ``/`` (valid for both fsspec
URLs and, on Windows, for Python file APIs). Use :func:`ensure_local_dir` only
for the local case — when writing to Blob later, steps go through fsspec and do
not pre-create directories.

Note on ``lib`` compatibility
------------------------------
``GEEUtils.save_global_results(df, code, output_folder, date)`` writes
``{output_folder}/global/{code}_{date}.csv``. So passing ``base_root()`` as its
``output_folder`` yields exactly ``base/global/{code}_{date}.csv`` — no lib
change needed. Likewise ``save_country_results`` writes
``{output_folder}/hazards/{code}/partials/...`` → also pass ``base_root()``
(giving ``base/hazards/{code}/partials/...``).
"""

from __future__ import annotations

import os

from .settings import Settings


def _join(*parts: str) -> str:
    """Join path segments with forward slashes, safe for local paths and
    fsspec URLs alike (avoids backslashes that would break ``abfs://`` URLs)."""
    cleaned = [str(p).strip("/") for p in parts if p is not None and str(p) != ""]
    # Preserve a scheme like "abfs://container" or a leading "/" if present.
    head = str(parts[0]) if parts else ""
    if "://" in head:
        scheme, _, rest = head.partition("://")
        cleaned[0] = rest.strip("/")
        return f"{scheme}://" + "/".join(cleaned)
    joined = "/".join(cleaned)
    if head.startswith("/"):
        joined = "/" + joined
    return joined


def is_remote(settings: Settings) -> bool:
    """True if storage_root is an fsspec URL (has a scheme) rather than a local path."""
    return "://" in settings.storage_root


# -- Layer roots -----------------------------------------------------------

def aux_root(s: Settings) -> str:
    return _join(s.storage_root, "aux")


def base_root(s: Settings) -> str:
    """The 01-02 extraction+indices stage root.

    Hand this to BOTH GEEUtils.save_country_results (it appends
    ``hazards/{code}/partials/...`` → ``base/hazards/...``) and
    GEEUtils.save_global_results (it appends ``global/...`` → ``base/global/...``).
    """
    return _join(s.storage_root, "base")


def export_root(s: Settings) -> str:
    """The 03/05 delivery-formats stage root (Excel, GeoPackage, SDMX)."""
    return _join(s.storage_root, "export")


def upscale_root(s: Settings) -> str:
    """The 06/07 admin1/admin0 rollup stage root."""
    return _join(s.storage_root, "upscale")


def manifest_root(s: Settings) -> str:
    return _join(s.storage_root, "_manifests", s.prod_date)


# -- Concrete artifact paths ----------------------------------------------

def hazs_count_csv(s: Settings) -> str:
    """NB00 assembled weight table."""
    return _join(aux_root(s), f"hazs_count_{s.prod_date}.csv")


def export_manifest_csv(s: Settings) -> str:
    """NB00 export-task manifest."""
    return _join(aux_root(s), f"export_manifest_{s.prod_date}.csv")


def base_partial_csv(s: Settings, hazard_code: str, ucode: str) -> str:
    """NB01 per-(hazard, country) partial. Matches GEEUtils.save_country_results
    when handed base_root() as output_folder → base/hazards/.../partials/..."""
    return _join(base_root(s), "hazards", hazard_code, "partials",
                 f"{ucode}_{hazard_code}_admin2.csv")


def base_partials_glob(s: Settings, hazard_code: str) -> str:
    """Glob for all country partials of one hazard (NB02 concat input)."""
    return _join(base_root(s), "hazards", hazard_code, "partials",
                 f"*_{hazard_code}_admin2.csv")


def base_global_csv(s: Settings, hazard_code: str) -> str:
    """NB02 main deliverable. Matches GEEUtils.save_global_results output when
    handed base_root() as output_folder → base/global/{code}_{date}.csv."""
    return _join(base_root(s), "global", f"{hazard_code}_{s.prod_date}.csv")


def export_excel(s: Settings, hazard_code: str, ucode: str | None = None) -> str:
    """NB03 excel; per-country if ucode given, else global."""
    if ucode:
        return _join(export_root(s), "results", ucode, "excel",
                     f"{ucode}_{hazard_code}_{s.prod_date}.xlsx")
    return _join(export_root(s), "global", "excel", f"{hazard_code}_{s.prod_date}.xlsx")


def export_geopackage(s: Settings, hazard_code: str, ucode: str | None = None) -> str:
    """NB03 geopackage; per-country if ucode given, else global."""
    if ucode:
        return _join(export_root(s), "results", ucode, "geopackage",
                     f"{ucode}_{hazard_code}_{s.prod_date}.gpkg")
    return _join(export_root(s), "global", "geopackage", f"{hazard_code}_{s.prod_date}.gpkg")


def export_sdmx_csv(s: Settings, stream: str, hazard_code: str | None = None) -> str:
    """NB05 SDMX output. stream in {'hazard','exposure','population'}. Population
    is written once (no hazard code)."""
    if stream not in ("hazard", "exposure", "population"):
        raise ValueError(f"unknown SDMX stream {stream!r}")
    base = _join(export_root(s), "sdmx", stream, "CSV")
    if stream == "population":
        return _join(base, f"HAZARD_SDMX_{s.prod_date}.csv")
    return _join(base, f"HAZARD_SDMX_{stream}_{hazard_code}_{s.prod_date}.csv")


def upscale_admin1_csv(s: Settings, hazard_code: str) -> str:
    """NB07 admin1 rollup, per hazard."""
    return _join(upscale_root(s), "global_admin1", f"{hazard_code}_{s.prod_date}.csv")


def upscale_admin0_csv(s: Settings, hazard_code: str) -> str:
    """NB07 admin0 rollup, per hazard."""
    return _join(upscale_root(s), "global_admin0", f"{hazard_code}_{s.prod_date}.csv")


def upscale_country_admin1(s: Settings, ucode: str, shape: str) -> str:
    """NB06 single-country admin1 summary. shape in {'long','wide'}."""
    if shape not in ("long", "wide"):
        raise ValueError(f"shape must be 'long' or 'wide', got {shape!r}")
    return _join(upscale_root(s), "results_admin1", ucode,
                 f"{ucode}_admin1_{shape}_{s.prod_date}.csv")


def manifest_json(s: Settings, step: str) -> str:
    """Per-step run manifest (Stage 5)."""
    return _join(manifest_root(s), f"{step}.json")


# -- Local helpers ---------------------------------------------------------

def ensure_local_dir(path: str) -> str:
    """Create the parent directory for a LOCAL path. No-op for fsspec URLs
    (remote writes go through fsspec, which creates prefixes implicitly).
    Returns the path unchanged for convenient chaining."""
    if "://" not in path:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    return path
