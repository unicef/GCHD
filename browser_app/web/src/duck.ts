// DuckDB-WASM: the summary (exposure) tables for the chosen country, queried locally in the browser.
import * as duckdb from "@duckdb/duckdb-wasm";
import type { Catalog } from "./catalog";
import { getJson } from "./catalog";
import { byCountryHref } from "./config";
import { guardSql } from "./sqlguard";

export interface Table { columns: string[]; rows: Record<string, unknown>[] }
export interface Country { iso3: string; name: string; bbox: [number, number, number, number] }

let db: duckdb.AsyncDuckDB | null = null;
let conn: duckdb.AsyncDuckDBConnection | null = null;

function normalize(v: unknown): unknown {
  if (typeof v === "bigint") return Number(v);
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  return v;
}

async function run(sql: string): Promise<Table> {
  if (!conn) throw new Error("DuckDB is not started");
  const res = await conn.query(sql);
  const columns = res.schema.fields.map((f) => f.name);
  const rows = res.toArray().map((r: any) => {
    const o: Record<string, unknown> = {};
    for (const c of columns) o[c] = normalize(r[c]);
    return o;
  });
  return { columns, rows };
}

const q = (s: string) => `'${s.replace(/'/g, "''")}'`;

export async function startDuckDB(): Promise<void> {
  if (db) return;
  // WASM bundles from jsDelivr (cached by the browser); GitHub Pages cannot send the COOP/COEP headers that
  // the multithreaded build needs, so selectBundle picks a single-threaded one.
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: "text/javascript" }));
  const worker = new Worker(workerUrl);
  db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
  URL.revokeObjectURL(workerUrl);
  conn = await db.connect();
}

/*
 * The exposure tables are fetched whole, once per tab, and handed to DuckDB as in-memory files: the
 * Azure container does not expose the Content-Range header, so DuckDB's own HTTP reader cannot do range
 * requests and would re-download the whole file for every query.
 */
const loaded = new Map<string, Promise<void>>();

class HttpError extends Error { constructor(readonly status: number, url: string) { super(`${status} ${url}`); } }

async function fetchBytes(url: string, label: string, onProgress?: (msg: string) => void): Promise<Uint8Array> {
  const res = await fetch(url);
  if (!res.ok || !res.body) throw new HttpError(res.status, url);
  const total = Number(res.headers.get("content-length")) || 0;
  const reader = res.body.getReader();
  const parts: Uint8Array[] = [];
  let got = 0, lastShown = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    got += value.length;
    if (got - lastShown > 2e6) {
      lastShown = got;
      onProgress?.(`Downloading ${label}: ${(got / 1e6).toFixed(0)}${total ? ` / ${(total / 1e6).toFixed(0)}` : ""} MB (once per session)…`);
    }
  }
  const out = new Uint8Array(got);
  let o = 0;
  for (const part of parts) { out.set(part, o); o += part.length; }
  return out;
}

export function ensureTable(cat: Catalog, level: 0 | 1 | 2, onProgress?: (msg: string) => void): Promise<void> {
  const name = `adm${level}_hazard_src.parquet`;
  let p = loaded.get(name);
  if (!p) {
    p = fetchBytes(cat.tableHref[level], `ADM${level} exposure table`, onProgress)
      .then((buf) => db!.registerFileBuffer(name, buf));
    p.catch(() => loaded.delete(name));
    loaded.set(name, p);
  }
  return p;
}

/**
 * Countries with exposure data: bboxes from the WorldPop country items of the STAC catalog
 * (items.geojson), names and the has-data filter from the ADM0 exposure table.
 */
export async function listCountries(cat: Catalog): Promise<Country[]> {
  const c = cat.collections.get("worldpop_u18_2025_total");
  if (!c) throw new Error("worldpop_u18_2025_total missing from the catalog");
  const g = await getJson(new URL(c.raw.assets.items_geojson.href, c.url).href);
  const names = new Map((await run(`SELECT iso3, any_value(adm0_name) AS n
      FROM read_parquet('adm0_hazard_src.parquet') GROUP BY 1`)).rows.map((r) => [String(r.iso3), String(r.n)]));
  return g.features
    .map((f: any) => ({ iso3: String(f.properties["GCHD:iso3"]), bbox: f.bbox as Country["bbox"],
                        name: names.get(f.properties["GCHD:iso3"]) ?? String(f.properties["GCHD:country"]) }))
    .filter((x: Country) => names.has(x.iso3))
    .sort((x: Country, y: Country) => x.name.localeCompare(y.name));
}

/** Hazards present in the summary tables (all countries): code, name, UNICEF code, source, period. */
export async function listTableHazards(): Promise<Table> {
  return run(`SELECT DISTINCT hazard_code, hazard, unicef_code, source, time_period
    FROM read_parquet('adm0_hazard_src.parquet') ORDER BY hazard_code`);
}

/**
 * Registers the source file for one country and level and returns its DuckDB file name. ADM0 is small
 * and already loaded whole (country list); ADM1/ADM2 come from the per-country copies when published,
 * otherwise from the whole table (downloaded once per session).
 */
