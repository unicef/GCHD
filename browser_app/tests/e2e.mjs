// End-to-end smoke test: real catalog + data, mocked LLM (no key needed), headless Chrome without WebGL.
//   npx vite preview --port 4173 &   then   node tests/e2e.mjs [ISO3]
import { chromium } from "playwright-core";

const ISO3 = process.argv[2] ?? "KEN";
const URL_ = process.env.APP_URL ?? "http://localhost:4173/";
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", args: ["--disable-webgl", "--disable-3d-apis"] });
const page = await browser.newPage({ viewport: { width: 1500, height: 950 }, acceptDownloads: true });
const logs = [];
page.on("console", (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on("pageerror", (e) => logs.push(`[pageerror] ${e.message}`));
// NO_SPLIT=1: pretend the per-country tables are not published, to test the whole-table fallback
if (process.env.NO_SPLIT) await page.route(/exposure_by_country/, (r) => r.fulfill({ status: 404, body: "" }));
// data files fetched (parquet), with their size, to check the per-country tables are used
const fetched = [];
page.on("response", async (r) => {
  if (!/\.parquet$/.test(new URL(r.url()).pathname)) return;
  fetched.push(`${r.status()} ${(Number(r.headers()["content-length"] || 0) / 1e6).toFixed(2)} MB ${r.url().replace(/^.*\/public\//, "")}`);
});
process.on("exit", () => console.log("parquet fetched:\n  " + fetched.join("\n  ")));

// mocked Claude: plan -> (confirm) -> query + map + csv -> summary
let turn = 0;
const requests = [];
await page.route("https://api.anthropic.com/v1/messages*", async (route) => {
  const body = JSON.parse(route.request().postData());
  requests.push(body);
  if (requests.length === 1) {
    const h = route.request().headers();
    console.log("request:", JSON.stringify({ beta: h["anthropic-beta"], version: h["anthropic-version"], browser: h["anthropic-dangerous-direct-browser-access"],
      keys: Object.keys(body), model: body.model, thinking: body.thinking, output_config: body.output_config, fallbacks: body.fallbacks,
      system_chars: body.system?.[0]?.text?.length, cache: body.system?.[0]?.cache_control, tools: body.tools?.map((t) => t.name) }));
  }
  turn++;
  const msg = (content, stop) => ({ id: `m${turn}`, type: "message", role: "assistant", model: body.model, content, stop_reason: stop, usage: { input_tokens: 1, output_tokens: 1 } });
  const tool = (name, input) => ({ type: "tool_use", id: `t${turn}_${name}`, name, input });
  let res;
  if (turn === 1) res = msg([{ type: "text", text: "Here is my plan." }, tool("propose_plan", {
    intent: "Children exposed to river floods by ADM2", data_route: "summary", admin_level: 2,
    hazards: [{ hazard_code: "river_flood_100yr" }], population: "u18", sex: "total", outputs: ["table", "map", "csv"],
    steps: ["query adm2_hazard", "map u18_aexp", "offer CSV"], can_do: ["official numbers per district"], cannot_do: ["no time series"] })], "tool_use");
  // the app ends the turn after a plan; the propose_plan result comes with the user's "Confirm"
  else if (turn === 2) {
    const last = body.messages.at(-1).content;
    console.log("confirm request carries:", last.map((b) => b.type === "tool_result" ? `tool_result(${b.tool_use_id})` : b.type).join(" + "));
    res = msg([
    tool("query_tables", { plan_id: "P1", title: "Children exposed to river floods", sql:
      "SELECT adm2_ucode, adm2_name, u18_pop_total, u18_aexp, round(u18_rexp*100,1) AS pct FROM adm2_hazard WHERE hazard_code='river_flood_100yr' ORDER BY u18_aexp DESC" }),
  ], "tool_use");
  }
  else if (turn === 3) res = msg([tool("show_map", { plan_id: "P1", result_id: "R1", value_column: "u18_aexp", title: "Children exposed" }),
    tool("export_csv", { plan_id: "P1", result_id: "R1", filename: "flood_children.csv" })], "tool_use");
  else if (turn === 4) res = msg([{ type: "text", text: "Done: the map and CSV are ready." }], "end_turn");
  // raster route: custom threshold + pixel map
  else if (turn === 5) res = msg([tool("propose_plan", {
    intent: "Children in areas with flood depth over 0.5 m, by ADM1", data_route: "raster", admin_level: 1,
    hazards: [{ hazard_code: "river_flood_100yr", op: ">", threshold: 0.5 }], combine: "single", population: "u18", sex: "total",
    outputs: ["table", "map", "pixel_map"], steps: ["zonal stats", "maps"], can_do: ["approximate shares"], cannot_do: ["official numbers for custom thresholds"],
    why_not_summary: "The summary tables use the default 0.01 m threshold." })], "tool_use");
  else if (turn === 6) res = msg([tool("zonal_stats", { plan_id: "P2", hazards: [{ hazard_code: "river_flood_100yr", op: ">", threshold: 0.5 }],
    combine: "single", admin_level: 1, population: "u18", sex: "total", title: "Children, flood depth > 0.5 m",
    // UNITS=Jagang,... restricts the computation to those units
    ...(process.env.UNITS ? { units: process.env.UNITS.split(",") } : {}) })], "tool_use");
  else if (turn === 7) res = msg([tool("show_map", { plan_id: "P2", hazard_code: "river_flood_100yr", title: "Flood depth (m)" })], "tool_use");
  else res = msg([{ type: "text", text: "Raster done." }], "end_turn");
  await route.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": "*" }, body: JSON.stringify(res) });
});

const t0 = Date.now();
// raster progress lines seen in the status box (to check how many tiles are read)
const tilesSeen = new Set();
const poll = setInterval(async () => {
  const t = await page.textContent("#status").catch(() => "");
  if (/tile \d+\/\d+/.test(t)) tilesSeen.add(t.match(/tile \d+\/\d+[^…]*/)[0]);
}, 300);
process.on("exit", () => { clearInterval(poll); console.log("raster tiles:", [...tilesSeen].join(" | ")); });
const stamp = (s) => console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s  ${s}`);
await page.goto(URL_);
await page.waitForFunction(() => document.getElementById("status").textContent.startsWith("Ready:"), null, { timeout: 180_000 })
  .catch(async () => { console.log("STATUS:", await page.textContent("#status")); });
stamp(await page.textContent("#status"));
await page.fill("#apikey", "sk-test");
const opt = await page.$$eval("#countries option", (os, iso) => os.map((o) => o.value).find((v) => v.endsWith(`(${iso})`)), ISO3);
await page.fill("#country", opt);
await page.click("#loadCountry");
await page.waitForFunction(() => document.getElementById("countryInfo").textContent.length > 0, null, { timeout: 300_000 });
stamp(await page.textContent("#countryInfo"));
await page.fill("#question", "How many children are exposed to river floods in each district?");
await page.click("#send");
await page.waitForSelector(".plan button[data-a=ok]", { timeout: 60_000 });
stamp("plan card shown: " + (await page.textContent(".plan h3")));
await page.click(".plan button[data-a=ok]");
await page.waitForFunction(() => [...document.querySelectorAll(".msg.assistant")].some((m) => m.textContent.includes("Done")), null, { timeout: 300_000 });
stamp("flow finished");
const result = await page.textContent(".result h3");
const rows = await page.$$eval(".result tbody tr", (r) => r.length);
const legend = await page.textContent(".legend").catch(() => null);
const [dl] = await Promise.all([page.waitForEvent("download"), page.click(".msg.system button")]);
const csvPath = `/tmp/claude-1000/e2e_${ISO3}.csv`;
await dl.saveAs(csvPath);
await page.screenshot({ path: `/tmp/claude-1000/e2e_${ISO3}.png` });
// map export: PNG and GeoJSON of the choropleth
for (const kind of ["png", "geojson"]) {
  const [d] = await Promise.all([page.waitForEvent("download"), page.click(`.map-export button[data-x=${kind}]`)]);
  const out = `/tmp/claude-1000/export_${ISO3}.${kind}`;
  await d.saveAs(out);
  console.log(`map export ${kind}:`, d.suggestedFilename(), out);
}
console.log({ result, rows, legend: legend?.slice(0, 120), csv: dl.suggestedFilename(), csvPath });
// agents_check: AGENTS.md notes reach the model
console.log("system prompt has table notes:", requests[0].system[0].text.includes("Notes on the summary tables"),
  "| plan result has hazard notes:", JSON.stringify(requests[1].messages.at(-1).content).includes("Usage notes of the hazards"));
console.log("tool result sent to the LLM:", JSON.stringify(requests[3]?.messages?.at(-1)?.content?.[0]?.content ?? "").slice(0, 400));
console.log("chat:", (await page.$$eval("#chat .msg", (m) => m.map((x) => x.textContent))).join(" | ").slice(0, 900));
console.log(logs.filter((l) => !l.includes("[debug]")).slice(0, 15).join("\n"));
// raster route
await page.fill("#question", "Same, but only where flood depth is over 0.5 m, by ADM1, with a depth map");
await page.click("#send");
await page.waitForSelector(".plan:not(.done) button[data-a=ok]", { timeout: 60_000 });
stamp("raster plan shown");
await page.click(".plan:not(.done) button[data-a=ok]");
await page.waitForFunction(() => [...document.querySelectorAll(".msg")].some((m) => m.textContent.includes("Raster done") || m.classList.contains("error")), null, { timeout: 560_000 });
stamp("raster flow finished: " + (await page.textContent("#status")));
console.log("raster result:", await page.textContent(".result h3"), (await page.$$eval(".result .note", (n) => n.map((x) => x.textContent))).join(" | ").slice(0, 500));
console.log("raster rows:", (await page.$$eval(".result:first-child tbody tr", (r) => r.slice(0, 5).map((x) => x.textContent))).join(" || "));
console.log("tool errors:", (await page.$$eval(".msg.system, .msg.error", (m) => m.map((x) => x.textContent).filter((t) => /Error|rejected|not /.test(t)))).join(" | "));
await page.screenshot({ path: `/tmp/claude-1000/e2e_${ISO3}_raster.png` });
{
  const [d] = await Promise.all([page.waitForEvent("download"), page.click(".map-export button[data-x=png]")]);
  await d.saveAs(`/tmp/claude-1000/export_${ISO3}_raster.png`);
  console.log("raster map export:", d.suggestedFilename());
}
console.log(logs.filter((l) => /error/i.test(l)).slice(0, 10).join("\n"));
await browser.close();
