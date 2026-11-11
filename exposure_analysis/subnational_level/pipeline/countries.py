"""Resolve a country filter (``settings.process_countries``) to ucodes.

The filter accepts ucodes (``EGY_V1``, ``BES1_V2``) and ISO3 codes (``EGY``),
mixed. An ISO3 code expands to every ucode that shares it in
``config/countries_info.csv`` (``EGY`` -> ``EGY_V1``, ``EGY1_V1``), so the
pure-pandas steps resolve it without Earth Engine.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

COUNTRIES_INFO_CSV = Path(__file__).resolve().parents[1] / "config" / "countries_info.csv"


@lru_cache(maxsize=1)
def iso3_to_ucodes() -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    with open(COUNTRIES_INFO_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mapping.setdefault(row["ISO3"], []).append(row["ucode"])
    return {k: tuple(sorted(v)) for k, v in mapping.items()}


def is_ucode(entry: str) -> bool:
    return "_V" in entry


def resolve(entries: list[str] | None, available: list[str] | None = None) -> list[str] | None:
    """Ucodes selected by ``entries``, or None (meaning "all") when no filter is set.

    When ``available`` is given (e.g. the EE country list without the
    no-population countries), the result is restricted to it and keeps its
    order. Unknown entries raise, so a typo never silently selects nothing.
    """
    if not entries:
        return None if available is None else list(available)
    lookup = iso3_to_ucodes()
    wanted: set[str] = set()
    unknown = []
    for e in entries:
        e = e.strip()
        if is_ucode(e):
            wanted.add(e)
        elif e in lookup:
            wanted.update(lookup[e])
        else:
            unknown.append(e)
    if unknown:
        raise ValueError(f"unknown country codes (not a ucode or ISO3 in {COUNTRIES_INFO_CSV.name}): {unknown}")
    if available is None:
        return sorted(wanted)
    return [u for u in available if u in wanted]


def countries_to_process(utils, entries: list[str] | None) -> list[str]:
    """EE-backed list of ucodes to process (no-population countries removed),
    filtered by ``entries``."""
    return resolve(entries, utils.get_countries_to_process(None))
