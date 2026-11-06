"""Step 2: read-only COG audit of every source raster -> reports/cog_audit.csv.

Public "Azure link" files are read through /vsicurl/, and the private river
flood tiles through /vsiaz/ (needs AZURE_STORAGE_CONNECTION_STRING). Nothing
is downloaded in full; only headers and validation reads go over the network.

Usage:  python scripts/02_audit_cog.py [--skip-tiles] [--workers 8]
"""
import argparse
import csv
from concurrent.futures import ThreadPoolExecutor

import rasterio
from rio_cogeo.cogeo import cog_validate

from common import (RAW_CONTAINER, REPORTS_DIR, gdal_env, gdal_path, has_credentials,
                    load_layers)

FIELDS = ["layer", "source", "valid_cog", "errors", "warnings", "width", "height",
          "dtype", "count", "nodata", "res_x", "res_y", "crs", "bounds",
          "block", "overviews", "compression", "interleave"]


def audit(layer_id: str, source: str) -> dict:
    path = gdal_path(source)
    row = {"layer": layer_id, "source": source}
    with rasterio.Env(**gdal_env()):
        try:
            valid, errors, warnings = cog_validate(path, quiet=True)
            with rasterio.open(path) as src:
                row.update(
                    valid_cog=valid,
                    errors="; ".join(errors),
                    warnings="; ".join(warnings),
                    width=src.width, height=src.height,
                    dtype=src.dtypes[0], count=src.count, nodata=src.nodata,
                    res_x=src.res[0], res_y=src.res[1],
                    crs=src.crs.to_string() if src.crs else None,
                    bounds=",".join(f"{v:.6f}" for v in src.bounds),
                    block="x".join(map(str, src.block_shapes[0])),
                    overviews=",".join(map(str, src.overviews(1))),
                    compression=src.compression.value if src.compression else None,
                    interleave=src.interleaving.value if src.interleaving else None,
                )
        except Exception as e:  # keep auditing the rest
            row.update(valid_cog=False, errors=f"OPEN FAILED: {e}")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-tiles", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    jobs = []
    for l in load_layers():
        src = l["source"]
        if src["type"] == "file":
            jobs.append((l["id"], src["href"]))
        elif args.skip_tiles:
            continue
        elif not has_credentials():
            print("No Azure credentials: skipping river flood tiles")
        else:
            tiles_csv = REPORTS_DIR / "river_flood_tiles.csv"
            if not tiles_csv.exists():
                raise SystemExit(f"{tiles_csv} missing; run 01_extract_catalog.py first")
            with open(tiles_csv) as f:
                for t in csv.DictReader(f):
                    jobs.append((l["id"], f"{RAW_CONTAINER}/{t['blob']}"))

    print(f"Auditing {len(jobs)} rasters ...")
    with ThreadPoolExecutor(args.workers) as ex:
        rows = list(ex.map(lambda j: audit(*j), jobs))

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / "cog_audit.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    n_valid = sum(bool(r.get("valid_cog")) for r in rows)
    n_fail = sum(str(r.get("errors", "")).startswith("OPEN FAILED") for r in rows)
    print(f"{n_valid}/{len(rows)} valid COGs, {n_fail} failed to open -> {out}")


if __name__ == "__main__":
    main()
