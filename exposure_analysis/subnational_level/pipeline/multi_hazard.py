"""Children simultaneously exposed to several climate hazards (admin0).

Per-hazard exposure tables cannot give overlap: they say how many children are
exposed, not which ones. So each pixel gets a bitcode (0-255) recording which of
the 8 climate topics apply, and child population is summed per code per country.
That single reduction yields every combination; "at least N hazards", "exactly N"
and any specific pair are then pure pandas, as is clearing a suppressed hazard.

Hazard definitions come from the pipeline (``GEEUtils.define_hazard``), so a
single-topic total reconciles with the per-hazard tables. Population and geometry
follow the dashboard (``gee_core.compute_exposure``): the WorldPop mosaics, which
include the Kosovo / Aland rasters, and the 500 km chunks of adm0, which avoid
memory limits on large countries.

``ee`` is passed in rather than imported, so this module loads without EE.
"""

from __future__ import annotations

import glob
import json
import re

import numpy as np
import pandas as pd

from .na_rules import nb02_status_for

# (topic, hazard_info codes). Position in this list is the topic's bit. A topic
# applies to a pixel if ANY of its layers exceeds its threshold.
TOPICS = [
    ("River Flood",       ["river_flood_100yr"]),
    ("Coastal Flood",     ["coastal_flood_100yr"]),
    ("Tropical Storm",    ["tropical_storm_100yr"]),
    ("Drought",           ["drought_asi", "drought_spi_tc", "drought_spei_tc"]),
    ("Heatwave",          ["heatwave_frequency", "heatwave_duration", "heatwave_severity"]),
    ("Extreme Heat",      ["extreme_heat_days"]),
    ("Fire",              ["fire_intensity", "fire_frequency"]),
    ("Sand & Dust Storm", ["sand_dust_storm_susc"]),
]
N_TOPICS = len(TOPICS)

POP_ASSET_TMPL = "projects/unicef-ccri/assets/population/worldpop_{}_2025_CN_100m"
CHUNK_ASSET = "projects/unicef-ccri/assets/global_boundary/adm0_chunked_500km_shp"
# Countries whose source-table ucode differs from the one in CHUNK_ASSET.
CHUNK_UCODE = {"MLI_V2": "MLI_V1"}

# population class id -> output column, in reducer order
POP_CLASSES = {"T_U18": "pop_t", "T_M_U18": "pop_m", "T_F_U18": "pop_f"}
SUM_COLS = list(POP_CLASSES.values())


# -- Earth Engine ----------------------------------------------------------

def build_stack(ee, utils, hazards) -> tuple:
    """Return (image, grid) where image is [pop_t, pop_m, pop_f, code].

    ``grid`` holds the native WorldPop crs/crsTransform: a mosaic has no fixed
    projection (see the scale defect in CLAUDE.md), so the reduction must be
    pinned to the population grid rather than inferred from the image.
    """
    by_code = {h.code: h for h in hazards}

    code_img = ee.Image.constant(0).toInt()
    for bit, (_, layers) in enumerate(TOPICS):
        union = ee.Image.constant(0)
        for hazard_code in layers:
            mask = utils.define_hazard(by_code[hazard_code])["hazard_masked_image"]
            # Outside a raster's coverage means "not exposed", not "drop the
            # pixel" -- the same semantics as the agreed No Data = 0.
            union = union.Or(mask.unmask(0))
        code_img = code_img.add(union.toInt().multiply(1 << bit))

    collections = {k: ee.ImageCollection(POP_ASSET_TMPL.format(k)) for k in POP_CLASSES}
    pop = {k: c.mosaic().select(0).rename(POP_CLASSES[k]) for k, c in collections.items()}
    # The group reducer drops a pixel if any input is masked, so the sex bands
    # must not remove a pixel that the total band has.
    base = pop["T_U18"]
    stack = (base
             .addBands(pop["T_M_U18"].unmask(0).updateMask(base.mask()))
             .addBands(pop["T_F_U18"].unmask(0).updateMask(base.mask()))
             .addBands(code_img.rename("code").toInt()))

    proj = collections["T_U18"].first().projection().getInfo()
    return stack, {"crs": proj["crs"], "crsTransform": proj["transform"]}


def reduce_country(ee, stack, grid, ucode: str, tile_scale: int = 8):
    """FeatureCollection with one feature per chunk of ``ucode``, each carrying
    ``groups``: a list of {code, sum: [t, m, f]}."""
    chunks = (ee.FeatureCollection(CHUNK_ASSET)
              .filter(ee.Filter.eq("ucode", CHUNK_UCODE.get(ucode, ucode)))
              .map(lambda f: f.set("ucode", ucode)))
    reducer = ee.Reducer.sum().repeat(len(SUM_COLS)).group(
        groupField=len(SUM_COLS), groupName="code")
    reduced = stack.reduceRegions(collection=chunks, reducer=reducer,
                                  tileScale=tile_scale, **grid)
    return reduced.select(["ucode", "groups"], None, False)


