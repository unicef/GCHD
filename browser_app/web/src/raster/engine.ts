// Raster route: exposure per admin unit computed in the browser from the hazard COGs and WorldPop.
//
// Exact mode (download ≤ EXACT_MAX_BYTES), after GCHD_portolan/gchd/zonal_engine.py and the GEE pipeline:
//   * analysis grid = the country's WorldPop 2025 100 m grid, processed in tiles of TILE x TILE cells
//   * every hazard read at full resolution and sampled nearest-neighbour at the 100 m cell centres
//   * exposed cell = hazard valid AND value <op> threshold (several hazards: any / all, per cell)
//   * units burned in by cell centre
// Coarse mode (very large countries): a coarser grid sampled from the COG overviews; approximate.
// In both modes: exposed share per unit = WorldPop people in exposed cells / WorldPop people in the unit,
// and exposed people = share x the unit's official population from the summary tables, so unit totals
// always match the official numbers.
import { Catalog, Source, tileIndex, worldpopSource } from "../catalog";
import { MAX_GRID_CELLS, WORLDPOP_RES } from "../config";
import { unitPopulation } from "../duck";
import type { BBox } from "../geo";
import { bboxIntersects, polysBBox } from "../geo";
import type { Boundaries } from "../boundaries";
import { Native, cogGeo, readNative, readOnGrid, readWindow, sampleOnGrid } from "./cog";
import { Grid, HazardLayer, Op, ZoneResult, makeGrid, parseRule, rasterizeZones, zonalExposure } from "./grid";

export interface ZonalRequest {
  hazards: { hazard_code: string; op?: string; threshold?: number }[];
  combine: "single" | "any" | "all";
  population: "u18" | "all";
  sex: "total" | "female" | "male";
}

export interface ZonalOutput { columns: string[]; rows: Record<string, unknown>[]; notes: string[]; mode: "exact" | "coarse" }

const EXACT_MAX_BYTES = 400e6;
const EXACT_MAX_CELLS = 800e6;
const TILE = 2048;
// hazard groups whose official exposure used a different layer version in GEE than the catalog COG
// (see the exposure tables' AGENTS.md): heatwave, extreme heat, ASI / SPI / SPEI drought, malaria
export const GEE_VERSION_DIFFERS = /^hazards\/(heatwave|drought|malaria)$/;

const POP_COLL = { u18: "worldpop_u18_2025", all: "worldpop_2025" } as const;
const POP_COL = {
  u18: { total: "u18_pop_total", female: "u18_pop_f", male: "u18_pop_m" },
  all: { total: "pop_total", female: "pop_total_f", male: "pop_total_m" },
} as const;

const area = (b: number[]) => Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
const overlap = (a: number[], b: number[]) =>
  area([Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])]);

/** A hazard's raster files within a bbox (a single COG, or the tiles of a tiled layer), with sizes. */
export async function hazardSources(cat: Catalog, code: string, b: BBox): Promise<Source[]> {
  const h = cat.hazards.get(code);
  if (!h) throw new Error(`unknown hazard ${code}`);
  const tiles = await tileIndex(h.collection);
  if (tiles) return tiles.filter((t) => bboxIntersects(t.bbox as BBox, b));
  const a = h.collection.raw.assets?.data;
  if (!a?.href || !/\.tiff?$/i.test(a.href)) throw new Error(`${code}: no COG the browser can read (${a?.href})`);
  return [{ href: a.href, bbox: a["proj:bbox"] ?? h.collection.raw.extent?.spatial?.bbox?.[0] ?? [-180, -90, 180, 90], size: a["file:size"] ?? 0 }];
}

/** Bytes to download for the country window of each source (file size x share of its area). */
const windowBytes = (s: Source, b: BBox) => s.size * Math.min(1, overlap(s.bbox, b) / Math.max(area(s.bbox), 1e-12));

function layerFor(cat: Catalog, h: ZonalRequest["hazards"][number], values: Float32Array): HazardLayer {
  const rule = cat.hazards.get(h.hazard_code)?.rule;
  return {
    code: h.hazard_code, values,
    valid: parseRule(rule?.valid ?? "> -1e30"),
    op: (h.op ?? rule?.op ?? ">") as Op,
    threshold: Number(h.threshold ?? rule?.threshold ?? 0),
  };
}

