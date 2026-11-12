"""Step 01c — admin-2 hazard exposure, chunked and multi-band.

Same output as s01 (the per-country partials s02 reads), computed differently:

  - One country is one job and covers every hazard: one image stacks the six
    exposed-population bands of every hazard, another every hazard band, so one
    request answers every hazard at once (s01 made three per hazard).
  - Regions are the admin-2 units cut by a 500 km grid
    (``global_boundary/adm2_chunked_500km_shp``), so no region is ever huge and
    the tiled gap-fill is not needed. The exposure sums of a unit's chunks are
    added up in ``pipeline.chunked``.
  - Countries run in parallel (``--workers``); a request that times out or runs
    out of memory is split in two and retried.

Hazard statistics (mean, min, max, median, std) come from Earth Engine's own
reducers, as in s01: units in one chunk (most of them) take the chunk's, and
units split across chunks are reduced whole in a separate pass that runs in
parallel with the chunk reduction. Only the exposures, which are sums, are
recombined from chunks.

Countries absent from the chunk asset (e.g. Mali's V2 boundaries, newer than
the asset) fall back to their admin-2 features as single chunks.
"""

from __future__ import annotations

import csv
import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

from .. import auth, io_paths
from ..chunked import POP_CLASSES, band, combine
from ..countries import countries_to_process
from ..hazards import load_hazards
from ..settings import Settings

STEP = "s01c"
CHUNK_ASSET = "global_boundary/adm2_chunked_500km_shp"
CHUNK_UCODE = {"MLI_V2": "MLI_V1"}  # adm0 ucodes renamed in the boundaries after the chunks were cut
# adm1 units with their own WorldPop rasters (see GEEUtils.set_population_dicts)
SPECIAL_POP_ADM1 = {"USA_V1": "USA_0002", "FIN_V1": "FIN_0001", "SRB_V1": "SRB_0001"}
PAGE = 4000  # features per getInfo page (EE caps a FeatureCollection listing at 5000)
RETRYABLE = ("too many concurrent", "rate limit", "quota", "429", "503", "internal error",
             "deadline", "connection", "temporarily")
# hazard statistics, all from Earth Engine's own reducers (as s01)
STAT_REDUCERS = {"mean": "mean", "min": "min", "max": "max", "median": "median", "std": "stdDev"}
SPLITTABLE = ("timed out", "memory limit", "too large", "payload size")

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


# -- Earth Engine helpers ---------------------------------------------------

def get_info(obj, what: str, attempts: int = 6):
    """getInfo with backoff on transient errors. Splittable errors are re-raised
    so the caller can halve the request."""
    for i in range(attempts):
        try:
            return obj.getInfo()
        except Exception as e:
            msg = str(e).lower()
            if any(s in msg for s in SPLITTABLE):
                raise
            if i == attempts - 1 or not any(s in msg for s in RETRYABLE):
                raise
            wait = min(120, 5 * 2 ** i) * (0.5 + random.random())
            log(f"    retry {what} in {wait:.0f}s: {str(e)[:120]}")
            time.sleep(wait)


def fc_rows(ee, fc, props: list[str], what: str) -> list[dict]:
    """Properties of every feature, paging past the 5000-feature listing cap."""
    n = get_info(fc.size(), f"{what} size")
    rows = []
    for off in range(0, n, PAGE):
        page = ee.FeatureCollection(fc.toList(PAGE, off)).select(props, None, False)
        rows += [f["properties"] for f in get_info(page, f"{what} page {off}")["features"]]
    return rows


# -- one country -----------------------------------------------------------

