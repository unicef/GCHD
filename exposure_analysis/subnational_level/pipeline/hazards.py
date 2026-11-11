"""Sole loader of the hazard registry (``config/hazard_info.json``).

Every step gets its hazard list from here, so the config lives in exactly one
place (replacing the notebooks' scattered ``pd.read_json`` calls, one of which
used a bare relative path). Returns fully-parsed ``Hazard`` dataclasses via the
existing ``lib.GEE_functions.Hazard.from_dict``.

Also exposes the known duplicate-count relationships (earthquake / landslide
threshold twins whose raw-pixel count is identical) so NB00-style steps don't
recompute them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .settings import Settings

# Package is pipeline/, config is a sibling of pipeline/ under subnational_level/.
_SUBNATIONAL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = _SUBNATIONAL_ROOT / "config"
HAZARD_INFO_JSON = CONFIG_DIR / "hazard_info.json"

# Hazards whose raw-image pixel count equals another's (same asset/nodata/th_min,
# differ ONLY by threshold, which count() ignores). key = duplicate, value = source.
# Mirrors the map in the productionized notebook 00.
DUPLICATE_COUNT_OF = {
    "earthquake_pga_0p34": "earthquake_pga_0p09",
    "landslides_0p01": "landslides_0p1",
}


def _import_hazard_cls():
    """Import Hazard from lib/. Done lazily so this module imports even if the
    lib path isn't wired yet (e.g. during isolated unit tests of settings)."""
    import sys

    lib_dir = str(_SUBNATIONAL_ROOT / "lib")
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from GEE_functions import Hazard  # noqa: E402

    return Hazard


@lru_cache(maxsize=4)
def _load_raw(json_path: str) -> tuple[dict, ...]:
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{json_path} must contain a JSON list of hazards")
    return tuple(data)


def load_hazards(settings: Settings, *, json_path: Path | None = None):
    """Return the list of ``Hazard`` objects for a run, honoring
    ``settings.process_hazards`` (None = all) and preserving file order.

    Duplicate-count twins are kept (they're real hazards); use
    :func:`unique_count_hazards` when you only want assets to reduce.
    """
    path = str(json_path or HAZARD_INFO_JSON)
    Hazard = _import_hazard_cls()
    rows = _load_raw(path)
    hazards = [Hazard.from_dict(dict(r), asset_prefix=settings.unicef_data_source_path)
               for r in rows]

    if settings.process_hazards:
        wanted = set(settings.process_hazards)
        hazards = [h for h in hazards if h.code in wanted]
        missing = wanted - {h.code for h in hazards}
        if missing:
            raise ValueError(f"process_hazards not found in hazard_info.json: {sorted(missing)}")
    return hazards


def unique_count_hazards(settings: Settings, *, json_path: Path | None = None):
    """Hazards to actually reduce for pixel counts: drops the duplicate twins
    whose count is identical to a source hazard (NB00 optimization)."""
    return [h for h in load_hazards(settings, json_path=json_path)
            if h.code not in DUPLICATE_COUNT_OF]


def hazard_codes(settings: Settings, *, json_path: Path | None = None) -> list[str]:
    return [h.code for h in load_hazards(settings, json_path=json_path)]
