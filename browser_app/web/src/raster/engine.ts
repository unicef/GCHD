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
// (see the exposure tables' AGENTS.md): heatwave, extreme heat, ASI drought, malaria (SPI / SPEI match since the catalog fix of 2026-11-27)
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

export interface RasterPlan {
  exact: boolean;
  bytes: number;            // full-resolution download for the area
  aoi: BBox;                // bbox of the units computed (within the country)
  blockers: string[];       // why the request cannot be computed reliably (empty = ok)
}

/**
 * Exact or coarse mode for a request, from the area actually computed (all units of the level, or the ones
 * asked for). Coarse mode reads the COG overviews; a hazard whose native pixels are finer than the coarse grid
 * would be thresholded on averaged overview values, which inflates exposure (the overviews average only valid
 * pixels: where "no hazard" is nodata, e.g. flood depth, a coarse cell with a few flooded pixels counts as
 * flooded everywhere; around São Paulo 7.5 % of 100 m cells are flooded but 37 % of ~1.6 km overview cells).
 * Such a request is refused, with the way out: fewer units, so exact mode fits.
 */
export async function planRaster(cat: Catalog, iso3: string, countryBBox: BBox, bounds: Boundaries, req: ZonalRequest,
                                 allUnits: number): Promise<RasterPlan & { pop: Source; popGeo: Awaited<ReturnType<typeof cogGeo>>; sources: Source[][]; grid?: Grid }> {
  const units = [...bounds.units.values()];
  const ub = units.map((u) => polysBBox(u.polygons)).reduce<BBox>((a, b) =>
    [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[2], b[2]), Math.max(a[3], b[3])], [Infinity, Infinity, -Infinity, -Infinity]);
  const aoi: BBox = units.length ? [Math.max(ub[0], countryBBox[0]), Math.max(ub[1], countryBBox[1]), Math.min(ub[2], countryBBox[2]), Math.min(ub[3], countryBBox[3])] : countryBBox;
  const popColl = `${POP_COLL[req.population]}_${req.sex}`;
  const pop = await worldpopSource(cat, popColl, iso3);
  if (!pop) throw new Error(`no WorldPop ${popColl} raster for ${iso3}`);
  const popGeo = await cogGeo(pop.href);
  const sources = await Promise.all(req.hazards.map((h) => hazardSources(cat, h.hazard_code, aoi)));
  const bytes = windowBytes(pop, aoi) + sources.flat().reduce((s, x) => s + windowBytes(x, aoi), 0);
  const cells = area(aoi) / (popGeo.rx * popGeo.ry);
  const exact = bytes <= EXACT_MAX_BYTES && cells <= EXACT_MAX_CELLS;
  const blockers: string[] = [];
  let grid: Grid | undefined;
  if (!exact) {
    grid = makeGrid(aoi, WORLDPOP_RES, MAX_GRID_CELLS);
    const km = (grid.dx * 111.32 * Math.cos((((aoi[1] + aoi[3]) / 2) * Math.PI) / 180)).toFixed(1);
    for (let h = 0; h < req.hazards.length; h++) {
      if (!sources[h].length) continue;
      const native = (await cogGeo(sources[h][0].href)).rx;
      if (native < grid.dx * 0.999) {
        const code = req.hazards[h].hazard_code;
        blockers.push(`${code}: computing ${units.length === allUnits ? "the whole country" : `these ${units.length} units`} at full resolution `
          + `would download about ${(bytes / 1e6).toFixed(0)} MB (limit ${EXACT_MAX_BYTES / 1e6} MB), and on the coarse ~${km} km grid the `
          + `${(native * 111.32).toFixed(1)} km hazard pixels would be averaged before the threshold is applied, which overstates `
          + "exposure badly (for flood: several times the true value). Ask the user to limit the area: one or a few ADM1 units "
          + "(set units in the plan), which runs at full resolution.");
      }
    }
  }
  return { exact, bytes, aoi, blockers, pop, popGeo, sources, grid };
}

export async function runZonal(cat: Catalog, iso3: string, bbox: BBox, bounds: Boundaries, req: ZonalRequest,
                               onProgress: (msg: string) => void, allUnits = bounds.units.size): Promise<ZonalOutput> {
  const units = [...bounds.units.values()];
  const plan = await planRaster(cat, iso3, bbox, bounds, req, allUnits);
  if (plan.blockers.length) throw new Error(`Cannot compute this reliably in the browser. ${plan.blockers.join(" ")}`);
  const { exact, bytes, pop, popGeo, sources } = plan;
  const combine = req.combine === "single" ? "all" : req.combine;
  const totals: ZoneResult[] = units.map(() => ({ pixelPop: 0, exposedPixelPop: 0, hazSum: 0, hazN: 0, hazMax: -Infinity, hazMin: Infinity }));
  const notes: string[] = [];

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
    const g = plan.grid!;
    const m = Math.round(g.dx * 111_320 * Math.cos((((plan.aoi[1] + plan.aoi[3]) / 2) * Math.PI) / 180));
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