class CountryJob:
    def __init__(self, settings: Settings, ee, ucode: str, hazards, hazard_images,
                 chunk_batch: int, hazard_batch: int, tile_scale: int):
        self.s, self.ee, self.ucode = settings, ee, ucode
        self.hazards, self.hazard_images = hazards, hazard_images
        self.chunk_batch, self.hazard_batch, self.tile_scale = chunk_batch, hazard_batch, tile_scale
        self.utils = auth.make_utils(settings, ee)  # own instance: GEEUtils keeps per-country state
        self.requests = 0
        self.splits = 0
        self.phases: dict[str, float] = {}

    def timed(self, name, t0):
        self.phases[name] = self.phases.get(name, 0) + time.time() - t0

    # regions
    def chunks(self):
        ee = self.ee
        src = f"{self.s.unicef_data_source_path}/{CHUNK_ASSET}"
        fc = ee.FeatureCollection(src).filter(ee.Filter.eq("adm0_ucode", CHUNK_UCODE.get(self.ucode, self.ucode)))
        adm2 = self.utils.get_admin2_boundaries(self.ucode)
        unit_codes = {r["adm2_ucode"] for r in fc_rows(ee, adm2, ["adm2_ucode"], f"{self.ucode} units")}
        chunk_codes = [r["ucode"] for r in fc_rows(ee, fc, ["ucode"], f"{self.ucode} chunks")]
        if not chunk_codes or not unit_codes <= set(chunk_codes):
            log(f"  {self.ucode}: chunk asset does not cover its units; using whole admin-2 units")
            fc = adm2.map(lambda f: f.set("ucode", f.get("adm2_ucode")))
            chunk_codes = sorted(unit_codes)
        return fc, adm2, chunk_codes

    def groups(self, fc):
        """(label, chunk collection) pairs that share one set of population rasters."""
        special = SPECIAL_POP_ADM1.get(self.ucode)
        if not special:
            return [(self.ucode, fc)]
        ee = self.ee
        return [(f"{self.ucode}:{special}", fc.filter(ee.Filter.stringStartsWith("adm1_ucode", special))),
                (f"{self.ucode}:rest", fc.filter(ee.Filter.stringStartsWith("adm1_ucode", special).Not()))]

    # images
    def population(self, group_fc):
        u = self.utils
        u.set_population_dicts(self.ucode, group_fc)
        info = u.get_population_classes()
        return info["valid_population_classes"], u.analysis_scale

    def chain(self, fc, hazard_ids, scale, pop=None):
        """Chain the reductions of ``hazard_ids`` onto ``fc``: two stacks, one request.

        A stack is sampled on its FIRST band's grid. Exposures (population counts)
        go in a stack that starts with population, as in s01; the hazard
        statistics in a stack of hazard bands, reduced with Earth Engine's own
        reducers so they equal s01's.
        """
        ee = self.ee
        if pop is not None:
            exposure = ee.Image.cat([pop[c].multiply(self.hazard_images[h]["hazard_masked_image"])
                                     .rename(band(h, f"e_{c}")) for h in hazard_ids for c in POP_CLASSES if c in pop])
            fc = exposure.reduceRegions(collection=fc, reducer=ee.Reducer.sum(), scale=scale, tileScale=self.tile_scale)
        stats = ee.Image.cat([self.hazard_images[h]["hazard_raw_image"].toFloat().rename(f"h{h}")
                              for h in hazard_ids])
        red = ee.Reducer.count().setOutputs(["n"])
        for stat, name in STAT_REDUCERS.items():
            red = red.combine(getattr(ee.Reducer, name)().setOutputs([stat]), sharedInputs=True)
        fc = stats.reduceRegions(collection=fc, reducer=red, scale=scale, tileScale=self.tile_scale)
        if len(hazard_ids) == 1:  # a one-band stack drops the band prefix from the output names
            h = hazard_ids[0]
            keep = ["n", *STAT_REDUCERS]
            fc = fc.map(lambda f: f.set(ee.Dictionary.fromLists(
                [band(h, k) for k in keep], [f.get(k) for k in keep])))
        return fc

    # reductions
    def reduce(self, fc_list, offset: int, size: int, pop, scale, hazard_ids) -> list[dict]:
        """Reduce chunks [offset, offset+size) for ``hazard_ids``; halves on failure."""
        ee = self.ee
        part = ee.FeatureCollection(fc_list.slice(offset, offset + size)).select(["ucode"])
        fc = self.chain(part, hazard_ids, scale, pop=pop)
        try:
            self.requests += 1
            feats = get_info(fc.select([".*"], None, False), f"{self.ucode} chunks {offset}+{size}")["features"]
            return [f["properties"] for f in feats]
        except Exception as e:
            msg = str(e).lower()
            if any(s in msg for s in SPLITTABLE):
                self.splits += 1
                if size > 1:
                    half = size // 2
                    log(f"    {self.ucode}: split {offset}+{size} ({str(e)[:60]})")
                    return (self.reduce(fc_list, offset, half, pop, scale, hazard_ids)
                            + self.reduce(fc_list, offset + half, size - half, pop, scale, hazard_ids))
                if len(hazard_ids) > 1:
                    half = len(hazard_ids) // 2
                    a = self.reduce(fc_list, offset, 1, pop, scale, hazard_ids[:half])
                    b = self.reduce(fc_list, offset, 1, pop, scale, hazard_ids[half:])
                    return [{**x, **y} for x, y in zip(a, b)]
            raise

    def split_unit_stats(self, adm2, split_codes: list[str], scale) -> pd.DataFrame:
        """Hazard statistics of units cut by the grid, reduced whole, as s01 does.
        One row per (adm2_ucode, hazard_index)."""
        if not split_codes:
            return pd.DataFrame()
        ee = self.ee
        hids = list(range(len(self.hazards)))
        rows = []
        for off in range(0, len(split_codes), self.chunk_batch):
            units = adm2.filter(ee.Filter.inList("adm2_ucode", split_codes[off:off + self.chunk_batch]))
            fc = self.chain(units.select(["adm2_ucode"]), hids, scale)
            self.requests += 1
            for r in fc_rows(ee, fc, [".*"], f"{self.ucode} split units"):
                for h in hids:
                    rows.append({"adm2_ucode": r["adm2_ucode"], "hazard_index": h,
                                 **{f"hazs_{s}": r.get(band(h, s)) for s in STAT_REDUCERS}})
        return pd.DataFrame(rows)

    def run(self) -> dict:
        t0 = time.time()
        fc, adm2, chunk_codes = self.chunks()
        self.timed("regions", t0)
        t1 = time.time()
        groups, scale = [], None
        hids = list(range(len(self.hazards)))
        counts = pd.Series(chunk_codes).value_counts()
        split = sorted(counts[counts > 1].index)
        split_future, pool = None, ThreadPoolExecutor(max_workers=1)
        for label, gfc in self.groups(fc):
            n = get_info(gfc.size(), f"{label} size")
            if n == 0:
                continue
            pop, scale = self.population(gfc)
            scale = get_info(scale, f"{label} scale")
            if split_future is None:  # needs only the hazards and the scale: start it now
                split_future = pool.submit(self.split_unit_stats, adm2, split, scale)
            fc_list = gfc.toList(n)
            frame = None
            for hb in range(0, len(hids), self.hazard_batch):
                part: list[dict] = []
                for off in range(0, n, self.chunk_batch):
                    part += self.reduce(fc_list, off, min(self.chunk_batch, n - off), pop, scale,
                                        hids[hb:hb + self.hazard_batch])
                df = pd.DataFrame(part)
                if frame is None:
                    frame = df
                else:  # every hazard batch reduces the same chunks in the same order
                    assert (frame["ucode"].values == df["ucode"].values).all(), f"{label}: chunk order changed"
                    frame = frame.join(df.drop(columns="ucode"))
            groups.append(frame)
        stats = combine(pd.concat(groups, ignore_index=True), len(self.hazards))
        self.timed("chunk_reduction", t1)
        t1 = time.time()

        stats = merge_split(stats, split_future.result() if split_future else pd.DataFrame())
        pool.shutdown()
        self.timed("split_units", t1)
        t1 = time.time()
        units = pd.DataFrame(fc_rows(self.ee, adm2, [".*"], f"{self.ucode} unit properties"))
        self.timed("unit_properties", t1)
        return {"stats": stats, "units": units, "n_units": len(units), "n_chunks": len(chunk_codes),
                "n_split": len(split), "seconds": time.time() - t0, "requests": self.requests,
                "splits": self.splits, "phases": {k: round(v, 1) for k, v in self.phases.items()}}


