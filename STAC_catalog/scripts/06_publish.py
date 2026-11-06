"""Step 6: build STAC Browser for GitHub Pages -> STAC_catalog/browser/.

  - checks (read-only) that the storage account's CORS rules allow GET from
    https://unicef.github.io, which the browser needs to preview COGs
  - builds radiantearth/stac-browser (pinned) with browser_config/config.GCHD.mjs,
    catalogUrl = the Pages URL of stac/catalog.json, and strips source maps

STAC Browser v5 needs Node >= 22. Give a node binary directory with --node-bin
if the system node is older (e.g. work/node22/node_modules/node/bin).

Usage:  python scripts/06_publish.py [--node-bin DIR] [--local]
        --local builds into work/browser-local for http://localhost:8765 instead
"""
import argparse
import os
import subprocess
from pathlib import Path

from azure.storage.blob import BlobServiceClient

from common import CONN_STR, PAGES_URL, REPO_DIR, STAC_DIR

STAC_BROWSER_TAG = "v5.1.0"
SRC = STAC_DIR / "work" / "stac-browser"
CONFIG = STAC_DIR / "browser_config" / "config.GCHD.mjs"
PAGES_ORIGIN = "https://unicef.github.io"


def check_cors():
    rules = BlobServiceClient.from_connection_string(CONN_STR).get_service_properties()["cors"]
    ok = any(PAGES_ORIGIN in r.allowed_origins.split(",") or r.allowed_origins == "*" for r in rules
             if "GET" in r.allowed_methods.split(","))
    print(f"CORS GET from {PAGES_ORIGIN}: {'ok' if ok else 'MISSING - COG previews will not render'}")


# STAC Browser draws basemaps with WebGLTile layers. Where WebGL is unavailable (hardware
# acceleration off, remote desktops, some embedded browsers) the basemap fails silently and the
# whole map stays blank, overlays included. Fall back to the canvas Tile layer there.
BASEMAP_PATCH = (
    "src/components/maps/MapMixin.js",
    "          let layerClassName = 'WebGLTile';\n",
    "          // GCHD patch: canvas fallback where WebGL is unavailable (see scripts/06_publish.py)\n"
    "          const canvas = document.createElement('canvas');\n"
    "          const hasWebGL = Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl'));\n"
    "          let layerClassName = hasWebGL ? 'WebGLTile' : 'Tile';\n",
)


def patch_source():
    path, old, new = BASEMAP_PATCH
    f = SRC / path
    text = f.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"{path}: basemap patch no longer applies to {STAC_BROWSER_TAG}, check it")
    f.write_text(text.replace(old, new))


def build(node_bin: str | None, local: bool):
    if not SRC.exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", STAC_BROWSER_TAG,
                        "https://github.com/radiantearth/stac-browser.git", str(SRC)], check=True)
    patch_source()
    env = os.environ.copy()
    if node_bin:
        env["PATH"] = f"{Path(node_bin).resolve()}:{env['PATH']}"
    if local:
        out = STAC_DIR / "work" / "browser-local"
        env |= {"SB_catalogUrl": "http://localhost:8765/STAC_catalog/stac/catalog.json",
                "SB_pathPrefix": "/STAC_catalog/work/browser-local/"}
    else:
        out = STAC_DIR / "browser"
        env |= {"SB_catalogUrl": PAGES_URL + "stac/catalog.json",
                "SB_pathPrefix": "/GCHD/STAC_catalog/browser/"}
    env["SB_CONFIG"] = str(CONFIG)

    if not (SRC / "node_modules" / "ol-mapbox-style").exists():
        subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=SRC, env=env, check=True)
    subprocess.run(["npx", "vite", "build", "--outDir", str(out), "--emptyOutDir"], cwd=SRC, env=env, check=True)
    for m in out.rglob("*.map"):
        m.unlink()
    # Pages runs Jekyll by default, which drops files starting with "_" (e.g. __vite-browser-external.js).
    # .nojekyll only works at the site root, i.e. the repo root.
    if not local:
        (REPO_DIR / ".nojekyll").touch()
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"STAC Browser -> {out} ({size:.0f} MB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--node-bin")
    ap.add_argument("--local", action="store_true")
    args = ap.parse_args()
    check_cors()
    build(args.node_bin, args.local)
