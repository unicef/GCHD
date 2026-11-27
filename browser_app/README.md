# GCHD data assistant

A static web app at **https://unicef.github.io/GCHD/browser_app/app/**. Users choose a country and ask questions in plain language, such as "How many children are exposed to river floods in each district?". An LLM, called with the user's own API key, turns the question into a plan. The plan runs in the user's browser on data from the [GCHD STAC catalog](https://unicef.github.io/GCHD/STAC_catalog/stac/catalog.json). There is no server.

## How a request goes

1. **Choose a country.** The app loads that country's rows of the exposure tables into DuckDB-WASM: ADM0 is downloaded whole at start-up (0.3 MB, it also gives the country list), and ADM1/ADM2 come from per-country copies (Kenya: 0.4 MB; the largest country 4.7 MB). Boundaries come from the ADM0/1/2 PMTiles.
2. **Clarify.** The model asks short questions until the request is clear: the hazard, admin level, under-18 or all ages, sex, threshold and outputs.
3. **Explain.** The model calls `propose_plan`. A plan card lists the steps, what can and cannot be done, and the data route.
4. **Confirm.** The user clicks **Confirm**, **Edit** or **Cancel**. The tools that touch data refuse to run until the plan is confirmed, and they only accept that plan's id.
5. **Show.** The app shows the result table and a map (a choropleth, or a hazard pixel map), and offers a CSV download.
6. **Export the map.** The **PNG** button on the map redraws the current view at 4× its on-screen size (basemap tiles from a closer zoom level, polygons as vectors, hazard pixels unsmoothed; at most 6000 px on the long side) and saves it with its title, legend, a metric scale bar, OpenStreetMap attribution and a GCHD source line. The **GeoJSON** button saves the mapped units and their values, for use in a GIS (choropleths only). The GeoJSON polygons come from the boundary vector tiles (the tile pieces are dissolved into one shape per unit on export), so they are simplified; for exact boundaries, join the CSV to `adm*.parquet` on `ucode`.

## How the catalog's AGENTS.md reaches the model

- **System prompt:** it includes the "Data quality & usage notes", "Related collections" and "Additional notes" sections of `exposure/adm2_hazard/AGENTS.md`.
- **Plan check:** when the model proposes a plan, the app returns the "Data quality & usage notes" and "Additional notes" of each hazard in it with the tool result. The model sees those caveats before the user confirms.
- **On request:** the model can read any collection's full AGENTS.md with `describe_collection`.

"Additional notes" holds the hand-written notes from `STAC_catalog/config/agents/<collection id>.md`. A note added there and published with the catalog reaches the assistant without any change to the app.

## Data routes: summary tables first

| Route | Used when | Source | Numbers |
|---|---|---|---|
| **Summary** (default) | The tables can answer: any hazard in them, ADM0/1/2, default thresholds | `adm0/1/2_hazard` exposure tables (DuckDB SQL; one SELECT, checked by `sqlguard.ts`) | Official GCHD figures |
| **Raster** | Only for custom thresholds, combined hazards (any/all), hazards missing from the tables, or a pixel map | Hazard COGs and WorldPop 2025, read with geotiff.js | Computed in the browser |

The route is enforced in code as well as in the prompt. `route.ts` works out which route the request needs, and the app rejects a plan whose `data_route` does not match. It also rejects `zonal_stats` in a summary plan.

The raster route has two modes:
- **Exact mode**, when the country's full-resolution rasters total at most about 400 MB (most countries). It uses the WorldPop 100 m grid, processed tile by tile, with hazards sampled at full resolution, as in the GCHD pipeline.
  - Checked against the official ADM1 numbers for river flood: Bangladesh +0.8 % and Kenya +2.0 % in total, with per-unit differences at most 2.3 % of a unit's children.
- **Coarse mode**, when the area is too large for exact mode. It uses a coarser grid sampled from the COG overviews. It is allowed only for hazards whose native pixels are at least as coarse as that grid, so no averaged overview gets thresholded.
  - The COG overviews average the valid pixels only. Where "no hazard" is stored as nodata, as in flood depth, a coarse cell with a few flooded pixels counts as flooded over its whole area. Around São Paulo, 7.5 % of the 100 m cells are flooded, but 37 % of the ~1.6 km overview cells are, so a whole-Brazil run overstated exposure about tenfold.
  - A raster plan that would need this is rejected before the user confirms it, with the reason. The assistant then offers to compute one or a few ADM1 units instead (`units` in the plan and in `zonal_stats`).
- **Area:** exact or coarse mode is decided from the area actually computed (the bbox of the units asked for), not the whole country. São Paulo state (645 districts) runs in exact mode in about 50 s. Its river-flood numbers at the default threshold match the official ones with a median per-district difference of 0.08 % of the district's children (São Paulo city 71,593 against 69,263).

