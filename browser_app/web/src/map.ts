// Leaflet map (canvas renderer, no WebGL): choropleths from the summary tables and raster overlays.
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { BBox } from "./geo";
import type { Grid } from "./raster/grid";

// sequential ramp (light yellow -> dark red), colour-blind safe
const RAMP = ["#ffffcc", "#ffeda0", "#fed976", "#feb24c", "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026"];

let map: L.Map;
const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
let dataLayer: L.Layer | null = null;
let legend: L.Control | null = null;
const renderer = L.canvas({ padding: 0.5 });

// what is on the map now, for export
interface Shown {
  title: string; br: number[]; note?: string;
  geojson?: GeoJSON.FeatureCollection; prop?: string; outlines?: GeoJSON.FeatureCollection;   // choropleth
  raster?: { canvas: HTMLCanvasElement; bounds: L.LatLngBounds };                  // pixel map
}
let shown: Shown | null = null;
let exportName = "GCHD_map";
export function setExportName(name: string) { exportName = name.replace(/[^\w.-]+/g, "_"); }

export function initMap(el: HTMLElement): L.Map {
  map = L.map(el, { preferCanvas: true, worldCopyJump: true }).setView([10, 20], 2);
  // crossOrigin: OSM tiles allow CORS, so they can be drawn into the exported PNG
  L.tileLayer(OSM, {
    maxZoom: 12, attribution: "© OpenStreetMap contributors", crossOrigin: "anonymous",
  }).addTo(map);
  const ctl = new L.Control({ position: "topright" });
  ctl.onAdd = () => {
    const d = L.DomUtil.create("div", "map-export");
    d.innerHTML = `<button data-x="png" title="Download the map as a PNG image">PNG</button>`
      + `<button data-x="geojson" title="Download the mapped units and values as GeoJSON">GeoJSON</button>`;
    L.DomEvent.disableClickPropagation(d);
    d.querySelector<HTMLButtonElement>('[data-x="png"]')!.onclick = () => exportPng();
    d.querySelector<HTMLButtonElement>('[data-x="geojson"]')!.onclick = () => exportGeoJSON();
    return d;
  };
  ctl.addTo(map);
  return map;
}

function save(blob: Blob, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}

/** The mapped units with their values (choropleths only), as GeoJSON. */
export function exportGeoJSON() {
  if (!shown?.geojson) { alert("GeoJSON export is available for district / region maps (choropleths)."); return; }
  const fc = {
    type: "FeatureCollection",
    features: shown.geojson.features.map((f) => ({
      type: "Feature",
      properties: { ucode: f.properties?.ucode, name: f.properties?.name, [shown!.prop!]: f.properties?.[shown!.prop!] ?? null },
      geometry: f.geometry,
    })),
  };
  save(new Blob([JSON.stringify(fc)], { type: "application/geo+json" }), `${exportName}.geojson`);
}

// PNG export: the current view redrawn at EXPORT_SCALE x its on-screen size (capped at EXPORT_MAX_PX on the
// long side): basemap tiles from a higher zoom level, choropleth polygons as vectors, raster pixels unsmoothed.
const EXPORT_SCALE = 4;
const EXPORT_MAX_PX = 6000;
const EXPORT_MAX_TILES = 400;

function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((res) => {
    const i = new Image();
    i.crossOrigin = "anonymous";
    i.onload = () => res(i);
    i.onerror = () => res(null);
    i.src = url;
  });
}

