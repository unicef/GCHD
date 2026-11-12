"""Recombine per-chunk reductions into per-admin2 statistics (no Earth Engine).

s01c reduces every country over the admin-2 units cut by a 500 km grid
(``adm2_chunked_500km_shp``) and gets, per chunk and hazard:

    e_<class>  sum of pop_<class> x hazard_mask      (exposed population)
    w          sum of 1 over valid hazard pixels      (pixel weight)
    x, x2      sum of hazard, sum of hazard squared
    min, max   extremes of the hazard
    n          unweighted count of valid hazard pixels (the s00 hazs_count)

Earth Engine weights ``sum`` by the fraction of each pixel inside the region,
and the chunks of a unit partition it, so the chunk sums add up to the unit's
sums exactly. From them:

    mean = sum(x) / sum(w)
    std  = sqrt(sum(x2) / sum(w) - mean^2)    (population std, as ee.Reducer.stdDev)

Earth Engine's own ``mean`` and ``stdDev`` can differ slightly from these, and a
median cannot be combined at all. So a unit in a single chunk keeps the chunk's
own mean, std and median when present, and s01c replaces every statistic of a
unit split across chunks with a whole-unit reduction; the moments are the
fallback.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

POP_CLASSES = ["total", "total_female", "total_male",
               "under_18_total", "under_18_female", "under_18_male"]
SUM_STATS = ["w", "x", "x2", "n"]


def band(h: int, stat: str) -> str:
    """Band / property name for hazard index ``h`` (short, EE-safe)."""
    return f"h{h}_{stat}"


def combine(chunks: pd.DataFrame, n_hazards: int, key: str = "ucode") -> pd.DataFrame:
    """Per-unit statistics from per-chunk rows.

    ``chunks`` has one row per chunk with ``key`` and, for each hazard index h,
    columns ``h{h}_e_<class>``, ``h{h}_w``, ``h{h}_x``, ``h{h}_x2``, ``h{h}_n``,
    ``h{h}_min``, ``h{h}_max`` and optionally ``h{h}_median``. Missing values
    (masked chunks) count as 0 in sums and are ignored by min/max.

    Returns one row per (unit, hazard index) with ``exp_<class>``, ``hazs_mean``,
    ``hazs_std``, ``hazs_min``, ``hazs_max``, ``hazs_count``, ``n_chunks`` and
    ``hazs_median`` (the chunk's own, for single-chunk units; else NaN). ``hazs_std``
    is the chunk's own for single-chunk units when ``h{h}_std`` is present.
    """
    grouped = chunks.groupby(key, sort=True)
    n_chunks = grouped.size().rename("n_chunks")
    out = []
    for h in range(n_hazards):
        sums = [band(h, f"e_{c}") for c in POP_CLASSES] + [band(h, s) for s in SUM_STATS]
        present = [c for c in sums if c in chunks.columns]
        s = grouped[present].sum(min_count=1)
        mn = grouped[band(h, "min")].min() if band(h, "min") in chunks else np.nan
        mx = grouped[band(h, "max")].max() if band(h, "max") in chunks else np.nan

        df = pd.DataFrame(index=s.index)
        df["hazard_index"] = h
        for c in POP_CLASSES:
            df[f"exp_{c}"] = s.get(band(h, f"e_{c}"), np.nan)
        nan = pd.Series(np.nan, index=s.index)
        w, x, x2 = (s.get(band(h, k), nan) for k in ("w", "x", "x2"))  # moments are optional
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = (x / w).where(w > 0)
            var = (x2 / w - mean ** 2).clip(lower=0)
        df["hazs_mean"] = mean
        df["hazs_std"] = np.sqrt(var)
        df["hazs_min"] = mn
        df["hazs_max"] = mx
        df["hazs_count"] = s.get(band(h, "n"), np.nan)
        df = df.join(n_chunks)
        single = df["n_chunks"] == 1
        med_col = band(h, "median")
        df["hazs_median"] = grouped[med_col].first().where(single) if med_col in chunks else np.nan
        for stat in ("mean", "std"):  # the engine's own value for a unit in one chunk
            col = band(h, stat)
            if col in chunks:
                df[f"hazs_{stat}"] = grouped[col].first().where(single, df[f"hazs_{stat}"])
        out.append(df)
    return pd.concat(out).reset_index().rename(columns={key: "adm2_ucode"})