# -- partial assembly ------------------------------------------------------

def assemble(utils, settings: Settings, hazard, h: int, stats: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """One hazard's partial, in the same shape s01 writes."""
    s = stats[stats["hazard_index"] == h].drop(columns=["hazard_index", "n_chunks", "hazs_count"])
    df = units.merge(s, on="adm2_ucode", how="left")
    df["geo_level"] = "DISTRICT"
    # the run metadata add_ratios_pandas stamps (define_hazard would rebuild the images)
    utils.hazard_name, utils.prod_date = hazard.name, settings.prod_date
    utils.time_period, utils.dataflow = settings.time_period, settings.dataflow
    utils.valid_population_keys = list(POP_CLASSES)
    df = utils._process_null_exposure(df)
    df = utils._ceil_columns(df)
    df = utils.add_ratios_pandas(df)
    df["source"] = hazard.asset.split("/").pop()
    cols = [c for c in utils.OUTPUT_COLUMNS if c in df.columns]
    return df[cols + [c for c in units.columns if c not in cols]]


def _done(settings: Settings, hazards, ucode: str) -> bool:
    return all(Path(io_paths.base_partial_csv(settings, h.code, ucode)).exists() for h in hazards)


def write_country(settings: Settings, utils, hazards, ucode: str, stats: pd.DataFrame,
                  units: pd.DataFrame) -> None:
    """The country's partials (one per hazard) and its pixel counts."""
    for h, hazard in enumerate(hazards):
        df = assemble(utils, settings, hazard, h, stats, units)
        df.to_csv(io_paths.ensure_local_dir(io_paths.base_partial_csv(settings, hazard.code, ucode)), index=False)
    counts_dir = Path(io_paths.aux_root(settings)) / f"hazs_count_s01c_{settings.prod_date}"
    counts_dir.mkdir(parents=True, exist_ok=True)
    counts = stats[["adm2_ucode", "hazard_index", "hazs_count"]].copy()
    counts["hazard_code"] = counts["hazard_index"].map(lambda i: hazards[i].code)
    counts.drop(columns="hazard_index").to_csv(counts_dir / f"{ucode}.csv", index=False)


def merge_split(stats: pd.DataFrame, whole: pd.DataFrame) -> pd.DataFrame:
    """Every hazard statistic of a split unit from its whole-unit reduction."""
    if not len(whole):
        return stats
    stats = stats.set_index(["adm2_ucode", "hazard_index"])
    stats.update(whole.set_index(["adm2_ucode", "hazard_index"]))
    return stats.reset_index()


def split_long(wide: pd.DataFrame, n_hazards: int) -> pd.DataFrame:
    """Whole-unit export (one row per unit, h{h}_<stat> columns) to (unit, hazard) rows."""
    rows = [{"adm2_ucode": r["adm2_ucode"], "hazard_index": h,
             **{f"hazs_{s}": r.get(band(h, s)) for s in STAT_REDUCERS}}
            for r in wide.to_dict("records") for h in range(n_hazards)]
    return pd.DataFrame(rows)


# -- batch mode: Earth Engine exports to Drive -------------------------------
#
# Interactive requests stop at 5 minutes, which large countries exceed. In batch
# mode each country is one Export.table.toDrive task (plus one for its split
# units); Earth Engine runs the tasks on its own, with no time cap, and the
# step downloads the CSVs and assembles the same partials. Drive is reached
# with the Earth Engine login, whose scopes include Drive.

MANIFEST_FIELDS = ["ucode", "kind", "task_id", "file", "submitted_at"]


def drive_service(ee):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=ee.data.get_persistent_credentials(), cache_discovery=False)


