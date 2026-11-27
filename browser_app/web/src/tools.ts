// Tools the LLM can call, and the dispatcher that enforces the plan / confirmation gate and the
// summary-first route.
import type { Catalog } from "./catalog";
import { agentsMd, usageNotes } from "./catalog";
import { LLM_ROW_LIMIT } from "./config";
import type { Table } from "./duck";
import { emptyResultHint, querySummary } from "./duck";
import type { ToolCall, ToolDef, ToolResult } from "./llm";
import { Plan, RouteContext, checkPlan } from "./route";

const hazardItem = {
  type: "object",
  properties: {
    hazard_code: { type: "string", description: "hazard_code from the hazard list" },
    op: { type: "string", enum: [">", ">=", "<", "<="], description: "only for a custom rule" },
    threshold: { type: "number", description: "only for a custom threshold; omit to use the default" },
  },
  required: ["hazard_code"],
};

export const TOOLS: ToolDef[] = [
  {
    name: "describe_collection",
    description: "Read the AGENTS.md guidance of a GCHD STAC collection (units, method, caveats, joins). Allowed any time.",
    parameters: { type: "object", properties: { id: { type: "string", description: "collection id" } }, required: ["id"] },
  },
  {
    name: "propose_plan",
    description: "Show the user what you will do, what can and cannot be done, and the data route. Nothing runs until the user confirms. Call once per request, then stop and wait.",
    parameters: {
      type: "object",
      properties: {
        intent: { type: "string", description: "the request as you understood it, one sentence" },
        data_route: { type: "string", enum: ["summary", "raster"] },
        admin_level: { type: "integer", enum: [0, 1, 2] },
        hazards: { type: "array", items: hazardItem },
        combine: { type: "string", enum: ["single", "any", "all"], description: "how several hazards combine (raster route)" },
        population: { type: "string", enum: ["u18", "all"] },
        sex: { type: "string", enum: ["total", "female", "male"] },
        outputs: { type: "array", items: { type: "string", enum: ["table", "map", "csv", "pixel_map"] } },
        steps: { type: "array", items: { type: "string" } },
        can_do: { type: "array", items: { type: "string" } },
        cannot_do: { type: "array", items: { type: "string" } },
        why_not_summary: { type: "string", description: "required for the raster route" },
        user_asked_for_raster: { type: "boolean" },
        units: { type: "array", items: { type: "string" }, description: "raster route: only these units (names or ucodes at admin_level; for ADM2 an ADM1 name selects its districts). Omit for the whole country." },
      },
      required: ["intent", "data_route", "admin_level", "hazards", "outputs", "steps", "can_do", "cannot_do"],
    },
  },
  {
    name: "query_tables",
    description: "Run one DuckDB SELECT on adm0/1/2_hazard (one row per hazard and unit) or adm0/1/2_pop (one row per unit: population only), chosen country only. Needs a confirmed plan. Returns a result_id and the first rows; the full result stays in the app for maps and CSV. Include adm{level}_ucode in the result if it will be mapped.",
    parameters: {
      type: "object",
      properties: { plan_id: { type: "string" }, sql: { type: "string" }, title: { type: "string" } },
      required: ["plan_id", "sql", "title"],
    },
  },
  {
    name: "zonal_stats",
    description: "Raster route: exposure per admin unit computed in the browser from the hazard rasters and WorldPop. Only in a confirmed plan with data_route raster.",
    parameters: {
      type: "object",
      properties: {
        plan_id: { type: "string" },
        hazards: { type: "array", items: hazardItem },
        combine: { type: "string", enum: ["single", "any", "all"] },
        admin_level: { type: "integer", enum: [0, 1, 2] },
        population: { type: "string", enum: ["u18", "all"] },
        sex: { type: "string", enum: ["total", "female", "male"] },
        units: { type: "array", items: { type: "string" }, description: "optional: compute only these units (names or ucodes at admin_level; for ADM2 an ADM1 name or ucode selects its districts). Omit for the whole country." },
        title: { type: "string" },
      },
      required: ["plan_id", "hazards", "admin_level", "population", "sex", "title"],
    },
  },
  {
    name: "show_map",
    description: "Map a result as a choropleth (result_id + value_column; joins on adm{level}_ucode), or, on the raster route only, a pixel map of a hazard (hazard_code). Needs a confirmed plan.",
    parameters: {
      type: "object",
      properties: {
        plan_id: { type: "string" },
        result_id: { type: "string" },
        value_column: { type: "string" },
        hazard_code: { type: "string" },
        title: { type: "string" },
      },
      required: ["plan_id", "title"],
    },
  },
  {
    name: "export_csv",
    description: "Offer a result as a CSV download to the user. Needs a confirmed plan.",
    parameters: {
      type: "object",
      properties: { plan_id: { type: "string" }, result_id: { type: "string" }, filename: { type: "string" } },
      required: ["plan_id", "result_id", "filename"],
    },
  },
];

