// Parity: raster route at default thresholds vs the official ADM1 summary table (mocked LLM, real data).
//   node tests/parity.mjs ISO3 hazard_code
import { chromium } from "playwright-core";
const [ISO3 = "BGD", HZ = "river_flood_100yr"] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--disable-webgl"] });
const page = await browser.newPage();
let turn = 0; const toolResults = {};
await page.route("https://api.anthropic.com/v1/messages*", async (route) => {
  const body = JSON.parse(route.request().postData());
  for (const b of body.messages.at(-1).content ?? []) if (b.type === "tool_result") toolResults[b.tool_use_id] = b.content;
  turn++;
  const msg = (content, stop) => ({ id: `m${turn}`, type: "message", role: "assistant", model: body.model, content, stop_reason: stop, usage: { input_tokens: 1, output_tokens: 1 } });
  const tool = (name, input) => ({ type: "tool_use", id: `t${turn}`, name, input });
  let res;
  if (turn === 1) res = msg([tool("propose_plan", { intent: "parity", data_route: "raster", admin_level: 1, hazards: [{ hazard_code: HZ }],
    combine: "single", population: "u18", sex: "total", outputs: ["table"], steps: ["x"], can_do: ["x"], cannot_do: ["x"],
    why_not_summary: "parity test", user_asked_for_raster: true })], "tool_use");
  else if (turn === 2) res = msg([{ type: "text", text: "ok" }], "end_turn");
  else if (turn === 3) res = msg([tool("zonal_stats", { plan_id: "P1", hazards: [{ hazard_code: HZ }], combine: "single", admin_level: 1, population: "u18", sex: "total", title: "raster" })], "tool_use");
  else if (turn === 4) res = msg([tool("query_tables", { plan_id: "P1", title: "official", sql: `SELECT adm1_ucode, u18_aexp FROM adm1_hazard WHERE hazard_code='${HZ}'` })], "tool_use");
  else res = msg([{ type: "text", text: "PARITY DONE" }], "end_turn");
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(res) });
});
await page.goto("http://localhost:4173/");
await page.waitForFunction(() => document.getElementById("status").textContent.startsWith("Ready:"), null, { timeout: 120_000 });
await page.fill("#apikey", "sk-test");
await page.fill("#country", await page.$$eval("#countries option", (os, iso) => os.map((o) => o.value).find((v) => v.endsWith(`(${iso})`)), ISO3));
await page.click("#loadCountry");
await page.waitForFunction(() => document.getElementById("countryInfo").textContent.length > 0, null, { timeout: 300_000 });
await page.fill("#question", "parity"); await page.click("#send");
await page.waitForSelector(".plan button[data-a=ok]"); await page.click(".plan button[data-a=ok]");
await page.waitForFunction(() => [...document.querySelectorAll(".msg")].some((m) => /PARITY DONE|Error/.test(m.textContent)), null, { timeout: 560_000 });
// full results from the app's tables are not exposed; use the tool results (first 40 rows) sent to the LLM
const ras = JSON.parse(toolResults.t3 ?? "{}"), off = JSON.parse(toolResults.t4 ?? "{}");
const o = new Map((off.rows ?? []).map((r) => [r.adm1_ucode, r.u18_aexp]));
let sumR = 0, sumO = 0; const rel = [];
for (const r of ras.rows ?? []) {
  if (!o.has(r.adm1_ucode) || r.exposed === null) continue;
  sumR += r.exposed; sumO += o.get(r.adm1_ucode);
  if (r.population > 0) rel.push(Math.abs(r.exposed - o.get(r.adm1_ucode)) / r.population);
}
rel.sort((a, b) => a - b);
console.log(`${ISO3} ${HZ}: units ${rel.length}; grid note: ${(ras.notes ?? [])[0]?.slice(0, 80)}`);
console.log(`  exposed children: raster ${sumR.toLocaleString()} vs official ${sumO.toLocaleString()} (${((sumR / sumO - 1) * 100).toFixed(1)} %)`);
console.log(`  per-unit |diff| as share of unit children: median ${(rel[rel.length >> 1] * 100).toFixed(2)} %, max ${(rel.at(-1) * 100).toFixed(2)} %`);
await browser.close();
