// Basic tool: the official summary-table numbers chosen with dropdowns (no language model, no raster analysis).
// country -> level -> (province) -> hazard -> population -> map value: a table, a choropleth and a CSV.
import type { Boundaries } from "./boundaries";
import { outlinesGeoJSON, toGeoJSON } from "./boundaries";
import { Catalog, usageNotes } from "./catalog";
import { STAC_BASE } from "./config";
import { Country, Table, querySummary } from "./duck";
import type { BBox } from "./geo";
import { fitBBox, setExportName, showChoropleth, showOutline, showRaster } from "./map";
import { hazardPixelMap } from "./raster/engine";
import { escapeHtml, resultBlock } from "./ui";

import {
  DEFAULT_STATE, Level, Pop, Sex, State, VALUE_LABELS, Value, popLabel, popSql, profileSql, stateToHash, unitSql, valuesFor,
} from "./basic_query";
export { hashToState } from "./basic_query";

// ---------------------------------------------------------------- UI

export interface BasicDeps {
  catalog: () => Catalog;
  country: () => Country | null;
  boundaries: (level: Level) => Promise<Boundaries>;
  status: (msg: string) => void;
  active: () => boolean;           // the Basic tab is shown
}

const q = (s: string) => `'${s.replace(/'/g, "''")}'`;
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