export interface StoredResult extends Table { id: string; title: string; level?: number; notes?: string[] }

export interface Hooks {
  catalog: Catalog;
  routeContext: RouteContext;
  showPlan(plan: Plan): void;
  progress(msg: string): void;
  showTable(r: StoredResult): void;
  offerCsv(r: StoredResult, filename: string): void;
  choropleth(r: StoredResult, column: string, level: number, title: string): Promise<void>;
  pixelMap(planId: string, hazardCode: string, title: string): Promise<void>;
  zonal(plan: Plan, args: Record<string, unknown>): Promise<StoredResult>;
  rasterCheck(plan: Plan): Promise<string[]>;     // reasons a raster plan cannot be computed reliably
}

export class Dispatcher {
  plans = new Map<string, Plan>();
  confirmed = new Set<string>();
  results = new Map<string, StoredResult>();
  private nPlan = 0;
  private nResult = 0;

  constructor(private h: Hooks) {}

  latest = "";            // only the most recent plan may run; earlier ones are superseded

  confirm(planId: string) { if (planId === this.latest) this.confirmed.add(planId); }

  addResult(t: Table, title: string, extra: Partial<StoredResult> = {}): StoredResult {
    const r = { ...t, ...extra, id: `R${++this.nResult}`, title };
    this.results.set(r.id, r);
    return r;
  }

  private gate(args: Record<string, unknown>): Plan {
    const id = String(args.plan_id ?? "");
    const plan = this.plans.get(id);
    if (!plan) throw new Error(`unknown plan_id ${id}; call propose_plan first`);
    if (id !== this.latest) throw new Error(`plan ${id} was superseded by plan ${this.latest}; use ${this.latest} (if the user confirmed it)`);
    if (!this.confirmed.has(id)) throw new Error(`plan ${id} is not confirmed yet; wait for the user's confirmation`);
    return plan;
  }

