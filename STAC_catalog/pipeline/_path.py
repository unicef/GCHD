"""Put STAC_catalog/ on sys.path so the pipeline scripts can import the gchd_stac package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
