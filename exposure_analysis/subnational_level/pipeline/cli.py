"""Command-line entry point for the pipeline.

Built on ``click`` (already in the environment) rather than ``typer`` to avoid a
new dependency mid-refactor; the UX is the same and a typer swap later is trivial.
Every command builds one :class:`Settings` from env + flag overrides, then calls
a step's ``run``. No Earth Engine work happens at import or ``--help`` time.

Examples
--------
    gchd s00 --countries EGY_V1 --storage-root output
    gchd s00 --hazards river_flood_100yr,fire_intensity
    GCHD_STORAGE_ROOT=output gchd s00
    gchd s00-assemble --csv-dir output/aux/drive_csvs

Console script (Stage 6): ``gchd = pipeline.cli:main``.
"""

from __future__ import annotations

import click

from .settings import Settings


def _csv_list(ctx, param, value):
    """Click callback: parse a comma-separated option into a list, or None."""
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


# Options shared by step commands. Applied via the @common_options decorator so
# every command accepts the same run-scoping flags that override Settings/env.
def common_options(f):
    f = click.option("--storage-root", default=None,
                     help="Output root (local path or fsspec URL). Overrides GCHD_STORAGE_ROOT.")(f)
    f = click.option("--prod-date", default=None,
                     help="ISO date stamped on outputs (default: today).")(f)
    f = click.option("--countries", callback=_csv_list, default=None,
                     help="Comma-separated ISO3 filter, e.g. EGY,DEU (default: all).")(f)
    f = click.option("--hazards", callback=_csv_list, default=None,
                     help="Comma-separated hazard-code filter (default: all).")(f)
    f = click.option("--allow-interactive", is_flag=True, default=False,
                     help="Local dev only: permit ee.Authenticate() browser flow if needed.")(f)
    return f


def _settings_from(storage_root, prod_date, countries, hazards) -> Settings:
    """Build Settings from env, then apply non-None CLI overrides (CLI wins)."""
    overrides = {}
    if storage_root is not None:
        overrides["storage_root"] = storage_root
    if prod_date is not None:
        overrides["prod_date"] = prod_date
    if countries is not None:
        overrides["process_countries"] = countries
    if hazards is not None:
        overrides["process_hazards"] = hazards
    return Settings.from_env(**overrides)


@click.group()
@click.version_option(package_name="gchd-pipeline", message="%(version)s", prog_name="gchd")
def main():
    """GCHD subnational hazard-exposure pipeline."""


@main.command("s00")
@common_options
def s00_cmd(storage_root, prod_date, countries, hazards, allow_interactive):
    """Submit admin2 x hazard pixel-count export tasks (weight table)."""
    from .steps import s00
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s00.run(settings, allow_interactive=allow_interactive)


@main.command("s01")
@click.option("--no-fill", is_flag=True, default=False,
              help="Skip Phase 2 gap-fill of missing admin2 units (tiled path).")
@common_options
def s01_cmd(no_fill, storage_root, prod_date, countries, hazards, allow_interactive):
    """Extract admin2 hazard-exposure stats per (hazard, country); fill gaps."""
    from .steps import s01
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s01.run(settings, allow_interactive=allow_interactive,
            fill_missing=(False if no_fill else None))


@main.command("s01b")
@click.option("--cache-dir", default=None, help="Boundaries and population cache [<storage_root>/cache].")
@common_options
def s01b_cmd(cache_dir, storage_root, prod_date, countries, hazards, allow_interactive):
    """Prototype: same partials as s01, from the COGs on Azure with exactextract (no Earth Engine compute)."""
    from .steps import s01b
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s01b.run(settings, cache_dir=cache_dir)


@main.command("s01c")
@click.option("--workers", type=int, default=8, show_default=True,
              help="Countries reduced in parallel.")
@click.option("--mode", type=click.Choice(["interactive", "batch"]), default="interactive", show_default=True,
              help="interactive: getInfo requests (5-minute cap each); batch: one Drive export per country.")
@click.option("--drive-folder", default=None, help="Drive folder for batch exports [gchd_s01c_<prod_date>].")
@click.option("--collect-only", is_flag=True, default=False,
              help="Batch mode: do not submit, only collect finished exports.")
@click.option("--chunk-batch", type=int, default=25, show_default=True,
              help="Interactive mode: chunks per request (halved automatically on timeout).")
@click.option("--hazard-batch", type=int, default=22, show_default=True,
              help="Hazards per request; lower it if requests run out of memory.")
@click.option("--tile-scale", type=int, default=4, show_default=True)
@click.option("--overwrite", is_flag=True, default=False,
              help="Recompute countries whose partials already exist.")
@common_options
def s01c_cmd(workers, mode, drive_folder, collect_only, chunk_batch, hazard_batch, tile_scale, overwrite,
             storage_root, prod_date, countries, hazards, allow_interactive):
    """Same partials as s01, from one multi-band reduction per country over 500 km chunks."""
    from .steps import s01c
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s01c.run(settings, allow_interactive=allow_interactive, workers=workers,
             chunk_batch=chunk_batch, hazard_batch=hazard_batch, tile_scale=tile_scale,
             overwrite=overwrite, mode=mode, drive_folder=drive_folder, collect_only=collect_only)


@main.command("s02")
@common_options
def s02_cmd(storage_root, prod_date, countries, hazards, allow_interactive):
    """Compute indices/classes + status rules -> base/global CSVs (pure pandas)."""
    from .steps import s02
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s02.run(settings)


@main.command("s03")
@click.option("--no-excel", is_flag=True, default=False, help="Skip Excel export.")
@click.option("--no-geopackage", is_flag=True, default=False, help="Skip GeoPackage export.")
@common_options
def s03_cmd(no_excel, no_geopackage, storage_root, prod_date, countries, hazards, allow_interactive):
    """Export Excel + GeoPackage deliverables (GeoPackage needs EE geometry)."""
    from .steps import s03
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s03.run(settings, allow_interactive=allow_interactive,
            excel=not no_excel, geopackage=not no_geopackage)


@main.command("s04")
@click.option("--push-sharepoint", is_flag=True, default=False,
              help="Also push to SharePoint (deferred: needs AAD app registration).")
@common_options
def s04_cmd(push_sharepoint, storage_root, prod_date, countries, hazards, allow_interactive):
    """Export per-country hazard/exposure GeoTIFFs to Drive (SharePoint deferred)."""
    from .steps import s04
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s04.run(settings, allow_interactive=allow_interactive, push_sharepoint=push_sharepoint)


@main.command("s05")
@common_options
def s05_cmd(storage_root, prod_date, countries, hazards, allow_interactive):
    """Export SDMX-CSV (hazard/exposure/population) from base/global (pure pandas)."""
    from .steps import s05
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s05.run(settings)


@main.command("s00-assemble")
@click.option("--csv-dir", required=True,
              help="Directory holding the downloaded Drive CSVs to assemble.")
@common_options
def s00_assemble_cmd(csv_dir, storage_root, prod_date, countries, hazards, allow_interactive):
    """Assemble aux/hazs_count_{date}.csv from downloaded s00 export CSVs."""
    from .steps import s00
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    s00.assemble_from_local_csvs(settings, csv_dir)


@main.command("config")
@common_options
def config_cmd(storage_root, prod_date, countries, hazards, allow_interactive):
    """Print the resolved Settings for the given env + flags (no EE/network)."""
    settings = _settings_from(storage_root, prod_date, countries, hazards)
    for k, v in settings.model_dump().items():
        click.echo(f"{k:28s} = {v}")
    click.echo(f"{'dataflow (derived)':28s} = {settings.dataflow}")


if __name__ == "__main__":
    main()