  /** "Data quality & usage notes" (+ hand-written notes) of each hazard collection in a plan. */
  private async hazardNotes(plan: Plan): Promise<string> {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const h of plan.hazards ?? []) {
      const c = this.h.catalog.hazards.get(h.hazard_code)?.collection;
      if (!c || seen.has(c.id)) continue;
      seen.add(c.id);
      const n = await usageNotes(c).catch(() => "");
      if (n) out.push(`## ${c.title} (${c.id})\n${n}`);
    }
    return out.join("\n\n");
  }

  private preview(r: StoredResult): string {
    return JSON.stringify({
      result_id: r.id, title: r.title, row_count: r.rows.length, columns: r.columns,
      rows: r.rows.slice(0, LLM_ROW_LIMIT),
      truncated: r.rows.length > LLM_ROW_LIMIT ? `${r.rows.length - LLM_ROW_LIMIT} more rows kept in the app` : undefined,
      notes: r.notes,
    });
  }

  async run(call: ToolCall): Promise<ToolResult> {
    const ok = (content: string): ToolResult => ({ id: call.id, name: call.name, content });
    const a = call.input;
    try {
      switch (call.name) {
        case "describe_collection": {
          const c = this.h.catalog.collections.get(String(a.id));
          if (!c) return ok(`unknown collection ${a.id}; known: ${[...this.h.catalog.collections.keys()].join(", ")}`);
          return ok((await agentsMd(c)).slice(0, 8000) || c.description);
        }
        case "propose_plan": {
          const plan = a as unknown as Plan;
          plan.hazards ??= [];
          plan.admin_level = Number(plan.admin_level) as Plan["admin_level"];   // some providers send "2"
          for (const h of plan.hazards) if (h.threshold !== undefined && h.threshold !== null) h.threshold = Number(h.threshold);
          const chk = checkPlan(plan, this.h.routeContext);
          if (!chk.ok) return { ...ok(`Plan rejected: ${chk.errors.join(" ")}`), isError: true };
          if (plan.data_route === "raster") {
            this.h.progress("Checking what the raster route needs…");
            const blockers = await this.h.rasterCheck(plan);
            if (blockers.length)
              return { ...ok(`Plan rejected: ${blockers.join(" ")} Explain this to the user in plain words and ask which area to compute; `
                + "do not propose the same plan again."), isError: true };
          }
          plan.plan_id = `P${++this.nPlan}`;
          this.plans.set(plan.plan_id, plan);
          this.latest = plan.plan_id;
          this.h.showPlan(plan);
          const notes = await this.hazardNotes(plan);
          return ok(`Plan ${plan.plan_id} is shown to the user. Stop now and wait for their confirmation; do not call other tools in this turn.`
            + (notes ? `\n\nUsage notes of the hazards in this plan (from their AGENTS.md); if one changes the plan, tell the user before they confirm:\n${notes}` : ""));
        }
        case "query_tables": {
          const plan = this.gate(a);
          this.h.progress("Querying the summary tables…");
          const t = await querySummary(String(a.sql));
          const r = this.addResult(t, String(a.title ?? "Result"), { level: plan.admin_level });
          if (!r.rows.length) return ok(`${this.preview(r)}\n${await emptyResultHint()}`);
          if (r.rows.length > 1 && new Set(r.rows.map((x) => JSON.stringify(x))).size === 1)
            return ok(`${this.preview(r)}\nAll ${r.rows.length} rows are identical: the hazard tables repeat population once per hazard. `
              + "For population use adm0_pop / adm1_pop / adm2_pop (one row per unit), or SELECT DISTINCT. Run the query again before answering.");
          this.h.showTable(r);
          return ok(this.preview(r));
        }
        case "zonal_stats": {
          const plan = this.gate(a);
          if (plan.data_route !== "raster")
            return { ...ok(`Plan ${plan.plan_id} uses the summary route; answer it with query_tables. zonal_stats is only for raster plans.`), isError: true };
          const r = await this.h.zonal(plan, a);
          this.h.showTable(r);
          return ok(this.preview(r));
        }
        case "show_map": {
          const plan = this.gate(a);
          if (a.hazard_code) {
            if (plan.data_route !== "raster" || !plan.outputs.includes("pixel_map"))
              return { ...ok("A pixel map needs a confirmed raster plan with pixel_map in outputs. Map a summary result instead (result_id + value_column)."), isError: true };
            await this.h.pixelMap(plan.plan_id!, String(a.hazard_code), String(a.title ?? a.hazard_code));
            return ok("Pixel map shown.");
          }
          const r = this.results.get(String(a.result_id));
          if (!r) return { ...ok(`unknown result_id ${a.result_id}`), isError: true };
          const col = String(a.value_column ?? "");
          if (!r.columns.includes(col)) return { ...ok(`column ${col} is not in ${r.id}; columns: ${r.columns.join(", ")}`), isError: true };
          const level = [2, 1, 0].find((l) => r.columns.includes(`adm${l}_ucode`));
          if (level === undefined) return { ...ok(`${r.id} has no adm0/1/2_ucode column to join to the boundaries; re-run the query including it.`), isError: true };
          await this.h.choropleth(r, col, level, String(a.title ?? col));
          return ok(`Choropleth of ${col} at ADM${level} shown.`);
        }
        case "export_csv": {
          this.gate(a);
          const r = this.results.get(String(a.result_id));
          if (!r) return { ...ok(`unknown result_id ${a.result_id}`), isError: true };
          const name = String(a.filename || `${r.id}.csv`).replace(/[^\w.-]+/g, "_");
          this.h.offerCsv(r, name.endsWith(".csv") ? name : `${name}.csv`);
          return ok(`CSV download offered as ${name}.`);
        }
        default:
          return { ...ok(`unknown tool ${call.name}`), isError: true };
      }
    } catch (e) {
      return { ...ok(`Error: ${(e as Error).message}`), isError: true };
    }
  }
}
