"""Step 11: per-country copies of the ADM1/ADM2 exposure tables, for the browser data assistant.

The browser app (browser_app/) cannot range-read the whole-world tables (Azure does not expose
Content-Range), so without these it downloads adm2_hazard.parquet (~50 MB) in full. This step writes
one Parquet file per country, same columns and rows as the source table:

  public/gchd_cog/exposure_by_country/<table>/<sha>/<ISO3>.parquet

<sha> is the first 16 hex digits of the sha256 in the STAC data asset's file:checksum, so a new version
of a table goes to a new folder and published files are never overwritten. The app derives the same
path from the catalog and falls back to the whole table when a file is missing.

Usage:  python pipeline/11_split_exposure.py [--tables adm1_hazard adm2_hazard] [--upload]
        without --upload the files are only written to work/exposure_by_country/
"""
import argparse
import hashlib
import json
import urllib.request

import duckdb

import _path  # noqa: F401,E402  (STAC_catalog/ on sys.path)
from gchd_stac.common import COG_PREFIX, PUBLIC_CONTAINER, STAC_OUT, WORK_DIR, container_client

PREFIX = f"{COG_PREFIX}/exposure_by_country"


def source(table: str) -> tuple[str, str]:
    """(href, sha256 hex) of the table's data asset in the generated STAC catalog."""
    asset = json.loads((STAC_OUT / "exposure" / table / "collection.json").read_text())["assets"]["data"]
    mh = asset["file:checksum"]
    if not mh.startswith("1220"):
        raise SystemExit(f"{table}: file:checksum is not a sha256 multihash: {mh}")
    return asset["href"], mh[4:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", nargs="+", default=["adm1_hazard", "adm2_hazard"])
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    cc = container_client(PUBLIC_CONTAINER) if args.upload else None

    for table in args.tables:
        href, sha = source(table)
        tag = sha[:16]
        out = WORK_DIR / "exposure_by_country" / table / tag
        out.mkdir(parents=True, exist_ok=True)
        src = WORK_DIR / "exposure_by_country" / f"{table}.parquet"
        if not src.exists() or hashlib.sha256(src.read_bytes()).hexdigest() != sha:
            print(f"downloading {href}")
            urllib.request.urlretrieve(href, src)
        got = hashlib.sha256(src.read_bytes()).hexdigest()
        if got != sha:
            raise SystemExit(f"{table}: downloaded file sha256 {got} does not match the catalog ({sha})")

        con = duckdb.connect()
        isos = [r[0] for r in con.execute(f"SELECT DISTINCT iso3 FROM '{src}' WHERE iso3 IS NOT NULL ORDER BY 1").fetchall()]
        total = con.execute(f"SELECT count(*) FROM '{src}'").fetchone()[0]
        n = 0
        for iso in isos:
            f = out / f"{iso}.parquet"
            if not f.exists():
                con.execute(f"COPY (SELECT * FROM '{src}' WHERE iso3 = ?) TO '{f}' (FORMAT parquet, COMPRESSION zstd)", [iso])
            n += con.execute(f"SELECT count(*) FROM '{f}'").fetchone()[0]
        if n != total:
            raise SystemExit(f"{table}: split files hold {n} rows, source has {total} (rows without iso3?)")
        sizes = sorted(f.stat().st_size for f in out.glob("*.parquet"))
        print(f"{table}: {len(isos)} countries, {n} rows; file sizes median {sizes[len(sizes)//2]/1e3:.0f} kB, "
              f"max {sizes[-1]/1e6:.2f} MB -> {out}")

        if cc:
            from azure.storage.blob import ContentSettings
            existing = {b.name for b in cc.list_blobs(name_starts_with=f"{PREFIX}/{table}/{tag}/")}
            up = 0
            for f in sorted(out.glob("*.parquet")):
                name = f"{PREFIX}/{table}/{tag}/{f.name}"
                if name in existing:
                    continue          # never overwrite
                with f.open("rb") as fh:
                    cc.upload_blob(name, fh, overwrite=False, content_settings=ContentSettings(
                        content_type="application/vnd.apache.parquet", cache_control="public, max-age=31536000, immutable"))
                up += 1
            print(f"  uploaded {up} new files to {PUBLIC_CONTAINER}/{PREFIX}/{table}/{tag}/ ({len(existing)} already there)")


if __name__ == "__main__":
    main()
