"""Make a saved static STAC catalog conform to the Portolan profile (https://portolan-sdi.org, schema v0.2.0).

08_build_stac.py builds and saves the catalog with pystac, writes README.md / AGENTS.md (gchd_stac/docs.py)
and then calls conform(), which edits the JSON files in place:

  every Catalog/Collection  Portolan schema URI in stac_extensions; rel agents -> AGENTS.md and
                            rel describedby -> README.md; a title on every child/item link (PTL-TTL-003)
  every Collection          rel license link when license is "other" (PTL-LIC-002) or an SPDX id we know;
                            providers with a producer and the host (UNICEF) last (PTL-PRV-*);
                            a collection whose producer is not UNICEF is a mirror: rel via to the producer
                            and a top-level `updated` (PTL-PRO-001/003)
  every object              projection v2.0.0 (proj:epsg -> proj:code) and raster v2.0.0
                            (raster:bands -> STAC 1.1 `bands`), as the Portolan registry pins (PTL-CNF-004);
                            file:size + file:checksum on assets (PTL-AST-003): sha2-256 multihash for files
                            in the catalog tree; for remote files the size and, where the blob has a
                            Content-MD5, an md5 multihash (no download), cached in work/file_info.json
"""
import base64
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

PORTOLAN_EXT = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
PROJ_V1 = "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
PROJ_V2 = "https://stac-extensions.github.io/projection/v2.0.0/schema.json"
RASTER_V1 = "https://stac-extensions.github.io/raster/v1.1.0/schema.json"
RASTER_V2 = "https://stac-extensions.github.io/raster/v2.0.0/schema.json"
SPDX_URLS = {"CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/"}
# raster v1.1 band fields that keep their name in STAC 1.1 `bands`; the others get a raster: prefix
COMMON_BAND_FIELDS = {"name", "description", "nodata", "data_type", "statistics", "unit"}
MD = "text/markdown"


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def _save(p: Path, d: dict):
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")


def _ext(d: dict, uri: str, replaces: str | None = None):
    exts = d.setdefault("stac_extensions", [])
    if replaces in exts:
        exts.remove(replaces)
    if uri not in exts:
        exts.append(uri)


def _title(d: dict) -> str | None:
    return d.get("title") or d.get("properties", {}).get("title")


def sha256_multihash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "1220" + h.hexdigest()


# --- extension upgrades ---------------------------------------------------------------------------

def upgrade_bands(bands: list) -> list:
    out = []
    for b in bands:
        nb = {}
        for k, v in b.items():
            if v is None:
                continue
            nb[k if k in COMMON_BAND_FIELDS or k.startswith("raster:") else f"raster:{k}"] = v
        out.append(nb)
    return out


def _upgrade_fields(fields: dict) -> bool:
    """proj:epsg -> proj:code and raster:bands -> bands on one dict (item properties, collection or asset)."""
    changed = False
    if "proj:epsg" in fields:
        epsg = fields.pop("proj:epsg")
        if epsg is not None:
            fields["proj:code"] = f"EPSG:{epsg}"
        changed = True
    if "raster:bands" in fields:
        fields["bands"] = upgrade_bands(fields.pop("raster:bands"))
        changed = True
    return changed


def upgrade_extensions(d: dict):
    containers = [d, d.get("properties", {})] + list(d.get("assets", {}).values())
    used_raster = any(_upgrade_fields(c) for c in containers if c is not None)
    exts = d.get("stac_extensions", [])
    if PROJ_V1 in exts:
        _ext(d, PROJ_V2, PROJ_V1)
    if RASTER_V1 in exts or used_raster:
        _ext(d, RASTER_V2, RASTER_V1)
    if any(k.startswith("proj:") for c in containers for k in (c or {})):
        _ext(d, PROJ_V2, PROJ_V1)


# --- file info ------------------------------------------------------------------------------------

