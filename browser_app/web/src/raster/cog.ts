// Windowed reads of Cloud-Optimized GeoTIFFs onto an analysis grid (geotiff.js, HTTP range requests).
import { fromUrl, GeoTIFF, GeoTIFFImage, Pool } from "geotiff";
import type { BBox } from "../geo";
import { Grid, gridBBox } from "./grid";

const tiffs = new Map<string, Promise<GeoTIFF>>();
let pool: Pool | null = null;

function open(url: string): Promise<GeoTIFF> {
  let t = tiffs.get(url);
  if (!t) { t = fromUrl(url, { allowFullFile: false }); tiffs.set(url, t); }
  return t;
}

interface Level { img: GeoTIFFImage; resX: number; resY: number }

async function levels(tiff: GeoTIFF): Promise<{ levels: Level[]; origin: [number, number]; nodata: number | null }> {
  const base = await tiff.getImage(0);
  const [ox, oy] = base.getOrigin();
  const [rx, ry] = base.getResolution();
  const n = await tiff.getImageCount();
  const out: Level[] = [{ img: base, resX: rx, resY: Math.abs(ry) }];
  for (let i = 1; i < n; i++) {
    const img = await tiff.getImage(i);
    // overviews (not masks): same aspect, smaller size
    if (img.getWidth() >= base.getWidth()) continue;
    out.push({ img, resX: (rx * base.getWidth()) / img.getWidth(), resY: (Math.abs(ry) * base.getHeight()) / img.getHeight() });
  }
  return { levels: out, origin: [ox, oy], nodata: base.getGDALNoData() };
}

/** Native resolution (degrees) and bbox of a COG. */
export async function cogInfo(url: string): Promise<{ res: number; bbox: BBox; nodata: number | null }> {
  const t = await open(url);
  const img = await t.getImage(0);
  return { res: img.getResolution()[0], bbox: img.getBoundingBox() as BBox, nodata: img.getGDALNoData() };
}

/**
 * Band 1 of each source, sampled (nearest) at the grid cells, as float32 with NaN for nodata and
 * outside. Several sources (tiles of one layer) are pasted into the same grid.
 */
export async function readOnGrid(urls: string[], g: Grid, onProgress?: (msg: string) => void): Promise<Float32Array> {
  const out = new Float32Array(g.width * g.height).fill(NaN);
  const gb = gridBBox(g);
  pool ??= new Pool();
  let i = 0;
  for (const url of urls) {
    i++;
    if (urls.length > 1) onProgress?.(`Reading tile ${i}/${urls.length}…`);
    const tiff = await open(url);
    const { levels: lv, origin, nodata } = await levels(tiff);
    const base = lv[0].img;
    const ib: BBox = base.getBoundingBox() as BBox;
    const ix0 = Math.max(gb[0], ib[0]), ix1 = Math.min(gb[2], ib[2]);
    const iy0 = Math.max(gb[1], ib[1]), iy1 = Math.min(gb[3], ib[3]);
    if (ix0 >= ix1 || iy0 >= iy1) continue;
    // grid cells whose centres fall inside the image
    const c0 = Math.max(0, Math.ceil((ix0 - g.x0) / g.dx - 0.5)), c1 = Math.min(g.width - 1, Math.floor((ix1 - g.x0) / g.dx - 0.5));
    const r0 = Math.max(0, Math.ceil((g.y0 - iy1) / g.dx - 0.5)), r1 = Math.min(g.height - 1, Math.floor((g.y0 - iy0) / g.dx - 0.5));
    if (c0 > c1 || r0 > r1) continue;
    const w = c1 - c0 + 1, h = r1 - r0 + 1;
    // coarsest level that is still at least as fine as the grid
    let L = lv[0];
    for (const l of lv) if (l.resX <= g.dx * 1.0001 && l.resX > L.resX) L = l;
    const lw = L.img.getWidth(), lh = L.img.getHeight();
    // window in level pixels covering the cell span [c0, c1] x [r0, r1]
    const wx0 = g.x0 + c0 * g.dx, wx1 = g.x0 + (c1 + 1) * g.dx;
    const wy1 = g.y0 - r0 * g.dx, wy0 = g.y0 - (r1 + 1) * g.dx;
    const px0 = Math.max(0, Math.floor((wx0 - origin[0]) / L.resX)), px1 = Math.min(lw, Math.ceil((wx1 - origin[0]) / L.resX));
    const py0 = Math.max(0, Math.floor((origin[1] - wy1) / L.resY)), py1 = Math.min(lh, Math.ceil((origin[1] - wy0) / L.resY));
    if (px1 <= px0 || py1 <= py0) continue;
    const ras = (await L.img.readRasters({
      window: [px0, py0, px1, py1], samples: [0], interleave: true, pool,
      width: Math.min(w, px1 - px0), height: Math.min(h, py1 - py0), resampleMethod: "nearest",
    })) as unknown as ArrayLike<number> & { width: number; height: number };
    // map each grid cell centre to the nearest returned sample
    const rw = ras.width, rh = ras.height;
    const sx = (px1 - px0) * L.resX / rw, sy = (py1 - py0) * L.resY / rh;
    const ax = origin[0] + px0 * L.resX, ay = origin[1] - py0 * L.resY;
    for (let r = 0; r < h; r++) {
      const yc = g.y0 - (r0 + r + 0.5) * g.dx;
      const rr = Math.min(rh - 1, Math.max(0, Math.floor((ay - yc) / sy)));
      for (let c = 0; c < w; c++) {
        const xc = g.x0 + (c0 + c + 0.5) * g.dx;
        const cc = Math.min(rw - 1, Math.max(0, Math.floor((xc - ax) / sx)));
        const v = ras[rr * rw + cc];
        out[(r0 + r) * g.width + c0 + c] = nodata !== null && v === nodata ? NaN : v;
      }
    }
  }
  return out;
}