/** OSM tiles covering the view, drawn at the export scale (ctx is in CSS pixels of the map view). */
async function drawBasemap(ctx: CanvasRenderingContext2D, W: number, H: number, s: number) {
  const zoom = map.getZoom();
  let z = Math.min(19, Math.round(zoom + Math.log2(s)));
  let tiles: { x: number; y: number; dx: number; dy: number; f: number }[] = [];
  for (;;) {
    const f = 2 ** (z - zoom);                         // z-level pixels per view CSS pixel
    const p0 = map.project(map.containerPointToLatLng([0, 0]), z);
    const n = 2 ** z;
    tiles = [];
    for (let ty = Math.floor(p0.y / 256); ty <= Math.floor((p0.y + H * f) / 256); ty++) {
      if (ty < 0 || ty >= n) continue;
      for (let tx = Math.floor(p0.x / 256); tx <= Math.floor((p0.x + W * f) / 256); tx++)
        tiles.push({ x: ((tx % n) + n) % n, y: ty, dx: (tx * 256 - p0.x) / f, dy: (ty * 256 - p0.y) / f, f });
    }
    if (tiles.length <= EXPORT_MAX_TILES || z <= Math.round(zoom)) break;
    z--;
  }
  const url = (t: { x: number; y: number }) => OSM.replace("{z}", String(z)).replace("{x}", String(t.x)).replace("{y}", String(t.y));
  for (let i = 0; i < tiles.length; i += 8) {           // a few at a time, to be polite to the OSM tile servers
    const batch = tiles.slice(i, i + 8);
    const imgs = await Promise.all(batch.map((t) => loadImage(url(t))));
    batch.forEach((t, k) => { if (imgs[k]) ctx.drawImage(imgs[k]!, t.dx, t.dy, 256 / t.f + 0.02, 256 / t.f + 0.02); });
  }
}

function tracePolys(ctx: CanvasRenderingContext2D, g: GeoJSON.Geometry) {
  const ring = (r: number[][]) => r.forEach(([lon, lat], i) => {
    const p = map.latLngToContainerPoint([lat, lon]);
    if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
  });
  if (g.type === "Polygon") g.coordinates.forEach((r) => { ring(r); ctx.closePath(); });
  else if (g.type === "MultiPolygon") g.coordinates.forEach((pl) => pl.forEach((r) => { ring(r); ctx.closePath(); }));
  else if (g.type === "LineString") ring(g.coordinates);
  else if (g.type === "MultiLineString") g.coordinates.forEach(ring);
}

function drawData(ctx: CanvasRenderingContext2D, s: Shown) {
  if (s.geojson && s.prop) {
    ctx.globalAlpha = 0.75;
    for (const f of s.geojson.features) {
      ctx.beginPath();
      tracePolys(ctx, f.geometry);
      ctx.fillStyle = colorFor(Number(f.properties?.[s.prop]), s.br);
      ctx.fill("evenodd");
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 0.6;
    ctx.lineJoin = "round";
    for (const f of s.outlines?.features ?? []) {
      ctx.beginPath();
      tracePolys(ctx, f.geometry);
      ctx.stroke();
    }
  }
  if (s.raster) {
    const b = s.raster.bounds;
    const a = map.latLngToContainerPoint(b.getNorthWest()), c = map.latLngToContainerPoint(b.getSouthEast());
    ctx.globalAlpha = 0.85;
    ctx.imageSmoothingEnabled = false;                   // keep the hazard pixels crisp
    ctx.drawImage(s.raster.canvas, a.x, a.y, c.x - a.x, c.y - a.y);
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = 1;
  }
}

/** The current view as a high-resolution PNG: basemap, data, title, legend, attribution and source. */
export async function exportPng(withBasemap = true): Promise<void> {
  const size = map.getSize();
  const W = size.x, H = size.y;
  const s = Math.max(2, Math.min(EXPORT_SCALE, EXPORT_MAX_PX / Math.max(W, H)));
  const btn = map.getContainer().querySelector<HTMLButtonElement>('.map-export [data-x="png"]');
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const c = document.createElement("canvas");
    c.width = Math.round(W * s); c.height = Math.round(H * s);
    const ctx = c.getContext("2d")!;
    ctx.scale(s, s);
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, W, H);
    if (withBasemap) await drawBasemap(ctx, W, H, s);
    if (shown) drawData(ctx, shown);

    if (shown) {                                         // title
      ctx.font = "bold 15px system-ui, sans-serif";
      const w = ctx.measureText(shown.title).width;
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillRect(8, 8, w + 16, 26);
      ctx.fillStyle = "#1d2733";
      ctx.fillText(shown.title, 16, 26);
      drawLegend(ctx, shown, W, H);
    }
    const foot = `${withBasemap ? "Basemap © OpenStreetMap contributors · " : ""}Data: UNICEF Global Child Hazard Database (GCHD)`;
    ctx.font = "11px system-ui, sans-serif";
    const fw = ctx.measureText(foot).width;
    ctx.fillStyle = "rgba(255,255,255,0.85)";
    ctx.fillRect(0, H - 18, fw + 12, 18);
    ctx.fillStyle = "#333";
    ctx.fillText(foot, 6, H - 5);

    let blob: Blob | null = null;
    try { blob = await new Promise<Blob | null>((res) => c.toBlob(res, "image/png")); } catch { blob = null; }
    if (!blob) {
      // a tile without CORS taints the canvas: export again without the basemap
      if (withBasemap) return await exportPng(false);
      throw new Error("could not create the PNG");
    }
    save(blob, `${exportName}.png`);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "PNG"; }
  }
}

