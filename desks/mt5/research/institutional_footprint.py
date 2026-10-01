"""THE INSTITUTIONAL FOOTPRINT ENGINE -- public exhaust in, latent actor states and cells out.

THE PRINCIPAL, 2026-09-30 17:47-18:14Z: reconstruct who is likely doing what from public
regulatory, exchange, central-bank and physical-market exhaust, in every jurisdiction, merged into
the country packs -- and every state carries its uncertainty. The chain this organ runs, hourly:

    atlas rows (source_rosters/institutional_footprint.yaml, one canonical id per dataset)
      -> fetch (a recipe per public API, or an existing lane's frame read in place)
      -> PIT frame in data/lake/series/<id>.csv   (event_time, available_time, numeric columns)
      -> features (level, change, acceleration, percentile, z, extreme, divergence vs price)
      -> latent states per MT5 asset: P(state) with a 95% interval and the share of evidence
         measured, fused in log-odds from stated prior weights (ontology.LATENT_STATES)
      -> dealer gamma as a POSTERIOR OVER THREE SCENARIOS, never a signed number
      -> conditioner cells through the one registry door (`libs.moat.registry.enqueue_candidate`,
         family `exogenous_conditioner`), each carrying its source id and the culture fields
      -> INSTITUTIONAL_COVERAGE.json: the jurisdiction x class grid with exactly one status per
         cell, the role grid, commodity triangulation, the future-source watch, the unfed count
         and the age of every latent state
      -> INSTITUTIONAL_STATE.json: the latest state per asset, the allocator's input

WHAT THIS IS NOT. It does not judge, size, veto or promote: every cell goes to the one gauntlet
and is charged there, once (a cell key already enqueued is never re-enqueued, so a pass never
inflates a search count). It never throttles a miner: the budget is a wall clock and whatever a
pass does not reach leads the next pass. It fetches only public, keyless endpoints; a recipe that
fails is recorded with its reason and the row stays DISCOVERED -- absence is UNMEASURED, never a
zero. No crypto venue is ever fetched; the public-chain row is a sensor with no recipe here.

    python desks/mt5/research/institutional_footprint.py --once --budget-s 300
    python desks/mt5/research/institutional_footprint.py --once --offline     # no network
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import sys
import time
import zipfile
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROSTER = DESK / "data" / "source_rosters" / "institutional_footprint.yaml"
SERIES = DESK / "data" / "lake" / "series"
STATE_DIR = DESK / "data" / "institutional"
EMITTED = STATE_DIR / "cells_emitted.json"
FETCH_STATE = STATE_DIR / "fetch_state.json"
WATCH_STATE = STATE_DIR / "watch_state.json"
RULINGS = DESK / "data" / "institutional_coverage_rulings.json"
#: Culture rows per cell, kept here until #139's registry columns stamp them at the door.
CULTURE_LOG = STATE_DIR / "cell_culture.jsonl"
REPORT = DESK / "reports" / "INSTITUTIONAL_COVERAGE.json"
STATE_REPORT = DESK / "reports" / "INSTITUTIONAL_STATE.json"
#: The full equivalence-search queue, for the dataset hunters on the box; the report carries counts.
SEARCH_QUEUE = STATE_DIR / "search_queue.json"

LEG = "institutional_footprint"
STATE_SERIES_PREFIX = "institutional_state"
#: The charts a conditioner is asked on -- the same set pack_cells mints.
CHARTS: tuple[str, ...] = ("H1", "H4", "D1")
#: (transform, threshold) per cell kind, each threshold IN THE UNITS THE FAMILY READS. A state is a
#: probability, so its `delta` extreme is a move of STATE_DELTA_THRESHOLD in p (the family's 1.0
#: default is a move no probability can make: every such cell was dead on arrival, audit
#: 2026-09-30). A raw series carries arbitrary units, so it is read as `delta_z`, never `delta`.
STATE_DELTA_THRESHOLD = 0.10
TRANSFORMS_STATE: tuple[tuple[str, float], ...] = (("level_z", 1.0),
                                                   ("delta", STATE_DELTA_THRESHOLD))
TRANSFORMS_RAW: tuple[tuple[str, float], ...] = (("level_z", 1.0), ("delta_z", 1.0))
#: ONE side per cell. The family is symmetric (side_when_high when high, its negation when low),
#: so +1 and -1 are the same bet mirrored and minting both charged every trial twice. The side is
#: LEARNED on the first TRAIN_FRACTION of the joint history and stated in the mechanism; the
#: cell key carries no side, so a cell is charged once whichever side it learned.
TRAIN_FRACTION = 0.5
MIN_TRAIN_EVENTS = 30
#: Observations the rolling percentile and z are measured over (156 weeks ~ 3 years of COT).
ROLL = 156
MIN_OBS = 20
#: Distinct published vintages a series needs before it may mint a cell (the #133 swap rule).
MIN_VINTAGES = 60
#: A latent state older than this is UNMEASURED in every published block (CRO D37: < 7 days).
STATE_MAX_AGE = pd.Timedelta(days=7)
#: ACTIVE decays: a source is ACTIVE only while its frame was refreshed AND fed within this window.
ACTIVE_WINDOW = timedelta(days=30)
#: pit_grade of a frame. FIRST_RELEASE: every value is what was published at available_time.
#: LATEST_REVISED: a revisable series fetched as its latest vintage -- stored and reported, but
#: UNMEASURED for anything point-in-time (features, states, cells) until a vintage recipe runs.
FIRST_RELEASE = "FIRST_RELEASE"
LATEST_REVISED = "LATEST_REVISED"


def _ontology() -> Any:
    for name in ("research.countries.institutional.ontology", "countries.institutional.ontology"):
        with contextlib.suppress(ImportError):
            import importlib
            return importlib.import_module(name)
    raise ImportError("countries.institutional.ontology is not importable")


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False, default=str), "utf-8")
    tmp.replace(p)


# =========================================================================== the atlas
def load_roster(path: Path = ROSTER) -> list[dict[str, Any]]:
    """The atlas rows. An unreadable roster is an empty atlas and the report says so."""
    try:
        import yaml
        doc = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    except Exception:
        return []
    rows = doc.get("sources") if isinstance(doc, Mapping) else doc
    return [dict(r) for r in rows or [] if isinstance(r, Mapping) and r.get("id")]


def rows_for(jurisdiction: str, rows: Iterable[Mapping[str, Any]] | None = None
             ) -> list[dict[str, Any]]:
    """One jurisdiction's slice of the atlas: what a country pack's footprint reads."""
    src = load_roster() if rows is None else rows
    return [dict(r) for r in src if str(r.get("jurisdiction")) == jurisdiction]


# =========================================================================== PIT frames
def series_path(sid: str) -> Path:
    return SERIES / f"{sid}.csv"


def write_frame(sid: str, df: pd.DataFrame, *, lag_hours: float,
                pit_grade: str = FIRST_RELEASE) -> int:
    """Stamp and write one frame. `available_time` is event_time plus the publication lag, or
    the recipe's own per-row release stamp when it carries one, whichever is LATER.

    The stamp fixes WHEN a value could be known; it does not fix WHICH value. A recipe that reads
    the latest vintage of a revisable series (FRED's fredgraph.csv, the OFR API) gets today's
    revised number at yesterday's stamp, so it writes pit_grade LATEST_REVISED and nothing
    point-in-time reads it. Only a first-release recipe (ALFRED vintages, operation results,
    auction results, exchange files that are never restated) writes FIRST_RELEASE."""
    if df is None or df.empty or "event_time" not in df.columns:
        return 0
    out = df.copy()
    out["event_time"] = pd.to_datetime(out["event_time"], utc=True, errors="coerce")
    out = out.dropna(subset=["event_time"]).sort_values("event_time")
    lagged = out["event_time"] + pd.Timedelta(hours=float(lag_hours))
    if "available_time" in out.columns:
        own = pd.to_datetime(out["available_time"], utc=True, errors="coerce")
        out["available_time"] = own.where(own > lagged, lagged).fillna(lagged)
    else:
        out["available_time"] = lagged
    out["source_id"] = sid
    out["retrieval_time"] = now_utc().isoformat(timespec="seconds")
    out["pit_grade"] = pit_grade
    stamp = ["event_time", "available_time", "source_id", "retrieval_time", "pit_grade"]
    keep = stamp + [c for c in out.columns
                    if c not in stamp and pd.api.types.is_numeric_dtype(out[c])]
    out = out[keep].drop_duplicates(subset=["event_time"], keep="last")
    SERIES.mkdir(parents=True, exist_ok=True)
    out.to_csv(series_path(sid), index=False)
    return len(out)


def read_frame(sid: str) -> pd.DataFrame | None:
    p = series_path(sid)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if "available_time" not in df.columns:
        return None
    df["available_time"] = pd.to_datetime(df["available_time"], utc=True, errors="coerce")
    df["event_time"] = pd.to_datetime(df.get("event_time"), utc=True, errors="coerce")
    return df.dropna(subset=["available_time"]).sort_values("available_time")


def pit_ok(df: pd.DataFrame | None, row: Mapping[str, Any] | None = None) -> bool:
    """May a point-in-time consumer read this frame? Only a FIRST_RELEASE frame. A frame written
    before the grade existed falls back to the row's declared `pit_grade`, and fails closed."""
    if df is None:
        return False
    if "pit_grade" in df.columns:
        return bool((df["pit_grade"].astype(str) == FIRST_RELEASE).all())
    return str((row or {}).get("pit_grade") or LATEST_REVISED) == FIRST_RELEASE


#: Every column that is a stamp, never a signal (the family's STAMP_COLUMNS plus the grade).
STAMP = ("event_time", "available_time", "source_id", "retrieval_time", "vintage_id",
         "pit_grade", "published_time", "revision_time", "ingested_time")


def signal_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in STAMP and pd.api.types.is_numeric_dtype(df[c])]