/** Full-resolution pixels of band 1 inside a pixel window of level 0 (no resampling). */
export interface Native { data: Float32Array; width: number; height: number; x0: number; y0: number; rx: number; ry: number }

export async function cogGeo(url: string) {
  const img = await (await open(url)).getImage(0);
  const [ox, oy] = img.getOrigin();
  const [rx, ry] = img.getResolution();
  return { ox, oy, rx, ry: Math.abs(ry), width: img.getWidth(), height: img.getHeight(), nodata: img.getGDALNoData() };
}

export async function readWindow(url: string, win: [number, number, number, number]): Promise<Native | null> {
  const img = await (await open(url)).getImage(0);
  const geo = await cogGeo(url);
  const w: [number, number, number, number] = [Math.max(0, win[0]), Math.max(0, win[1]), Math.min(geo.width, win[2]), Math.min(geo.height, win[3])];
  if (w[2] <= w[0] || w[3] <= w[1]) return null;
  pool ??= new Pool();
  const r = (await img.readRasters({ window: w, samples: [0], interleave: true, pool })) as unknown as ArrayLike<number>;
  const n = (w[2] - w[0]) * (w[3] - w[1]);
  const data = new Float32Array(n);
  for (let i = 0; i < n; i++) { const v = r[i]; data[i] = geo.nodata !== null && v === geo.nodata ? NaN : v; }
  return { data, width: w[2] - w[0], height: w[3] - w[1], x0: geo.ox + w[0] * geo.rx, y0: geo.oy - w[1] * geo.ry, rx: geo.rx, ry: geo.ry };
}

/** Full-resolution pixels of level 0 covering a bbox (one pixel margin). */
export async function readNative(url: string, b: BBox): Promise<Native | null> {
  const g = await cogGeo(url);
  return readWindow(url, [Math.floor((b[0] - g.ox) / g.rx) - 1, Math.floor((g.oy - b[3]) / g.ry) - 1,
                          Math.ceil((b[2] - g.ox) / g.rx) + 1, Math.ceil((g.oy - b[1]) / g.ry) + 1]);
}

/** Nearest-neighbour sample of a set of native windows at the centres of a grid (NaN outside). */
export function sampleOnGrid(wins: Native[], g: Grid): Float32Array {
  const out = new Float32Array(g.width * g.height).fill(NaN);
  for (const n of wins) {
    for (let r = 0; r < g.height; r++) {
      const y = g.y0 - (r + 0.5) * g.dx;
      const row = Math.floor((n.y0 - y) / n.ry);
      if (row < 0 || row >= n.height) continue;
      for (let c = 0; c < g.width; c++) {
        const x = g.x0 + (c + 0.5) * g.dx;
        const col = Math.floor((x - n.x0) / n.rx);
        if (col < 0 || col >= n.width) continue;
        out[r * g.width + c] = n.data[row * n.width + col];
      }
    }
  }
  return out;
}
