"""Step 6 (optional): ADM2 hazard-exposure CSVs -> Parquet tables (ADM2 + ADM1/ADM0 roll-ups).

The catalog (08_build_stac.py) references the published copies on Azure
(public/GCHD_portolan/adm{0,1,2}_hazard/*.parquet) and reads the column dictionary from
config/exposure_schema.json, which this step rewrites. Ported from the GCHD_portolan project
(pipeline/04_exposure_tables.py). The CSVs come from exposure_analysis/subnational_level/.

Schema is the " Data Schema" sheet (leading space) of `Global Hazard Data catalog.xlsx`.
The CSVs additionally carry 24 male/female index & class columns (gmexpi, u18_cfexpc, ...)
that fill the numbering gaps in that sheet, plus `status`; their metadata is derived
from the parent column.

Outputs (work/out/gchd_tables/exposure/<release>/):
  adm2_hazard.parquet  1 row per (ADM2, hazard), workbook columns verbatim + keys
  adm1_hazard.parquet  roll-up following each column's Aggregation Logic
  adm0_hazard.parquet  roll-up
  schema.json          column dictionary

Usage: ../.venv/bin/python pipeline/06_exposure_tables.py [--csv-dir work/src/csv]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb
import openpyxl
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT.parent / "docs" / "Global Hazard Data catalog.xlsx"
SHEET = " Data Schema"          # leading space: the current schema tab
HAZARD_MAP = ROOT / "config" / "hazard_map.yaml"

TYPE_MAP = {"string": "VARCHAR", "integer": "BIGINT", "float": "DOUBLE",
            "decimal": "DOUBLE", "datetime": "SMALLINT"}
KEY_COLS = ["hazard_code", "unicef_code", "source_release"]
GENDER = {"m": "male", "f": "female"}


# --------------------------------------------------------------------------- schema
def load_schema() -> list[dict]:
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    rows = [r for r in wb[SHEET].iter_rows(values_only=True) if any(c is not None for c in r)]
    hdr = [str(h).strip() for h in rows[0]]
    cols = []
    for r in rows[1:]:
        d = dict(zip(hdr, r))
        if not d.get("Indicator code"):
            continue
        cols.append({
            "name": str(d["Indicator code"]).strip(),
            "title": (d.get("Indicators") or "").strip(),
            "description": (d.get("Description") or "").strip(),
            "indicator_type": (d.get("Indicator type") or "").strip(),
            "unit": (str(d.get("Unit") or "")).strip(),
            "workbook_type": (d.get("Data type") or "").strip(),
            "aggregation": (d.get("Aggregation Logic/Provisional") or "").strip(),
            "source": "workbook",
        })
    return cols


def derive_extra(name: str, by_name: dict) -> dict | None:
    """gmexpi -> parent gexpi (male); u18_cfexpc -> u18_cexpc (female)."""
    m = re.fullmatch(r"(u18_)?([gcr])([mf])(exp[ic])", name)
    if not m:
        return None
    u18, scope, g, kind = m.groups()
    parent = by_name.get(f"{u18 or ''}{scope}{kind}")
    if parent is None:
        return None
    d = dict(parent)
    d.update(name=name, source=f"derived from {parent['name']} ({GENDER[g]})",
             title=f"{parent['title']} ({GENDER[g]})",
             description=f"{parent['description']} {GENDER[g].capitalize()} population only.")
    return d


def full_schema(csv_header: list[str]) -> list[dict]:
    sheet = load_schema()
    by_name = {c["name"]: c for c in sheet}
    missing = [c for c in by_name if c not in csv_header]
    if missing:
        raise SystemExit(f"CSV lacks workbook columns: {missing}")
    out = []
    for h in csv_header:
        if h in by_name:
            out.append(by_name[h])
        elif h == "status":
            out.append({"name": "status", "title": "Status", "description":
                        "Data availability flag: empty = valid, 'No Data', 'Insufficient Data', 'Not Applicable'.",
                        "indicator_type": "metadata", "unit": "", "workbook_type": "string",
                        "aggregation": "metadata", "source": "csv"})
        else:
            d = derive_extra(h, by_name)
            if d is None:
                raise SystemExit(f"CSV column {h!r} not in workbook and not derivable")
            out.append(d)
    for c in out:
        c["parquet_type"] = parquet_type(c)
    return out


def parquet_type(c: dict) -> str:
    if c["name"] == "prod_date":
        return "DATE"
    if c["indicator_type"] == "Exposure Class":
        return "TINYINT"
    return TYPE_MAP[c["workbook_type"]]


# --------------------------------------------------------------------------- casting
def cast_expr(c: dict) -> str:
    n, t = c["name"], c["parquet_type"]
    q = f'"{n}"'
    if n == "prod_date":   # mixed dd/mm/yyyy and yyyy-mm-dd across files
        return (f"coalesce(try_strptime({q}, '%Y-%m-%d'), try_strptime({q}, '%d/%m/%Y'))::DATE AS {q}")
    if t in ("BIGINT", "TINYINT", "SMALLINT"):
        # values arrive as '22221.0'; integrality is asserted separately
        return f"CAST(round(TRY_CAST({q} AS DOUBLE)) AS {t}) AS {q}"
    if t == "DOUBLE":
        return f"TRY_CAST({q} AS DOUBLE) AS {q}"
    return f"nullif(trim({q}), '') AS {q}"


def assert_clean_cast(con, schema) -> None:
    probs = []
    for c in schema:
        n, t = c["name"], c["parquet_type"]
        q = f'"{n}"'
        if t in ("BIGINT", "TINYINT", "SMALLINT"):
            bad = con.sql(f"""select count(*) from raw where nullif(trim({q}),'') is not null and
                (TRY_CAST({q} AS DOUBLE) is null or TRY_CAST({q} AS DOUBLE) != round(TRY_CAST({q} AS DOUBLE)))""").fetchone()[0]
        elif t == "DOUBLE":
            bad = con.sql(f"select count(*) from raw where nullif(trim({q}),'') is not null and TRY_CAST({q} AS DOUBLE) is null").fetchone()[0]
        elif t == "DATE":
            bad = con.sql(f"""select count(*) from raw where nullif(trim({q}),'') is not null and
                coalesce(try_strptime({q}, '%Y-%m-%d'), try_strptime({q}, '%d/%m/%Y')) is null""").fetchone()[0]
        else:
            continue
        if bad:
            probs.append(f"{n} ({t}): {bad} values not cleanly castable")
    if probs:
        raise SystemExit("Type validation failed:\n  " + "\n  ".join(probs))


# --------------------------------------------------------------------------- roll-ups
SUM_COLS = ["pop_total", "pop_total_m", "pop_total_f", "u18_pop_total", "u18_pop_m", "u18_pop_f",
            "aexp", "amexp", "afexp", "u18_aexp", "u18_amexp", "u18_afexp"]
# relative exposure recomputed: (numerator, denominator) - denominator only over units with data
REL = {"rexp": ("aexp", "pop_total"), "rmexp": ("amexp", "pop_total_m"), "rfexp": ("afexp", "pop_total_f"),
       "u18_rexp": ("u18_aexp", "u18_pop_total"), "u18_rmexp": ("u18_amexp", "u18_pop_m"),
       "u18_rfexp": ("u18_afexp", "u18_pop_f")}
WMEAN = ["hazs_mean", "gindex", "cindex", "rindex"]     # population-weighted, provisional


def rollup_sql(schema, level: int) -> str:
    # group only on codes; descriptive text is taken with max() because the source CSVs
    # have occasional blanks (e.g. `hazard` empty in 3,108 USA rows of sand_dust_storm_susc)
    keys = ["hazard_code", "unicef_code", "source_release", "adm0_ucode"] + (["adm1_ucode"] if level == 1 else [])
    descriptive = ["hazard", "source", "dataflow", "time_period", "iso3", "adm0_id", "adm0_name",
                   "unicef_region", "unicef_region_full"] + (["adm1_name"] if level == 1 else [])
    geo = "'ADMIN1'" if level == 1 else "'COUNTRY'"
    sel = list(KEY_COLS)
    for c in schema:
        n = c["name"]
        q = f'"{n}"'
        if n == "geo_level":
            sel.append(f"{geo} AS geo_level")
        elif n in keys:
            sel.append(q)
        elif n in descriptive:
            sel.append(f"max({q}) AS {q}")
        elif n in ("adm2_name", "adm2_ucode") or (level == 0 and n in ("adm1_name", "adm1_ucode")):
            sel.append(f"NULL::VARCHAR AS {q}")
        elif n == "prod_date":
            sel.append(f"max({q}) AS {q}")
        elif n in SUM_COLS:
            sel.append(f"sum({q}) AS {q}")
        elif n == "hazs_max":
            sel.append(f"max({q}) AS {q}")
        elif n == "hazs_min":
            sel.append(f"min({q}) AS {q}")
        elif n in REL:
            num, den = REL[n]
            sel.append(f"round(100.0 * sum(\"{num}\") / nullif(sum(CASE WHEN \"{num}\" IS NOT NULL THEN \"{den}\" END), 0), 1) AS {q}")
        elif n in WMEAN:
            sel.append(f"sum({q} * pop_total) / nullif(sum(CASE WHEN {q} IS NOT NULL THEN pop_total END), 0) AS {q}")
        elif n == "status":
            sel.append("CASE WHEN count(aexp) = 0 THEN mode(status) END AS status")
        else:   # median, std, exposure indices & classes: not aggregable
            sel.append(f"NULL::{c['parquet_type']} AS {q}")
    sel += ["count(*)::INTEGER AS n_adm2", "count(aexp)::INTEGER AS n_adm2_with_data"]
    order = "hazard_code, adm0_ucode" + (", adm1_ucode" if level == 1 else "")
    return f"SELECT {', '.join(sel)} FROM adm2 GROUP BY {', '.join(keys)} ORDER BY {order}"


# --------------------------------------------------------------------------- QA
def write_qa_report(con, out: Path) -> None:
    """Source-data issues found while ingesting. Values are kept verbatim; this only reports."""
    def rows(sql):
        r = con.sql(sql)
        return [dict(zip(r.columns, v)) for v in r.fetchall()]

    over = rows("""SELECT hazard_code, adm0_ucode, adm2_ucode, u18_pop_total, u18_aexp, pop_total, aexp
                   FROM adm2 WHERE u18_aexp > u18_pop_total OR aexp > pop_total
                   ORDER BY hazard_code, adm2_ucode""")
    blank = rows("""SELECT hazard_code, adm0_ucode, count(*) AS n_rows FROM adm2
                    WHERE hazard IS NULL GROUP BY ALL ORDER BY n_rows DESC""")
    status = rows("""SELECT hazard_code, coalesce(status, '(valid)') AS status, count(*) AS n
                     FROM adm2 GROUP BY ALL ORDER BY hazard_code, status""")
    report = {
        "exposed_exceeds_population": {"count": len(over), "note":
            "exposure > population in source CSV; kept verbatim (likely coarse-raster resampling in GEE)",
            "rows": over},
        "blank_hazard_name": {"count": sum(r["n_rows"] for r in blank), "rows": blank},
        "status_counts": status,
    }
    (out / "qa_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"QA: {len(over)} rows exposed>population, {report['blank_hazard_name']['count']} rows blank hazard name")


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", default=str(ROOT / "work" / "src" / "csv"))
    args = ap.parse_args()

    hm = yaml.safe_load(HAZARD_MAP.read_text())
    release = hm["release"]
    out = ROOT / "work" / "out" / "gchd_tables" / "exposure" / release
    out.mkdir(parents=True, exist_ok=True)

    files = {code: Path(args.csv_dir) / f"{code}_{release}.csv" for code in hm["hazards"]}
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise SystemExit(f"missing CSVs: {missing}")

    con = duckdb.connect()
    con.sql("SET preserve_insertion_order=false")
    union = " UNION ALL ".join(
        f"SELECT '{code}' AS hazard_code, '{hm['hazards'][code]['unicef_code']}' AS unicef_code, "
        f"'{release}' AS source_release, * FROM read_csv('{p}', all_varchar=true, header=true)"
        for code, p in files.items())
    con.sql(f"CREATE TABLE raw AS {union}")

    header = [c for c in con.sql("SELECT * FROM raw LIMIT 0").columns if c not in KEY_COLS]
    schema = full_schema(header)
    assert_clean_cast(con, schema)

    con.sql(f"CREATE TABLE adm2 AS SELECT {', '.join(KEY_COLS)}, {', '.join(cast_expr(c) for c in schema)} "
            f"FROM raw ORDER BY hazard_code, adm0_ucode, adm2_ucode")
    n_raw = con.sql("select count(*) from raw").fetchone()[0]
    n_adm2 = con.sql("select count(*) from adm2").fetchone()[0]
    dup = con.sql("select count(*) from (select hazard_code, adm2_ucode from adm2 group by 1,2 having count(*)>1)").fetchone()[0]
    assert n_raw == n_adm2 and dup == 0, (n_raw, n_adm2, dup)

    copt = "(FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 50000)"
    con.sql(f"COPY adm2 TO '{out / 'adm2_hazard.parquet'}' {copt}")
    for lvl in (1, 0):
        con.sql(f"COPY ({rollup_sql(schema, lvl)}) TO '{out / f'adm{lvl}_hazard.parquet'}' {copt}")

    keys_meta = [
        {"name": "hazard_code", "title": "Hazard code", "description": "GCHD pipeline hazard code (CSV file stem); see config/hazard_map.yaml.",
         "indicator_type": "key", "unit": "", "parquet_type": "VARCHAR", "aggregation": "key", "source": "pipeline"},
        {"name": "unicef_code", "title": "UNICEF hazard code", "description": "UNICEF proposed / GLIDE code from the 'Hazard Codes' tab.",
         "indicator_type": "key", "unit": "", "parquet_type": "VARCHAR", "aggregation": "key", "source": "pipeline"},
        {"name": "source_release", "title": "Source release", "description": "Release date of the source CSVs.",
         "indicator_type": "metadata", "unit": "", "parquet_type": "VARCHAR", "aggregation": "key", "source": "pipeline"},
    ]
    rollup_meta = [
        {"name": "n_adm2", "title": "ADM2 units", "description": "Number of ADM2 units aggregated (roll-up tables only).",
         "indicator_type": "metadata", "unit": "count", "parquet_type": "INTEGER", "aggregation": "count", "source": "pipeline"},
        {"name": "n_adm2_with_data", "title": "ADM2 units with data", "description": "ADM2 units with non-null aexp (roll-up tables only).",
         "indicator_type": "metadata", "unit": "count", "parquet_type": "INTEGER", "aggregation": "count", "source": "pipeline"},
    ]
    rollup_rule = {}
    for c in schema:
        n = c["name"]
        rollup_rule[n] = ("sum" if n in SUM_COLS else "max" if n == "hazs_max" else "min" if n == "hazs_min"
                          else f"recomputed {REL[n][0]}/{REL[n][1]}*100 over units with data" if n in REL
                          else "population-weighted mean (provisional)" if n in WMEAN
                          else "key" if c["indicator_type"] in ("nominal", "metadata") else "null (not aggregable)")
    (out / "schema.json").write_text(json.dumps({
        "source": f"{WORKBOOK.name} / sheet '{SHEET}'",
        "release": release,
        "tables": {"adm2_hazard": "1 row per (adm2_ucode, hazard_code)",
                   "adm1_hazard": "roll-up of adm2_hazard by (adm1_ucode, hazard_code)",
                   "adm0_hazard": "roll-up of adm2_hazard by (adm0_ucode, hazard_code)"},
        "columns": keys_meta + [dict(c, rollup=rollup_rule[c["name"]]) for c in schema] + rollup_meta,
    }, indent=2, ensure_ascii=False))

    (ROOT / "config" / "exposure_schema.json").write_text((out / "schema.json").read_text())
    write_qa_report(con, out)

    for name in ("adm2_hazard", "adm1_hazard", "adm0_hazard"):
        p = out / f"{name}.parquet"
        n = con.sql(f"select count(*) from '{p}'").fetchone()[0]
        print(f"{name:12s} rows={n:>7,}  size={p.stat().st_size/1e6:6.1f} MB")


if __name__ == "__main__":
    main()
