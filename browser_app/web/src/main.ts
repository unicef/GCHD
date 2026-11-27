import "./style.css";
import { Boundaries, loadBoundaries, outlinesGeoJSON, toGeoJSON } from "./boundaries";
import { Catalog, loadCatalog, usageNotes } from "./catalog";
import { downloadCsv } from "./csv";
import { Country, Table, ensureTable, listCountries, listTableHazards, loadCountryTables, startDuckDB } from "./duck";
import type { BBox } from "./geo";
import { DEFAULT_MODELS, LlmError, LlmSession, Provider, StepInput, createSession } from "./llm";
import { fitBBox, initMap, setExportName, showChoropleth, showOutline, showRaster } from "./map";
import { systemPrompt } from "./prompt";
import { hazardPixelMap, runZonal } from "./raster/engine";
import type { Plan, RouteContext } from "./route";
import { Dispatcher, StoredResult, TOOLS } from "./tools";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const el = {
  provider: $<HTMLSelectElement>("provider"), model: $<HTMLInputElement>("model"),
  key: $<HTMLInputElement>("apikey"), remember: $<HTMLInputElement>("remember"),
  country: $<HTMLInputElement>("country"), countries: $<HTMLDataListElement>("countries"),
  loadCountry: $<HTMLButtonElement>("loadCountry"), countryInfo: $("countryInfo"), status: $("status"),
  chat: $("chat"), ask: $<HTMLFormElement>("ask"), question: $<HTMLTextAreaElement>("question"),
  send: $<HTMLButtonElement>("send"), results: $("results"),
};

let catalog: Catalog;
let tableHazards: Table;
let countries: Country[] = [];
let country: Country | null = null;
let rowCounts: Record<string, number> = {};
let tableNotes = "";
let session: LlmSession | null = null;
let sessionKey = "";
let dispatcher: Dispatcher;
let busy = false;

// ---------------------------------------------------------------- settings (key stays in the browser)
const KEY_STORE = "gchd.llm";
// AGENTS.md sections of the exposure tables that go into the system prompt
const NOTE_SECTIONS_TABLE = ["Data quality & usage notes", "Related collections", "Additional notes"] as const;
function loadSettings() {
  const saved = JSON.parse(localStorage.getItem(KEY_STORE) ?? sessionStorage.getItem(KEY_STORE) ?? "{}");
  el.provider.value = saved.provider ?? "anthropic";
  el.model.value = saved.model ?? DEFAULT_MODELS[el.provider.value as Provider];
  el.key.value = saved.key ?? "";
  el.remember.checked = !!localStorage.getItem(KEY_STORE);
}
function saveSettings() {
  const v = JSON.stringify({ provider: el.provider.value, model: el.model.value.trim(), key: el.key.value.trim() });
  localStorage.removeItem(KEY_STORE);
  sessionStorage.removeItem(KEY_STORE);
  (el.remember.checked ? localStorage : sessionStorage).setItem(KEY_STORE, v);
}
el.provider.addEventListener("change", () => { el.model.value = DEFAULT_MODELS[el.provider.value as Provider]; saveSettings(); });
for (const e of [el.model, el.key, el.remember]) e.addEventListener("change", saveSettings);

