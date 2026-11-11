"""GCHD subnational hazard-exposure pipeline.

Thin, parameterized drivers around the frozen science in ``lib/``. The notebooks
00-07 are the exploratory originals; this package is their productionized form.

Foundation modules (Stage 1):
    settings   - the single config object (env-driven), replacing every hardcode
    io_paths   - canonical aux/base/export/upscale path builder
    hazards    - sole loader of config/hazard_info.json
    na_rules   - sole loader of config/countries_NA_summary.csv

Nothing here imports ``ee`` at module load time, so these modules are safe to
import and unit-test without Earth Engine auth.
"""

__all__ = ["settings", "io_paths", "hazards", "na_rules"]
