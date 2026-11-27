// Administrative boundaries for one country, decoded in the browser from the GCHD PMTiles vector tiles
// (adm0/1/2.pmtiles on Azure). Polygons are clipped to each tile's own extent (vector tiles carry a
// buffer) and the pieces of one unit are gathered by ucode, so fills tile seamlessly.
import { PMTiles } from "pmtiles";
import { VectorTile } from "@mapbox/vector-tile";
import { PbfReader } from "pbf";
import { MAX_BOUNDARY_TILES } from "./config";
import { BBox, Ring, clipRing, tileBBox, tilesFor, zoomFor } from "./geo";

export interface Unit {
  ucode: string;
  name: string;
  props: Record<string, unknown>;
  polygons: Ring[][];            // each polygon: [outer, ...holes]
  lines: Ring[];                 // outline without the tile-edge cuts (for drawing borders)
}

export interface Boundaries { level: 0 | 1 | 2; zoom: number; units: Map<string, Unit> }

const archives = new Map<string, PMTiles>();
const cache = new Map<string, Boundaries>();

export async function loadBoundaries(url: string, level: 0 | 1 | 2, iso3: string, bbox: BBox,
                                     onProgress?: (msg: string) => void): Promise<Boundaries> {
  const key = `${iso3}:${level}`;
  const hit = cache.get(key);
  if (hit) return hit;
  let pm = archives.get(url);
  if (!pm) { pm = new PMTiles(url); archives.set(url, pm); }
  const zoom = zoomFor(bbox, MAX_BOUNDARY_TILES);
  const tiles = tilesFor(bbox, zoom);
  onProgress?.(`Loading ADM${level} boundaries (${tiles.length} tiles at zoom ${zoom})…`);
  const units = new Map<string, Unit>();
  const layerName = `adm${level}`;
  let done = 0;
  const work = tiles.map(async ([x, y]) => {
    const t = await pm!.getZxy(zoom, x, y);
    done++;
    if (done % 20 === 0) onProgress?.(`Loading ADM${level} boundaries… ${done}/${tiles.length} tiles`);
    if (!t?.data) return;
    const vt = new VectorTile(new PbfReader(new Uint8Array(t.data)));
    const layer = vt.layers[layerName];
    if (!layer) return;
    const tb = tileBBox(x, y, zoom);
    for (let i = 0; i < layer.length; i++) {
      const f = layer.feature(i);
      if (f.properties.iso3 !== iso3) continue;
      const gj = f.toGeoJSON(x, y, zoom) as any;
      const g = gj.geometry;
      const polys: Ring[][] = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : [];
      const ucode = String(f.properties.ucode);
      let u = units.get(ucode);
      if (!u) {
        u = { ucode, name: String(f.properties.name_en || f.properties.name || ucode), props: { ...f.properties }, polygons: [], lines: [] };
        units.set(ucode, u);
      }
      for (const p of polys) {
        const outer = clipRing(p[0] as Ring, tb);
        if (outer.length < 4) continue;
        const holes = p.slice(1).map((r) => clipRing(r as Ring, tb)).filter((r) => r.length >= 4);
        u.polygons.push([outer, ...holes]);
        for (const r of [outer, ...holes]) u.lines.push(...realEdges(r, tb));
      }
    }
  });
  await Promise.all(work);
  const res = { level, zoom, units };
  cache.set(key, res);
  return res;
}

/** Splits a clipped ring into polylines, dropping segments that run along the tile's edge. */
export function realEdges(r: Ring, tb: BBox): Ring[] {
  const eps = 1e-9;
  const onEdge = (a: [number, number], b: [number, number]) =>
    (Math.abs(a[0] - tb[0]) < eps && Math.abs(b[0] - tb[0]) < eps) || (Math.abs(a[0] - tb[2]) < eps && Math.abs(b[0] - tb[2]) < eps)
    || (Math.abs(a[1] - tb[1]) < eps && Math.abs(b[1] - tb[1]) < eps) || (Math.abs(a[1] - tb[3]) < eps && Math.abs(b[1] - tb[3]) < eps);
  const out: Ring[] = [];
  let cur: Ring = [];
  for (let i = 0; i < r.length - 1; i++) {
    if (onEdge(r[i], r[i + 1])) {
      if (cur.length > 1) out.push(cur);
      cur = [];
      continue;
    }
    if (!cur.length) cur.push(r[i]);
    cur.push(r[i + 1]);
  }
  if (cur.length > 1) out.push(cur);
  return out;
}

export function outlinesGeoJSON(b: Boundaries): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [...b.units.values()].map((u) => ({
      type: "Feature", properties: { ucode: u.ucode }, geometry: { type: "MultiLineString", coordinates: u.lines },
    })),
  };
}

export function toGeoJSON(b: Boundaries, values?: Map<string, Record<string, unknown>>): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [...b.units.values()].map((u) => ({
      type: "Feature",
      properties: { ucode: u.ucode, name: u.name, ...u.props, ...(values?.get(u.ucode) ?? {}) },
      geometry: { type: "MultiPolygon", coordinates: u.polygons },
    })),
  };
}