function drawLegend(ctx: CanvasRenderingContext2D, s: Shown, W: number, H: number) {
  const labels = legendLabels(s.br);
  const rows = labels.length + 1;
  const lh = 17, pad = 8, bw = 190;
  const bh = pad * 2 + 20 + rows * lh + (s.note ? 16 : 0);
  const x = W - bw - 10, y = H - bh - 26;
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.fillRect(x, y, bw, bh);
  ctx.strokeStyle = "#bbb";
  ctx.strokeRect(x, y, bw, bh);
  ctx.fillStyle = "#1d2733";
  ctx.font = "bold 12px system-ui, sans-serif";
  ctx.fillText(s.title.length > 28 ? s.title.slice(0, 27) + "…" : s.title, x + pad, y + pad + 12);
  ctx.font = "12px system-ui, sans-serif";
  [...labels.map((l, i) => ({ l, c: classColor(i, s.br) })), { l: "no data", c: "#cccccc" }].forEach((r, i) => {
    const yy = y + pad + 22 + i * lh;
    ctx.fillStyle = r.c;
    ctx.fillRect(x + pad, yy, 16, 11);
    ctx.strokeStyle = "#999";
    ctx.strokeRect(x + pad, yy, 16, 11);
    ctx.fillStyle = "#1d2733";
    ctx.fillText(r.l, x + pad + 24, yy + 10);
  });
  if (s.note) {
    ctx.font = "10px system-ui, sans-serif";
    ctx.fillStyle = "#555";
    ctx.fillText(s.note.length > 34 ? s.note.slice(0, 33) + "…" : s.note, x + pad, y + bh - pad);
  }
}

export function fitBBox(b: BBox) {
  map.fitBounds([[b[1], b[0]], [b[3], b[2]]], { padding: [10, 10] });
}

function clear() {
  if (dataLayer) map.removeLayer(dataLayer);
  if (legend) map.removeControl(legend);
  dataLayer = legend = null;
  shown = null;
}

/** Class breaks: quantiles of the finite values (unique, ascending), at most RAMP.length classes. */
export function breaks(values: number[], n = RAMP.length): number[] {
  const v = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!v.length) return [];
  const out: number[] = [];
  for (let i = 1; i < n; i++) out.push(v[Math.min(v.length - 1, Math.floor((i / n) * v.length))]);
  return [...new Set(out)];
}

const classColor = (i: number, br: number[]) => RAMP[Math.round((i / Math.max(1, br.length)) * (RAMP.length - 1))];

function colorFor(x: number, br: number[]): string {
  if (!Number.isFinite(x)) return "#cccccc";
  let i = 0;
  while (i < br.length && x > br[i]) i++;
  return classColor(i, br);
}

const fmt = (x: number) => Math.abs(x) >= 1000 ? Math.round(x).toLocaleString() : Number(x.toPrecision(3)).toString();

function legendLabels(br: number[]): string[] {
  return [-Infinity, ...br].map((lo, i) => {
    const hi = br[i];
    return i === 0 ? `≤ ${fmt(hi ?? lo)}` : hi === undefined ? `> ${fmt(lo)}` : `${fmt(lo)} – ${fmt(hi)}`;
  });
}

function addLegend(title: string, br: number[], extra?: string) {
  legend = new L.Control({ position: "bottomright" });
  legend.onAdd = () => {
    const d = L.DomUtil.create("div", "legend");
    const rows = [`<b>${title}</b>`];
    legendLabels(br).forEach((label, i) => rows.push(`<i style="background:${classColor(i, br)}"></i>${label}`));
    rows.push(`<i style="background:#cccccc"></i>no data`);
    if (extra) rows.push(`<small>${extra}</small>`);
    d.innerHTML = rows.join("<br>");
    return d;
  };
  legend.addTo(map);
}