# -- Pure pandas -----------------------------------------------------------

def parse_groups(ucode: str, groups) -> pd.DataFrame:
    """One chunk's ``groups`` (list, JSON string, or the ``{code=20, sum=[...]}``
    text a Drive CSV holds) -> long frame [adm0_ucode, code, pop_t, pop_m, pop_f]."""
    if isinstance(groups, str):
        groups = json.loads(re.sub(r"(\w+)=", r'"\1":', groups))
    rows = [(ucode, int(g["code"]), *g["sum"]) for g in groups]
    return pd.DataFrame(rows, columns=["adm0_ucode", "code"] + SUM_COLS)


def load_exports(csv_dir: str) -> pd.DataFrame:
    """Read every exported country CSV (columns ucode, groups) in ``csv_dir`` into
    one long frame, summed over chunks. A chunk with no population has no groups."""
    files = glob.glob(f"{csv_dir}/*.csv")
    if not files:
        raise FileNotFoundError(f"no CSVs in {csv_dir}")
    frames = []
    for f in files:
        for row in pd.read_csv(f).itertuples():
            if isinstance(row.groups, str) and row.groups.strip():
                frames.append(parse_groups(row.ucode, row.groups))
    return combine_chunks(pd.concat(frames, ignore_index=True))


def combine_chunks(long: pd.DataFrame) -> pd.DataFrame:
    """Sum chunks of the same country and code."""
    return long.groupby(["adm0_ucode", "code"], as_index=False)[SUM_COLS].sum()


def n_hazards(code) -> np.ndarray:
    """Number of topics set in each bitcode."""
    return np.array([bin(int(c)).count("1") for c in np.atleast_1d(code)])


def topic_names(code: int) -> str:
    """'Drought + Heatwave' for a bitcode; 'None' for 0."""
    names = [t for bit, (t, _) in enumerate(TOPICS) if code >> bit & 1]
    return " + ".join(names) if names else "None"


def suppressed_bits(ucode: str) -> int:
    """Bitmask of the topics with Insufficient Data for this country. A topic is
    suppressed if any of its layers is; a partly assessed topic is not a topic."""
    mask = 0
    for bit, (_, layers) in enumerate(TOPICS):
        if any(nb02_status_for(ucode, c) == "Insufficient Data" for c in layers):
            mask |= 1 << bit
    return mask


def apply_suppression(long: pd.DataFrame) -> pd.DataFrame:
    """Clear each country's suppressed bits and re-sum. Children stay in the
    total; they just no longer count as exposed to that hazard."""
    df = long.copy()
    keep = df["adm0_ucode"].map(lambda u: ~suppressed_bits(u) & (2 ** N_TOPICS - 1))
    df["code"] = df["code"].astype(int) & keep.astype(int)
    return combine_chunks(df)


def exactly_table(long: pd.DataFrame) -> pd.DataFrame:
    """Long [adm0_ucode, n, pop_t, pop_m, pop_f]: children exposed to exactly n
    topics, for every n in 0..N_TOPICS (0 where none)."""
    df = long.assign(n=n_hazards(long["code"]))
    out = df.groupby(["adm0_ucode", "n"])[SUM_COLS].sum()
    idx = pd.MultiIndex.from_product(
        [sorted(long["adm0_ucode"].unique()), range(N_TOPICS + 1)],
        names=["adm0_ucode", "n"])
    return out.reindex(idx, fill_value=0.0).reset_index()


def at_least_table(long: pd.DataFrame) -> pd.DataFrame:
    """Long [adm0_ucode, n, pop_t, pop_m, pop_f]: children exposed to at least n
    topics. n = 0 is the whole child population."""
    ex = exactly_table(long).sort_values(["adm0_ucode", "n"], ascending=[True, False])
    ex[SUM_COLS] = ex.groupby("adm0_ucode")[SUM_COLS].cumsum()
    return ex.sort_values(["adm0_ucode", "n"]).reset_index(drop=True)


def topic_marginals(long: pd.DataFrame) -> pd.DataFrame:
    """Long [adm0_ucode, topic, pop_t, pop_m, pop_f]: children exposed to each
    topic regardless of the others, for reconciling with the per-hazard tables."""
    frames = []
    for bit, (topic, _) in enumerate(TOPICS):
        hit = long[(long["code"].astype(int) & (1 << bit)) != 0]
        frames.append(hit.groupby("adm0_ucode", as_index=False)[SUM_COLS].sum()
                      .assign(topic=topic))
    return pd.concat(frames, ignore_index=True)