// ---------------------------------------------------------------- chat rendering
function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
}
function md(s: string) {
  return escapeHtml(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>");
}
function addMsg(kind: "user" | "assistant" | "system" | "error", text: string) {
  const d = document.createElement("div");
  d.className = `msg ${kind}`;
  d.innerHTML = md(text);
  el.chat.append(d);
  el.chat.scrollTop = el.chat.scrollHeight;
}
function status(msg: string) { el.status.textContent = msg; }

function list(title: string, items?: string[]) {
  return items?.length ? `<b>${title}</b><ul>${items.map((i) => `<li>${md(i)}</li>`).join("")}</ul>` : "";
}

const openPlans: { id: string; done: (label: string) => void }[] = [];

function showPlan(p: Plan) {
  // a new plan supersedes every earlier one that is still open
  for (const o of openPlans.splice(0)) o.done(`Superseded by plan ${p.plan_id}`);
  const d = document.createElement("div");
  d.className = "plan";
  const hz = p.hazards.map((h) => h.threshold !== undefined ? `${h.hazard_code} (${h.op ?? ">"} ${h.threshold})` : h.hazard_code).join(", ");
  d.innerHTML = `<h3>Plan ${p.plan_id}: ${md(p.intent)}</h3>
    <span class="route ${p.data_route}">${p.data_route === "summary" ? "Summary tables (official numbers)" : "Raster route (computed in your browser, approximate)"}</span>
    <p>ADM${p.admin_level} · ${hz || "no hazard"} · ${p.population === "all" ? "all ages" : "under 18"}${p.sex && p.sex !== "total" ? `, ${p.sex}` : ""} · outputs: ${p.outputs.join(", ")}</p>
    ${p.why_not_summary ? `<p><b>Why not the summary tables:</b> ${md(p.why_not_summary)}</p>` : ""}
    ${list("Steps", p.steps)}${list("Can do", p.can_do)}${list("Cannot do", p.cannot_do)}
    <div class="actions"><button data-a="ok">Confirm</button><button class="secondary" data-a="edit">Edit</button><button class="secondary" data-a="no">Cancel</button></div>`;
  const done = (label: string) => {
    d.classList.add("done");
    d.querySelector(".actions")!.innerHTML = `<i>${label}</i>`;
    const i = openPlans.findIndex((o) => o.id === p.plan_id);
    if (i >= 0) openPlans.splice(i, 1);
  };
  openPlans.push({ id: p.plan_id!, done });
  d.querySelector<HTMLButtonElement>('[data-a="ok"]')!.onclick = () => {
    dispatcher.confirm(p.plan_id!);
    done("Confirmed");
    send({ userText: `I confirm plan ${p.plan_id}. Please run it.` }, `Confirmed plan ${p.plan_id}.`);
  };
  d.querySelector<HTMLButtonElement>('[data-a="edit"]')!.onclick = () => {
    done("Being edited");
    el.question.value = `Change plan ${p.plan_id}: `;
    el.question.focus();
  };
  d.querySelector<HTMLButtonElement>('[data-a="no"]')!.onclick = () => {
    done("Cancelled");
    send({ userText: `Cancel plan ${p.plan_id}.` }, `Cancelled plan ${p.plan_id}.`);
  };
  el.chat.append(d);
  el.chat.scrollTop = el.chat.scrollHeight;
}

const fmtCell = (v: unknown) => typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString() : Number(v.toPrecision(4)).toLocaleString()) : escapeHtml(String(v ?? ""));

