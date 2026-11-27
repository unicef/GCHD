"""Structure and content of the built catalog (stac/). Offline except tests marked `network`.

Run: ../.venv/bin/python -m pytest tests -q            (from STAC_catalog/)
     ../.venv/bin/python -m pytest tests -q -m "not network"
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
STAC = ROOT / "stac"
HM = yaml.safe_load((ROOT / "config" / "hazard_map.yaml").read_text())
PORTOLAN_EXT = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"

pytestmark = pytest.mark.skipif(not (STAC / "catalog.json").exists(), reason="run pipeline/08_build_stac.py first")


def load(p: Path) -> dict:
    return json.loads(p.read_text())


@pytest.fixture(scope="module")
def objects() -> dict[Path, dict]:
    return {p: load(p) for p in STAC.rglob("*.json") if p.name in ("catalog.json", "collection.json")}


@pytest.fixture(scope="module")
def collections(objects) -> dict[str, tuple[Path, dict]]:
    return {d["id"]: (p, d) for p, d in objects.items() if d["type"] == "Collection"}


def test_groups_and_layout(objects):
    root = load(STAC / "catalog.json")
    groups = [l["href"].split("/")[1] for l in root["links"] if l["rel"] == "child"]
    assert groups == ["hazards", "multi_hazard", "population", "boundaries", "exposure", "infrastructure", "reference"]
    for p, d in objects.items():
        kids = [load((p.parent / l["href"]).resolve()) for l in d["links"] if l["rel"] == "child"]
        if d["type"] == "Collection":
            assert not kids, f"{p}: collections are leaves (PTL-COL-002)"
        else:
            assert kids, f"{p}: empty catalog"


def test_every_collection_has_a_data_asset(collections):
    for cid, (p, d) in collections.items():
        data = d.get("assets", {}).get("data")
        assert data and "data" in data["roles"] and data.get("type"), cid
        assert data["href"].startswith("https://unidatadapmclimatechange.blob.core.windows.net/public/"), cid


def test_portolan_basics(objects):
    for p, d in objects.items():
        assert PORTOLAN_EXT in d.get("stac_extensions", []), p
        assert d.get("title") and d.get("description"), p
        rels = {l["rel"] for l in d["links"]}
        assert {"agents", "describedby"} <= rels, p
        assert (p.parent / "AGENTS.md").exists() and (p.parent / "README.md").exists(), p
        for l in d["links"]:
            if l["rel"] in ("child", "item"):
                assert l.get("title") and l.get("type"), (p, l["href"])
        if d["type"] == "Collection":
            assert d["providers"][-1]["name"] == "UNICEF" and "host" in d["providers"][-1]["roles"], p
            assert any("producer" in pr["roles"] for pr in d["providers"]), p
            if d["license"] == "other":
                assert "license" in rels, p
            for a in d["assets"].values():
                assert a.get("type") and a.get("roles"), (p, a["href"])


def test_no_raster_v1_fields(objects):
    for p in STAC.rglob("*.json"):
        if p.name == "items.geojson":
            continue
        text = p.read_text()
        assert '"raster:bands"' not in text and '"proj:epsg"' not in text, p


def test_local_assets_exist(objects):
    for p in STAC.rglob("*.json"):
        if p.name == "items.geojson":
            continue
        for a in load(p).get("assets", {}).values():
            if "://" not in a["href"]:
                assert (p.parent / a["href"]).exists(), (p, a["href"])


def test_item_counts(collections):
    n = {cid: sum(1 for l in d["links"] if l["rel"] == "item") for cid, (_, d) in collections.items()}
    assert n["river_flood_100yr_jrc_2024"] == 264
    for g in ("total", "female", "male"):
        assert n[f"worldpop_u18_2025_{g}"] == 240
    assert n["worldpop_2025_total"] == 240
    assert n["worldpop_2025_female"] == n["worldpop_2025_male"] == 237
    for cid, (_, d) in collections.items():
        if n[cid]:
            assert "collection-mirror" in d["assets"]["items_parquet"]["roles"], cid


def test_every_yaml_hazard_has_its_rule(collections):
    rules = {r["hazard_code"]: (cid, r) for cid, (_, d) in collections.items()
             for r in d.get("GCHD:exposure_rules", [])}
    assert set(rules) == set(HM["hazards"])
    for code, h in HM["hazards"].items():
        cid, r = rules[code]
        assert cid == h["stac_collection"], code
        assert (r["valid"], r["op"], float(r["threshold"])) == (h["valid"], h["op"], float(h["threshold"])), code
        assert r["unicef_code"] == h["unicef_code"] and r["app_name"] == h.get("app_name"), code


def test_exposure_tables_describe_their_columns(collections):
    for cid in ("adm0_hazard", "adm1_hazard", "adm2_hazard"):
        cols = collections[cid][1]["table:columns"]
        names = {c["name"] for c in cols}
        assert {"hazard_code", "iso3", "u18_aexp", "u18_rexp"} <= names, cid
        described = [c for c in cols if c.get("description")]
        assert len(described) >= 0.9 * len(cols), cid


@pytest.mark.network
def test_data_assets_are_live(collections):
    for cid, (_, d) in collections.items():
        req = urllib.request.Request(d["assets"]["data"]["href"], method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            assert r.status == 200, cid
            size = d["assets"]["data"].get("file:size")
            assert size is None or int(r.headers["content-length"]) == size, cid


def test_infrastructure_points(collections):
    p, d = collections["giga_schools"]
    assert p.parent.parent.name == "infrastructure"
    assert d["table:primary_geometry"] == "geometry" and d["GCHD:geometry_types"] == ["Point"]
    assert d["assets"]["data"]["file:checksum"].startswith("1220")
    assert any(l["rel"] == "license" and "giga.global" in l["href"] for l in d["links"])
