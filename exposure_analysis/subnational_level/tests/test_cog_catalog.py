"""The COG route's fixed paths (``cog_zonal.COG_LAYERS``) against the STAC catalogue.

Each COG the route reads must be a catalogue item whose ``GCHD:gee_asset`` is
the asset s01/s01c read for that hazard (``config/hazard_info.json``), so the
code and the catalogue cannot drift apart unnoticed. Reads the catalogue in
this repository (``STAC_catalog/stac``); with GCHD_TEST_STAC=1 also the
published one. No Earth Engine.

    ..\\..\\.venv\\Scripts\\python.exe tests/test_cog_catalog.py
    set GCHD_TEST_STAC=1 && ..\\..\\.venv\\Scripts\\python.exe tests/test_cog_catalog.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.cog_zonal import AZURE, COG_LAYERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
STAC_DIR = REPO / "STAC_catalog" / "stac"
STAC_URL = "https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json"
CONFIG = ROOT / "config" / "hazard_info.json"
ASSET_PREFIX = "projects/unicef-ccri/assets"
STAC_LIVE = os.environ.get("GCHD_TEST_STAC") == "1"

# catalogue link known to be wrong (STAC_catalog/qa/ISSUES.md); the COG itself matches the pipeline asset
KNOWN_WRONG_LINK = {
    "complex_emergencies_acled_0p01_grid": "S-06",
    "volcano_100km_buff": "S-07",
}


def _pipeline_assets() -> dict[str, str]:
    out = {}
    for h in json.loads(CONFIG.read_text(encoding="utf-8")):
        a = h["asset"]
        out[h["code"]] = a if a.startswith("projects/") else f"{ASSET_PREFIX}/hazards/{a}"
    return out


def _local_items() -> dict[str, str]:
    """COG href -> GCHD:gee_asset, every item in the repository's catalogue."""
    out = {}
    for f in STAC_DIR.rglob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("type") == "Feature" and "data" in d.get("assets", {}):
            out[d["assets"]["data"]["href"]] = d["properties"].get("GCHD:gee_asset")
    return out


def _live_items() -> dict[str, str]:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()  # GitHub Pages answers bursts with 503
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=6, backoff_factor=2, status_forcelist=(429, 503))))
    out, todo = {}, [STAC_URL]
    while todo:
        url = todo.pop()
        d = s.get(url, timeout=60).json()
        if d.get("type") == "Feature":
            if "data" in d.get("assets", {}):
                out[requests.compat.urljoin(url, d["assets"]["data"]["href"])] = d["properties"].get("GCHD:gee_asset")
            continue
        todo += [requests.compat.urljoin(url, l["href"]) for l in d.get("links", []) if l["rel"] in ("child", "item")]
    return out


def _check(items: dict[str, str]) -> None:
    assets, problems = _pipeline_assets(), []
    for code, path in COG_LAYERS.items():
        href = f"{AZURE}/gchd_cog/{path}"
        if href not in items:
            problems.append(f"{code}: {path} is not a catalogue item")
            continue
        same = items[href] == assets[code]
        if code in KNOWN_WRONG_LINK:
            if same:
                problems.append(f"{code}: link fixed ({KNOWN_WRONG_LINK[code]}), remove it from KNOWN_WRONG_LINK")
        elif not same:
            problems.append(f"{code}: catalogue links {items[href]}, the pipeline reads {assets[code]}")
    assert not problems, "\n        ".join([""] + problems)


def test_cog_layers_are_known_hazards():
    unknown = set(COG_LAYERS) - set(_pipeline_assets())
    assert not unknown, f"not in hazard_info.json: {sorted(unknown)}"


def test_cog_layers_match_repository_catalogue():
    _check(_local_items())


def test_cog_layers_match_published_catalogue():
    if not STAC_LIVE:
        print("  SKIP  published catalogue (set GCHD_TEST_STAC=1)")
        return
    _check(_live_items())


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
