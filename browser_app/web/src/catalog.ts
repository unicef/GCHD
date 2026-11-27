// Reads the GCHD STAC catalog (static, Portolan profile) and builds the registry the app and the LLM use.
import { STAC_BASE, STAC_ROOT } from "./config";

export interface ExposureRule {
  hazard_code: string;
  unicef_code?: string;
  valid: string;       // e.g. "> -1000"
  op: string;          // ">", ">=", "<", "<="
  threshold: number;
  default?: boolean;
}

export interface Collection {
  id: string;
  title: string;
  description: string;
  url: string;              // collection.json URL
  group: string;            // hazards/<theme>, population, boundaries, exposure, multi_hazard, reference
  raw: any;
  dataHref?: string;
  dataType?: string;
  nodata?: number;
  units?: string;
  resolution?: string;
  rules: ExposureRule[];
}

export interface Column { name: string; type: string; description?: string }

export interface Catalog {
  collections: Map<string, Collection>;
  hazards: Map<string, { rule: ExposureRule; collection: Collection }>;  // by hazard_code
  tableColumns: Column[];                                                // exposure tables
  tableHref: Record<0 | 1 | 2, string>;
  tableSha: Record<0 | 1 | 2, string>;     // sha256 hex of each table (STAC file:checksum), "" if absent
  boundaryHref: Record<0 | 1 | 2, { parquet: string; pmtiles: string }>;
}

async function getJson(url: string): Promise<any> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

function parseNodata(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  if (v === "nan") return NaN;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export async function loadCatalog(onProgress?: (msg: string) => void): Promise<Catalog> {
  const collections = new Map<string, Collection>();
  const walk = async (url: string): Promise<void> => {
    const d = await getJson(url);
    if (d.type === "Collection") {
      const data = d.assets?.data;
      const band = data?.bands?.[0] ?? data?.["raster:bands"]?.[0];
      const group = url.slice(STAC_BASE.length).split("/").slice(0, -2).join("/");
      collections.set(d.id, {
        id: d.id, title: d.title ?? d.id, description: d.description ?? "", url, group, raw: d,
        dataHref: data?.href, dataType: data?.type, nodata: parseNodata(band?.nodata),
        units: d["GCHD:units"], resolution: d["GCHD:nominal_resolution"],
        rules: d["GCHD:exposure_rules"] ?? [],
      });
      return;
    }
    const kids = (d.links ?? []).filter((l: any) => l.rel === "child");
    await Promise.all(kids.map((l: any) => walk(new URL(l.href, url).href)));
  };
  onProgress?.("Reading the GCHD STAC catalog…");
  await walk(STAC_ROOT);

  const hazards = new Map<string, { rule: ExposureRule; collection: Collection }>();
  for (const c of collections.values())
    for (const rule of c.rules) hazards.set(rule.hazard_code, { rule, collection: c });

  const need = (id: string) => {
    const c = collections.get(id);
    if (!c) throw new Error(`collection ${id} missing from the catalog`);
    return c;
  };
  const sha = (id: string) => {
    const mh = String(need(id).raw.assets?.data?.["file:checksum"] ?? "");
    return mh.startsWith("1220") ? mh.slice(4) : "";    // multihash prefix for sha2-256
  };
  const tiles = (id: string) => need(id).raw.assets?.tiles?.href as string;
  return {
    collections, hazards,
    tableColumns: need("adm2_hazard").raw["table:columns"] ?? [],
    tableHref: { 0: need("adm0_hazard").dataHref!, 1: need("adm1_hazard").dataHref!, 2: need("adm2_hazard").dataHref! },
    tableSha: { 0: sha("adm0_hazard"), 1: sha("adm1_hazard"), 2: sha("adm2_hazard") },
    boundaryHref: {
      0: { parquet: need("adm0").dataHref!, pmtiles: tiles("adm0") },
      1: { parquet: need("adm1").dataHref!, pmtiles: tiles("adm1") },
      2: { parquet: need("adm2").dataHref!, pmtiles: tiles("adm2") },
    },
  };
}

const agentsCache = new Map<string, Promise<string>>();

/** AGENTS.md of a collection (generated guidance: access, units, caveats, joins, plus hand-written notes). */
export function agentsMd(c: Collection): Promise<string> {
  let p = agentsCache.get(c.id);
  if (!p) {
    p = fetch(new URL("AGENTS.md", c.url).href).then((r) => (r.ok ? r.text() : "")).catch(() => "");
    agentsCache.set(c.id, p);
  }
  return p;
}

/** Named "## " sections of a markdown document (heading line excluded), in the order asked for. */
export function mdSections(md: string, names: string[]): string {
  const parts = md.split(/^## /m).slice(1);
  return names.flatMap((n) => {
    const s = parts.find((p) => p.split("\n", 1)[0].trim().toLowerCase() === n.toLowerCase());
    return s ? [`### ${n}\n${s.slice(s.indexOf("\n") + 1).trim()}`] : [];
  }).join("\n\n");
}

// sections of AGENTS.md the assistant needs; "Additional notes" holds the hand-written notes from
// STAC_catalog/config/agents/<collection id>.md
export const NOTE_SECTIONS = ["Data quality & usage notes", "Additional notes"];

/** Usage notes of a collection's AGENTS.md, without code-access hints that do not apply in the app. */
export async function usageNotes(c: Collection, sections = NOTE_SECTIONS): Promise<string> {
  return mdSections(await agentsMd(c), sections)
    .split("\n").filter((l) => !/masked=True|rasterio|read_parquet|vsicurl/i.test(l)).join("\n").trim();
}

export interface Source { href: string; bbox: number[]; size: number }

/** Per-country WorldPop item (data href, bbox, file size); item ids are <collection>_<iso3 lower-case>. */
export async function worldpopSource(cat: Catalog, collectionId: string, iso3: string): Promise<Source | null> {
  const c = cat.collections.get(collectionId);
  if (!c) return null;
  const id = `${collectionId}_${iso3.toLowerCase()}`;
  const r = await fetch(new URL(`${id}/${id}.json`, c.url).href);
  if (!r.ok) return null;
  const item = await r.json();
  const a = item.assets?.data;
  return a ? { href: a.href, bbox: item.bbox, size: a["file:size"] ?? 0 } : null;
}

const tileCache = new Map<string, Promise<Source[] | null>>();

/** Tiled layers (river flood): item bboxes, hrefs and sizes from the collection's items.geojson. */
export function tileIndex(c: Collection): Promise<Source[] | null> {
  let p = tileCache.get(c.id);
  if (!p) {
    const a = c.raw.assets?.items_geojson;
    p = a ? getJson(new URL(a.href, c.url).href).then((g) =>
      g.features.map((f: any) => ({ bbox: f.bbox, href: f.assets.data.href, size: f.assets.data["file:size"] ?? 0 }))) : Promise.resolve(null);
    tileCache.set(c.id, p);
  }
  return p;
}
