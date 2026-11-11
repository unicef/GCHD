"""Sole loader of the country exclusion / status registry
(``config/countries_NA_summary.csv``).

Replaces the NA/state-country rule lists that were triplicated (inlined in
NB02, again as class attributes on ``GEEUtils``, and here in the CSV). The CSV is
the single source; this module reads it into named sets keyed by the CSV's
``list_name`` column.

CSV schema: ``no, ucode, name, type, list_name`` with these ``list_name`` values:
    non_official_codes              - Non-official territories
    sovereignty_unsettled_countries - Sovereignty unsettled
    id_countries_insufficient_data  - Insufficient data (all hazards)
    id_countries_spei_spi           - Insufficient data for SPEI/SPI drought only
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

_SUBNATIONAL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = _SUBNATIONAL_ROOT / "config"
NA_SUMMARY_CSV = CONFIG_DIR / "countries_NA_summary.csv"

# Recognized list_name categories (validated on load so a typo in the CSV fails
# loudly rather than silently producing an empty set).
KNOWN_LIST_NAMES = {
    "non_official_codes",
    "sovereignty_unsettled_countries",
    "id_countries_insufficient_data",
    "id_countries_spei_spi",
}

# Drought hazard codes to which the SPEI/SPI-specific exclusion applies.
SPEI_SPI_HAZARD_CODES = {"drought_spi_tc", "drought_spei_tc"}


@lru_cache(maxsize=4)
def _load(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    required = {"ucode", "list_name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} missing columns: {sorted(missing)}")
    unknown = set(df["list_name"].dropna().unique()) - KNOWN_LIST_NAMES
    if unknown:
        raise ValueError(
            f"{csv_path} has unrecognized list_name values {sorted(unknown)}; "
            f"expected a subset of {sorted(KNOWN_LIST_NAMES)}"
        )
    return df


class NARules:
    """Country exclusion sets, loaded once from the CSV."""

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self._by_list = {
            name: set(df.loc[df["list_name"] == name, "ucode"])
            for name in KNOWN_LIST_NAMES
        }

    # -- Named categories -------------------------------------------------
    @property
    def non_official(self) -> set[str]:
        return set(self._by_list["non_official_codes"])

    @property
    def sovereignty_unsettled(self) -> set[str]:
        return set(self._by_list["sovereignty_unsettled_countries"])

    @property
    def insufficient_data(self) -> set[str]:
        return set(self._by_list["id_countries_insufficient_data"])

    @property
    def spei_spi_insufficient(self) -> set[str]:
        return set(self._by_list["id_countries_spei_spi"])

    # -- Derived helpers --------------------------------------------------
    def excluded_for(self, hazard_code: str) -> set[str]:
        """All ucodes that should be marked non-applicable / NA for a given
        hazard: the always-excluded categories, plus the SPEI/SPI exclusion
        only when the hazard is an SPEI/SPI drought."""
        excluded = self.non_official | self.sovereignty_unsettled | self.insufficient_data
        if hazard_code in SPEI_SPI_HAZARD_CODES:
            excluded |= self.spei_spi_insufficient
        return excluded

    def status_for(self, ucode: str, hazard_code: str) -> str | None:
        """Return a status label for an excluded (ucode, hazard), or None if the
        unit is a normally-processed state. Precedence: non-official > sovereignty
        > insufficient-data > SPEI/SPI."""
        if ucode in self.non_official:
            return "Non-official"
        if ucode in self.sovereignty_unsettled:
            return "Sovereignty unsettled"
        if ucode in self.insufficient_data:
            return "Insufficient data"
        if hazard_code in SPEI_SPI_HAZARD_CODES and ucode in self.spei_spi_insufficient:
            return "SPEI/SPI insufficient data"
        return None


def load_na_rules(*, csv_path: Path | None = None) -> NARules:
    return NARules(_load(str(csv_path or NA_SUMMARY_CSV)))


# =====================================================================
# NB02-specific status rules (used by step s02).
#
# Ported verbatim from notebook 02's inline lists, with TWO deliberate
# corrections agreed during the refactor:
#   (1) DEAD-BRANCH FIX: the notebook keyed per-hazard exclusions on the wrong
#       hazard codes ('riverine_flood', 'coastal_flood', 'fire') so they never
#       fired. Here they use the REAL config codes, so the exclusions now apply.
#   (2) SCOPE: s02 does NOT apply the CSV's SPEI/SPI drought exclusion
#       (id_countries_spei_spi) — NB02 never had it; that rule lives elsewhere.
#
# These stay in code (not the CSV) on purpose: the CSV and the notebook had
# diverged, and the notebook's set is the authoritative one for this step. When
# the CSV is later extended to cover these, s02 can switch to reading it.
# =====================================================================

# Excluded entirely from indices/classes → blank numerics + status="Not Applicable".
NB02_NON_OFFICIAL = ["ALA_V1", "CCK_V1", "CXR_V1", "ESH_V1", "GGY_V1",
                     "JEY_V1", "NFK_V1", "PCN_V1", "SJM_V1"]
NB02_SOVEREIGNTY_UNSETTLED = ["EGY1_V1", "SDN1_V1", "SSD1_V1", "xAB_V1", "xAC_V1",
                              "xAP_V1", "xJK_V1", "xJL_V1", "xPI_V1", "xRI_V1",
                              "xSI_V1", "xSK_V1", "xSR_V1", "xxx_V1"]

# Insufficient data for ALL hazards → blank numerics + status="Insufficient Data".
NB02_INSUFFICIENT_ALL = ["NIC_V1", "PSE_V1", "CUB_V2"]  # Nicaragua, State of Palestine, Cuba

# Insufficient data for SPECIFIC hazards, keyed by the REAL config hazard code
# (this is the dead-branch fix — notebook used 'riverine_flood'/'coastal_flood'/'fire').
NB02_INSUFFICIENT_BY_HAZARD = {
    "river_flood_100yr":   ["FJI_V2"],  # Fiji
    "coastal_flood_100yr": ["CPV_V2", "MDV_V2", "MUS_V2", "NRU_V2",
                            "WSM_V2", "SYC_V2", "TON_V2", "TUV_V2"],
    # Fire is split into two hazards in config; the notebook's single 'fire' list
    # applies to both intensity and frequency.
    "fire_intensity":      ["TUV_V2", "MHL_V2", "MDV_V2", "NRU_V2", "LIE_V1"],
    "fire_frequency":      ["TUV_V2", "MHL_V2", "MDV_V2", "NRU_V2", "LIE_V1"],
    "air_pollution_pm25":  ["NRU_V2", "MCO_V1"],  # Nauru, Monaco
}


def nb02_status_for(ucode: str, hazard_code: str) -> str | None:
    """Return the NB02 status label for an excluded (ucode, hazard), or None if
    the unit is normally processed. Precedence matches the notebook's if/elif:
    Not Applicable (non-official / sovereignty) > Insufficient Data (all) >
    Insufficient Data (per-hazard)."""
    if ucode in NB02_NON_OFFICIAL or ucode in NB02_SOVEREIGNTY_UNSETTLED:
        return "Not Applicable"
    if ucode in NB02_INSUFFICIENT_ALL:
        return "Insufficient Data"
    if ucode in NB02_INSUFFICIENT_BY_HAZARD.get(hazard_code, ()):
        return "Insufficient Data"
    return None