class RemoteFileInfo:
    """file:size / md5 multihash of remote assets from HTTP HEAD, cached by URL across runs."""

    def __init__(self, cache: Path):
        self.cache = cache
        self.data = _load(cache) if cache.exists() else {}

    def fetch(self, urls: set[str], workers: int = 16):
        todo = sorted(u for u in urls if u not in self.data)

        def head(url):
            req = urllib.request.Request(url, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    h = {k.lower(): v for k, v in r.headers.items()}
            except Exception as e:   # noqa: BLE001 - reported, the asset keeps no file info
                print(f"WARN   HEAD {url}: {e}")
                return url, None
            md5 = h.get("content-md5")
            return url, {"size": int(h["content-length"]),
                         "checksum": "d50110" + base64.b64decode(md5).hex() if md5 else None}

        with ThreadPoolExecutor(workers) as ex:
            for url, info in ex.map(head, todo):
                if info:
                    self.data[url] = info
        if todo:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            _save(self.cache, self.data)
            print(f"file   HEAD {len(todo)} remote assets (cache {self.cache.name})")

    def hash_missing(self, urls: set[str], workers: int = 4):
        """sha2-256 multihash, by streaming the bytes, of remote files that have no checksum yet (one-off cost)."""
        todo = sorted(u for u in urls if u in self.data and not self.data[u]["checksum"])

        def digest(url):
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=300) as r:
                for chunk in iter(lambda: r.read(8 << 20), b""):
                    h.update(chunk)
            return url, "1220" + h.hexdigest()

        if todo:
            gb = sum(self.data[u]["size"] for u in todo) / 1e9
            print(f"file   hashing {len(todo)} remote files without Content-MD5 ({gb:.1f} GB)", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            for i, (url, checksum) in enumerate(ex.map(digest, todo), 1):
                self.data[url]["checksum"] = checksum
                if i % 10 == 0 or i == len(todo):
                    _save(self.cache, self.data)

    def get(self, url: str) -> dict | None:
        return self.data.get(url)


def _asset_urls(files: list[Path]) -> set[str]:
    return {a["href"] for p in files for a in _load(p).get("assets", {}).values() if "://" in a["href"]}


def add_file_info(d: dict, path: Path, remote: RemoteFileInfo, known: dict[str, str]):
    used = False
    for a in d.get("assets", {}).values():
        href = a["href"]
        if "://" in href:
            info = remote.get(href)
            if info:
                a["file:size"] = info["size"]
                checksum = known.get(href) or info["checksum"]
                if checksum:
                    a["file:checksum"] = checksum
                used = True
        else:
            f = (path.parent / href).resolve()
            if f.exists():
                a["file:size"] = f.stat().st_size
                a["file:checksum"] = sha256_multihash(f)
                used = True
    if used:
        _ext(d, FILE_EXT)


# --- catalog / collection rules -------------------------------------------------------------------

def _set_link(d: dict, rel: str, href: str, media_type: str, title: str | None = None):
    if any(l["rel"] == rel for l in d["links"]):
        return
    link = {"rel": rel, "href": href, "type": media_type}
    if title:
        link["title"] = title
    d["links"].append(link)


def conform_container(d: dict, path: Path, titles: dict[Path, str], license_url: str, host: str, now: str):
    _ext(d, PORTOLAN_EXT)
    for link in d["links"]:
        if link["rel"] in ("child", "item", "parent", "root") and not link.get("title"):
            t = titles.get((path.parent / link["href"]).resolve())
            if t:
                link["title"] = t
        if link["rel"] in ("child", "parent", "root"):
            link.setdefault("type", "application/json")
        if link["rel"] == "item":
            link.setdefault("type", "application/geo+json")
    _set_link(d, "agents", "./AGENTS.md", MD, "Agent/LLM usage guide")
    _set_link(d, "describedby", "./README.md", MD, "Human-readable documentation")
    if d["type"] != "Collection":
        return
    lic = d.get("license")
    if lic == "other":
        _set_link(d, "license", license_url, "text/html", "License and terms of use")
    elif lic in SPDX_URLS:
        _set_link(d, "license", SPDX_URLS[lic], "text/html", lic)
    providers = d.get("providers") or []
    hosts = [p for p in providers if p.get("name") == host]
    others = [p for p in providers if p.get("name") != host]
    if not any("producer" in p.get("roles", []) for p in providers):
        for p in hosts:
            p["roles"] = ["producer"] + [r for r in p.get("roles", []) if r != "producer"]
    for p in hosts:
        if "host" not in p.get("roles", []):
            p["roles"] = p.get("roles", []) + ["host"]
    d["providers"] = others + hosts
    producers = [p for p in others if "producer" in p.get("roles", [])]
    if producers:   # data produced elsewhere, hosted/re-served by UNICEF: a mirror
        url = next((p["url"] for p in producers if p.get("url")), None)
        url = url or next((l["href"] for l in d["links"] if l["rel"] == "derived_from"), None)
        if url:
            _set_link(d, "via", url, "text/html", f"Original source ({producers[0]['name']})")
        d["updated"] = now


def conform(stac_root: Path, license_url: str, cache: Path, host: str = "UNICEF",
            known_checksums: dict[str, str] | None = None, hash_remote: bool = False):
    files = sorted(stac_root.rglob("*.json"))
    files = [p for p in files if _load(p).get("type") in ("Catalog", "Collection", "Feature")]
    titles = {p.resolve(): _title(_load(p)) for p in files}
    remote = RemoteFileInfo(cache)
    urls = _asset_urls(files)
    remote.fetch(urls)
    if hash_remote:
        # only our own COGs/VRTs (public/gchd_cog/); never the ~87 GB of WorldPop country files
        remote.hash_missing({u for u in urls if "/gchd_cog/" in u} - set(known_checksums or {}))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for p in files:
        d = _load(p)
        if d["type"] in ("Catalog", "Collection"):
            conform_container(d, p, titles, license_url, host, now)
        upgrade_extensions(d)
        add_file_info(d, p, remote, known_checksums or {})
        _save(p, d)
    print(f"conform {len(files)} STAC objects (Portolan v0.2.0)")
