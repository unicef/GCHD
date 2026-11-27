// Summary-first routing. The precomputed exposure tables (adm0/1/2_hazard) hold the official GCHD numbers;
// the raster route (reading COGs in the browser) is used only when they cannot answer the request.

export interface PlanHazard { hazard_code: string; op?: string; threshold?: number }

export interface Plan {
  plan_id?: string;
  intent: string;
  data_route: "summary" | "raster";
  admin_level: 0 | 1 | 2;
  hazards: PlanHazard[];
  combine?: "single" | "any" | "all";
  population?: "u18" | "all";
  sex?: "total" | "female" | "male";
  outputs: string[];                 // table, map, csv, pixel_map
  steps: string[];
  can_do: string[];
  cannot_do: string[];
  why_not_summary?: string;
  user_asked_for_raster?: boolean;
  units?: string[];                  // raster route: only these units (names / ucodes; ADM1 names at ADM2)
}

export interface RouteContext {
  tableHazards: Set<string>;                                   // hazard codes present in the tables
  defaultRule: (code: string) => { op: string; threshold: number } | undefined;
  rasterHazards: Set<string>;                                  // codes with a readable raster layer
}

export interface RouteDecision { route: "summary" | "raster"; reasons: string[] }

/** Which route the request needs, from the plan's content (not from what the model chose). */
export function requiredRoute(p: Plan, ctx: RouteContext): RouteDecision {
  const reasons: string[] = [];
  for (const h of p.hazards) {
    if (!ctx.tableHazards.has(h.hazard_code)) reasons.push(`${h.hazard_code} is not in the summary tables`);
    const d = ctx.defaultRule(h.hazard_code);
    const customThr = h.threshold !== undefined && h.threshold !== null && (!d || Number(h.threshold) !== Number(d.threshold));
    const customOp = !!h.op && !!d && h.op !== d.op;
    if (customThr || customOp) reasons.push(`custom threshold for ${h.hazard_code} (${h.op ?? d?.op} ${h.threshold}; default ${d?.op} ${d?.threshold})`);
  }
  if ((p.combine === "any" || p.combine === "all") && p.hazards.length > 1)
    reasons.push(`combined exposure to ${p.hazards.length} hazards (${p.combine}) is not precomputed`);
  if (p.outputs.includes("pixel_map")) reasons.push("a pixel-level hazard map was requested");
  return { route: reasons.length ? "raster" : "summary", reasons };
}

export interface PlanCheck { ok: boolean; errors: string[]; decision: RouteDecision }

export function checkPlan(p: Plan, ctx: RouteContext): PlanCheck {
  const errors: string[] = [];
  if (![0, 1, 2].includes(Number(p.admin_level))) errors.push("admin_level must be 0, 1 or 2");
  if (!Array.isArray(p.hazards)) errors.push("hazards must be a list");
  if (!Array.isArray(p.outputs) || !p.outputs.length) errors.push("outputs must list at least one of table, map, csv, pixel_map");
  for (const h of p.hazards ?? [])
    if (!ctx.tableHazards.has(h.hazard_code) && !ctx.rasterHazards.has(h.hazard_code))
      errors.push(`unknown hazard_code ${h.hazard_code}`);
  if (errors.length) return { ok: false, errors, decision: { route: "summary", reasons: [] } };
  const decision = requiredRoute(p, ctx);
  if (p.data_route === "raster" && decision.route === "summary" && !p.user_asked_for_raster)
    errors.push("the summary tables can answer this request, so data_route must be \"summary\" "
      + "(the raster route is only for custom thresholds, combined hazards, hazards missing from the tables, "
      + "or a pixel-level map, or when the user explicitly asks for raster processing: then set user_asked_for_raster)");
  if (p.data_route === "summary" && decision.route === "raster")
    errors.push(`the summary tables cannot answer this: ${decision.reasons.join("; ")}. Use data_route "raster" `
      + "and explain why in why_not_summary, or change the request to default thresholds.");
  if (p.data_route === "raster" && !p.why_not_summary)
    errors.push("a raster plan needs why_not_summary (shown to the user)");
  for (const h of p.hazards ?? [])
    if (p.data_route === "raster" && !ctx.rasterHazards.has(h.hazard_code))
      errors.push(`${h.hazard_code} has no raster layer the browser can read`);
  return { ok: !errors.length, errors, decision };
}
