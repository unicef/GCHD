import { describe, expect, it } from "vitest";
import { Plan, RouteContext, checkPlan, requiredRoute } from "../web/src/route";

const ctx: RouteContext = {
  tableHazards: new Set(["river_flood_100yr", "extreme_heat_days", "heatwave_frequency"]),
  rasterHazards: new Set(["river_flood_100yr", "extreme_heat_days", "heatwave_frequency", "mhi_only"]),
  defaultRule: (c) => ({ river_flood_100yr: { op: ">", threshold: 0.01 }, extreme_heat_days: { op: ">", threshold: 35 } } as any)[c],
};
const base = (p: Partial<Plan>): Plan => ({
  intent: "x", data_route: "summary", admin_level: 2, hazards: [], outputs: ["table"], steps: [], can_do: [], cannot_do: [], ...p,
});

describe("summary-first routing", () => {
  it("children exposed to floods by district -> summary", () => {
    const p = base({ hazards: [{ hazard_code: "river_flood_100yr" }], outputs: ["table", "map", "csv"] });
    expect(requiredRoute(p, ctx).route).toBe("summary");
    expect(checkPlan(p, ctx).ok).toBe(true);
  });
  it("show the heatwave map (choropleth) -> summary", () => {
    const p = base({ hazards: [{ hazard_code: "heatwave_frequency" }], outputs: ["map"] });
    expect(checkPlan(p, ctx).ok).toBe(true);
  });
  it("the default threshold restated is still summary", () => {
    expect(requiredRoute(base({ hazards: [{ hazard_code: "river_flood_100yr", threshold: 0.01 }] }), ctx).route).toBe("summary");
  });
  it("flood depth > 0.5 m -> raster", () => {
    const p = base({ hazards: [{ hazard_code: "river_flood_100yr", op: ">", threshold: 0.5 }] });
    expect(requiredRoute(p, ctx).route).toBe("raster");
    expect(checkPlan(p, ctx).ok).toBe(false);                         // marked summary: rejected
    expect(checkPlan({ ...p, data_route: "raster", why_not_summary: "custom threshold" }, ctx).ok).toBe(true);
  });
  it("combined hazards and pixel maps -> raster", () => {
    expect(requiredRoute(base({ hazards: [{ hazard_code: "river_flood_100yr" }, { hazard_code: "extreme_heat_days" }], combine: "any" }), ctx).route).toBe("raster");
    expect(requiredRoute(base({ hazards: [{ hazard_code: "extreme_heat_days" }], outputs: ["pixel_map"] }), ctx).route).toBe("raster");
  });
  it("a raster plan the tables can answer is rejected unless the user asked for it", () => {
    const p = base({ data_route: "raster", why_not_summary: "because", hazards: [{ hazard_code: "river_flood_100yr" }] });
    expect(checkPlan(p, ctx).ok).toBe(false);
    expect(checkPlan({ ...p, user_asked_for_raster: true }, ctx).ok).toBe(true);
  });
  it("raster plans need a reason, and unknown hazards are rejected", () => {
    expect(checkPlan(base({ data_route: "raster", hazards: [{ hazard_code: "mhi_only" }] }), ctx).ok).toBe(false);
    expect(checkPlan(base({ hazards: [{ hazard_code: "nope" }] }), ctx).ok).toBe(false);
  });
});
