"""Tests for the multi-hazard overlap assembly (notebook 10).

Pure, no Earth Engine / no network. Run from the subnational_level dir:
    ..\\..\\.venv\\Scripts\\python.exe tests/test_multi_hazard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import multi_hazard as mh

RIVER, COASTAL, STORM, DROUGHT, HEATWAVE = 1, 2, 4, 8, 16


def _long(rows, ucode="MLI_V1"):
    return pd.DataFrame([dict(adm0_ucode=ucode, code=c, pop_t=t, pop_m=m, pop_f=f)
                         for c, t, m, f in rows])


def test_topics_fit_the_bitcode():
    assert mh.N_TOPICS == 8
    assert len({c for _, layers in mh.TOPICS for c in layers}) == 13


def test_topic_codes_exist_in_hazard_info():
    import json
    info = json.load(open(Path(mh.__file__).parent.parent / "config/hazard_info.json",
                          encoding="utf-8"))
    known = {h["code"] for h in info}
    assert not {c for _, layers in mh.TOPICS for c in layers} - known


def test_parse_groups_accepts_list_and_json_string():
    groups = [{"code": 9, "sum": [10.0, 6.0, 4.0]}]
    assert mh.parse_groups("X", groups).equals(mh.parse_groups("X", '[{"code": 9, "sum": [10.0, 6.0, 4.0]}]'))
    assert mh.parse_groups("X", groups).iloc[0]["pop_f"] == 4.0


def test_parse_groups_accepts_drive_csv_text():
    text = "[{code=20, sum=[12086.6, 6081.7, 6004.8]}, {code=150, sum=[0.0, 1.5E7, 0.0]}]"
    out = mh.parse_groups("X", text)
    assert out["code"].tolist() == [20, 150]
    assert out.iloc[1]["pop_m"] == 1.5e7


def test_chunks_of_a_country_sum():
    a = mh.parse_groups("X", [{"code": 1, "sum": [1, 1, 0]}])
    b = mh.parse_groups("X", [{"code": 1, "sum": [2, 1, 1]}])
    out = mh.combine_chunks(pd.concat([a, b]))
    assert len(out) == 1 and out.iloc[0]["pop_t"] == 3


def test_topic_names():
    assert mh.topic_names(0) == "None"
    assert mh.topic_names(DROUGHT | HEATWAVE) == "Drought + Heatwave"


def test_exactly_covers_the_whole_population():
    long = _long([(0, 100, 50, 50), (RIVER, 40, 20, 20), (RIVER | DROUGHT, 30, 16, 14)])
    ex = mh.exactly_table(long)
    assert ex["pop_t"].sum() == 170
    assert len(ex) == mh.N_TOPICS + 1
    assert ex.set_index("n").loc[2, "pop_f"] == 14
    assert ex.set_index("n").loc[8, "pop_t"] == 0


def test_at_least_is_cumulative_and_never_rises():
    long = _long([(0, 100, 50, 50), (RIVER, 40, 20, 20),
                  (RIVER | DROUGHT, 30, 16, 14), (RIVER | DROUGHT | HEATWAVE, 7, 4, 3)])
    al = mh.at_least_table(long).set_index("n")
    assert al.loc[0, "pop_t"] == 177
    assert al.loc[1, "pop_t"] == 77
    assert al.loc[3, "pop_f"] == 3
    assert al.loc[4, "pop_t"] == 0
    assert al["pop_t"].is_monotonic_decreasing


def test_at_least_keeps_countries_apart():
    long = pd.concat([_long([(RIVER, 5, 3, 2)], "AAA_V1"), _long([(RIVER, 9, 5, 4)], "BBB_V1")])
    al = mh.at_least_table(long).set_index(["adm0_ucode", "n"])
    assert al.loc[("AAA_V1", 1), "pop_t"] == 5
    assert al.loc[("BBB_V1", 1), "pop_t"] == 9


def test_marginal_counts_every_combination_with_the_topic():
    long = _long([(RIVER, 40, 20, 20), (RIVER | DROUGHT, 30, 16, 14), (DROUGHT, 5, 3, 2)])
    m = mh.topic_marginals(long).set_index("topic")
    assert m.loc["River Flood", "pop_t"] == 70
    assert m.loc["Drought", "pop_t"] == 35


def test_suppressed_bits_follow_the_status_rules():
    assert mh.suppressed_bits("MLI_V1") == 0
    assert mh.suppressed_bits("FJI_V2") == RIVER
    assert mh.suppressed_bits("MDV_V2") == COASTAL | 64  # coastal and fire


def test_suppression_clears_the_bit_and_keeps_the_children():
    long = _long([(RIVER, 10, 6, 4), (RIVER | STORM, 5, 3, 2), (STORM, 1, 1, 0)], "FJI_V2")
    out = mh.apply_suppression(long).set_index("code")
    assert RIVER not in out.index
    assert out.loc[0, "pop_t"] == 10
    assert out.loc[STORM, "pop_t"] == 6
    assert out["pop_t"].sum() == 16


def test_suppression_leaves_other_countries_alone():
    long = _long([(RIVER, 10, 6, 4)])
    assert mh.apply_suppression(long).iloc[0]["code"] == RIVER


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e!r}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