def drive_download(service, folder: str, name: str, dest: Path) -> Path | None:
    """Download ``name`` from any Drive folder called ``folder`` (newest copy);
    None if it is not listed yet."""
    import io
    from googleapiclient.http import MediaIoBaseDownload
    ids = drive_folder_ids(service, folder)
    if not ids:
        return None
    parents = " or ".join(f"'{i}' in parents" for i in ids)
    files = service.files().list(q=f"name = '{name}' and trashed = false and ({parents})",
                                 fields="files(id, modifiedTime)", orderBy="modifiedTime desc",
                                 pageSize=5).execute().get("files", [])
    if not files:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    with io.FileIO(dest, "wb") as fh:
        dl = MediaIoBaseDownload(fh, service.files().get_media(fileId=files[0]["id"]))
        done = False
        while not done:
            _, done = dl.next_chunk()
    return dest


def drive_folder_ids(service, folder: str) -> list[str]:
    """Ids of every folder named ``folder``: exports started together can each
    create one."""
    q = f"name = '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    return [f["id"] for f in service.files().list(q=q, fields="files(id)", pageSize=20).execute().get("files", [])]


def ensure_drive_folder(service, folder: str) -> None:
    """Create the export folder up front, so concurrent exports share it."""
    if not drive_folder_ids(service, folder):
        service.files().create(body={"name": folder, "mimeType": "application/vnd.google-apps.folder"},
                               fields="id").execute()