function showTable(r: StoredResult) {
  const d = document.createElement("div");
  d.className = "result";
  const shown = r.rows.slice(0, 200);
  d.innerHTML = `<h3><span>${r.id}: ${escapeHtml(r.title)} <small>(${r.rows.length} rows)</small></span><button class="secondary">CSV</button></h3>
    ${(r.notes ?? []).map((n) => `<p class="note">${escapeHtml(n)}</p>`).join("")}
    <div style="overflow:auto"><table><thead><tr>${r.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>
    <tbody>${shown.map((row) => `<tr>${r.columns.map((c) => `<td class="${typeof row[c] === "number" ? "num" : ""}">${fmtCell(row[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    ${r.rows.length > shown.length ? `<p class="note">First ${shown.length} rows shown; the CSV has all ${r.rows.length}.</p>` : ""}`;
  d.querySelector("button")!.onclick = () => downloadCsv(`${country?.iso3 ?? "GCHD"}_${r.id}.csv`, r.columns, r.rows);
  el.results.prepend(d);
}

function offerCsv(r: StoredResult, filename: string) {
  const b = document.createElement("button");
  b.textContent = `Download ${filename}`;
  b.onclick = () => downloadCsv(filename, r.columns, r.rows);
  const wrap = document.createElement("div");
  wrap.className = "msg system";
  wrap.append(b);
  el.chat.append(wrap);
  el.chat.scrollTop = el.chat.scrollHeight;
}

// ---------------------------------------------------------------- data hooks
async function boundaries(level: 0 | 1 | 2): Promise<Boundaries> {
  if (!country) throw new Error("no country chosen");
  return loadBoundaries(catalog.boundaryHref[level].pmtiles, level, country.iso3, country.bbox as BBox, status);
}

async function choropleth(r: StoredResult, column: string, level: number, title: string) {
  const b = await boundaries(level as 0 | 1 | 2);
  const key = `adm${level}_ucode`;
  const values = new Map<string, Record<string, unknown>>();
  for (const row of r.rows) values.set(String(row[key]), { [column]: row[column] });
  const fc = toGeoJSON(b, values);
  const unmatched = r.rows.filter((row) => !b.units.has(String(row[key]))).length;
  setExportName(`${country!.iso3}_ADM${level}_${title}`);
  showChoropleth(fc, column, title, outlinesGeoJSON(b), unmatched ? `${unmatched} result rows had no boundary match` : undefined);
  fitBBox(country!.bbox as BBox);
}

async function zonal(plan: Plan, a: Record<string, unknown>): Promise<StoredResult> {
  const hazards = (a.hazards as Plan["hazards"]) ?? plan.hazards;
  const allowed = new Set(plan.hazards.map((h) => h.hazard_code));
  const extra = hazards.filter((h) => !allowed.has(h.hazard_code));
  if (extra.length) throw new Error(`hazards not in plan ${plan.plan_id}: ${extra.map((h) => h.hazard_code).join(", ")}`);
  const level = Number(a.admin_level ?? plan.admin_level) as 0 | 1 | 2;
  const b = await boundaries(level);
  const out = await runZonal(catalog, country!.iso3, country!.bbox as BBox, b, {
    hazards, combine: (a.combine as any) ?? plan.combine ?? "single",
    population: (a.population as any) ?? plan.population ?? "u18", sex: (a.sex as any) ?? plan.sex ?? "total",
  }, status);
  status("Raster route done.");
  return dispatcher.addResult({ columns: out.columns, rows: out.rows }, String(a.title ?? "Raster exposure"), { level, notes: out.notes });
}

async function pixelMap(_planId: string, code: string, title: string) {
  const b = await boundaries(0);
  const { grid, values, mask } = await hazardPixelMap(catalog, code, country!.bbox as BBox, b, status);
  const units = catalog.hazards.get(code)?.collection.units;
  setExportName(`${country!.iso3}_${title}`);
  showRaster(grid, values, title, mask, units);
  fitBBox(country!.bbox as BBox);
  status("Pixel map shown.");
}

// ---------------------------------------------------------------- conversation loop
function ensureSession(): LlmSession {
  const key = el.key.value.trim();
  if (!key) throw new LlmError("Paste an API key for the chosen provider first.");
  const sig = `${el.provider.value}|${el.model.value}|${key}|${country?.iso3}`;
  if (!session || sig !== sessionKey) {
    session = createSession(el.provider.value as Provider, {
      apiKey: key, model: el.model.value.trim() || DEFAULT_MODELS[el.provider.value as Provider],
      system: systemPrompt(catalog, tableHazards, country!, rowCounts, tableNotes), tools: TOOLS,
    });
    sessionKey = sig;
  }
  return session;
}

function setBusy(b: boolean) {
  busy = b;
  el.send.disabled = b || !country;
  el.question.disabled = !country;
}

// a plan-card click while the model is still finishing its turn waits for that turn to end
let queued: { input: StepInput; shown?: string } | null = null;
function send(input: StepInput, shown?: string) {
  if (busy) {
    queued = { input, shown };
    status("Will continue when the current reply is finished…");
  } else converse(input, shown);
}

async function converse(input: StepInput, shown?: string) {
  if (busy) return;
  setBusy(true);
  if (shown ?? input.userText) addMsg("user", shown ?? input.userText!);
  try {
    const s = ensureSession();
    status("Thinking…");
    let res = await s.step(input);
    for (let i = 0; i < 16; i++) {
      if (res.text.trim()) addMsg("assistant", res.text.trim());
      if (res.stop === "refusal") addMsg("error", "The model declined this request. Try rephrasing it.");
      if (res.stop === "max_tokens") addMsg("error", "The model's reply was cut off (output limit).");
      if (!res.text.trim() && !res.toolCalls.length && res.stop !== "refusal")
        addMsg("error", res.detail ?? `The model returned an empty reply (${res.stop}). Try asking again.`);
      if (!res.toolCalls.length) break;
      const results = [];
      for (const call of res.toolCalls) {
        addMsg("system", `→ ${call.name}${call.name === "query_tables" ? `: ${String(call.input.sql ?? "").slice(0, 300)}` : ""}`);
        const r = await dispatcher.run(call);
        if (r.isError) addMsg("system", `  ${r.content.slice(0, 400)}`);
        results.push(r);
      }
      status("Thinking…");
      res = await s.step({ toolResults: results });
    }
    status("Ready.");
  } catch (e) {
    addMsg("error", e instanceof LlmError ? e.message : `Error: ${(e as Error).message}`);
    status("Ready.");
  } finally {
    setBusy(false);
    if (queued) {
      const q = queued;
      queued = null;
      setTimeout(() => converse(q.input, q.shown), 0);
    }
  }
}

el.ask.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const q = el.question.value.trim();
  if (!q || busy) return;
  el.question.value = "";
  converse({ userText: q });
});
el.question.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) { ev.preventDefault(); el.ask.requestSubmit(); }
});