async function countrySource(cat: Catalog, lvl: 0 | 1 | 2, iso3: string, onProgress?: (msg: string) => void): Promise<string> {
  const href = lvl ? byCountryHref(`adm${lvl}_hazard`, cat.tableSha[lvl], iso3) : null;
  const name = `adm${lvl}_hazard_${iso3}.parquet`;
  if (href && !loaded.has(`adm${lvl}_hazard_src.parquet`)) {
    let p = loaded.get(name);
    if (!p) {
      p = fetchBytes(href, `ADM${lvl} exposure table (${iso3})`, onProgress).then((buf) => db!.registerFileBuffer(name, buf));
      loaded.set(name, p);
    }
    try {
      await p;
      return name;
    } catch (e) {
      loaded.delete(name);
      if (!(e instanceof HttpError)) throw e;      // network failure: report it
      console.warn(`no per-country table at ${href} (${e.status}); downloading the whole ADM${lvl} table`);
    }
  }
  await ensureTable(cat, lvl, onProgress);
  return `adm${lvl}_hazard_src.parquet`;
}

/** Copies the country's rows of the three exposure tables into local tables adm0_hazard … adm2_hazard. */
export async function loadCountryTables(cat: Catalog, iso3: string, onProgress?: (msg: string) => void): Promise<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const lvl of [0, 1, 2] as const) {
    const src = await countrySource(cat, lvl, iso3, onProgress);
    onProgress?.(`Loading ADM${lvl} exposure table for ${iso3}…`);
    await run(`CREATE OR REPLACE TABLE adm${lvl}_hazard AS
      SELECT * REPLACE (coalesce(status, '') AS status)
      FROM read_parquet('${src}') WHERE iso3 = ${q(iso3)}`);
    counts[`adm${lvl}_hazard`] = Number((await run(`SELECT count(*) AS n FROM adm${lvl}_hazard`)).rows[0].n);
    // population per unit, one row per unit (the hazard tables repeat it once per hazard)
    const keys = ["adm0_ucode", "adm1_ucode", "adm2_ucode"].slice(0, lvl + 1);
    const names = ["adm0_name", "adm1_name", "adm2_name"].slice(0, lvl + 1);
    await run(`CREATE OR REPLACE TABLE adm${lvl}_pop AS
      SELECT iso3, ${keys.join(", ")}, ${names.map((n) => `any_value(${n}) AS ${n}`).join(", ")},
        max(pop_total) AS pop_total, max(pop_total_f) AS pop_total_f, max(pop_total_m) AS pop_total_m,
        max(u18_pop_total) AS u18_pop_total, max(u18_pop_f) AS u18_pop_f, max(u18_pop_m) AS u18_pop_m
      FROM adm${lvl}_hazard GROUP BY iso3, ${keys.join(", ")} ORDER BY ${keys.join(", ")}`);
    counts[`adm${lvl}_pop`] = Number((await run(`SELECT count(*) AS n FROM adm${lvl}_pop`)).rows[0].n);
  }
  return counts;
}

/** A query written by the LLM (or the app), checked by the SQL guard first. */
export async function querySummary(sql: string, maxRows = 50_000): Promise<Table> {
  const g = guardSql(sql);
  if (!g.ok) throw new Error(g.error);
  const t = await run(`SELECT * FROM (${g.sql}) AS q LIMIT ${maxRows}`);
  return t;
}

/** What a query that returned no rows could have matched: hazard codes and status values in the tables. */
export async function emptyResultHint(): Promise<string> {
  const codes = (await run(`SELECT hazard_code, count(*) AS n FROM adm2_hazard GROUP BY 1 ORDER BY 1`)).rows
    .map((r) => `${r.hazard_code} (${r.n})`).join(", ");
  const status = (await run(`SELECT status, count(*) AS n FROM adm2_hazard GROUP BY 1 ORDER BY 2 DESC`)).rows
    .map((r) => `'${r.status}' (${r.n})`).join(", ");
  return `The query returned 0 rows, so a filter matched nothing. Values present in adm2_hazard: hazard_code: ${codes}. `
    + `status: ${status} (valid rows have status = ''). Fix the filter and run query_tables again with the same plan_id; do not give up.`;
}

/** Official population per admin unit (for calibrating the raster route), from the local summary tables. */
export async function unitPopulation(level: 0 | 1 | 2): Promise<Map<string, Record<string, number>>> {
  const key = `adm${level}_ucode`;
  const t = await run(`SELECT ${key} AS ucode, max(pop_total) AS pop_total, max(pop_total_f) AS pop_total_f,
      max(pop_total_m) AS pop_total_m, max(u18_pop_total) AS u18_pop_total, max(u18_pop_f) AS u18_pop_f,
      max(u18_pop_m) AS u18_pop_m FROM adm${level}_hazard GROUP BY 1`);
  const m = new Map<string, Record<string, number>>();
  for (const r of t.rows) m.set(String(r.ucode), r as Record<string, number>);
  return m;
}

/** ADM2 ucodes of the chosen country inside the given ADM1 units (names or ucodes, any case). */
export async function adm2Within(adm1: string[]): Promise<string[]> {
  if (!adm1.length) return [];
  const list = adm1.map((k) => q(k.toLowerCase())).join(", ");
  return (await run(`SELECT DISTINCT adm2_ucode FROM adm2_hazard
    WHERE lower(adm1_ucode) IN (${list}) OR lower(adm1_name) IN (${list})`)).rows.map((r) => String(r.adm2_ucode));
}
