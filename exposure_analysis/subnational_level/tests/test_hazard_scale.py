"""Guards on the reduction SCALE used for hazard statistics and pixel counts.

The pure checks (no Earth Engine, no network) run everywhere and are the ones
that would have caught the 2026-09 defect at config level. The live checks hit
Earth Engine and are skipped unless GCHD_TEST_GEE=1 is set.

    ..\\..\\.venv\\Scripts\\python.exe -m pytest tests -q
    set GCHD_TEST_GEE=1 && ..\\..\\.venv\\Scripts\\python.exe tests/test_hazard_scale.py

BACKGROUND
----------
`ee.ImageCollection.mosaic()` returns an image with no fixed projection, so
`.projection().nominalScale()` reports the WGS84 default of 111319.49 m (~1
degree) rather than the raster's true resolution. Notebook 00 used that value
as its reduction scale, which sampled ~1 point per 111 km, collapsed hazs_count
to 0-3 per admin2, and blanked 44 admin1 hazs_mean values for Egypt.

Notebook 01 was never affected: it reduces at GEEUtils.analysis_scale, taken
from the WorldPop population raster (~92.77 m). The fix aligns notebook 00 to
that same scale, so the weight counts the same pixel set the mean was
computed over.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "hazard_info.json"
NOTEBOOK_00 = ROOT / "notebooks" / "pipeline" / "00_adm2_hazard_pixel_counts.ipynb"
STEP_S00 = ROOT / "pipeline" / "steps" / "s00.py"

# The WGS84 1-degree default that mosaic() reports when it has no projection.
DEGREE_SCALE_M = 111319.49
GEE_LIVE = os.environ.get("GCHD_TEST_GEE") == "1"


def _hazards():
    with open(CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


def _is_mosaic(h):
    """Truthiness of the mosaic flag, tolerating the string form.

    hazard_info.json stores these as the STRINGS "0"/"1", and "0" is truthy in
    Python — a plain `if h["mosaic"]` treats every hazard as a mosaic. Always
    compare against the value, never rely on truthiness.
    """
    return str(h.get("mosaic", "0")).strip() in ("1", "true", "True")


def _notebook_code():
    with open(NOTEBOOK_00, encoding="utf-8") as fh:
        nb = json.load(fh)
    return "\n".join("".join(c["source"]) for c in nb["cells"]
                     if c["cell_type"] == "code")


# -- pure: config ---------------------------------------------------------

def test_mosaic_hazards_are_declared():
    """Pin which hazards are mosaics. A new one added here without revisiting
    the scale logic is exactly how this defect would come back."""
    mosaics = {h["code"] for h in _hazards() if _is_mosaic(h)}
    assert mosaics == {"river_flood_100yr", "coastal_flood_100yr",
                       "tropical_storm_100yr"}, (
        f"mosaic hazard set changed: {sorted(mosaics)}. Confirm the pixel-count "
        "reduction still uses the population/analysis scale for these.")


def test_every_hazard_declares_mosaic_flag():
    for h in _hazards():
        assert "mosaic" in h, f"{h['code']} has no mosaic flag"


def test_mosaic_flag_is_never_read_by_truthiness():
    """The flags are the STRINGS "0"/"1", and "0" is truthy in Python.

    Anything doing `if hazard_dict["mosaic"]` on the raw JSON silently treats
    all 22 hazards as mosaics. Pinned so the storage type cannot change to
    something truthiness-unsafe without a failing test.
    """
    vals = {str(h.get("mosaic")) for h in _hazards()}
    assert vals <= {"0", "1"}, f"unexpected mosaic flag values: {vals}"
    assert sum(1 for h in _hazards() if _is_mosaic(h)) == 3
    # The trap itself: raw truthiness would count all of them.
    assert sum(1 for h in _hazards() if h.get("mosaic")) == len(_hazards())


# -- pure: notebook 00 source ---------------------------------------------

def test_notebook00_does_not_scale_from_the_hazard_image():
    """REGRESSION: the defect was literally

        scale = scale_override if scale_override else raw.projection().nominalScale()

    `raw` is the (possibly mosaicked) hazard image, so this is the 111 km trap.
    """
    code = _notebook_code()
    assert "raw.projection().nominalScale()" not in code, (
        "notebook 00 is taking its reduction scale from the hazard image. For "
        "mosaicked hazards that is 111319.49 m, not the native resolution.")


def test_notebook00_uses_the_analysis_scale():
    """The counts must be reduced at the same scale notebook 01 uses."""
    code = _notebook_code()
    assert "get_analysis_scale" in code, (
        "notebook 00 should resolve the population/analysis scale per country")
    assert "analysis_scale" in code


def test_s00_step_does_not_scale_from_the_hazard_image():
    """The CLI step had kept the defect after the notebook was fixed."""
    code = STEP_S00.read_text(encoding="utf-8")
    assert "raw.projection().nominalScale()" not in code
    assert "_analysis_scale(utils, ucode)" in code
    body = code.split("def _native_scale", 1)[1].split("\ndef ", 1)[0]
    assert "ImageCollection" in body and ".first()" in body

def test_notebook00_native_scale_helper_avoids_the_mosaic():
    """The no-population fallback must read the scale from a MEMBER image."""
    code = _notebook_code()
    if "def get_native_scale" in code:
        body = code.split("def get_native_scale", 1)[1].split("\ndef ", 1)[0]
        assert "ImageCollection" in body and ".first()" in body, (
            "get_native_scale must take the scale from a collection member, "
            "not from the mosaic")


# -- live: Earth Engine ---------------------------------------------------

def _skip_live():
    msg = "set GCHD_TEST_GEE=1 to run live Earth Engine checks"
    try:
        import pytest
        pytest.skip(msg, allow_module_level=False)
    except ImportError:
        print(f"  SKIP  (live) {msg}")
    return True


def test_live_mosaic_reports_the_degree_default():
    """Documents the upstream GEE behaviour this whole guard exists for."""
    if not GEE_LIVE:
        return _skip_live()
    import ee
    ee.Initialize(project="unicef-ccri")
    prefix = "projects/unicef-ccri/assets"
    for h in _hazards():
        if not _is_mosaic(h):
            continue
        asset = h["asset"] if str(h["asset"]).startswith("projects/") \
            else f"{prefix}/hazards/{h['asset']}"
        ic = ee.ImageCollection(asset)
        mosaic_scale = ic.mosaic().projection().nominalScale().getInfo()
        member_scale = ee.Image(ic.first()).projection().nominalScale().getInfo()
        assert abs(mosaic_scale - DEGREE_SCALE_M) < 1.0, (
            f"{h['code']}: mosaic scale {mosaic_scale} no longer the 1-degree "
            "default — GEE behaviour may have changed, revisit the fix")
        assert member_scale < mosaic_scale, (
            f"{h['code']}: member scale {member_scale} should be finer than "
            f"the mosaic default {mosaic_scale}")


def test_live_analysis_scale_is_worldpop_resolution():
    """analysis_scale must come from the population raster (~92.77 m)."""
    if not GEE_LIVE:
        return _skip_live()
    import ee
    sys.path.insert(0, str(ROOT / "lib"))
    from GEE_functions import GEEUtils
    ee.Initialize(project="unicef-ccri")
    utils = GEEUtils(ee)
    fc = utils.get_admin2_boundaries("EGY_V1", admin_level="adm0_ucode")
    utils.set_population_dicts("EGY_V1", fc)
    utils.get_population_classes()
    scale = utils.analysis_scale.getInfo()
    assert 90 < scale < 100, f"analysis scale {scale} is not ~92.77 m WorldPop"


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed"
          + ("" if GEE_LIVE else "  (live GEE checks skipped)"))
    sys.exit(1 if failed else 0)