export function initBasic(deps: BasicDeps) {
  const el = {
    controls: $("basicControls"), level: $<HTMLSelectElement>("b_level"), adm1: $<HTMLSelectElement>("b_adm1"),
    adm1Row: $("b_adm1Row"), hazard: $<HTMLSelectElement>("b_hazard"), hazardRow: $("b_hazardRow"),
    pop: $<HTMLSelectElement>("b_pop"), sex: $<HTMLSelectElement>("b_sex"), value: $<HTMLSelectElement>("b_value"),
    layer: $<HTMLInputElement>("b_layer"), layerRow: $("b_layerRow"),
    info: $("b_info"), profile: $("b_profile"), results: $("basicResults"),
  };
  let state: State = { ...DEFAULT_STATE };
  let hazards: { code: string; name: string }[] = [];
  let run = 0;   // drops stale renders when controls change quickly
  const layerCache = new Map<string, Awaited<ReturnType<typeof hazardPixelMap>>>();

  const rasterable = (code: string) => {
    const c = deps.catalog().hazards.get(code)?.collection;
    return !!c && (/\.tiff?$/i.test(c.dataHref ?? "") || !!c.raw.assets?.items_geojson);
  };

  function readControls() {
    state = {
      ...state, level: Number(el.level.value) as Level, adm1: el.adm1.value, hazard: el.hazard.value,
      pop: el.pop.value as Pop, sex: el.sex.value as Sex, value: el.value.value as Value, layer: el.layer.checked,
    };
  }

  function syncControls() {
    el.level.value = String(state.level);
    el.adm1.value = state.adm1;
    if (el.adm1.value !== state.adm1) state.adm1 = el.adm1.value = "";
    el.adm1Row.hidden = state.level !== 2;
    el.hazardRow.hidden = state.level === 0;
    el.hazard.value = state.hazard;
    el.pop.value = state.pop;
    el.sex.innerHTML = state.pop === "u18"
      ? `<option value="total">All children</option><option value="f">Girls</option><option value="m">Boys</option>`
      : `<option value="total">Total</option><option value="f">Female</option><option value="m">Male</option>`;
    el.sex.value = state.sex;
    const vals = valuesFor(state.level);
    if (!vals.includes(state.value)) state.value = "exposed";
    el.value.innerHTML = vals.map((v) => `<option value="${v}">${VALUE_LABELS[v]}</option>`).join("");
    el.value.value = state.value;
    el.value.parentElement!.hidden = state.level === 0;
    el.layerRow.hidden = state.level === 0;
    el.layer.disabled = !rasterable(state.hazard);
    if (el.layer.disabled) el.layer.checked = state.layer = false;
    else el.layer.checked = state.layer;
  }

  function writeHash() {
    if (deps.active()) history.replaceState(null, "", stateToHash({ ...state, iso3: deps.country()?.iso3 }));
  }

  /** Fill the country-specific choices (hazards present, ADM1 units), apply `want`, then render. */
  async function onCountry(want: Partial<State> = {}) {
    const c = deps.country();
    if (!c) return;
    const t = await querySummary(`SELECT hazard_code, any_value(hazard) AS hazard FROM adm0_hazard GROUP BY 1 ORDER BY 2`);
    hazards = t.rows.map((r) => ({ code: String(r.hazard_code), name: String(r.hazard) }));
    el.hazard.innerHTML = hazards.map((h) => `<option value="${escapeHtml(h.code)}">${escapeHtml(h.name)}</option>`).join("");
    const a1 = await querySummary(`SELECT DISTINCT adm1_ucode, adm1_name FROM adm2_hazard ORDER BY adm1_name`);
    el.adm1.innerHTML = `<option value="">All</option>`
      + a1.rows.map((r) => `<option value="${escapeHtml(String(r.adm1_ucode))}">${escapeHtml(String(r.adm1_name))}</option>`).join("");
    const n2 = Number((await querySummary(`SELECT count(*) AS n FROM adm2_hazard`)).rows[0].n);
    state = { ...state, adm1: "", ...want };
    if (!want.level) state.level = want.level === 0 ? 0 : n2 ? 2 : 1;
    if (!hazards.some((h) => h.code === state.hazard)) state.hazard = hazards[0]?.code ?? "";
    el.controls.querySelectorAll("select, input").forEach((x) => ((x as HTMLInputElement).disabled = false));
    syncControls();
    await render();
  }

  async function render() {
    const c = deps.country();
    if (!c) return;
    const my = ++run;
    writeHash();
    el.profile.innerHTML = "";
    el.results.innerHTML = "";
    showInfo();
    try {
      if (state.level === 0) {
        const u0 = String((await querySummary(`SELECT adm0_ucode FROM adm0_hazard LIMIT 1`)).rows[0].adm0_ucode);
        const t = await querySummary(profileSql(0, u0, state.pop, state.sex));
        const total = await popTotal(0, u0);
        if (my !== run) return;
        const who = popLabel(state.pop, state.sex);
        el.results.append(resultBlock(t, `${c.name}: ${who} exposed, all hazards`, `${c.iso3}_ADM0_all_hazards_${who}.csv`,
          [`${cap(who)} in ${c.name}: ${total}. Official GCHD summary numbers (default exposure thresholds); empty values: no data for that hazard.`],
          200, labelsFor(who)));
        const b = await deps.boundaries(0);
        if (my !== run) return;
        showOutline(toGeoJSON(b), outlinesGeoJSON(b));
        fitBBox(c.bbox as BBox);
        deps.status("Ready.");
        return;
      }
      const t = await querySummary(unitSql(state));
      if (my !== run) return;
      const who = popLabel(state.pop, state.sex);
      const hz = hazards.find((h) => h.code === state.hazard)?.name ?? state.hazard;
      const where = state.adm1 ? `${el.adm1.selectedOptions[0]?.text}, ` : "";
      const noData = t.rows.filter((r) => r.status).length;
      el.results.append(resultBlock(t, `${hz}: ${who} exposed by ADM${state.level} (${where}${c.name})`,
        `${c.iso3}_ADM${state.level}_${state.hazard}_${who}.csv`,
        ["Official GCHD summary numbers at the hazard's default exposure threshold.",
          ...(noData ? [`${noData} unit(s) have no valid data (see status); they are grey on the map.`] : [])], 200, labelsFor(who)));
      await drawMap(t, my);
    } catch (e) {
      if (my === run) deps.status(`Error: ${(e as Error).message}`);
    }
  }

  function labelsFor(who: string): Record<string, string> {
    return { population: `${who} (total)`, exposed: `${who} exposed`, pct_exposed: "% exposed", hazard_mean: "hazard mean",
      hazard_max: "hazard max", exposure_index: "exposure index", exposure_class: "exposure class" };
  }

  async function drawMap(t: Table, my: number) {
    const c = deps.country()!;
    const lvl = state.level;
    let b = await deps.boundaries(lvl);
    if (my !== run) return;
    if (lvl === 2 && state.adm1) {
      const keep = new Set(t.rows.map((r) => String(r.adm2_ucode)));
      b = { ...b, units: new Map([...b.units].filter(([k]) => keep.has(k))) };
    }
    const key = `adm${lvl}_ucode`;
    const hz = hazards.find((h) => h.code === state.hazard)?.name ?? state.hazard;
    setExportName(`${c.iso3}_ADM${lvl}_${state.hazard}_${state.value}`);
    if (state.layer) {
      const ck = `${c.iso3}|${state.hazard}`;
      let px = layerCache.get(ck);
      if (!px) {
        px = await hazardPixelMap(deps.catalog(), state.hazard, c.bbox as BBox, await deps.boundaries(0), deps.status);
        layerCache.set(ck, px);
      }
      if (my !== run) return;
      const unit = deps.catalog().hazards.get(state.hazard)?.collection.units;
      showRaster(px.grid, px.values, hz, px.mask, `Hazard layer for display${unit ? ` (${unit})` : ""}; the table has the official numbers.`, outlinesGeoJSON(b));
    } else {
      const values = new Map<string, Record<string, unknown>>();
      for (const r of t.rows) values.set(String(r[key]), { [state.value]: r[state.value] });
      const fc = toGeoJSON(b, values);
      const unmatched = t.rows.filter((r) => !b.units.has(String(r[key]))).length;
      showChoropleth(fc, state.value, `${VALUE_LABELS[state.value]}${state.value === "exposed" || state.value === "pct_exposed" ? ` (${popLabel(state.pop, state.sex)})` : ""}`,
        outlinesGeoJSON(b), unmatched ? `${unmatched} table rows had no boundary match` : hz, (u) => void showProfile(u));
    }
    fitTo(b, c);
    deps.status("Ready.");
  }

  function fitTo(b: Boundaries, c: Country) {
    if (!state.adm1) { fitBBox(c.bbox as BBox); return; }
    const bb: BBox = [180, 90, -180, -90];
    for (const u of b.units.values()) for (const poly of u.polygons) for (const [x, y] of poly[0] ?? []) {
      bb[0] = Math.min(bb[0], x); bb[1] = Math.min(bb[1], y); bb[2] = Math.max(bb[2], x); bb[3] = Math.max(bb[3], y);
    }
    fitBBox(bb[0] <= bb[2] ? bb : (c.bbox as BBox));
  }

  async function popTotal(level: Level, ucode: string): Promise<string> {
    const v = (await querySummary(popSql(level, ucode, state.pop, state.sex))).rows[0]?.population;
    return typeof v === "number" ? Math.round(v).toLocaleString() : "unknown";
  }
  const cap = (s: string) => s[0].toUpperCase() + s.slice(1);

  async function showProfile(ucode: string) {
    const c = deps.country();
    if (!c) return;
    const t = await querySummary(profileSql(state.level, ucode, state.pop, state.sex));
    const name = (await querySummary(`SELECT adm${state.level}_name AS n FROM adm${state.level}_hazard WHERE adm${state.level}_ucode = ${q(ucode)} LIMIT 1`)).rows[0]?.n;
    const who = popLabel(state.pop, state.sex);
    const total = await popTotal(state.level, ucode);
    el.profile.innerHTML = "";
    const block = resultBlock(t, `${name ?? ucode}: all hazards`, `${c.iso3}_${ucode}_all_hazards_${who}.csv`,
      [`${cap(who)}: ${total} (ADM${state.level} unit ${ucode}). Official summary numbers.`], 200, labelsFor(who));
    block.classList.add("profile");
    el.profile.append(block);
    el.profile.scrollIntoView({ block: "nearest" });
  }

  async function showInfo() {
    if (state.level === 0) {
      el.info.innerHTML = `<h3>All hazards</h3><p>Every hazard in the GCHD summary tables for this country, ranked by the number of ${escapeHtml(popLabel(state.pop, state.sex))} exposed. Choose ADM1 or ADM2 to map one hazard.</p>`;
      return;
    }
    const cat = deps.catalog();
    const h = cat.hazards.get(state.hazard);
    if (!h) { el.info.innerHTML = `<h3>${escapeHtml(state.hazard)}</h3><p>No catalog entry for this hazard.</p>`; return; }
    const col = h.collection;
    const period = (col.raw.extent?.temporal?.interval?.[0] ?? []).filter(Boolean).map((x: string) => x.slice(0, 4)).join("–");
    const producers = (col.raw.providers ?? []).filter((p: any) => p.roles?.includes("producer")).map((p: any) => p.name).join(", ");
    const browse = `https://unicef.github.io/GCHD/STAC_catalog/browser/#/${col.url.slice(STAC_BASE.length)}`;
    const name = hazards.find((x) => x.code === state.hazard)?.name ?? col.title;
    el.info.innerHTML = `<h3>${escapeHtml(name)}</h3>
      <p>${escapeHtml(col.description.split("\n\n")[0])}</p>
      <table class="facts">
        <tr><th>Exposed when</th><td>value ${escapeHtml(h.rule.op)} ${h.rule.threshold}${col.units ? ` (${escapeHtml(col.units)})` : ""}</td></tr>
        ${period ? `<tr><th>Period</th><td>${escapeHtml(period)}</td></tr>` : ""}
        ${col.resolution ? `<tr><th>Resolution</th><td>${escapeHtml(col.resolution)}</td></tr>` : ""}
        ${producers ? `<tr><th>Source</th><td>${escapeHtml(producers)}</td></tr>` : ""}
      </table>
      <p><a href="${browse}" target="_blank" rel="noopener">Open in the GCHD catalog</a></p>
      <div class="notes"></div>`;
    const notes = await usageNotes(col).catch(() => "");
    const box = el.info.querySelector(".notes");
    if (box && notes) box.innerHTML = `<details><summary>Usage notes</summary>${notes.split("\n").filter((l) => l.trim() && !l.startsWith("###"))
      .map((l) => `<p>${escapeHtml(l.replace(/^- /, "• ").replace(/\*\*|`/g, ""))}</p>`).join("")}</details>`;
  }

  for (const x of [el.level, el.adm1, el.hazard, el.pop, el.sex, el.value, el.layer])
    x.addEventListener("change", () => { readControls(); if (x === el.pop) state.sex = "total"; syncControls(); void render(); });

  return { onCountry, render, state: () => state };
}
