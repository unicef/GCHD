// Small geometry helpers: web-mercator tile maths and rectangle clipping (no dependencies).

export type Ring = [number, number][];
export type BBox = [number, number, number, number];   // xmin, ymin, xmax, ymax (lon/lat)

export function lon2tile(lon: number, z: number): number {
  return Math.floor(((lon + 180) / 360) * 2 ** z);
}
export function lat2tile(lat: number, z: number): number {
  const r = (Math.max(Math.min(lat, 85.0511), -85.0511) * Math.PI) / 180;
  return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z);
}
export function tile2lon(x: number, z: number): number {
  return (x / 2 ** z) * 360 - 180;
}
export function tile2lat(y: number, z: number): number {
  const n = Math.PI - (2 * Math.PI * y) / 2 ** z;
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
}
export function tileBBox(x: number, y: number, z: number): BBox {
  return [tile2lon(x, z), tile2lat(y + 1, z), tile2lon(x + 1, z), tile2lat(y, z)];
}

/** Tiles covering a bbox at zoom z. */
export function tilesFor(b: BBox, z: number): [number, number][] {
  const n = 2 ** z;
  const x0 = Math.max(0, lon2tile(b[0], z)), x1 = Math.min(n - 1, lon2tile(b[2], z));
  const y0 = Math.max(0, lat2tile(b[3], z)), y1 = Math.min(n - 1, lat2tile(b[1], z));
  const out: [number, number][] = [];
  for (let x = x0; x <= x1; x++) for (let y = y0; y <= y1; y++) out.push([x, y]);
  return out;
}

/** Highest zoom (≤ maxZoom) at which the bbox needs at most maxTiles tiles. */
export function zoomFor(b: BBox, maxTiles: number, maxZoom = 10, minZoom = 2): number {
  for (let z = maxZoom; z > minZoom; z--) if (tilesFor(b, z).length <= maxTiles) return z;
  return minZoom;
}

/** Sutherland–Hodgman clip of one ring to a rectangle (keeps fills exact; seams fall on tile edges). */
export function clipRing(ring: Ring, b: BBox): Ring {
  type Edge = { inside: (p: [number, number]) => boolean; cut: (a: [number, number], c: [number, number]) => [number, number] };
  const at = (a: [number, number], c: [number, number], t: number): [number, number] => [a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t];
  const edges: Edge[] = [
    { inside: (p) => p[0] >= b[0], cut: (a, c) => at(a, c, (b[0] - a[0]) / (c[0] - a[0])) },
    { inside: (p) => p[0] <= b[2], cut: (a, c) => at(a, c, (b[2] - a[0]) / (c[0] - a[0])) },
    { inside: (p) => p[1] >= b[1], cut: (a, c) => at(a, c, (b[1] - a[1]) / (c[1] - a[1])) },
    { inside: (p) => p[1] <= b[3], cut: (a, c) => at(a, c, (b[3] - a[1]) / (c[1] - a[1])) },
  ];
  let out = ring.slice();
  if (out.length && out[0][0] === out[out.length - 1][0] && out[0][1] === out[out.length - 1][1]) out.pop();
  for (const e of edges) {
    const input = out;
    out = [];
    for (let i = 0; i < input.length; i++) {
      const cur = input[i], prev = input[(i + input.length - 1) % input.length];
      const ci = e.inside(cur), pi = e.inside(prev);
      if (ci) {
        if (!pi) out.push(e.cut(prev, cur));
        out.push(cur);
      } else if (pi) out.push(e.cut(prev, cur));
    }
    if (!out.length) return [];
  }
  if (out.length < 3) return [];
  out.push([out[0][0], out[0][1]]);
  return out;
}

export function bboxIntersects(a: BBox, b: BBox): boolean {
  return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
}

/** bbox of a list of polygons (each a list of rings). */
export function polysBBox(polys: Ring[][]): BBox {
  const b: BBox = [Infinity, Infinity, -Infinity, -Infinity];
  for (const p of polys) for (const r of p) for (const [x, y] of r) {
    if (x < b[0]) b[0] = x; if (y < b[1]) b[1] = y; if (x > b[2]) b[2] = x; if (y > b[3]) b[3] = y;
  }
  return b;
}