def submit_country(job: "CountryJob", folder: str, prefix: str) -> list[dict]:
    """Start the export task(s) of one country; returns manifest rows."""
    ee = job.ee
    fc, adm2, chunk_codes = job.chunks()
    counts = pd.Series(chunk_codes).value_counts()
    split = sorted(counts[counts > 1].index)
    hids = list(range(len(job.hazards)))
    parts, scale = [], None
    for label, gfc in job.groups(fc):
        if get_info(gfc.size(), f"{label} size") == 0:
            continue
        pop, scale = job.population(gfc)
        scale = get_info(scale, f"{label} scale")
        parts.append(job.chain(gfc.select(["ucode"]), hids, scale, pop=pop))
    jobs = [("chunks", ee.FeatureCollection(parts).flatten() if len(parts) > 1 else parts[0])]
    if split:
        units = adm2.filter(ee.Filter.inList("adm2_ucode", split)).select(["adm2_ucode"])
        jobs.append(("split", job.chain(units, hids, scale)))
    rows = []
    for kind, coll in jobs:
        name = f"{prefix}_{job.ucode}_{kind}"
        task = ee.batch.Export.table.toDrive(collection=coll.select([".*"], None, False), description=name[:100],
                                             folder=folder, fileNamePrefix=name, fileFormat="CSV")
        task.start()
        rows.append({"ucode": job.ucode, "kind": kind, "task_id": task.id, "file": f"{name}.csv",
                     "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    return rows


def run_batch(settings: Settings, ee, utils, hazards, hazard_images, todo: list[str], *,
              folder: str, tile_scale: int, collect_only: bool, poll_seconds: int = 60) -> dict:
    mdir = Path(io_paths.manifest_root(settings))
    mdir.mkdir(parents=True, exist_ok=True)
    manifest_path, timing_path = mdir / "s01c_tasks.csv", mdir / "s01c_batch_timing.csv"
    manifest = pd.read_csv(manifest_path) if manifest_path.exists() else pd.DataFrame(columns=MANIFEST_FIELDS)
    prefix = f"s01c_{settings.prod_date}"

    service = drive_service(ee)
    if not collect_only:  # submit countries that have no live task yet
        ensure_drive_folder(service, folder)
        live = set(manifest["ucode"])
        for u in [c for c in todo if c not in live]:
            try:
                job = CountryJob(settings, ee, u, hazards, hazard_images, 1, len(hazards), tile_scale)
                rows = submit_country(job, folder, prefix)
                manifest = pd.concat([manifest, pd.DataFrame(rows)], ignore_index=True)
                manifest.to_csv(manifest_path, index=False)
                log(f"  submitted {u}: {', '.join(r['kind'] for r in rows)}")
            except Exception as e:
                log(f"  ERROR submitting {u}: {str(e)[:300]}")

    pending = [u for u in todo if u in set(manifest["ucode"])]
    downloads = Path(io_paths.aux_root(settings)) / f"s01c_exports_{settings.prod_date}"
    done, failed, t0 = 0, [], time.time()
    missing: dict[str, int] = {}  # Drive lists a finished export with some delay
    new_timing = not timing_path.exists()
    with open(timing_path, "a", newline="", encoding="utf-8") as tf:
        w = csv.writer(tf)
        if new_timing:
            w.writerow(["ucode", "kind", "task_id", "state", "created", "started", "finished",
                        "queued_s", "run_s", "eecu_s"])
        while pending:
            rows = manifest[manifest["ucode"].isin(pending)]
            status = {s["id"]: s for s in ee.data.getTaskStatus(list(rows["task_id"]))}
            for u in list(pending):
                mine = rows[rows["ucode"] == u]
                states = [status.get(t, {}).get("state", "UNKNOWN") for t in mine["task_id"]]
                if any(s in ("FAILED", "CANCELLED") for s in states):
                    err = "; ".join(status[t].get("error_message", "") for t in mine["task_id"] if t in status)
                    log(f"  ERROR {u}: task {states}: {err[:200]}")
                    failed.append(u); pending.remove(u)
                    continue
                if not all(s == "COMPLETED" for s in states):
                    continue
                try:
                    frames = {}
                    for r in mine.itertuples():
                        path = drive_download(service, folder, r.file, downloads / r.file)
                        if path is None:
                            raise FileNotFoundError(r.file)
                        frames[r.kind] = pd.read_csv(path)
                        st = status[r.task_id]
                        c, s, f = (st.get(k, 0) / 1000 for k in
                                   ("creation_timestamp_ms", "start_timestamp_ms", "update_timestamp_ms"))
                        w.writerow([u, r.kind, r.task_id, "COMPLETED", time.strftime("%H:%M:%S", time.localtime(c)),
                                    time.strftime("%H:%M:%S", time.localtime(s)),
                                    time.strftime("%H:%M:%S", time.localtime(f)),
                                    round(s - c), round(f - s), st.get("batch_eecu_usage_seconds", "")])
                    tf.flush()
                    stats = merge_split(combine(frames["chunks"], len(hazards)),
                                        split_long(frames["split"], len(hazards)) if "split" in frames else pd.DataFrame())
                    job_utils = auth.make_utils(settings, ee)
                    adm2 = job_utils.get_admin2_boundaries(u)
                    units = pd.DataFrame(fc_rows(ee, adm2, [".*"], f"{u} unit properties"))
                    write_country(settings, job_utils, hazards, u, stats, units)
                    done += 1
                    log(f"  {u}: collected ({done} done, {len(pending) - 1} waiting, {time.time() - t0:.0f}s elapsed)")
                except FileNotFoundError as e:
                    missing[u] = missing.get(u, 0) + 1
                    if missing[u] < 10:
                        log(f"  {u}: {e} not listed in Drive yet")
                        continue
                    log(f"  ERROR collecting {u}: {e} not in Drive folder {folder}")
                    failed.append(u)
                except Exception as e:
                    log(f"  ERROR collecting {u}: {str(e)[:300]}")
                    failed.append(u)
                pending.remove(u)
            if pending:
                running = sum(1 for s in status.values() if s.get("state") == "RUNNING")
                log(f"  [{time.strftime('%H:%M:%S')}] waiting on {len(pending)} countries ({running} tasks running)")
                time.sleep(poll_seconds)
    return {"countries_done": done, "failed": failed, "seconds": round(time.time() - t0, 1)}


def run(settings: Settings, *, allow_interactive: bool = False, workers: int = 8,
        chunk_batch: int = 25, hazard_batch: int = 22, tile_scale: int = 4,
        overwrite: bool = False, mode: str = "interactive", drive_folder: str | None = None,
        collect_only: bool = False) -> dict:
    ee, utils = auth.ee_and_utils(settings, allow_interactive=allow_interactive)
    hazards = load_hazards(settings)
    countries = countries_to_process(utils, settings.process_countries)
    todo = [c for c in countries if overwrite or not _done(settings, hazards, c)]
    log(f"s01c ({mode}): {len(hazards)} hazards x {len(todo)}/{len(countries)} countries")

    hazard_images = [utils.define_hazard(h, production_date=settings.prod_date,
                                         time_period=settings.time_period, dataflow=settings.dataflow)
                     for h in hazards]

    if mode == "batch":
        summary = run_batch(settings, ee, utils, hazards, hazard_images, todo,
                            folder=drive_folder or f"gchd_s01c_{settings.prod_date}",
                            tile_scale=tile_scale, collect_only=collect_only)
        log(f"s01c done: {summary}")
        return summary

    timing_path = Path(io_paths.manifest_root(settings)) / "s01c_timing.csv"
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not timing_path.exists()
    t_all = time.time()
    done, failed = 0, []

    def one(ucode):
        job = CountryJob(settings, ee, ucode, hazards, hazard_images,
                         chunk_batch, hazard_batch, tile_scale)
        res = job.run()
        write_country(settings, job.utils, hazards, ucode, res["stats"], res["units"])
        return res

    with open(timing_path, "a", newline="", encoding="utf-8") as tf:
        w = csv.writer(tf)
        if new_file:
            w.writerow(["ucode", "n_units", "n_chunks", "n_split_units", "hazards", "seconds",
                        "requests", "splits", "workers", "chunk_batch", "hazard_batch", "finished_at"])
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(one, u): u for u in todo}
            for fut in as_completed(futures):
                u = futures[fut]
                try:
                    r = fut.result()
                    done += 1
                    w.writerow([u, r["n_units"], r["n_chunks"], r["n_split"], len(hazards),
                                round(r["seconds"], 1), r["requests"], r["splits"], workers,
                                chunk_batch, hazard_batch, time.strftime("%Y-%m-%dT%H:%M:%S")])
                    tf.flush()
                    log(f"  {u}: {r['n_units']} units, {r['n_chunks']} chunks, {r['seconds']:.0f}s {r['phases']} "
                        f"({done}/{len(todo)}, {time.time() - t_all:.0f}s elapsed)")
                except Exception as e:
                    failed.append(u)
                    log(f"  ERROR {u}: {str(e)[:300]}")

    summary = {"countries_done": done, "failed": failed, "seconds": round(time.time() - t_all, 1)}
    log(f"s01c done: {summary}")
    return summary