// ---------------------------------------------------------------- country
async function chooseCountry() {
  const v = el.country.value.trim().toLowerCase();
  const c = countries.find((x) => x.name.toLowerCase() === v || x.iso3.toLowerCase() === v || `${x.name} (${x.iso3})`.toLowerCase() === v);
  if (!c) { status("Pick a country from the list."); return; }
  el.loadCountry.disabled = true;
  try {
    rowCounts = await loadCountryTables(catalog, c.iso3, status);
    country = c;
    session = null;           // a new conversation per country
    dispatcher = newDispatcher();
    el.chat.innerHTML = "";
    el.results.innerHTML = "";
    fitBBox(c.bbox as BBox);
    const b = await boundaries(1).catch(() => boundaries(0));
    showOutline(toGeoJSON(b), outlinesGeoJSON(b));
    el.countryInfo.textContent = `${c.name}: ${rowCounts.adm2_hazard.toLocaleString()} ADM2 rows, ${rowCounts.adm1_hazard.toLocaleString()} ADM1 rows loaded.`;
    addMsg("system", `${c.name} loaded. Ask a question about hazards and children (or people) exposed, by country, ADM1 or ADM2.`);
    status("Ready.");
  } catch (e) {
    status(`Could not load ${c.name}: ${(e as Error).message}`);
  } finally {
    el.loadCountry.disabled = false;
    setBusy(false);
  }
}
el.loadCountry.addEventListener("click", chooseCountry);
el.country.addEventListener("keydown", (ev) => { if (ev.key === "Enter") chooseCountry(); });

function newDispatcher(): Dispatcher {
  const inTables = new Set(tableHazards.rows.map((r) => String(r.hazard_code)));
  const rasterHazards = new Set([...catalog.hazards.keys()].filter((code) => {
    const c = catalog.hazards.get(code)!.collection;
    return /\.tiff?$/i.test(c.dataHref ?? "") || !!c.raw.assets?.items_geojson;
  }));
  const routeContext: RouteContext = {
    tableHazards: inTables, rasterHazards,
    defaultRule: (code) => { const r = catalog.hazards.get(code)?.rule; return r && { op: r.op, threshold: r.threshold }; },
  };
  return new Dispatcher({
    catalog, routeContext, showPlan, progress: status, showTable, offerCsv, choropleth, pixelMap, zonal,
  });
}

// ---------------------------------------------------------------- start
async function start() {
  loadSettings();
  initMap($("map"));
  try {
    catalog = await loadCatalog(status);
    status("Starting DuckDB (WebAssembly)…");
    await startDuckDB();
    await ensureTable(catalog, 0, status);
    status("Reading the country list…");
    [countries, tableHazards, tableNotes] = await Promise.all([listCountries(catalog), listTableHazards(),
      usageNotes(catalog.collections.get("adm2_hazard")!, [...NOTE_SECTIONS_TABLE]).catch(() => "")]);
    el.countries.innerHTML = countries.map((c) => `<option value="${escapeHtml(`${c.name} (${c.iso3})`)}">`).join("");
    el.country.disabled = false;
    el.country.placeholder = "Type a country name";
    el.loadCountry.disabled = false;
    status(`Ready: ${catalog.collections.size} catalog collections, ${countries.length} countries, ${tableHazards.rows.length} hazards in the summary tables.`);
  } catch (e) {
    status(`Start-up failed: ${(e as Error).message}`);
  }
}
start();