function merge(into: ZoneResult[], add: ZoneResult[]) {
  add.forEach((a, i) => {
    const t = into[i];
    t.pixelPop += a.pixelPop; t.exposedPixelPop += a.exposedPixelPop; t.hazSum += a.hazSum; t.hazN += a.hazN;
    t.hazMax = Math.max(t.hazMax, a.hazMax); t.hazMin = Math.min(t.hazMin, a.hazMin);
  });
}

export async function runZonal(cat: Catalog, iso3: string, bbox: BBox, bounds: Boundaries, req: ZonalRequest,
                               onProgress: (msg: string) => void): Promise<ZonalOutput> {
  const units = [...bounds.units.values()];
  const popColl = `${POP_COLL[req.population]}_${req.sex}`;
  const pop = await worldpopSource(cat, popColl, iso3);
  if (!pop) throw new Error(`no WorldPop ${popColl} raster for ${iso3}`);
  const sources = await Promise.all(req.hazards.map((h) => hazardSources(cat, h.hazard_code, bbox)));
  const bytes = pop.size + sources.flat().reduce((s, x) => s + windowBytes(x, bbox), 0);
  const popGeo = await cogGeo(pop.href);
  const combine = req.combine === "single" ? "all" : req.combine;
  const totals: ZoneResult[] = units.map(() => ({ pixelPop: 0, exposedPixelPop: 0, hazSum: 0, hazN: 0, hazMax: -Infinity, hazMin: Infinity }));
  const notes: string[] = [];
  const exact = bytes <= EXACT_MAX_BYTES && popGeo.width * popGeo.height <= EXACT_MAX_CELLS;

  if (exact) {
    // the WorldPop file covers the country: its own 100 m pixels are the analysis grid
    const ub = units.map((u) => polysBBox(u.polygons));
    const nx = Math.ceil(popGeo.width / TILE), ny = Math.ceil(popGeo.height / TILE);
    // only the tiles that touch a unit being computed (all of the country, or the units asked for)
    const todo: { win: [number, number, number, number]; g: Grid; tb: BBox; inTile: boolean[] }[] = [];
    for (let ty = 0; ty < ny; ty++) for (let tx = 0; tx < nx; tx++) {
      const win: [number, number, number, number] = [tx * TILE, ty * TILE, Math.min(popGeo.width, (tx + 1) * TILE), Math.min(popGeo.height, (ty + 1) * TILE)];
      const g: Grid = { x0: popGeo.ox + win[0] * popGeo.rx, y0: popGeo.oy - win[1] * popGeo.ry, dx: popGeo.rx, width: win[2] - win[0], height: win[3] - win[1] };
      const tb: BBox = [g.x0, g.y0 - g.height * g.dx, g.x0 + g.width * g.dx, g.y0];
      const inTile = units.map((_, i) => bboxIntersects(ub[i], tb));
      if (inTile.some(Boolean)) todo.push({ win, g, tb, inTile });
    }
    let k = 0;
    for (const { win, g, tb, inTile } of todo) {
      k++;
      onProgress(`Exact 100 m computation: tile ${k}/${todo.length} (${units.length} unit${units.length > 1 ? "s" : ""})…`);
      const zonesIdx = rasterizeZones(g, units.map((u, i) => (inTile[i] ? u.polygons : [])));
      if (!zonesIdx.some((z) => z > 0)) continue;
      const p = await readWindow(pop.href, win);
      if (!p) continue;
      const layers: HazardLayer[] = [];
      for (let h = 0; h < req.hazards.length; h++) {
        const wins = (await Promise.all(sources[h].filter((s) => bboxIntersects(s.bbox as BBox, tb))
          .map((s) => readNative(s.href, tb)))).filter((w): w is Native => !!w);
        layers.push(layerFor(cat, req.hazards[h], sampleOnGrid(wins, g)));
      }
      merge(totals, zonalExposure(zonesIdx, units.length, p.data, layers, combine));
    }
    notes.push(`Exact mode: WorldPop 2025 100 m grid, hazards sampled at full resolution (nearest), as in the GCHD pipeline.`);
  } else {
    const g = makeGrid(bbox, WORLDPOP_RES, MAX_GRID_CELLS);
    const m = Math.round(g.dx * 111_320 * Math.cos((((bbox[1] + bbox[3]) / 2) * Math.PI) / 180));
    notes.push(`Coarse mode: full-resolution rasters for this country would be ≈${(bytes / 1e6).toFixed(0)} MB, so the grid is ~${m} m `
      + `(${g.width}×${g.height}) sampled from the raster overviews; shares are approximate and can differ from official figures.`);
    onProgress(`Coarse computation on a ${g.width}×${g.height} grid…`);
    const zonesIdx = rasterizeZones(g, units.map((u) => u.polygons));
    const popVals = await readOnGrid([pop.href], g, onProgress);
    const layers: HazardLayer[] = [];
    for (let h = 0; h < req.hazards.length; h++)
      layers.push(layerFor(cat, req.hazards[h], await readOnGrid(sources[h].map((s) => s.href), g, onProgress)));
    merge(totals, zonalExposure(zonesIdx, units.length, popVals, layers, combine));
  }

  const official = await unitPopulation(bounds.level);
  const col = POP_COL[req.population][req.sex];
  const lvl = `adm${bounds.level}`;
  const rows = units.map((u, i) => {
    const r = totals[i];
    const off = official.get(u.ucode)?.[col];
    const share = r.pixelPop > 0 ? r.exposedPixelPop / r.pixelPop : null;
    return {
      [`${lvl}_ucode`]: u.ucode,
      [`${lvl}_name`]: u.name,
      population: off ?? null,
      exposed: off !== undefined && share !== null ? Math.round(off * share) : null,
      exposed_share: share === null ? null : Math.round(share * 10000) / 10000,
      hazard_mean: r.hazN ? Number((r.hazSum / r.hazN).toPrecision(5)) : null,
      hazard_max: r.hazN ? r.hazMax : null,
    };
  }).sort((a, b) => Number(b.exposed ?? -1) - Number(a.exposed ?? -1));
  const otherVersion = req.hazards.map((h) => h.hazard_code).filter((c) => GEE_VERSION_DIFFERS.test(cat.hazards.get(c)?.collection.group ?? ""));
  if (otherVersion.length)
    notes.push(`Caveat: the official tables for ${otherVersion.join(", ")} were computed in GEE on a different version of the layer than `
      + "the catalog COG used here, so even at the default threshold these numbers can differ from the official ones.");
  const missing = rows.filter((r) => r.population === null).length;
  if (missing) notes.push(`${missing} unit(s) have no official population in the summary table; their exposed count is left empty.`);
  const rule = req.hazards.map((h) => { const l = layerFor(cat, h, new Float32Array()); return `${l.code} ${l.op} ${l.threshold}`; })
    .join(combine === "all" ? " AND " : " OR ");
  notes.push(`Exposed = ${rule}; population ${req.population === "u18" ? "under 18" : "all ages"} (${req.sex}); `
    + "exposed share from WorldPop 2025 in the browser, scaled to the official unit population. hazard_mean/max: first hazard.");
  return { columns: Object.keys(rows[0] ?? {}), rows, notes, mode: exact ? "exact" : "coarse" };
}

/** A hazard layer on a display grid over the country (from overviews: for display only), masked to the country. */
export async function hazardPixelMap(cat: Catalog, code: string, bbox: BBox, bounds: Boundaries,
                                     onProgress: (msg: string) => void): Promise<{ grid: Grid; values: Float32Array; mask: Uint8Array }> {
  const g = makeGrid(bbox, WORLDPOP_RES * 3, 1_500_000);
  onProgress(`Reading ${cat.hazards.get(code)?.collection.title ?? code} for the map…`);
  const values = await readOnGrid((await hazardSources(cat, code, bbox)).map((s) => s.href), g, onProgress);
  const zones = rasterizeZones(g, [...bounds.units.values()].map((u) => u.polygons));
  const mask = new Uint8Array(zones.length);
  for (let i = 0; i < zones.length; i++) mask[i] = zones[i] ? 1 : 0;
  return { grid: g, values, mask };
}
