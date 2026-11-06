// STAC Browser (radiantearth/stac-browser v5.1.0) config for the GCHD catalog.
// Merged over the browser's own config.js. catalogUrl / pathPrefix are set per
// build through SB_catalogUrl / SB_pathPrefix (see scripts/06_publish.py).
export default {
  catalogTitle: "GCHD Data Catalog",
  allowExternalAccess: false,
  historyMode: "hash",          // GitHub Pages cannot rewrite routes
  supportedLocales: ["en", "fr", "es", "ar"],
  displayGeoTiffByDefault: true,
  // Maps show the coloured "overview" PNG overlay (scripts/04_thumbnails.py) by default:
  // ol-stac draws single-band COGs in plain greyscale (e.g. 0 in coastal flood as black).
  // The COG itself is still one click away via "Show on map" on the data asset.
  displayOverview: false,
  showThumbnailsAsAssets: false,
  defaultCollectionSort: "title",
  footerLinks: [
    { label: "GCHD on GitHub", url: "https://github.com/unicef/GCHD" },
    { label: "UNICEF", url: "https://www.unicef.org/" }
  ]
};
