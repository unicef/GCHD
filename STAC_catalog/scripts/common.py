"""Shared paths, settings and Azure helpers for the STAC_catalog scripts."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

STAC_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = STAC_DIR.parent
XLSX = REPO_DIR / "docs" / "Global Hazard Data catalog.xlsx"
LAYERS_YAML = STAC_DIR / "config" / "layers.yaml"
REPORTS_DIR = STAC_DIR / "reports"

load_dotenv(STAC_DIR / ".env")

ACCOUNT = "unidatadapmclimatechange"
ACCOUNT_URL = f"https://{ACCOUNT}.blob.core.windows.net"
CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
RAW_CONTAINER = os.getenv("RAW_CONTAINER", "climate")
PUBLIC_CONTAINER = os.getenv("PUBLIC_CONTAINER", "public")
COG_PREFIX = os.getenv("COG_PREFIX", "gchd_cog")
# Where STAC_catalog/ is served (GitHub Pages of unicef/GCHD)
PAGES_URL = "https://unicef.github.io/GCHD/STAC_catalog/"

# Layer whose source is the raw tile folder instead of the public "Azure link"
TILED_LAYER = "river_flood_100yr_jrc_2024"


def has_credentials() -> bool:
    return bool(CONN_STR)


def container_client(name: str):
    from azure.storage.blob import ContainerClient
    if not CONN_STR:
        raise SystemExit("AZURE_STORAGE_CONNECTION_STRING is not set (see STAC_catalog/.env.example)")
    return ContainerClient.from_connection_string(CONN_STR, name)


def gdal_path(source: str) -> str:
    """GDAL path for a source: public https URL -> /vsicurl/, 'container/blob' -> /vsiaz/."""
    if source.startswith("http"):
        return "/vsicurl/" + source
    return "/vsiaz/" + source


def gdal_env() -> dict:
    """GDAL config for remote reads (passed to rasterio.Env)."""
    env = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff,.vrt",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "2",
    }
    if CONN_STR:
        env["AZURE_STORAGE_CONNECTION_STRING"] = CONN_STR
    return env


def clamp_world(bbox) -> tuple:
    """Clip a lon/lat bbox to the valid world. Pixel-edge grids overhang it by half a pixel
    (e.g. -180.125), which map clients cannot draw."""
    return (max(bbox[0], -180.0), max(bbox[1], -90.0), min(bbox[2], 180.0), min(bbox[3], 90.0))


def load_layers() -> list[dict]:
    with open(LAYERS_YAML) as f:
        return yaml.safe_load(f)["layers"]
