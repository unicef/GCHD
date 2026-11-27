// Fixed endpoints. Everything the app reads is public: the GCHD STAC catalog on GitHub Pages and the
// data files it points at on Azure blob storage (public container, CORS GET + Range allowed).

export const STAC_ROOT = "https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json";
export const STAC_BASE = STAC_ROOT.replace(/catalog\.json$/, "");

// Admin levels the summary tables and boundaries exist for
export const LEVELS = [0, 1, 2] as const;
export type Level = (typeof LEVELS)[number];

// Raster route: cap on analysis-grid cells for one country (memory and download guard)
export const MAX_GRID_CELLS = 4_000_000;
// WorldPop native resolution (3 arc-seconds)
export const WORLDPOP_RES = 1 / 1200;

// Boundaries: most PMTiles tiles fetched per country and level
export const MAX_BOUNDARY_TILES = 160;

// Rows returned to the LLM from a query (the full result stays in the app for CSV / map)
export const LLM_ROW_LIMIT = 40;

// Per-country copies of the ADM1/ADM2 exposure tables (STAC_catalog/pipeline/11_split_exposure.py):
// <root>/<table>/<first 16 hex of the table's sha256>/<ISO3>.parquet. A new table version gets a new
// folder; when a file is missing the app falls back to downloading the whole table.
export const BY_COUNTRY_ROOT = "https://unidatadapmclimatechange.blob.core.windows.net/public/gchd_cog/exposure_by_country";

export function byCountryHref(table: string, sha: string, iso3: string): string | null {
  return sha ? `${BY_COUNTRY_ROOT}/${table}/${sha.slice(0, 16)}/${iso3}.parquet` : null;
}
