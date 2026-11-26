"""Step 9: check the built catalog in stac/. Exits non-zero on any failure.

  1. Portolan conformance: `portolan check --metadata --no-data` (offline; does not read asset bytes)
     -> reports/portolan_check.txt. Errors fail; warnings are listed.
  2. STAC schema validation of every object with pystac (core + extension schemas).
  3. Coverage: every collection of the published Portolan catalog (GCHD_portolan) has a collection here,
     with the same id; every hazard code of config/hazard_map.yaml has an exposure rule.
  4. Summary: collections per group and item counts -> reports/catalog_summary.csv.

Usage:  python pipeline/09_check.py [--skip-validate]
"""
import argparse
import csv
import json
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import pystac
import yaml

import _path  # noqa: F401  (STAC_catalog/ on sys.path)
from gchd_stac.common import HAZARD_MAP_YAML, REPO_DIR, REPORTS_DIR, STAC_OUT

PORTOLAN = REPO_DIR / ".venv" / "bin" / "portolan"
PORTOLAN_ROOT = "https://unidatadapmclimatechange.blob.core.windows.net/public/GCHD_portolan/catalog.json"


def portolan_check() -> bool:
    r = subprocess.run([str(PORTOLAN), "check", "--metadata", "--no-data", "."], cwd=STAC_OUT,
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    (REPORTS_DIR / "portolan_check.txt").write_text(out)
    rules = Counter(re.findall(r"^([✗⚠]) (PTL-[A-Z]+-\d+)", out, flags=re.M))
    for (sev, rule), n in sorted(rules.items()):
        print(f"  {sev} {rule}: {n}")
    tail = [line for line in out.splitlines() if "conform" in line.lower()]
    print("portolan:", tail[-1] if tail else out.strip().splitlines()[-1])
    return not any(sev == "✗" for sev, _ in rules)


def collections() -> dict[str, Path]:
    out = {}
    for p in STAC_OUT.rglob("collection.json"):
        out[json.loads(p.read_text())["id"]] = p
    return out


def coverage(cols: dict[str, Path]) -> bool:
    ok = True
    with urllib.request.urlopen(PORTOLAN_ROOT, timeout=60) as r:
        ref = {l["href"].split("/")[1] for l in json.load(r)["links"] if l["rel"] == "child"}
    missing = sorted(ref - set(cols))
    print(f"coverage: {len(ref)} Portolan collections, {len(ref) - len(missing)} present here"
          + (f"; MISSING {missing}" if missing else ""))
    ok &= not missing
    hm = yaml.safe_load(HAZARD_MAP_YAML.read_text())
    ruled = {r["hazard_code"] for p in cols.values()
             for r in json.loads(p.read_text()).get("GCHD:exposure_rules", [])}
    lost = sorted(set(hm["hazards"]) - ruled)
    print(f"exposure rules: {len(ruled)}/{len(hm['hazards'])} hazard codes" + (f"; MISSING {lost}" if lost else ""))
    return ok and not lost


def summary(cols: dict[str, Path]):
    rows = []
    for cid, p in sorted(cols.items(), key=lambda kv: str(kv[1])):
        d = json.loads(p.read_text())
        rows.append({"group": p.parent.parent.relative_to(STAC_OUT).as_posix(), "id": cid, "title": d["title"],
                     "items": sum(1 for l in d["links"] if l["rel"] == "item"),
                     "data": d.get("assets", {}).get("data", {}).get("href", "")})
    with open(REPORTS_DIR / "catalog_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = Counter(r["group"] for r in rows)
    print(f"summary: {len(rows)} collections, {sum(r['items'] for r in rows)} items; "
          + ", ".join(f"{g}: {n}" for g, n in sorted(by.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-validate", action="store_true", help="skip the pystac schema validation (slow)")
    args = ap.parse_args()
    ok = portolan_check()
    if not args.skip_validate:
        n = pystac.Catalog.from_file(str(STAC_OUT / "catalog.json")).validate_all()
        print(f"pystac: {n} objects valid")
    cols = collections()
    ok &= coverage(cols)
    summary(cols)
    print("OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
