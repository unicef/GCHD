"""Infrastructure point tables (Giga school locations): checksum, profile and thumbnail for 08_build_stac.

The tables are published by their owners under public/gchd_cog/infrastructure/ and are only referenced by the
catalog (this script writes nothing to Azure). For each entry of `tables.infrastructure` in config/catalog.yaml:

  - downloads the file to work/infrastructure/ (once) and prints its sha256 multihash, to paste into
    config/catalog.yaml `checksum` (08 publishes it as file:checksum; 09_check verifies file:size);
  - prints a short profile (rows, countries, top values of the columns in `profile`);
  - draws a point-density thumbnail to work/thumbnails/infrastructure/<id>.jpg (08 copies it next to the
    collection).

    python pipeline/12_infrastructure.py
"""
import hashlib
import urllib.request

import duckdb
import geopandas as gpd
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import _path  # noqa: F401,E402
from gchd_stac.common import THUMB_DIR, WORK_DIR, load_catalog_config  # noqa: E402

LAND = WORK_DIR / "naturalearth" / "ne_50m_land.geojson"


def sha256_multihash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "1220" + h.hexdigest()


def thumbnail(path, out, title: str):
    """Log point density on a 0.5 deg grid over the land mask, Web Mercator-like aspect cut at 60S."""
    lon, lat = duckdb.sql(f"SELECT longitude, latitude FROM '{path}'").fetchnumpy().values()
    h, xe, ye = np.histogram2d(lon, lat, bins=[720, 280], range=[[-180, 180], [-60, 80]])
    fig, ax = plt.subplots(figsize=(5.12, 2.4), dpi=100)
    gpd.read_file(LAND).plot(ax=ax, color="#e6e6e6", linewidth=0)
    ax.imshow(np.ma.masked_equal(np.log10(h.T + 1), 0), origin="lower", extent=[-180, 180, -60, 80],
              cmap="YlGnBu", vmin=0, vmax=3, interpolation="nearest", zorder=2)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-60, 80)
    ax.set_axis_off()
    ax.set_title(title, fontsize=8)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, bbox_inches="tight", pil_kwargs={"quality": 88})
    plt.close(fig)


def main():
    for spec in load_catalog_config()["tables"].get("infrastructure", []):
        local = WORK_DIR / "infrastructure" / spec["href"].rsplit("/", 1)[-1]
        if not local.exists():
            local.parent.mkdir(parents=True, exist_ok=True)
            print(f"get    {spec['href']}")
            urllib.request.urlretrieve(spec["href"], local)
        mh = sha256_multihash(local)
        same = mh == (spec.get("checksum") or "")
        print(f"{spec['id']}: {local.stat().st_size:,} bytes, checksum {mh}"
              + ("" if same else "  <- differs from config/catalog.yaml, update it"))
        con = duckdb.connect()
        rows, n_iso = con.sql(f"SELECT count(*), count(DISTINCT iso3) FROM '{local}'").fetchone()
        print(f"  {rows:,} rows, {n_iso} countries")
        for c in spec.get("profile", []):
            top = con.sql(f"SELECT {c}, count(*) n FROM '{local}' GROUP BY 1 ORDER BY n DESC LIMIT 8").fetchall()
            print(f"  {c}: " + ", ".join(f"{v} ({n:,})" for v, n in top))
        out = THUMB_DIR / "infrastructure" / f"{spec['id']}.jpg"
        thumbnail(local, out, f"{spec['title']}: {rows:,} points")
        print(f"  thumbnail {out}")


if __name__ == "__main__":
    main()