/** Choropleth of one numeric property of the features. */
export function showChoropleth(fc: GeoJSON.FeatureCollection, prop: string, title: string, outlines: GeoJSON.FeatureCollection, note?: string) {
  clear();
  const vals = fc.features.map((f) => Number(f.properties?.[prop]));
  const br = breaks(vals);
  const fills = L.geoJSON(fc, {
    renderer,
    style: (f) => ({ stroke: false, fillOpacity: 0.75, fillColor: colorFor(Number(f?.properties?.[prop]), br) }),
    onEachFeature: (f, layer) => {
      const v = Number(f.properties?.[prop]);
      layer.bindTooltip(`${f.properties?.name ?? f.properties?.ucode}<br>${title}: ${Number.isFinite(v) ? fmt(v) : "no data"}`, { sticky: true });
    },
  } as L.GeoJSONOptions);
  const lines = L.geoJSON(outlines, { renderer, interactive: false, style: () => ({ color: "#555", weight: 0.6 }) } as L.GeoJSONOptions);
  dataLayer = L.layerGroup([fills, lines]).addTo(map);
  addLegend(title, br, note);
  shown = { title, br, note, geojson: fc, prop, outlines };
}

/** Outline only (country chosen, nothing computed yet). */
export function showOutline(fc: GeoJSON.FeatureCollection, outlines: GeoJSON.FeatureCollection) {
  clear();
  const fills = L.geoJSON(fc, {
    renderer,
    style: () => ({ stroke: false, fillColor: "#1cabe2", fillOpacity: 0.08 }),
    onEachFeature: (f, layer) => layer.bindTooltip(String(f.properties?.name ?? ""), { sticky: true }),
  } as L.GeoJSONOptions);
  const lines = L.geoJSON(outlines, { renderer, interactive: false, style: () => ({ color: "#1cabe2", weight: 1 }) } as L.GeoJSONOptions);
  dataLayer = L.layerGroup([fills, lines]).addTo(map);
}

const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (Math.max(Math.min(lat, 85), -85) * Math.PI) / 360));

/** Raster overlay of a grid (re-projected row by row to web mercator so it lines up on the basemap). */
export function showRaster(g: Grid, values: Float32Array, title: string, mask?: Uint8Array, note?: string) {
  clear();
  const finite: number[] = [];
  for (let i = 0; i < values.length; i += Math.max(1, Math.floor(values.length / 20000)))
    if (Number.isFinite(values[i]) && (!mask || mask[i])) finite.push(values[i]);
  const br = breaks(finite);
  const H = Math.min(2048, Math.max(g.height, 256));
  const canvas = document.createElement("canvas");
  canvas.width = g.width; canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(g.width, H);
  const top = g.y0, bottom = g.y0 - g.height * g.dx;
  const m0 = mercY(top), m1 = mercY(bottom);
  const hex = (c: string) => [1, 3, 5].map((k) => parseInt(c.slice(k, k + 2), 16));
  const lut = RAMP.map(hex);
  for (let y = 0; y < H; y++) {
    const m = m0 + ((y + 0.5) / H) * (m1 - m0);
    const lat = (Math.atan(Math.sinh(m)) * 180) / Math.PI;
    const row = Math.min(g.height - 1, Math.max(0, Math.floor((top - lat) / g.dx)));
    for (let x = 0; x < g.width; x++) {
      const i = row * g.width + x, o = (y * g.width + x) * 4;
      const v = values[i];
      if (!Number.isFinite(v) || (mask && !mask[i])) { img.data[o + 3] = 0; continue; }
      let k = 0;
      while (k < br.length && v > br[k]) k++;
      const [r, gg, b] = lut[RAMP.indexOf(classColor(k, br))];
      img.data[o] = r; img.data[o + 1] = gg; img.data[o + 2] = b; img.data[o + 3] = 200;
    }
  }
  ctx.putImageData(img, 0, 0);
  const bounds: L.LatLngBoundsExpression = [[bottom, g.x0], [top, g.x0 + g.width * g.dx]];
  dataLayer = L.imageOverlay(canvas.toDataURL(), bounds, { opacity: 0.85 }).addTo(map);
  addLegend(title, br, note);
  shown = { title, br, note, raster: { canvas, bounds: L.latLngBounds(bounds) } };
}
