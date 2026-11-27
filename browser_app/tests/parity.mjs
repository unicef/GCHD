// Parity: raster route vs the official summary table (mocked LLM, real data).
//   node tests/parity.mjs ISO3 hazard_code [threshold] [level] [units, comma-separated]
//   node tests/parity.mjs BGD river_flood_100yr                    default threshold, ADM1, whole country
//   node tests/parity.mjs BRA river_flood_100yr 0.1 2 "São Paulo"  custom threshold, ADM2 districts of one state
// The official numbers are at the default threshold, so they compare like with like only without a threshold.
// A plan the app rejects (e.g. a whole large country) is printed as such.
import { chromium } from "playwright-core";
const [ISO3 = "BGD", HZ = "river_flood_100yr", TH = "", LEVEL = "1", UNITS = ""] = process.argv.slice(2);
const lvl = Number(LEVEL);
const hazard = { hazard_code: HZ, ...(TH ? { op: ">", threshold: Number(TH) } : {}) };
const units = UNITS ? UNITS.split(",") : undefined;
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--disable-webgl"] });
const page = await browser.newPage();
let turn = 0; const toolResults = {};
await page.route("https://api.anthropic.com/v1/messages*", async (route) => {
  const body = JSON.parse(route.request().postData());
  for (const b of body.messages.at(-1).content ?? []) if (b.type === "tool_result") toolResults[b.tool_use_id] = { content: b.content, error: b.is_error };
  turn++;
  const msg = (content, stop) => ({ id: `m${turn}`, type: "message", role: "assistant", model: body.model, content, stop_reason: stop, usage: { input_tokens: 1, output_tokens: 1 } });
  const tool = (name, input) => ({ type: "tool_use", id: `t${turn}`, name, input });
  let res;
  if (turn === 1) res = msg([tool("propose_plan", { intent: "parity", data_route: "raster", admin_level: lvl, hazards: [hazard],
    combine: "single", population: "u18", sex: "total", outputs: ["table"], steps: ["x"], can_do: ["x"], cannot_do: ["x"],
    why_not_summary: "parity test", user_asked_for_raster: true, ...(units ? { units } : {}) })], "tool_use");
  // a rejected plan comes back at once (turn 2); an accepted one waits for Confirm, which sends turn 2
  else if (turn === 2 && toolResults.t1?.error) res = msg([{ type: "text", text: "PLAN REJECTED" }], "end_turn");
  else if (turn === 2) res = msg([tool("zonal_stats", { plan_id: "P1", hazards: [hazard], combine: "single", admin_level: lvl, population: "u18", sex: "total", title: "raster" })], "tool_use");
  else if (turn === 3) res = msg([tool("query_tables", { plan_id: "P1", title: "official",
    sql: `SELECT adm${lvl}_ucode, adm${lvl}_name, u18_aexp FROM adm${lvl}_hazard WHERE hazard_code='${HZ}'`
      + (units ? ` AND (adm1_name IN (${units.map((u) => `'${u.replace(/'/g, "''")}'`).join(", ")}) OR adm${lvl}_name IN (${units.map((u) => `'${u.replace(/'/g, "''")}'`).join(", ")}))` : "")
      + " ORDER BY u18_aexp DESC" })], "tool_use");
  else res = msg([{ type: "text", text: "PARITY DONE" }], "end_turn");
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(res) });
});
await page.goto("http://localhost:4173/");
await page.waitForFunction(() => document.getElementById("status").textContent.startsWith("Ready:"), null, { timeout: 120_000 });
await page.click("[data-tab-btn=ai]"); await page.selectOption("#provider", "anthropic"); await page.fill("#apikey", "sk-test");
await page.fill("#country", await page.$$eval("#countries option", (os, iso) => os.map((o) => o.value).find((v) => v.endsWith(`(${iso})`)), ISO3));
await page.click("#loadCountry");
await page.waitForFunction(() => document.getElementById("countryInfo").textContent.length > 0, null, { timeout: 300_000 });
await page.fill("#question", "parity"); await page.click("#send");
await page.waitForFunction(() => document.querySelector(".plan button[data-a=ok]") || /PLAN REJECTED/.test(document.body.textContent), null, { timeout: 120_000 });
if (toolResults.t1?.error) {
  console.log(`${ISO3} ${HZ} ${TH || "default"} ADM${lvl}${units ? ` units=${units}` : ""}: plan rejected:\n  ${toolResults.t1.content}`);
  await browser.close();
  process.exit(0);
}
const t0 = Date.now();
await page.click(".plan button[data-a=ok]");
await page.waitForFunction(() => [...document.querySelectorAll(".msg")].some((m) => /PARITY DONE|Error/.test(m.textContent)), null, { timeout: 900_000 });
const ras = JSON.parse(toolResults.t2?.content ?? "{}"), off = JSON.parse(toolResults.t3?.content ?? "{}");
if (!ras.rows) { console.log("zonal_stats failed:", toolResults.t2?.content); await browser.close(); process.exit(1); }
// first 40 rows only (what the LLM sees); enough for totals of a state or small country
const key = `adm${lvl}_ucode`;
const o = new Map((off.rows ?? []).map((r) => [r[key], r.u18_aexp]));
const offAll = new Map();
let sumR = 0, sumO = 0; const rel = [];
for (const r of ras.rows) {
  if (r.exposed === null) continue;
  sumR += r.exposed;
  if (o.has(r[key])) { sumO += o.get(r[key]); if (r.population > 0) rel.push(Math.abs(r.exposed - o.get(r[key])) / r.population); }
}
rel.sort((a, b) => a - b);
console.log(`${ISO3} ${HZ} ${TH ? `> ${TH}` : "default"} ADM${lvl}${units ? ` units=${units}` : ""}: ${ras.row_count} rows, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
console.log(`  notes: ${(ras.notes ?? []).slice(0, 2).map((n) => n.slice(0, 110)).join(" | ")}`);
console.log(`  top rows: ${ras.rows.slice(0, 5).map((r) => `${r[`adm${lvl}_name`]} ${r.exposed?.toLocaleString()} (official ${o.get(r[key])?.toLocaleString() ?? "?"})`).join("; ")}`);
console.log(`  exposed children, rows shown: raster ${sumR.toLocaleString()} vs official ${sumO.toLocaleString()} (${((sumR / sumO - 1) * 100).toFixed(1)} %)`);
if (rel.length) console.log(`  per-unit |diff| as share of unit children: median ${(rel[rel.length >> 1] * 100).toFixed(2)} %, max ${(rel.at(-1) * 100).toFixed(2)} %`);
await browser.close();
