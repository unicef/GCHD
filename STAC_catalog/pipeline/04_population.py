"""Step 4: WorldPop R2025A population 2025 - VRT mosaics and thumbnails (see gchd_stac/population.py).

  --vrt      build mosaic_ovr.vrt per group in work/<dataset>/; with --upload, upload each to
             public/gchd_cog/<dataset>/<group>/ unless that blob already exists (never overwrites)
  --thumbs   render the global and per-country thumbnails and map overlays into work/thumbnails/

Step 8 (08_build_stac.py) adds the collections to the catalog.

Usage:  python pipeline/04_population.py [--datasets worldpop_u18_2025 worldpop_2025] [--vrt [--upload]]
                                         [--thumbs [--force]] [--workers 8]
"""
import argparse

import _path  # noqa: F401  (STAC_catalog/ on sys.path)
from gchd_stac import population


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", default=list(population.DATASETS), choices=list(population.DATASETS))
    ap.add_argument("--vrt", action="store_true", help="build the global mosaic_ovr.vrt per group")
    ap.add_argument("--upload", action="store_true", help="with --vrt: upload VRTs that are not yet published")
    ap.add_argument("--thumbs", action="store_true", help="render thumbnails and map overlays")
    ap.add_argument("--force", action="store_true", help="with --thumbs: re-render existing thumbnails")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    names = population.country_names()
    for ds in args.datasets:
        sources = population.list_sources(ds)
        missing = {iso for iso, _ in sources["total"]} - set(names)
        if missing:
            print(f"WARN   {ds}: no country name for {sorted(missing)}")
        if args.vrt:
            population.build_vrts(ds, sources, args.upload)
        if args.thumbs:
            population.render_thumbs(ds, sources, args.force, args.workers)


if __name__ == "__main__":
    main()
