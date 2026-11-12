"""Chunk recombination maths for s01c (pipeline/chunked.py). No Earth Engine. Run:
    ..\..\.venv\Scripts\python.exe tests/test_chunked.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.chunked import POP_CLASSES, band, combine

RNG = np.random.default_rng(7)


def _reduce(values, weights, pop, mask, h=0):
    """What Earth Engine returns for one region: weighted sums plus extremes."""
    row = {band(h, "w"): weights.sum(), band(h, "x"): (weights * values).sum(),
           band(h, "x2"): (weights * values ** 2).sum(), band(h, "n"): float(len(values)),
           band(h, "min"): values.min(), band(h, "max"): values.max(),
           band(h, "median"): float(np.median(values))}
    for c in POP_CLASSES:
        row[band(h, f"e_{c}")] = (weights * pop * mask).sum()
    return row


def _unit(n=500):
    values = RNG.gamma(2.0, 3.0, n)
    weights = RNG.uniform(0.2, 1.0, n)          # edge pixels partly inside
    pop = RNG.poisson(4, n).astype(float)
    mask = (values > 5).astype(float)
    return values, weights, pop, mask


def test_split_unit_equals_whole_unit():
    v, w, p, m = _unit()
    cut = [0, 120, 333, len(v)]                  # three chunks
    rows = [dict(ucode="A_0001_0001_V1", **_reduce(v[a:b], w[a:b], p[a:b], m[a:b]))
            for a, b in zip(cut, cut[1:])]
    out = combine(pd.DataFrame(rows), 1).iloc[0]
    mean = (w * v).sum() / w.sum()
    std = np.sqrt((w * (v - mean) ** 2).sum() / w.sum())
    assert np.isclose(out["hazs_mean"], mean)
    assert np.isclose(out["hazs_std"], std)
    assert out["hazs_min"] == v.min() and out["hazs_max"] == v.max()
    assert np.isclose(out["exp_total"], (w * p * m).sum())
    assert out["hazs_count"] == len(v) and out["n_chunks"] == 3
    assert np.isnan(out["hazs_median"]), "a split unit's median must come from the whole-unit pass"


def test_single_chunk_unit_keeps_its_median():
    v, w, p, m = _unit(50)
    out = combine(pd.DataFrame([dict(ucode="B_0001_0001_V1", **_reduce(v, w, p, m))]), 1).iloc[0]
    assert out["n_chunks"] == 1 and np.isclose(out["hazs_median"], np.median(v))


def test_single_chunk_unit_keeps_the_engine_std():
    v, w, p, m = _unit(50)
    row = dict(ucode="F_0001_0001_V1", **_reduce(v, w, p, m))
    row[band(0, "std")] = 1.234
    out = combine(pd.DataFrame([row]), 1).iloc[0]
    assert out["hazs_std"] == 1.234


def test_split_unit_falls_back_to_moment_std():
    v, w, p, m = _unit()
    rows = [dict(ucode="G_0001_0001_V1", **_reduce(v[a:b], w[a:b], p[a:b], m[a:b]), **{band(0, "std"): 9.9})
            for a, b in ((0, 200), (200, len(v)))]
    out = combine(pd.DataFrame(rows), 1).iloc[0]
    mean = (w * v).sum() / w.sum()
    assert np.isclose(out["hazs_std"], np.sqrt((w * (v - mean) ** 2).sum() / w.sum()))


def test_masked_chunk_does_not_blank_the_unit():
    v, w, p, m = _unit(40)
    good = dict(ucode="C_0001_0001_V1", **_reduce(v, w, p, m))
    masked = {k: (np.nan if k != "ucode" else "C_0001_0001_V1") for k in good}  # no valid pixels
    out = combine(pd.DataFrame([good, masked]), 1).iloc[0]
    assert np.isclose(out["hazs_mean"], (w * v).sum() / w.sum())
    assert out["n_chunks"] == 2


def test_fully_masked_unit_has_no_mean():
    row = {"ucode": "D_0001_0001_V1", band(0, "w"): np.nan, band(0, "x"): np.nan, band(0, "x2"): np.nan,
           band(0, "n"): 0.0, band(0, "min"): np.nan, band(0, "max"): np.nan}
    row.update({band(0, f"e_{c}"): 0.0 for c in POP_CLASSES})
    out = combine(pd.DataFrame([row]), 1).iloc[0]
    assert np.isnan(out["hazs_mean"]) and np.isnan(out["hazs_std"])


def test_two_hazards_are_kept_apart():
    v, w, p, m = _unit(60)
    r = {"ucode": "E_0001_0001_V1", **_reduce(v, w, p, m, h=0), **_reduce(v * 10, w, p, m, h=1)}
    out = combine(pd.DataFrame([r]), 2).set_index("hazard_index")
    assert np.isclose(out.loc[1, "hazs_mean"], 10 * out.loc[0, "hazs_mean"])


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} chunk tests passed.")