def vintages(df: pd.DataFrame, col: str) -> int:
    """Distinct published readings of one column: the minting gate counts these, not rows."""
    return int(df.loc[df[col].notna(), "available_time"].nunique()) if col in df else 0


def lag_hours_of(row: Mapping[str, Any]) -> float:
    """Publication lag in hours, conservative: the declared lag in days plus the whole day of
    publication, so a series never reaches a bar before the day it was released has ended.
    A recipe may state its exact offset (the COT is out Friday 19:30 UTC in summer)."""
    fetch = row.get("fetch") or {}
    if fetch.get("available_offset_hours") is not None:
        return float(fetch["available_offset_hours"])
    return (float(row.get("publication_lag_days") or 0) + 1.0) * 24.0


# =========================================================================== fetch recipes
HttpGet = Callable[[str], tuple[int | None, bytes, str]]


def polite_get(deadline: float) -> HttpGet:
    """The desk's polite transport, bounded by the leg's deadline. Returns (status, body, error)."""
    from libs.data import polite_fetch

    def get(url: str) -> tuple[int | None, bytes, str]:
        if url.lower().endswith(".zip"):
            # polite_fetch decodes to text; an archive needs its bytes. Same TLS context, same
            # deadline, one attempt.
            import urllib.request
            left = max(1.0, min(60.0, deadline - time.monotonic()))
            # The SEC's fair-access rule wants a declared agent; this is the one
            # side_channels/sec_edgar_miner.py already declares.
            ua = {"User-Agent": "QuantResearch quant@example.com"}
            req = urllib.request.Request(url, headers=ua)
            try:
                with urllib.request.urlopen(req, timeout=left,
                                            context=polite_fetch.ssl_context()) as resp:
                    return int(resp.status), resp.read(), ""
            except Exception as exc:
                return getattr(exc, "code", None), b"", f"{type(exc).__name__}: {exc}"[:120]
        r = polite_fetch.get(url, headers={"Accept": "*/*"}, timeout=25.0, retries=1,
                             deadline=deadline, leg=LEG)
        return r.status, (r.text or "").encode("utf-8", "replace"), str(r.error or "")
    return get


def _ok(status: int | None, err: str) -> bool:
    return status is not None and 200 <= status < 300 and not err


#: ALFRED's observation endpoint returns every vintage of a series; the first vintage per date is
#: the value as first published, stamped with the day it was published. The key is the box's own
#: (FRED_API_KEY, set with setx /M); it is read from the environment and never logged.
ALFRED = ("https://api.stlouisfed.org/fred/series/observations?series_id={series}"
          "&realtime_start=1776-07-04&realtime_end=9999-12-31&observation_start={start}"
          "&file_type=json&api_key={key}")


def _alfred_first_release(series: str, col: str, get: HttpGet, key: str
                          ) -> tuple[pd.DataFrame | None, str]:
    start = (now_utc() - timedelta(days=365 * 12)).date().isoformat()
    st, body, err = get(ALFRED.format(series=series, start=start, key=key))
    if not _ok(st, err):
        return None, f"ALFRED {series}: HTTP {st} {err.replace(key, '***')}"[:160]
    try:
        obs = json.loads(body.decode("utf-8")).get("observations") or []
    except ValueError:
        return None, f"ALFRED {series}: not JSON"
    df = pd.DataFrame(obs)
    if df.empty or not {"date", "value", "realtime_start"} <= set(df.columns):
        return None, f"ALFRED {series}: no vintages"
    df[col] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=[col]).sort_values(["date", "realtime_start"])
    first = df.groupby("date", as_index=False).first()
    # Known from the END of the publication day (ET), so never before the release itself.
    avail = pd.to_datetime(first["realtime_start"], utc=True) + pd.Timedelta(hours=28)
    return pd.DataFrame({"event_time": first["date"], col: first[col],
                         "available_time": avail}), ""


