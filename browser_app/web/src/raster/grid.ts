// Analysis grid and polygon rasterization for the raster route (pure functions, unit-tested).
import type { BBox, Ring } from "../geo";

export interface Grid { x0: number; y0: number; dx: number; width: number; height: number }  // y0 = top edge

/** A grid over bbox with cells of at least minCell degrees and at most maxCells cells. */
export function makeGrid(b: BBox, minCell: number, maxCells: number): Grid {
  const w = b[2] - b[0], h = b[3] - b[1];
  let dx = minCell;
  if ((w / dx) * (h / dx) > maxCells) dx = Math.sqrt((w * h) / maxCells);
  // snap the origin to multiples of dx so grids of one country line up between runs
  const x0 = Math.floor(b[0] / dx) * dx, y0 = Math.ceil(b[3] / dx) * dx;
  return { x0, y0, dx, width: Math.max(1, Math.ceil((b[2] - x0) / dx)), height: Math.max(1, Math.ceil((y0 - b[1]) / dx)) };
}

export function gridBBox(g: Grid): BBox {
  return [g.x0, g.y0 - g.height * g.dx, g.x0 + g.width * g.dx, g.y0];
}

/**
 * Burns zone index (1-based) into a grid by cell-centre sampling with the even-odd rule (holes and
 * multipolygons work). Zone 0 = outside every unit.
 */
export function rasterizeZones(g: Grid, zones: Ring[][][]): Int32Array {
  const out = new Int32Array(g.width * g.height);
  zones.forEach((polys, zi) => {
    const edges: [number, number, number, number][] = [];
    for (const p of polys) for (const r of p)
      for (let i = 0; i < r.length - 1; i++) {
        const [ax, ay] = r[i], [bx, by] = r[i + 1];
        if (ay !== by) edges.push([ax, ay, bx, by]);
      }
    if (!edges.length) return;
    let ymin = Infinity, ymax = -Infinity;
    for (const e of edges) { ymin = Math.min(ymin, e[1], e[3]); ymax = Math.max(ymax, e[1], e[3]); }
    const r0 = Math.max(0, Math.floor((g.y0 - ymax) / g.dx)), r1 = Math.min(g.height - 1, Math.ceil((g.y0 - ymin) / g.dx));
    const xs: number[] = [];
    for (let row = r0; row <= r1; row++) {
      const yc = g.y0 - (row + 0.5) * g.dx;
      xs.length = 0;
      for (const [ax, ay, bx, by] of edges)
        if ((ay <= yc && by > yc) || (by <= yc && ay > yc)) xs.push(ax + ((yc - ay) / (by - ay)) * (bx - ax));
      xs.sort((a, b) => a - b);
      for (let k = 0; k + 1 < xs.length; k += 2) {
        const c0 = Math.max(0, Math.ceil((xs[k] - g.x0) / g.dx - 0.5));
        const c1 = Math.min(g.width - 1, Math.floor((xs[k + 1] - g.x0) / g.dx - 0.5));
        for (let c = c0; c <= c1; c++) out[row * g.width + c] = zi + 1;
      }
    }
  });
  return out;
}

export type Op = ">" | ">=" | "<" | "<=";
export const OPS: Record<Op, (a: number, b: number) => boolean> = {
  ">": (a, b) => a > b, ">=": (a, b) => a >= b, "<": (a, b) => a < b, "<=": (a, b) => a <= b,
};

export function parseRule(s: string): { op: Op; value: number } {
  const m = s.trim().match(/^(>=|<=|>|<)\s*(-?[\d.eE+-]+)$/);
  if (!m) throw new Error(`bad rule ${s}`);
  return { op: m[1] as Op, value: Number(m[2]) };
}

export interface HazardLayer { code: string; values: Float32Array; valid: { op: Op; value: number }; op: Op; threshold: number }

export interface ZoneResult {
  pixelPop: number;                 // population on the grid inside the zone (before calibration)
  exposedPixelPop: number;          // … where the hazard condition holds
  hazSum: number; hazN: number; hazMax: number; hazMin: number;   // hazard statistics over valid cells
}

/**
 * Exposure per zone. exposed cell = every hazard valid and its condition true ("all") or at least one
 * condition true ("any"). Population is the WorldPop grid; the caller calibrates to official totals.
 */
export function zonalExposure(zonesIdx: Int32Array, nZones: number, pop: Float32Array, hazards: HazardLayer[],
                              combine: "any" | "all"): ZoneResult[] {
  const res: ZoneResult[] = Array.from({ length: nZones }, () =>
    ({ pixelPop: 0, exposedPixelPop: 0, hazSum: 0, hazN: 0, hazMax: -Infinity, hazMin: Infinity }));
  const first = hazards[0];
  for (let i = 0; i < zonesIdx.length; i++) {
    const z = zonesIdx[i];
    if (!z) continue;
    const r = res[z - 1];
    const p = pop[i] > 0 && Number.isFinite(pop[i]) ? pop[i] : 0;
    r.pixelPop += p;
    let hit = combine === "all";
    for (const h of hazards) {
      const v = h.values[i];
      const ok = Number.isFinite(v) && OPS[h.valid.op](v, h.valid.value);
      const e = ok && OPS[h.op](v, h.threshold);
      hit = combine === "all" ? hit && e : hit || e;
    }
    if (hit) r.exposedPixelPop += p;
    if (first) {
      const v = first.values[i];
      if (Number.isFinite(v) && OPS[first.valid.op](v, first.valid.value)) {
        r.hazSum += v; r.hazN++; if (v > r.hazMax) r.hazMax = v; if (v < r.hazMin) r.hazMin = v;
      }
    }
  }
  return res;
}