In both modes, exposed people = (exposed share computed in the browser) × (the unit's official population from the summary tables).

For heatwave, extreme heat, drought (ASI, SPI, SPEI) and malaria, the official tables were computed in Google Earth Engine on a different version of the layer than the catalog COGs. Raster-route numbers for these hazards can therefore differ from the official ones even at default thresholds: for heatwave frequency, Bangladesh came out 21 % lower. The app notes this whenever it applies.

## Privacy and hosting

- **API key:** the user's key is kept in the tab (`sessionStorage`, or `localStorage` if they tick "remember"). It is sent only to the chosen provider: `api.anthropic.com`, `api.openai.com` or `generativelanguage.googleapis.com`.
- **Hosts contacted:**
  - GitHub Pages: the app and the STAC catalog;
  - Azure blob `unidatadapmclimatechange` (`public`): the data;
  - jsDelivr: the DuckDB-WASM bundles;
  - OpenStreetMap tiles: the basemap;
  - the chosen LLM provider.
- **Hosting:** GitHub Pages only (the legacy build from `main`). Pages cannot send COOP/COEP headers, so DuckDB runs single-threaded.
- **Azure CORS:** the container allows GET and Range requests from any origin, but does not expose `Content-Range`. geotiff.js and PMTiles do not need it. DuckDB's HTTP reader does, so the app fetches files whole and hands them to DuckDB as in-memory files. For ADM1/ADM2 it fetches the per-country copies written by `STAC_catalog/pipeline/11_split_exposure.py` (`public/gchd_cog/exposure_by_country/<table>/<sha>/<ISO3>.parquet`). The `<sha>` folder comes from the table's `file:checksum` in the STAC catalog, so the copies always match the catalog's table version. If a copy is missing (for example after the tables are updated but before step 11 is run again), the app downloads the whole table instead (about 54 MB in all, once per session).
- **Map:** Leaflet with the canvas renderer, so no WebGL is needed.

## Models

- **Anthropic:** default `claude-opus-5-5`, through the official `@anthropic-ai/sdk` (`dangerouslyAllowBrowser`). It uses adaptive thinking, effort `medium`, the server-side refusal fallback, and a cached system prompt.
- **OpenAI** (Chat Completions with function tools): default `gpt-5`.
- **Gemini** (`generateContent` with function declarations): default `gemini-2.5-flash`. Gemini 2.5 sometimes ends a turn with no text and no tool call (only "thought" parts), often right after a confirmation; the app retries with a nudge, and after a confirmation the last retry requires a tool call (`functionCallingConfig` `ANY`).

The model field is editable, and each provider adapter keeps its own message history.

## Develop

```bash
cd browser_app
npm install
npm run dev          # http://localhost:5173 (sources in web/)
npm test             # unit tests: SQL guard, routing, rasterization, clipping, CSV
npm run build        # type-check + build into app/ (commit app/ so Pages serves it)
```

The end-to-end checks drive headless Chrome with WebGL disabled. They use real data and a mocked LLM, so they need no key:

```bash
npx vite preview --port 4173 &
node tests/e2e.mjs KEN                         # summary flow + raster flow (custom threshold, pixel map); lists the Parquet files fetched
NO_SPLIT=1 node tests/e2e.mjs BEN              # same, with the per-country tables blocked (whole-table fallback)
node tests/parity.mjs BGD river_flood_100yr    # raster route at default threshold vs the official ADM1 table
node tests/parity.mjs BRA river_flood_100yr 0.1 2 "São Paulo"   # custom threshold, districts of one state
node tests/parity.mjs BRA river_flood_100yr 0.1 2               # whole Brazil: the plan is rejected
```

## Files

| File | Role |
|---|---|
| `web/src/main.ts` | UI: settings, country, chat, plan cards, conversation loop |
| `web/src/tools.ts` | Tool schemas; dispatcher with the plan / confirmation gate |
| `web/src/route.ts` | Summary-first routing rules |
| `web/src/prompt.ts` | System prompt with the catalog digest (hazards, rules, table columns) |
| `web/src/llm/` | Provider adapters (Anthropic SDK, OpenAI, Gemini) |
| `web/src/catalog.ts` | Walks the STAC catalog: collections, exposure rules, WorldPop and tile items |
| `web/src/duck.ts`, `sqlguard.ts` | DuckDB-WASM tables and the SQL guard |
| `web/src/boundaries.ts`, `geo.ts` | PMTiles → country polygons (clipped per tile, outlines without tile seams) |
| `web/src/raster/` | COG reading, analysis grid, rasterization, zonal engine (exact and coarse modes) |
| `web/src/map.ts` | Leaflet choropleths and raster overlays |