def _fred_csv(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    """A FRED series. A series that is NEVER revised (an operation's result) is read from
    fredgraph.csv as FIRST_RELEASE. A revisable one (`revisable: true`, the default: fail closed)
    is read from ALFRED's first vintages when the box holds FRED_API_KEY, else from fredgraph.csv
    as LATEST_REVISED, which no point-in-time consumer reads."""
    import os
    revisable = bool(row["fetch"].get("revisable", True))
    key = os.environ.get("FRED_API_KEY", "").strip()
    if revisable and key:
        frames_v = []
        for col, series in (row["fetch"].get("series") or {}).items():
            df, why = _alfred_first_release(str(series), str(col), get, key)
            if df is None:
                return None, why
            frames_v.append(df)
        if not frames_v:
            return None, "no series named"
        out_v = frames_v[0]
        for f in frames_v[1:]:
            out_v = out_v.merge(f, on="event_time", how="outer", suffixes=("", "_r"))
            if "available_time_r" in out_v:
                out_v["available_time"] = out_v[["available_time", "available_time_r"]].max(axis=1)
                out_v = out_v.drop(columns=["available_time_r"])
        out_v.attrs["pit_grade"] = FIRST_RELEASE
        return out_v, ""
    frames = []
    for col, series in (row["fetch"].get("series") or {}).items():
        st, body, err = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
        if not _ok(st, err):
            return None, f"FRED {series}: HTTP {st} {err}"[:160]
        df = pd.read_csv(io.BytesIO(body))
        if df.shape[1] < 2:
            return None, f"FRED {series}: unexpected shape"
        df.columns = ["event_time", col]
        df[col] = pd.to_numeric(df[col], errors="coerce")
        frames.append(df.set_index("event_time"))
    if not frames:
        return None, "no series named"
    out = pd.concat(frames, axis=1).reset_index()
    out.attrs["pit_grade"] = LATEST_REVISED if revisable else FIRST_RELEASE
    return out, ""


def _dig(doc: Any, path: Iterable[str]) -> Any:
    for k in path:
        doc = doc.get(k) if isinstance(doc, Mapping) else None
    return doc


def _nyfed_json(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    end = now_utc().date()
    url = str(f["url"]).format(start=(end - timedelta(days=730)).isoformat(), end=end.isoformat())
    st, body, err = get(url)
    if not _ok(st, err):
        return None, f"HTTP {st} {err}"[:160]
    items = _dig(json.loads(body), f.get("path") or [])
    if not isinstance(items, list) or not items:
        return None, "the response carried no rows at the declared path"
    df = pd.DataFrame(items)
    if f["date"] not in df.columns or f["value"] not in df.columns:
        return None, f"columns {f['date']}/{f['value']} absent"
    df["event_time"] = pd.to_datetime(df[f["date"]], errors="coerce", utc=True)
    df["v"] = pd.to_numeric(df[f["value"]], errors="coerce")
    grp = f.get("group")
    if grp and grp in df.columns:
        wide = df.pivot_table(index="event_time", columns=grp, values="v", aggfunc="sum")
        wide.columns = [re.sub(r"\W+", "_", str(c)).strip("_").lower() for c in wide.columns]
        return wide.reset_index(), ""
    return df.groupby("event_time", as_index=False)["v"].sum().rename(
        columns={"v": re.sub(r"\W+", "_", f["value"]).lower()}), ""


def _nyfed_pd(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    st, body, err = get(f["list"])
    if not _ok(st, err):
        return None, f"list HTTP {st} {err}"[:160]
    doc = json.loads(body)
    keys = [str(_dig(x, ["keyid"]) or "") for x in (_dig(doc, ["pd", "timeseries"]) or [])]
    want = [k for k in keys if any(k.startswith(m) for m in f.get("match") or [])][:12]
    if not want:
        return None, "no primary-dealer series matched the declared prefixes"
    frames = []
    for k in want:
        st, body, err = get(str(f["get"]).format(keyid=k))
        if not _ok(st, err):
            continue
        ts = _dig(json.loads(body), ["pd", "timeseries"]) or []
        df = pd.DataFrame(ts)
        if df.empty or "asofdate" not in df.columns or "value" not in df.columns:
            continue
        df["event_time"] = pd.to_datetime(df["asofdate"], errors="coerce", utc=True)
        col = re.sub(r"\W+", "_", k).lower()
        df[col] = pd.to_numeric(df["value"], errors="coerce")
        frames.append(df[["event_time", col]].set_index("event_time"))
    if not frames:
        return None, "every matched series failed to fetch"
    return pd.concat(frames, axis=1).reset_index(), ""


def _fiscaldata(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    st, body, err = get(f["url"])
    if not _ok(st, err):
        return None, f"HTTP {st} {err}"[:160]
    df = pd.DataFrame(json.loads(body).get("data") or [])
    if df.empty or f["date"] not in df.columns:
        return None, "no rows"
    df["event_time"] = pd.to_datetime(df[f["date"]], errors="coerce", utc=True)
    cols = [c for c in f.get("fields") or [] if c in df.columns]
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    g = df.groupby("event_time", as_index=False)[cols].sum()
    if {"indirect_bidder_accepted", "total_accepted"} <= set(g.columns):
        g["indirect_share"] = g["indirect_bidder_accepted"] / g["total_accepted"].replace(0, np.nan)
    if {"primary_dealer_accepted", "total_accepted"} <= set(g.columns):
        g["dealer_share"] = g["primary_dealer_accepted"] / g["total_accepted"].replace(0, np.nan)
    return g, ""


def _ofr_search(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    """OFR's documented API: search the metadata, then pull each matched series. Discovery-based
    so a renamed mnemonic is found again rather than hard-coded and silently lost."""
    f = row["fetch"]
    base = str(f["base"]).rstrip("/")
    mnems: list[str] = []
    for q in f.get("queries") or []:
        st, body, err = get(f"{base}/metadata/search?query={q.replace(' ', '%20')}")
        if not _ok(st, err):
            continue
        with contextlib.suppress(ValueError):
            for hit in json.loads(body) or []:
                m = str(hit.get("mnemonic") or "") if isinstance(hit, Mapping) else ""
                if m and m not in mnems:
                    mnems.append(m)
    mnems = mnems[: int(f.get("max_series") or 12)]
    if not mnems:
        return None, "the OFR metadata search returned no mnemonics"
    frames = []
    for m in mnems:
        st, body, err = get(f"{base}/series/timeseries?mnemonic={m}")
        if not _ok(st, err):
            continue
        with contextlib.suppress(ValueError, TypeError):
            pts = json.loads(body)
            df = pd.DataFrame(pts, columns=["event_time", "v"])
            df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce", utc=True)
            col = re.sub(r"\W+", "_", m).lower()
            df[col] = pd.to_numeric(df["v"], errors="coerce")
            frames.append(df[["event_time", col]].dropna().set_index("event_time"))
    if not frames:
        return None, "every matched OFR series failed to fetch"
    return pd.concat(frames, axis=1).reset_index(), ""


def _finra_regsho(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    """Aggregate short-volume ratio across the consolidated tape, one number per day. Single
    names are summed away: this is an index-level crowding read, never a single-name signal."""
    f = row["fetch"]
    old = read_frame(str(row["id"]))
    have = set(old["event_time"].dt.strftime("%Y%m%d")) if old is not None else set()
    out = [] if old is None else [old[["event_time", "short_volume", "total_volume"]]]
    day = now_utc().date()
    tried = 0
    while tried < int(f.get("days") or 20):
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        tried += 1
        key = day.strftime("%Y%m%d")
        if key in have:
            continue
        st, body, err = get(str(f["url"]).format(yyyymmdd=key))
        if not _ok(st, err):
            continue
        with contextlib.suppress(Exception):
            df = pd.read_csv(io.BytesIO(body), sep="|")
            sv = pd.to_numeric(df.get("ShortVolume"), errors="coerce").sum()
            tv = pd.to_numeric(df.get("TotalVolume"), errors="coerce").sum()
            out.append(pd.DataFrame({"event_time": [pd.Timestamp(day, tz="UTC")],
                                     "short_volume": [sv], "total_volume": [tv]}))
    if not out:
        return None, "no daily file fetched"
    g = pd.concat(out, ignore_index=True)
    g["short_volume_ratio"] = g["short_volume"] / g["total_volume"].replace(0, np.nan)
    return g, ""


def ftd_available(month_start: Any, half: str) -> pd.Timestamp:
    """When one half-month FTD file is public. The SEC posts the first half (days 1-15) around the
    end of that month and the second half around the middle of the next; a flat lag from each
    settlement date made the 1st of the month ~13 days early. Every row of a file is stamped at
    the file's period end plus 21 days, which is never before the posting."""
    m = pd.Timestamp(month_start).tz_localize(None).normalize().replace(day=1)
    end = m.replace(day=15) if half == "a" else m + pd.offsets.MonthEnd(0)
    return (end + pd.Timedelta(days=21)).tz_localize("UTC")


def _sec_ftd(row: Mapping[str, Any], get: HttpGet) -> tuple[pd.DataFrame | None, str]:
    f = row["fetch"]
    out = []
    d = now_utc().date().replace(day=1)
    for _ in range(int(f.get("periods") or 6)):
        d = (d - timedelta(days=1)).replace(day=1)
        for half in ("a", "b"):
            st, body, err = get(str(f["url"]).format(yyyymm=d.strftime("%Y%m"), half=half))
            if not _ok(st, err):
                continue
            with contextlib.suppress(Exception):
                z = zipfile.ZipFile(io.BytesIO(body))
                txt = z.read(z.namelist()[0]).decode("latin-1")
                df = pd.read_csv(io.StringIO(txt), sep="|")
                df["event_time"] = pd.to_datetime(df.iloc[:, 0].astype(str), format="%Y%m%d",
                                                  errors="coerce", utc=True)
                df["qty"] = pd.to_numeric(df.iloc[:, 3], errors="coerce")
                g = (df.groupby("event_time", as_index=False)["qty"].sum()
                     .rename(columns={"qty": "fails_shares"}))
                g["available_time"] = ftd_available(d, half)
                out.append(g)
    if not out:
        return None, "no FTD file fetched"
    return pd.concat(out, ignore_index=True), ""


RECIPES: dict[str, Callable[[Mapping[str, Any], HttpGet], tuple[pd.DataFrame | None, str]]] = {
    "fred_csv": _fred_csv, "nyfed_json": _nyfed_json, "nyfed_pd": _nyfed_pd,
    "fiscaldata": _fiscaldata, "ofr_search": _ofr_search, "finra_regsho_daily": _finra_regsho,
    "sec_ftd_zip": _sec_ftd,
}


def fetch_all(rows: list[dict[str, Any]], *, get: HttpGet | None, deadline: float
              ) -> dict[str, Any]:
    """Run every recipe the atlas declares, oldest-fetched first, until the wall clock is spent.
    A row not reached leads the next pass (the cursor is the last-fetch time)."""
    state = _read_json(FETCH_STATE, {})
    order = sorted((r for r in rows if (r.get("fetch") or {}).get("kind") in RECIPES),
                   key=lambda r: str((state.get(r["id"]) or {}).get("at") or ""))
    for r in order:
        if get is None or time.monotonic() > deadline:
            break
        sid = str(r["id"])
        try:
            df, why = RECIPES[r["fetch"]["kind"]](r, get)
            grade = str((df.attrs.get("pit_grade") if df is not None else None)
                        or r.get("pit_grade") or LATEST_REVISED)
            n = (write_frame(sid, df, lag_hours=lag_hours_of(r), pit_grade=grade)
                 if df is not None else 0)
            state[sid] = {"at": now_utc().isoformat(timespec="seconds"), "rows": n,
                          "outcome": "OK" if n else (why or "EMPTY"), "pit_grade": grade}
        except Exception as exc:
            state[sid] = {"at": now_utc().isoformat(timespec="seconds"), "rows": 0,
                          "outcome": f"ERROR {type(exc).__name__}: {str(exc)[:120]}"}
    _write_json(FETCH_STATE, state)
    return state


# =========================================================================== features
def pct_rank(s: pd.Series, window: int = ROLL) -> pd.Series:
    return s.rolling(window, min_periods=MIN_OBS).apply(
        lambda a: float((a[:-1] <= a[-1]).mean()) if len(a) > 1 else np.nan, raw=True)


def zscore(s: pd.Series, window: int = ROLL) -> pd.Series:
    mu = s.rolling(window, min_periods=MIN_OBS).mean()
    sd = s.rolling(window, min_periods=MIN_OBS).std(ddof=0)
    return (s - mu) / sd.replace(0.0, np.nan)


def explode(s: pd.Series) -> pd.DataFrame:
    """The controlled feature family for one series (ontology.FEATURE_FAMILY, first eight)."""
    chg = s.diff()
    z = zscore(s)
    return pd.DataFrame({"level": s, "change": chg, "acceleration": chg.diff(),
                         "pct": pct_rank(s), "z": z, "chg_z": zscore(chg),
                         "extreme": (z.abs() > 2.0).astype(float).where(z.notna())})


#: COT frames -> MT5 asset, and the sign that turns the futures' long into the MT5 symbol's long.
COT_MAP: dict[str, tuple[str, str, int]] = {
    "cot_tff/eur": ("tff", "EURUSD", 1), "cot_tff/jpy": ("tff", "USDJPY", -1),
    "cot_tff/gbp": ("tff", "GBPUSD", 1), "cot_tff/cad": ("tff", "USDCAD", -1),
    "cot_tff/aud": ("tff", "AUDUSD", 1), "cot_tff/nzd": ("tff", "NZDUSD", 1),
    "cot_tff/chf": ("tff", "USDCHF", -1), "cot_tff/sp500": ("tff", "US500", 1),
    "cot_tff/nasdaq100": ("tff", "NAS100", 1),
    "cot_disagg/gold": ("disagg", "XAUUSD", 1), "cot_disagg/silver": ("disagg", "XAGUSD", 1),
}
#: The CFTC's release calendar exceptions: shutdown backlogs and any exact release dates the box
#: learns. Committed beside the ontology; a report date it cannot place is UNMEASURED, never early.
COT_CALENDAR = Path(__file__).resolve().parent / "countries" / "institutional" / \
    "cftc_release_calendar.json"
#: Friday 15:30 ET is 19:30 UTC in summer and 20:30 UTC in winter; 21:00 UTC covers both.
COT_RELEASE_HOUR_UTC = 21


def _us_holidays(lo: pd.Timestamp, hi: pd.Timestamp) -> set[pd.Timestamp]:
    from pandas.tseries.holiday import USFederalHolidayCalendar
    return {pd.Timestamp(d).normalize() for d in
            USFederalHolidayCalendar().holidays(lo.tz_localize(None), hi.tz_localize(None))}


def cot_release_times(report_dates: pd.Series, calendar: Mapping[str, Any] | None = None
                      ) -> pd.Series:
    """When each Tuesday snapshot was PUBLIC, on the CFTC's real calendar.

    Normal week: the Friday of the snapshot's week, 21:00 UTC. A federal holiday from the
    Monday to the Friday of that week moves the release to the next business day after the
    Friday (the CFTC publishes the following Monday), and a holiday on that Monday moves it again.
    A report date inside a declared disruption (the 2013, 2018-19 and Oct-Nov 2025 shutdowns, whose
    backlogs came out over weeks) is stamped at the disruption's `available_not_before`, the date
    the backlog was fully out; an `exact` entry wins over everything. Late is safe; early is
    lookahead, so every rule here errs late."""
    cal = dict(calendar if calendar is not None else _read_json(COT_CALENDAR, {}))
    exact = {pd.Timestamp(k).normalize(): pd.Timestamp(v) for k, v in
             (cal.get("exact") or {}).items()}
    delays = [(pd.Timestamp(d["report_date_from"]).normalize(),
               pd.Timestamp(d["report_date_to"]).normalize(),
               pd.Timestamp(d["available_not_before"]))
              for d in cal.get("disruptions") or []]
    rd = pd.to_datetime(report_dates, utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    valid = rd.dropna()
    if valid.empty:
        return pd.Series(pd.NaT, index=report_dates.index, dtype="datetime64[ns, UTC]")
    hol = _us_holidays(valid.min() - pd.Timedelta(days=7), valid.max() + pd.Timedelta(days=14))
    out = []
    for d in rd:
        if pd.isna(d):
            out.append(pd.NaT)
            continue
        if d in exact:
            t = exact[d]
            out.append(t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC"))
            continue
        monday = d - pd.Timedelta(days=d.weekday())
        friday = monday + pd.Timedelta(days=4)
        rel = friday
        if any(monday + pd.Timedelta(days=i) in hol for i in range(5)):
            rel = friday + pd.Timedelta(days=3)
            while rel in hol or rel.weekday() >= 5:
                rel += pd.Timedelta(days=1)
        t = rel + pd.Timedelta(hours=COT_RELEASE_HOUR_UTC)
        for lo, hi, nb in delays:
            if lo <= d <= hi:
                nb = nb.tz_localize(None) if nb.tzinfo is not None else nb
                t = max(t, nb)
        out.append(t.tz_localize("UTC"))
    return pd.Series(out, index=report_dates.index, dtype="datetime64[ns, UTC]")


def _main_market(df: pd.DataFrame) -> pd.DataFrame:
    """One row per report date: the largest-OI market. `fetch_tff` matches by substring, so a
    file can carry a cross (EURO FX/JAPANESE YEN) beside the outright; the outright is the one
    with the open interest."""
    oi = "oi" if "oi" in df.columns else "open_interest_all"
    return df.sort_values(oi).groupby("report_date", as_index=False).tail(1)


def cot_features(data_dir: Path = DESK / "data") -> dict[str, pd.DataFrame]:
    """Per-asset COT features on the PIT clock, read from the existing lane's frames."""
    out: dict[str, pd.DataFrame] = {}
    for key, (kind, asset, sign) in COT_MAP.items():
        p = data_dir / f"{key}.parquet"
        if not p.exists():
            continue
        try:
            df = _main_market(pd.read_parquet(p))
        except Exception:
            continue
        df["report_date"] = pd.to_datetime(df["report_date"], utc=True, errors="coerce")
        df = df.dropna(subset=["report_date"]).sort_values("report_date")
        if kind == "tff":
            oi = df["oi"].astype(float)
            lev = (df["lm_l"] - df["lm_s"]) / oi
            dealer = (df["dealer_l"] - df["dealer_s"]) / oi
            am = (df["am_l"] - df["am_s"]) / oi
            swap = pd.Series(np.nan, index=df.index)
            conc = pd.Series(np.nan, index=df.index)
        else:
            oi = df["open_interest_all"].astype(float)
            lev = (df["m_money_positions_long_all"] - df["m_money_positions_short_all"]) / oi
            swap = (df["swap_positions_long_all"] - df["swap__positions_short_all"]) / oi
            dealer = swap
            am = pd.Series(np.nan, index=df.index)
            conc = df["conc_net_le_4_tdr_long_all"].astype(float)
        # A rolling feature at row i reads rows <= i, so row i is usable only once ALL of them
        # are public: the running max, or a backlog's early rows would leak into a later read.
        rel = cot_release_times(df["report_date"]).cummax()
        f = pd.DataFrame({"available_time": rel})
        f["cot.lev_net_pct"] = pct_rank(sign * lev).to_numpy()
        f["cot.lev_net_z"] = zscore(sign * lev).to_numpy()
        f["cot.dealer_net_pct"] = pct_rank(sign * dealer).to_numpy()
        f["cot.swap_net_pct"] = pct_rank(sign * swap).to_numpy()
        f["cot.swap_net_z"] = zscore(sign * swap).to_numpy()
        f["cot.am_net_chg_z"] = zscore((sign * am).diff()).to_numpy()
        f["cot.oi_chg_z"] = zscore(oi.pct_change(fill_method=None)).to_numpy()
        f["cot.conc_top4_pct"] = pct_rank(conc).to_numpy()
        f = f.dropna(subset=["available_time"]).set_index("available_time")
        # A backlog publishes many weeks at one instant; the latest week is the reading then.
        out[asset] = f[~f.index.duplicated(keep="last")]
    return out


#: Macro features: (atlas id, column regex, feature key, transform). The column is found by regex
#: so an OFR or NY Fed rename that keeps the meaning keeps the feature.
_US = "institutional.us."
#: A leading "=" marks an absolute id another lane registered first (one canonical id per dataset).
MACRO_FEATURES: tuple[tuple[str, str, str, str], ...] = tuple((
    a[1:] if a.startswith("=") else _US + a, b, c, d) for a, b, c, d in (
    ("nyfed.repo_reverse_repo_operations", r"reverse", "nyfed.rrp_chg_z", "chg_z"),
    ("fed.rrp_overnight", r"on_rrp", "nyfed.rrp_chg_z", "chg_z"),
    ("nyfed.securities_lending_soma", r".", "nyfed.seclending_demand_z", "z"),
    ("nyfed.primary_dealer_statistics", r"pdposgst", "nyfed.pd_net_positions_z", "z"),
    ("nyfed.primary_dealer_statistics", r"pdft", "nyfed.pd_fails_z", "z"),
    ("nyfed.reference_rates", r"sofr|tgcr|bgcr", "ofr.repo_rate_spread_z", "spread_z"),
    ("ofr.short_term_funding_monitor", r"rate", "ofr.repo_rate_spread_z", "spread_z"),
    ("ofr.short_term_funding_monitor", r"vol", "ofr.repo_volume_chg_z", "chg_z"),
    ("ofr.hedge_fund_monitor", r"lev", "ofr.hf_leverage_z", "z"),
    ("ofr.hedge_fund_monitor", r"repo", "ofr.hf_repo_borrowing_z", "z"),
    ("=fed_h41", r"custody_total", "fed.custody_chg_z", "chg_z"),
    ("fed.h8_bank_balance_sheet", r"bank_securities", "h8.securities_chg_z", "chg_z"),
    ("treasury.auction_investor_class", r"indirect_share", "treasury.auction_indirect_z", "z"),
    ("finra.regsho_daily_short_volume", r"short_volume_ratio", "finra.short_volume_ratio_z", "z"),
    ("sec.fails_to_deliver", r"fails_shares", "sec.ftd_z", "z"),
))


def macro_features(rows: Iterable[Mapping[str, Any]] | None = None
                   ) -> dict[str, tuple[pd.Series, str]]:
    """Asset-independent features: key -> (series on available_time, source id). A frame that is
    not FIRST_RELEASE (a revised series read at its latest vintage) is UNMEASURED here."""
    by_id = {str(r.get("id")): r for r in (load_roster() if rows is None else rows)}
    out: dict[str, tuple[pd.Series, str]] = {}
    for sid, rx, key, how in MACRO_FEATURES:
        if key in out:
            continue          # the first measured source for a key wins; the next is a fallback
        df = read_frame(sid)
        if df is None or len(df) < MIN_OBS or not pit_ok(df, by_id.get(sid)):
            continue
        cols = [c for c in signal_columns(df) if re.search(rx, c, re.I)]
        if not cols:
            continue
        s = df.set_index("available_time")[cols].astype(float)
        # dispersion across repo benchmarks, or the one column
        v = s.max(axis=1) - s.min(axis=1) if how == "spread_z" and len(cols) >= 2 else s[cols[0]]
        v = v[~v.index.duplicated(keep="last")].dropna()
        f = explode(v)
        col = {"chg_z": "chg_z", "z": "z", "spread_z": "z"}[how]
        out[key] = (f[col].dropna(), sid)
    return out


def price_features(asset: str, cot: pd.DataFrame | None) -> dict[str, pd.Series]:
    """Features read off the desk's own bars: drawdown z and positioning-vs-price divergence.
    Daily closes, shifted one day so a broker-time bar cannot lead the UTC clock."""
    try:
        from research import proposer_common as pc
        bars = pc.bars(asset)
    except Exception:
        bars = None
    if bars is None or bars.empty:
        return {}
    close = bars["close"].astype(float).resample("1D").last().dropna()
    close.index = close.index + pd.Timedelta(days=1)
    dd = close / close.rolling(60, min_periods=20).max() - 1.0
    out = {"price.drawdown_z": -zscore(dd, 250)}
    if cot is not None and "cot.lev_net_pct" in cot:
        ret4w = close.pct_change(20, fill_method=None)
        pos = carry_forward(cot["cot.lev_net_pct"], pd.DatetimeIndex(close.index))
        # Crowded long while price fails to advance: high positioning percentile, low return rank.
        out["price.div_vs_positioning"] = (pos - pct_rank(ret4w, 250)).astype(float)
    return out


def calendar_features(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Deterministic calendar flows: month end (pension rebalance, fixing concentration) and the
    third-Friday index/option expiry, both known in advance and therefore lookahead-free."""
    if len(index) == 0:
        return {}
    idx = pd.DatetimeIndex(index)
    bme = (idx + pd.offsets.BMonthEnd(0)).normalize()
    days_to_me = (bme - idx.normalize()).days
    third_fri = [(d.weekday() == 4 and 15 <= d.day <= 21 and d.month % 3 == 0) for d in idx]
    return {"calendar.month_end": pd.Series((days_to_me <= 2).astype(float), index=idx),
            "calendar.index_event": pd.Series(np.asarray(third_fri, dtype=float), index=idx)}


# =========================================================================== latent states
def _as_z(key: str, v: float) -> float:
    """Every input on one scale: a percentile maps to an equivalent z, a z is clipped to +/-3."""
    if key.endswith("_pct") or key.endswith(".pct"):
        v = (v - 0.5) * 3.5
    if key.startswith("calendar."):
        v = 2.0 * v
    return float(max(-3.0, min(3.0, v)))


def fuse(state: Mapping[str, Any], inputs: Mapping[str, float]) -> dict[str, Any]:
    """P(state) from stated evidence weights, in log-odds, with a 95% interval.

    Every UNMEASURED input still costs its weight in variance: an input the desk cannot see is a
    N(0,1) unknown, so a state built on one of four inputs is wide and says so. `coverage` is the
    measured share of total weight. Below `min_inputs` the state is not emitted at all, and a
    calendar input never counts toward it: the calendar is known for every date ever, so a state
    that rested on it alone (passive_forced_flow before the ICI flow is ingested) could never read
    UNMEASURED and would publish a date as if it were an observation of the actor."""
    logit = 0.0
    var = 0.0
    wsum = wmeas = 0.0
    n = 0
    for key, sign, w in state["evidence"]:
        wsum += w
        v = inputs.get(key)
        if v is None or not math.isfinite(v):
            var += w * w
            continue
        if not key.startswith("calendar."):
            n += 1
        wmeas += w
        logit += sign * w * _as_z(key, v)
        var += (0.35 * w) ** 2                  # a measured input is itself a noisy proxy
    if n < int(state.get("min_inputs", 1)):
        return {"p": None, "reason": f"UNMEASURED: {n} of {len(state['evidence'])} inputs"}
    sd = math.sqrt(var)
    sig = lambda x: 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))  # noqa: E731
    return {"p": round(sig(logit), 4), "lo": round(sig(logit - 1.96 * sd), 4),
            "hi": round(sig(logit + 1.96 * sd), 4), "coverage": round(wmeas / wsum, 3),
            "n_inputs": n}


def dealer_gamma_posterior(bars: pd.DataFrame | None, *, window_days: int = 5
                           ) -> pd.DataFrame | None:
    """Posterior over (long, neutral, short) dealer gamma from observed intraday behaviour.

    Long dealer gamma dampens: hourly returns mean-revert (negative lag-1 autocorrelation).
    Short dealer gamma amplifies: they trend (positive). Each day's trailing autocorrelation is
    scored under three Gaussians at -0.10 / 0 / +0.10 with the sampling error 1/sqrt(n), from a
    flat prior -- the public OI cannot say which side the dealer holds, so no prior pretends to."""
    if bars is None or bars.empty or "close" not in bars:
        return None
    r = np.log(bars["close"].astype(float)).diff().dropna()
    n = int(window_days * 23)
    ac = r.rolling(n, min_periods=30).corr(r.shift(1))
    daily = ac.groupby(ac.index.normalize()).last().dropna()
    if daily.empty:
        return None
    se = 1.0 / math.sqrt(n)
    means = np.array([-0.10, 0.0, 0.10])
    lik = np.exp(-0.5 * ((daily.to_numpy()[:, None] - means[None, :]) / se) ** 2)
    tot = lik.sum(axis=1, keepdims=True)
    post = np.where(tot > 0, lik / np.where(tot > 0, tot, 1.0), 1.0 / 3.0)
    return pd.DataFrame({"gamma_autocorr": daily.to_numpy(),
                         "p_dealer_long_gamma": post[:, 0], "p_dealer_neutral": post[:, 1],
                         "p_dealer_short_gamma": post[:, 2]},
                        index=pd.DatetimeIndex(daily.index + pd.Timedelta(days=1),
                                               name="available_time"))


def carry_forward(s: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    """As-of join with a staleness horizon: a reading is carried forward for 2.5x the series'
    own median spacing (at least three days) and is UNMEASURED after that. A weekly COT read is
    good for ~17 days; a quarterly OFR read for ~7 months; a stopped feed goes dark, not flat."""
    s = s.dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        return pd.Series(np.nan, index=idx)
    gaps = pd.Series(s.index).diff().dropna()
    spacing = gaps.median() if not gaps.empty else pd.Timedelta(days=7)
    horizon = max(pd.Timedelta(days=3), spacing * 2.5)
    stamp = pd.Series(s.index, index=s.index).reindex(idx, method="ffill")
    out = s.reindex(idx, method="ffill")
    return out.where((idx - pd.DatetimeIndex(stamp)) <= horizon)


#: The atlas id the COT features are credited to (one canonical id: the US pack's COT spine).
COT_SOURCE_ID = "pack_us_us_cftc_cot"
#: Feature prefixes that are not an atlas source: the desk's own bars and the calendar.
DERIVED_SOURCES = {"price.": "desk_bars", "calendar.": "calendar"}


def state_attribution(state: Mapping[str, Any], panel: pd.DataFrame,
                      feature_source: Mapping[str, str]) -> dict[str, Any]:
    """The sources a state cell is TRULY built from: the evidence inputs measured on at least
    MIN_VINTAGES dates, each mapped to its atlas id. The primary source is the heaviest measured
    input from the atlas (the desk's bars and the calendar are inputs, never a credited source)."""
    measured = []
    for key, _sign, w in state["evidence"]:
        if key in panel.columns and int(panel[key].notna().sum()) >= MIN_VINTAGES:
            measured.append((w, key, feature_source.get(key, "")))
    atlas = [(w, k, sid) for w, k, sid in measured if sid and sid not in DERIVED_SOURCES.values()]
    atlas.sort(key=lambda t: -t[0])
    return {"source_id": atlas[0][2] if atlas else "",
            "source_ids": sorted({sid for _w, _k, sid in atlas}),
            "inputs": sorted(k for _w, k, _sid in measured)}


def build_states(assets: Iterable[str] | None = None) -> dict[str, pd.DataFrame]:
    """One state frame per MT5 asset on the PIT clock, written to the lake."""
    onto = _ontology()
    cot = cot_features()
    macro = macro_features()
    want = set(assets) if assets else {a for s in onto.LATENT_STATES for a in s["assets"]}
    out: dict[str, pd.DataFrame] = {}
    for asset in sorted(want):
        cols: dict[str, pd.Series] = {}
        fsrc: dict[str, str] = {}
        if asset in cot:
            cols.update({k: cot[asset][k] for k in cot[asset].columns})
            fsrc.update(dict.fromkeys(cot[asset].columns, COT_SOURCE_ID))
        for key, (s, sid) in macro.items():
            cols[key] = s
            fsrc[key] = sid
        cols.update(price_features(asset, cot.get(asset)))
        if not cols:
            continue
        idx = sorted(set().union(*[set(s.dropna().index) for s in cols.values()]))
        if not idx:
            continue
        idx = pd.DatetimeIndex(idx)
        cols.update(calendar_features(idx))
        # A value older than its staleness horizon is UNMEASURED, not carried forever.
        panel = pd.DataFrame({k: carry_forward(v, idx) for k, v in cols.items()})
        for k in panel.columns:
            for pre, name in DERIVED_SOURCES.items():
                if k.startswith(pre):
                    fsrc[k] = name
        rec = {}
        attribution: dict[str, dict[str, Any]] = {}
        for st in onto.LATENT_STATES:
            if asset not in st["assets"]:
                continue
            attribution[f"p_{st['id']}"] = state_attribution(st, panel, fsrc)
            ps, lo, hi, cov = [], [], [], []
            for _t, row in panel.iterrows():
                r = fuse(st, {k: row[k] for k in panel.columns if pd.notna(row[k])})
                ps.append(r.get("p"))
                lo.append(r.get("lo"))
                hi.append(r.get("hi"))
                cov.append(r.get("coverage"))
            rec[f"p_{st['id']}"] = ps
            rec[f"p_{st['id']}_lo"] = lo
            rec[f"p_{st['id']}_hi"] = hi
            rec[f"cov_{st['id']}"] = cov
        frame = pd.DataFrame(rec, index=idx).astype(float)
        if asset in ("US500", "NAS100", "US30", "US2000"):
            with contextlib.suppress(Exception):
                from research import proposer_common as pc
                g = dealer_gamma_posterior(pc.bars(asset))
                if g is not None:
                    frame = frame.join(pd.DataFrame({c: carry_forward(g[c], idx)
                                                     for c in g.columns}), how="left")
        frame = frame.dropna(axis=1, how="all").dropna(axis=0, how="all")
        if frame.empty:
            continue
        frame.index.name = "event_time"
        sid = f"{STATE_SERIES_PREFIX}.{asset}"
        f2 = frame.reset_index()
        # States are computed from inputs already on their PIT clock: available == event. Every
        # input passed pit_ok, so the state is first-release too.
        write_frame(sid, f2, lag_hours=0.0)
        f2 = f2.set_index("event_time")
        f2.attrs["attribution"] = attribution
        f2.attrs["sources"] = sorted({s_ for a_ in attribution.values()
                                      for s_ in a_["source_ids"]})
        out[asset] = f2
    return out


# =========================================================================== cells
def _culture(row: Mapping[str, Any] | None) -> dict[str, str]:
    row = row or {}
    return {k: str(row.get(k) or "") for k in ("source_culture", "participant_structure",
                                               "failure_mode_hypothesis", "crowding_prior")}


def _may_hunt(symbol: str) -> bool:
    try:
        import universe_policy as up
    except ImportError:
        try:
            from research import universe_policy as up  # type: ignore[no-redef]
        except ImportError:
            return False
    return bool(up.may_hypothesise(symbol))


def planned_cells(states: Mapping[str, pd.DataFrame], rows: list[dict[str, Any]]
                  ) -> list[dict[str, Any]]:
    """Every conditioner cell this pass owes: the latent states on their assets, and every raw
    atlas frame on disk against its declared targets (the dataset rule: no frame goes unfed).

    A column mints only with MIN_VINTAGES published readings, only from a FIRST_RELEASE frame,
    and each state cell is credited to the sources that state is actually built from."""
    by_id = {r["id"]: r for r in rows}
    plans: list[dict[str, Any]] = []
    for asset, frame in states.items():
        if not _may_hunt(asset):
            continue
        attribution = frame.attrs.get("attribution") or {}
        for col in frame.columns:
            if not col.startswith("p_") or col.endswith(("_lo", "_hi")):
                continue
            if int(frame[col].notna().sum()) < MIN_VINTAGES:
                continue
            att = attribution.get(col) or {"source_id": "", "source_ids": [], "inputs": []}
            culture = _culture(by_id.get(att["source_id"]))
            culture["participant_structure"] = "institutional"
            plans.append({"source": f"{STATE_SERIES_PREFIX}.{asset}", "signal": col,
                          "symbol": asset, "source_id": att["source_id"] or LEG,
                          "source_ids": list(att["source_ids"]), "inputs": list(att["inputs"]),
                          "culture": culture, "kind": "state"})
    for r in rows:
        df = read_frame(str(r["id"]))
        if df is None or len(df) < MIN_VINTAGES or not pit_ok(df, r):
            continue
        sigs = [c for c in signal_columns(df) if vintages(df, c) >= MIN_VINTAGES][:6]
        for sym in r.get("targets") or []:
            if not _may_hunt(sym):
                continue
            for sig in sigs:
                plans.append({"source": str(r["id"]), "signal": sig, "symbol": sym,
                              "source_id": str(r["id"]), "source_ids": [str(r["id"])],
                              "inputs": [sig], "culture": _culture(r), "kind": "raw"})
    return plans


def _conditioner_fn() -> Callable[..., pd.Series | None] | None:
    for name in ("mt5desk.family_exogenous_conditioner", "family_exogenous_conditioner"):
        with contextlib.suppress(ImportError):
            import importlib
            return importlib.import_module(name).conditioner  # type: ignore[no-any-return]
    return None


def _bars(symbol: str) -> pd.DataFrame | None:
    with contextlib.suppress(Exception):
        from research import proposer_common as pc
        b = pc.bars(symbol)
        return b if b is not None and not b.empty else None
    return None


def learn_side(source: str, signal: str, transform: str, threshold: float, symbol: str, *,
               bars: pd.DataFrame | None = None, cond: pd.Series | None = None,
               horizon_bars: int = 24) -> dict[str, Any] | None:
    """The side a cell trades, learned on the TRAINING span only.

    The family reads the conditioner exactly as `conditioner()` builds it (same transform, same
    publication-day lag) and goes `side_when_high` when it is above +threshold and the opposite
    below -threshold. So the edge is side_when_high * E[sign(m) * forward return | |m| >= thr];
    its sign on the first TRAIN_FRACTION of the joint history is the side. The span after
    `train_end` never touches the choice, so the gauntlet's out-of-sample stays out of sample.
    None -- no cell this pass -- when the family, the bars or MIN_TRAIN_EVENTS are missing."""
    if cond is None:
        fn = _conditioner_fn()
        cond = fn(source, signal, transform) if fn is not None else None
    bars = _bars(symbol) if bars is None else bars
    if cond is None or bars is None or bars.empty or "close" not in bars:
        return None
    close = bars["close"].astype(float)
    close = close[~close.index.duplicated(keep="last")].sort_index()
    fwd = np.log(close.shift(-horizon_bars) / close)
    try:
        m = cond.reindex(cond.index.union(close.index)).ffill().reindex(close.index)
    except (TypeError, ValueError):
        return None
    joint = pd.DataFrame({"m": m, "fwd": fwd}).dropna()
    if joint.empty:
        return None
    cut = joint.index[0] + (joint.index[-1] - joint.index[0]) * TRAIN_FRACTION
    train = joint[joint.index <= cut]
    ev = train[train["m"].abs() >= abs(float(threshold))]
    if len(ev) < MIN_TRAIN_EVENTS:
        return None
    edge = float((np.sign(ev["m"]) * ev["fwd"]).mean())
    return {"side": 1 if edge >= 0 else -1, "train_end": pd.Timestamp(cut).isoformat(),
            "train_events": len(ev), "train_edge": round(edge, 6)}


def _credit(credited: dict[str, str], ids: Iterable[str]) -> None:
    at = now_utc().isoformat(timespec="seconds")
    for i in ids:
        if i:
            credited[i] = at


def emit_cells(plans: list[dict[str, Any]], *, deadline: float, dry_run: bool = False,
               side_fn: Callable[..., dict[str, Any] | None] | None = None) -> dict[str, Any]:
    """Through the one door, once per cell key, ever. The key carries no side (a cell is ONE
    bet with its learned side), so no pass inflates a search count and no mirror is charged.

    `credited` maps each atlas id to the last time it was FED: a cell enqueued from it, or a
    pass that found every cell it owes already enqueued. ACTIVE reads that stamp (30 days)."""
    side_fn = side_fn or learn_side
    prev = _read_json(EMITTED, {})
    done = set(prev.get("keys") or [])
    raw_credit = prev.get("credited") or {}
    credited: dict[str, str] = (dict(raw_credit) if isinstance(raw_credit, Mapping)
                                else {})  # a list from the pre-decay ledger carries no time
    made = created = skipped = unlearned = 0
    errors: list[str] = []
    culture_rows: list[dict[str, Any]] = []
    for p in plans:
        grid = TRANSFORMS_STATE if p["kind"] == "state" else TRANSFORMS_RAW
        owed = fed = 0
        for tf, thr in grid:
            learned: dict[str, Any] | None = None
            for chart in CHARTS:
                key = f"{p['source']}|{p['signal']}|{tf}|{p['symbol']}|{chart}"
                owed += 1
                if key in done:
                    skipped += 1
                    fed += 1
                    continue
                if time.monotonic() > deadline:
                    break
                if learned is None:
                    learned = side_fn(p["source"], p["signal"], tf, thr, p["symbol"])
                    if learned is None:
                        unlearned += 1
                        break
                made += 1
                if dry_run:
                    continue
                side = int(learned["side"])
                try:
                    from libs.moat.registry import enqueue_candidate
                    mech = (f"{p['signal']} of {p['source']} (public institutional footprint) "
                            f"conditions {p['symbol']}: side {side:+d} when high, the side "
                            f"learned on data through {learned['train_end'][:10]} "
                            f"({learned['train_events']} events); only later data judges it")
                    cid, new = enqueue_candidate(
                        family="exogenous_conditioner", symbol=p["symbol"],
                        params={"source": p["source"], "signal": p["signal"],
                                "transform": tf, "threshold": thr, "side_when_high": side},
                        origin=LEG, mechanism=mech, chart=chart, horizon=chart,
                        source_id=p["source_id"], generator=LEG, department="information",
                        asset_class="", transformation="institutional_state"
                        if p["kind"] == "state" else "institutional_series",
                        required_data=[f"desks/mt5/data/lake/series/{p['source']}.csv"],
                        pit_status="STAMPED", causal_rationale=mech,
                        falsifier=(f"the {tf} of {p['source']}.{p['signal']} beyond {thr:g} has "
                                   f"no measurable relation to {p['symbol']} at {chart} after "
                                   f"{learned['train_end'][:10]}"), **p["culture"])
                    created += int(bool(new))
                    done.add(key)
                    fed += 1
                    culture_rows.append({"cell_id": cid, "source_id": p["source_id"],
                                         "source_ids": p["source_ids"], "inputs": p["inputs"],
                                         "side_fit": learned, "origin": LEG, **p["culture"]})
                except Exception as exc:
                    errors.append(f"{key}: {type(exc).__name__}: {str(exc)[:60]}")
        if owed and fed == owed and not dry_run:
            _credit(credited, p["source_ids"])
    if not dry_run:
        _write_json(EMITTED, {"at": now_utc().isoformat(timespec="seconds"),
                              "keys": sorted(done), "credited": dict(sorted(credited.items()))})
        if culture_rows:
            CULTURE_LOG.parent.mkdir(parents=True, exist_ok=True)
            with CULTURE_LOG.open("a", encoding="utf-8") as fh:
                for c in culture_rows:
                    fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return {"cells_attempted": made, "cells_created": created, "already_enqueued": skipped,
            "side_not_learned": unlearned, "errors": errors[:5], "n_errors": len(errors),
            "sources_planned": sorted({p["source_id"] for p in plans}),
            "sources_credited": dict(sorted(credited.items()))}


# =========================================================================== watcher
def watch(rows: list[dict[str, Any]], get: HttpGet | None, deadline: float) -> dict[str, Any]:
    """The future-source watcher (principal 18:08Z item 16): every WATCH row's probe page is read
    and its markers searched. A marker found flips the row to DISCOVERED_NOT_INGESTED in the
    watch state and names it in the report -- onboarding needs no code redesign, only a recipe.
    Every fetched row's recipe failing twice running is flagged BROKEN, so a moved dataset is
    noticed rather than silently going stale."""
    st = _read_json(WATCH_STATE, {})
    for r in rows:
        f = r.get("fetch") or {}
        if f.get("kind") != "watch" or get is None or time.monotonic() > deadline:
            continue
        code, body, err = get(str(f["probe"]))
        text = body.decode("utf-8", "replace") if body else ""
        hits = [m for m in f.get("markers") or [] if m.lower() in text.lower()]
        prev = st.get(r["id"]) or {}
        st[r["id"]] = {"at": now_utc().isoformat(timespec="seconds"), "http": code,
                       "error": err[:120], "markers_found": hits,
                       "status": "DISCOVERED_NOT_INGESTED" if hits else "WATCH",
                       "first_seen": prev.get("first_seen") or (
                           now_utc().isoformat(timespec="seconds") if hits else "")}
    _write_json(WATCH_STATE, st)
    return st


#: Atlas pages probed per pass. A row researched from the web is checked on the box, where the
#: hosts are reachable; the probe is the closure on its URL, not a one-off claim.
URL_PROBES_PER_PASS = 40
URL_STATE_NAME = "url_checks.json"


def verify_urls(rows: list[dict[str, Any]], get: HttpGet | None, deadline: float
                ) -> dict[str, Any]:
    """Probe the page of every row that has no fetch recipe, stalest first, and record what came
    back. Two failures running mark it BROKEN, which puts it back in the search queue as a
    `fix the URL` ask; a 2xx marks it VERIFIED. Without a transport nothing is claimed."""
    path = STATE_DIR / URL_STATE_NAME
    st = _read_json(path, {})
    todo = sorted((r for r in rows if r.get("url") and not (r.get("fetch") or {}).get("kind")),
                  key=lambda r: str((st.get(r["id"]) or {}).get("at") or ""))
    for r in todo[:URL_PROBES_PER_PASS]:
        if get is None or time.monotonic() > deadline:
            break
        code, _body, err = get(str(r["url"]))
        prev = st.get(r["id"]) or {}
        ok = _ok(code, err)
        fails = 0 if ok else int(prev.get("fails") or 0) + 1
        st[r["id"]] = {"at": now_utc().isoformat(timespec="seconds"), "http": code,
                       "error": err[:120], "fails": fails,
                       "status": "VERIFIED" if ok else ("BROKEN" if fails >= 2 else "RETRY")}
    _write_json(path, st)
    return st


# =========================================================================== coverage
def _fresh(ts: Any, now: datetime) -> bool:
    try:
        t = pd.Timestamp(ts)
    except (ValueError, TypeError):
        return False
    if pd.isna(t):
        return False
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    return bool(now - t.to_pydatetime() <= ACTIVE_WINDOW)


def frame_refreshed_at(r: Mapping[str, Any]) -> datetime | None:
    """When the row's frame was last written: its lake CSV, or the newest file of an existing
    lane's glob (the COT parquet). None when there is no frame."""
    f = r.get("fetch") or {}
    paths = ([q for g in (f.get("globs") or [f.get("glob")]) if g for q in ROOT.glob(str(g))]
             if f.get("kind") == "lake_parquet" else [series_path(str(r["id"]))])
    times = []
    for q in paths:
        with contextlib.suppress(OSError):
            times.append(q.stat().st_mtime)
    return datetime.fromtimestamp(max(times), tz=UTC) if times else None


def row_status(r: Mapping[str, Any], fetch_state: Mapping[str, Any],
               watch_state: Mapping[str, Any], credited: Mapping[str, Any] | set[str],
               *, now: datetime | None = None) -> str:
    """Measured, not declared, and it DECAYS: ACTIVE needs a frame refreshed within 30 days AND
    the source fed (a cell enqueued, or every owed cell already in) within 30 days. A source that
    stopped updating or stopped feeding falls back to its declared status on day 31."""
    sid = str(r["id"])
    now = now or now_utc()
    declared = str(r.get("declared_status") or "DISCOVERED_NOT_INGESTED")
    if declared == "WATCH":
        return str((watch_state.get(sid) or {}).get("status") or "WATCH")
    refreshed = frame_refreshed_at(r)
    fed_at = credited.get(sid) if isinstance(credited, Mapping) else None
    if refreshed is not None and _fresh(refreshed, now) and fed_at and _fresh(fed_at, now):
        return "ACTIVE"
    if declared in ("PAID_PUBLIC_PROXY", "BLOCKED_SUBSTITUTE", "NOT_PUBLISHED",
                    "TESTED_NO_INFORMATION", "NOT_RELEVANT"):
        return declared
    return "DISCOVERED_NOT_INGESTED"


def coverage(rows: list[dict[str, Any]], *, fetch_state: Mapping[str, Any] | None = None,
             watch_state: Mapping[str, Any] | None = None,
             emitted_sources: Mapping[str, Any] | None = None,
             rulings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The jurisdiction x class grid, one status per cell; the role grid; triangulation; the
    equivalence-search queue that asks each jurisdiction for what its peers publish."""
    onto = _ontology()
    fs = fetch_state or {}
    ws = watch_state or {}
    em = emitted_sources or {}
    doc = dict(rulings if rulings is not None else _read_json(RULINGS, {}))
    # {"cells": {"j|class": ruling}, "roles": {"j|role": ruling}}; a flat {"j|class": ...} map
    # (the first shape) is read as cells.
    rul = dict(doc.get("cells") or {}) if "cells" in doc or "roles" in doc else doc
    role_rul = dict(doc.get("roles") or {})
    rank = {s: i for i, s in enumerate(("ACTIVE", "TESTED_NO_INFORMATION",
                                        "DISCOVERED_NOT_INGESTED", "PAID_PUBLIC_PROXY",
                                        "BLOCKED_SUBSTITUTE", "WATCH", "NOT_PUBLISHED",
                                        "NOT_RELEVANT"))}
    status_of = {str(r["id"]): row_status(r, fs, ws, em) for r in rows}
    grid: dict[str, dict[str, dict[str, Any]]] = {}
    roles: dict[str, dict[str, list[str]]] = {}
    for j in onto.coverage_jurisdictions():
        grid[j] = {}
        roles[j] = {role: [] for role in onto.JURISDICTION_ROLES}
        for cls in onto.CLASS_IDS:
            ids = [str(r["id"]) for r in rows if r.get("jurisdiction") == j
                   and r.get("source_class") == cls]
            ruled = rul.get(f"{j}|{cls}")
            if ids:
                st = min((status_of[i] for i in ids), key=lambda s: rank.get(s, 99))
                if st == "WATCH":
                    st = "DISCOVERED_NOT_INGESTED"
            elif ruled:
                st = str(ruled.get("status") if isinstance(ruled, Mapping) else ruled)
            elif j != "global" and cls in onto.GLOBAL_ONLY_CLASSES:
                st = "NOT_RELEVANT"
            else:
                st = onto.UNSEARCHED
            grid[j][cls] = {"status": st, "sources": ids}
        for r in rows:
            if r.get("jurisdiction") == j:
                for role in onto.roles_of(r):
                    roles[j][role].append(str(r["id"]))
    counts: dict[str, int] = {}
    for j in grid.values():
        for c in j.values():
            counts[c["status"]] = counts.get(c["status"], 0) + 1
    queue = []
    for j, cells in grid.items():
        for cls, c in cells.items():
            if c["status"] != onto.UNSEARCHED:
                continue
            peers = [pid for jj, cc in grid.items() if jj != j for pid in cc[cls]["sources"]][:3]
            if peers:
                queue.append({"jurisdiction": j, "source_class": cls, "peer_examples": peers,
                              "ask": f"does {j} publish a local equivalent of {cls}? "
                                     "ingest it, else name a public proxy, else rule "
                                     "NOT_PUBLISHED"})
    for j, rr in roles.items():
        if j == "global" or j in onto.REGION_PACKS:
            continue          # region packs owe classes, not a national institution set
        for role, ids in rr.items():
            if not ids and not role_rul.get(f"{j}|{role}"):
                queue.append({"jurisdiction": j, "role": role,
                              "ask": f"name {j}'s {role.replace('_', ' ')} and its public "
                                     "datasets, or rule that it publishes none"})
    tri = {}
    for com, views in onto.COMMODITY_TRIANGULATION.items():
        tri[com] = {v: {i: status_of.get(i, "NOT_IN_ATLAS") for i in ids}
                    for v, ids in views.items()}
        tri[com]["views_covered"] = sum(
            1 for v, ids in views.items()
            if any(status_of.get(i) in ("ACTIVE", "DISCOVERED_NOT_INGESTED") for i in ids))
    return {"grid": grid, "status_counts": counts, "roles": roles,
            "role_gaps": {j: sorted(k for k, v in rr.items()
                                    if not v and not role_rul.get(f"{j}|{k}"))
                          for j, rr in roles.items()},
            "role_rulings": {k: (v.get("status") if isinstance(v, Mapping) else str(v))
                             for k, v in role_rul.items()},
            "row_status": status_of, "search_queue": queue, "triangulation": tri,
            "n_cells": sum(len(v) for v in grid.values())}


def state_ages(states: Mapping[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """The age of each latent state per asset (CRO D37 reads this): hours since the last
    available_time at which the state was measured, and the latest reading with its interval."""
    now = pd.Timestamp(now_utc())
    out: dict[str, dict[str, Any]] = {}
    for asset, f in states.items():
        out[asset] = {}
        for col in f.columns:
            if not col.startswith("p_") or col.endswith(("_lo", "_hi")):
                continue
            s = f[col].dropna()
            if s.empty:
                continue
            t = pd.Timestamp(s.index[-1])
            t = t.tz_localize("UTC") if t.tzinfo is None else t
            sid = col[2:]
            age = now - t
            last = {"p": round(float(s.iloc[-1]), 4),
                    "lo": _last(f, f"{col}_lo"), "hi": _last(f, f"{col}_hi"),
                    "coverage": _last(f, f"cov_{sid}")}
            row: dict[str, Any] = {"as_of": t.isoformat(),
                                   "age_hours": round(age.total_seconds() / 3600.0, 1)}
            if age > STATE_MAX_AGE:
                # Past its age limit a state is UNMEASURED everywhere it is published; the last
                # reading stays visible for the audit, never as a live p.
                row.update({"p": None, "lo": None, "hi": None, "coverage": None,
                            "status": "UNMEASURED",
                            "reason": f"stale: {row['age_hours']}h > "
                                      f"{STATE_MAX_AGE.total_seconds() / 3600:.0f}h",
                            "last_reading": last})
            else:
                row.update({**last, "status": "MEASURED"})
            out[asset][sid] = row
    return out


def regimes(ages: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> dict[str, dict[str, str]]:
    """The discrete reading a consumer can react to without re-solving on every decimal: HIGH
    when the whole 95% interval sits above one half and p > 0.7, LOW when it sits below and
    p < 0.3, else NEUTRAL; the dealer scenarios report their argmax. `allocator_trigger` hashes
    this block, so the book re-solves when a state CROSSES, never when it drifts."""
    scen = set(_ontology().DEALER_GAMMA_SCENARIOS)
    out: dict[str, dict[str, str]] = {}
    for asset, states in ages.items():
        row: dict[str, str] = {}
        gamma = {k: v["p"] for k, v in states.items() if k in scen and v.get("p") is not None}
        for sid, v in states.items():
            if sid in scen:
                continue
            p, lo, hi = v.get("p"), v.get("lo"), v.get("hi")
            if p is None:
                row[sid] = "UNMEASURED"
                continue
            row[sid] = ("HIGH" if lo is not None and lo > 0.5 and p > 0.7 else
                        "LOW" if hi is not None and hi < 0.5 and p < 0.3 else "NEUTRAL")
        if gamma:
            row["dealer_gamma"] = max(gamma, key=lambda k: gamma[k])
        elif any(k in scen for k in states):
            row["dealer_gamma"] = "UNMEASURED"
        out[asset] = row
    return out


def _last(f: pd.DataFrame, col: str) -> float | None:
    if col not in f.columns:
        return None
    s = f[col].dropna()
    return round(float(s.iloc[-1]), 4) if not s.empty else None


def load_states() -> dict[str, pd.DataFrame]:
    out = {}
    for p in sorted(SERIES.glob(f"{STATE_SERIES_PREFIX}.*.csv")):
        df = read_frame(p.stem)
        if df is not None:
            out[p.stem.split(".", 1)[1]] = df.set_index("available_time")
    return out


# =========================================================================== the pass
def run(budget_s: float = 300.0, *, offline: bool = False, dry_run: bool = False,
        get: HttpGet | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    rows = load_roster()
    transport = get if get is not None else (None if offline else polite_get(deadline))
    fs = fetch_all(rows, get=transport, deadline=t0 + budget_s * 0.45)
    ws = watch(rows, transport, deadline=t0 + budget_s * 0.50)
    urls = verify_urls(rows, transport, deadline=t0 + budget_s * 0.58)
    states = build_states()
    plans = planned_cells(states, rows)
    cells = emit_cells(plans, deadline=deadline, dry_run=dry_run)
    emitted_sources = dict(cells["sources_credited"])
    cov = coverage(rows, fetch_state=fs, watch_state=ws, emitted_sources=emitted_sources)
    broken = sorted(k for k, v in urls.items() if isinstance(v, Mapping)
                    and v.get("status") == "BROKEN")
    cov["search_queue"].extend({"source_id": k, "ask": "the atlas page no longer answers: find "
                                "the dataset's current URL, else rule the row"} for k in broken)
    ages = state_ages(states or load_states())
    fetched = {k: v for k, v in fs.items() if isinstance(v, Mapping)}
    # THE DATASET RULE (principal 2026-09-30 15:33Z): a frame on disk with no cell is UNFED.
    unfed = sorted(sid for sid, st in cov["row_status"].items()
                   if series_path(sid).exists() and st != "ACTIVE")
    report = {
        "at": now_utc().isoformat(timespec="seconds"), "leg": LEG,
        "atlas": {"rows": len(rows), "jurisdictions": len({r.get('jurisdiction') for r in rows}),
                  "with_recipe": sum(1 for r in rows if (r.get("fetch") or {}).get("kind")
                                     in RECIPES)},
        "status_counts": cov["status_counts"], "n_cells": cov["n_cells"],
        "grid": {j: {c: v["status"] for c, v in cells_.items()}
                 for j, cells_ in cov["grid"].items()},
        "grid_sources": {j: {c: v["sources"] for c, v in cells_.items() if v["sources"]}
                         for j, cells_ in cov["grid"].items()},
        "role_gaps": cov["role_gaps"],
        "search_queue_n": len(cov["search_queue"]),
        "url_checks": {"counts": _count_by([v for v in urls.values() if isinstance(v, Mapping)],
                                           "status"),
                       "unchecked": sum(1 for r in rows if r.get("url")
                                        and not (r.get("fetch") or {}).get("kind")
                                        and r["id"] not in urls),
                       "broken": broken},
        "role_rulings_n": len(cov["role_rulings"]),
        "search_queue_by_class": _count_by(cov["search_queue"], "source_class"),
        "search_queue_by_role": _count_by(cov["search_queue"], "role"),
        "search_queue_head": cov["search_queue"][:40],
        "search_queue_path": "desks/mt5/data/institutional/search_queue.json",
        "triangulation": cov["triangulation"], "row_status": cov["row_status"],
        "fetch": fetched, "watch": ws, "latent_state_age": ages,
        "cells": cells, "unfed": unfed, "unfed_count": len(unfed),
        "offline": bool(offline and get is None), "elapsed_s": round(time.monotonic() - t0, 1),
        "rule": ("one status per jurisdiction x class cell; ACTIVE is measured (a frame "
                 "refreshed AND fed within 30 days), never declared, and decays; UNSEARCHED is "
                 "red and every UNSEARCHED cell a peer jurisdiction covers is in search_queue; "
                 "states are probabilities with 95% intervals, UNMEASURED past 7 days; dealer "
                 "gamma is a scenario posterior; only FIRST_RELEASE frames reach a state or a "
                 "cell"),
        "pit": {"state_max_age_hours": STATE_MAX_AGE.total_seconds() / 3600,
                "min_vintages": MIN_VINTAGES,
                "latest_revised_frames": sorted(k for k, v in fetched.items()
                                                if v.get("pit_grade") == LATEST_REVISED)},
    }
    if not dry_run:
        _write_json(SEARCH_QUEUE, {"at": report["at"], "queue": cov["search_queue"]})
        _write_json(REPORT, report)
        _write_json(STATE_REPORT, {"at": report["at"], "states": ages,
                                   "regimes": regimes(ages),
                                   "use": "allocator and conditioner input: P(state) per asset "
                                          "with its interval and evidence coverage; a state "
                                          "absent here is UNMEASURED"})
    return report


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        if r.get(key):
            out[str(r[key])] = out.get(str(r[key]), 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--offline", action="store_true", help="no network; build from frames on disk")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(a.budget_s, offline=a.offline, dry_run=a.dry_run)
    print(json.dumps({k: rep[k] for k in ("at", "atlas", "status_counts", "unfed_count",
                                          "elapsed_s")}, default=str))
    print(json.dumps(rep["cells"], default=str)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
