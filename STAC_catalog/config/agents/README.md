# Hand-written AGENTS.md notes

Every catalog and collection in `stac/` gets an `AGENTS.md`, generated from its metadata by `gchd_stac/docs.py` on each build of `pipeline/08_build_stac.py`. Do not edit those files: the next build overwrites them.

To add your own guidance for one collection or catalog, create a file here named after its id, for example:

- `adm2_hazard.md`
- `river_flood_100yr_jrc_2024.md`
- `GCHD.md` (the root catalog)

The build appends that file to the generated AGENTS.md under `## Additional notes`. Useful things to add:

- known quirks;
- recommended thresholds;
- worked analysis examples;
- caveats that are not in the xlsx.

This README is not appended anywhere, since no collection has the id `README`.
