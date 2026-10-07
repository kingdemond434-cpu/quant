"""POINT-IN-TIME SERIES FROM THE DESK'S OWN DATASETS, for a family that loads its own input.

THE PRINCIPAL, 2026-09-30: every alt, macro or intelligence dataset must feed three uses -- direct
cells, INDIRECT cells (conditioning and interactions on existing families) and allocation state --
and a dataset that feeds no producer is a defect to wire first. The indirect use needs one thing
nothing on the desk had: a single loader that turns ANY dataset with a defensible availability
stamp into a series on the clock at which the desk could first have read it. This is that loader.
`family_dataset_conditioned` reads it at build time; `research/dataset_census` reads it to decide
which datasets carry a usable series at all.

THREE KINDS, each with its own honest stamp -- and a dataset with no stamp gets NO series:

    lake:<pack>    `data/lake/series/<pack>.parquet|csv`, stamped by the lake's PIT envelope
                   (`available_time`). Delegated to `family_exogenous_conditioner.conditioner`,
                   so the lake has exactly one reader.
    cot:<relpath>  `data/<relpath>.parquet` (the CFTC files under `cot*/`). The row carries only
                   `report_date` (a Tuesday); the CFTC publishes on the Friday after. The stamp is
                   the SATURDAY 00:00 UTC after the report date -- after every release time, EST
                   or EDT -- and never the report date, which would be three days of lookahead.
    intel:<seat>   `data/intelligence/<seat>/` under either root: snapshot files a miner wrote.
                   A file's stamp is the time IN ITS NAME (`discoveries_YYYYMMDD_HHMM.json`) -- when
                   the desk fetched it, which is when it knew it; a day rollup
                   (`rollup_YYYYMMDD.jsonl.gz`) is stamped at the END of its day. A file whose name
                   carries no time is not read: an mtime is when git checked it out, not when the
                   desk learnt it.

EVERY SERIES IS THEN LAGGED A FULL PUBLICATION DAY (`lag_hours`, default 24) before it may touch
a bar, for the reason `family_exogenous_conditioner` states: the bar index is broker time under a
UTC tzinfo, two to three hours ahead of UTC, so an unlagged UTC series lands early.

A FIELD is a numeric column (or row key), or `a-b`, the difference of two -- which is how a
positioning file's net long is named without a second copy of the file. An intelligence field may
carry `match` (`symbol=USDJPY`): only the rows whose key equals the value are averaged into the
snapshot's reading. Absence at any step returns None, which callers read as UNMEASURED.
"""
from __future__ import annotations

import gzip
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
DATA = DESK / "data"
INTEL_ROOTS: tuple[Path, ...] = (DATA / "intelligence", ROOT / "data" / "intelligence")

KINDS: tuple[str, ...] = ("lake", "cot", "intel")
DEFAULT_LAG_HOURS = 24
DEFAULT_Z_WINDOW = 250
TRANSFORMS: tuple[str, ...] = ("level", "level_z", "delta", "delta_z")

#: The CFTC report is Tuesday's; release is Friday 15:30 ET. Saturday 00:00 UTC is after it in
#: both EST and EDT, and the extra hours are the price of never reading it early.
COT_AVAILABLE_AFTER = timedelta(days=4)

#: Newest snapshot files read per intelligence dataset. The world crawler holds ~30,000; the
#: series is the newest MAX_SNAPSHOTS readings, and the census says when a dataset hit it.
MAX_SNAPSHOTS = 4000

#: Row keys that are numbers but are not readings: a model's confidence, a calendar coordinate.
NON_SIGNAL_KEYS: frozenset[str] = frozenset({
    "confidence", "month", "year", "day", "hour", "minute", "weekday", "dow", "rank", "priority",
    "version", "page", "n", "count", "index", "idx", "score_version"})

_STAMPED = re.compile(r"(20\d{2})(\d{2})(\d{2})(?:[_T-](\d{2})(\d{2})(\d{2})?)?")
_SNAPSHOT_SUFFIXES = (".json", ".jsonl", ".jsonl.gz", ".json.gz")


def kind_of(dataset: str) -> str | None:
    k, _, rest = str(dataset or "").partition(":")
    return k if k in KINDS and rest else None


# ------------------------------------------------------------------ field arithmetic
def _field(frame: pd.DataFrame, field: str) -> pd.Series | None:
    f = str(field or "")
    if f in frame.columns:
        return pd.to_numeric(frame[f], errors="coerce")
    a, sep, b = f.partition("-")
    if sep and a in frame.columns and b in frame.columns:
        return pd.to_numeric(frame[a], errors="coerce") - pd.to_numeric(frame[b], errors="coerce")
    return None


def pair_fields(columns: list[str]) -> list[str]:
    """`long-short` differences a positioning table implies: `x_long_y`/`x_short_y`, `x_l`/`x_s`."""
    cols = set(columns)
    out: list[str] = []
    for c in columns:
        for a, b in (("long", "short"), ("_l", "_s")):
            if a == "_l" and not c.endswith("_l"):
                continue
            other = c[:-2] + "_s" if a == "_l" else c.replace(a, b)
            if other != c and other in cols:
                out.append(f"{c}-{other}")
    return out


# ------------------------------------------------------------------ the shape every kind shares
def shape(s: pd.Series, transform: str = "level_z", *, z_window: int = DEFAULT_Z_WINDOW,
          lag_hours: int = DEFAULT_LAG_HOURS) -> pd.Series | None:
    """A stamped raw series, transformed on its OWN clock and then lagged. None when empty."""
    s = s.dropna()
    s = s[s.index.notna()]
    if s.empty:
        return None
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    t = str(transform or "level_z")
    if t in ("delta", "delta_z"):
        s = s.diff()
    if t in ("level_z", "delta_z"):
        w = max(5, int(z_window))
        mu = s.rolling(w, min_periods=5).mean()
        sd = s.rolling(w, min_periods=5).std(ddof=0)
        s = (s - mu) / sd.replace(0.0, np.nan)
    s = s.replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return None
    return s.shift(freq=pd.Timedelta(hours=max(0, int(lag_hours))))


# ------------------------------------------------------------------ cot
def cot_path(rel: str, data: Path | None = None) -> Path | None:
    base = data or DATA
    p = (base / f"{rel}.parquet").resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        return None
    return p if p.exists() and p.name.endswith(".parquet") else None


@lru_cache(maxsize=64)
def _cot_frame(path: str, mtime_ns: int) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if "report_date" not in df.columns:
        return None
    stamp = pd.to_datetime(df["report_date"], errors="coerce", utc=True)
    df = df.assign(_available=stamp + COT_AVAILABLE_AFTER)
    return df[df["_available"].notna()]


def cot_raw(rel: str, field: str, *, data: Path | None = None) -> pd.Series | None:
    p = cot_path(rel, data)
    if p is None:
        return None
    df = _cot_frame(str(p), p.stat().st_mtime_ns)
    if df is None or df.empty:
        return None
    v = _field(df, field)
    if v is None:
        return None
    return pd.Series(v.to_numpy(dtype=float), index=pd.DatetimeIndex(df["_available"]))


# ------------------------------------------------------------------ intelligence snapshots
def intel_dirs(seat: str, roots: tuple[Path, ...] | None = None) -> list[Path]:
    seat = str(seat or "").strip().strip("/")
    if not seat or "/" in seat or seat.startswith("."):
        return []
    return [r / seat for r in (roots or INTEL_ROOTS) if (r / seat).is_dir()]


def snapshot_time(name: str) -> datetime | None:
    """When the desk knew a snapshot file's contents, from its NAME; None when it names none."""
    m = _STAMPED.search(name)
    if not m:
        return None
    y, mo, d, hh, mm, ss = m.groups()
    try:
        day = datetime(int(y), int(mo), int(d), tzinfo=UTC)
    except ValueError:
        return None
    if hh is None:
        return day + timedelta(days=1)            # a day rollup: known at the end of its day
    try:
        return day.replace(hour=int(hh), minute=int(mm), second=int(ss or 0))
    except ValueError:
        return None


def snapshot_files(dirs: list[Path], limit: int = MAX_SNAPSHOTS) -> list[tuple[datetime, Path]]:
    """(stamp, file), oldest first, the newest `limit` of them."""
    out: list[tuple[datetime, Path]] = []
    for d in dirs:
        try:
            names = [p for p in d.iterdir() if p.is_file()
                     and p.name.endswith(_SNAPSHOT_SUFFIXES)]
        except OSError:
            continue
        for p in names:
            t = snapshot_time(p.name)
            if t is not None:
                out.append((t, p))
    out.sort(key=lambda x: (x[0], x[1].name))
    return out[-limit:] if limit else out


def rows_in(path: Path) -> Iterator[dict[str, Any]]:
    try:
        if path.name.endswith(".gz"):
            text = gzip.decompress(path.read_bytes()).decode("utf-8", "replace")
        else:
            text = path.read_text("utf-8", "replace")
    except OSError:
        return
    if ".jsonl" in path.name:
        for ln in text.splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict):
                yield r
        return
    try:
        doc = json.loads(text)
    except ValueError:
        return
    if isinstance(doc, dict):
        lists = [v for v in doc.values() if isinstance(v, list)]
        doc = [x for v in lists for x in v] if lists else [doc]
    for r in doc if isinstance(doc, list) else []:
        if isinstance(r, dict):
            yield r


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if np.isfinite(f) else None


def _matches(row: dict[str, Any], match: str) -> bool:
    if not match:
        return True
    k, _, want = match.partition("=")
    got = row.get(k)
    if isinstance(got, list):
        return want in [str(x) for x in got]
    return str(got) == want


def _reading(row: dict[str, Any], field: str) -> float | None:
    a, sep, b = field.partition("-")
    if sep and a in row and b in row:
        x, y = _num(row.get(a)), _num(row.get(b))
        return None if x is None or y is None else x - y
    return _num(row.get(field))


@lru_cache(maxsize=256)
def _intel_raw(key: tuple[str, ...], field: str, match: str, mtimes: tuple[int, ...],
               limit: int) -> pd.Series | None:
    dirs = [Path(k) for k in key]
    stamps: list[datetime] = []
    vals: list[float] = []
    for t, p in snapshot_files(dirs, limit):
        got = [v for r in rows_in(p) if _matches(r, match)
               for v in [_reading(r, field)] if v is not None]
        if got:
            stamps.append(t)
            vals.append(float(np.mean(got)))
    if not vals:
        return None
    return pd.Series(vals, index=pd.DatetimeIndex(stamps))


def intel_raw(seat: str, field: str, *, match: str = "", roots: tuple[Path, ...] | None = None,
              limit: int = MAX_SNAPSHOTS) -> pd.Series | None:
    dirs = intel_dirs(seat, roots)
    if not dirs or not field:
        return None
    mt: list[int] = []
    for d in dirs:
        try:
            mt.append(d.stat().st_mtime_ns)
        except OSError:
            mt.append(0)
    return _intel_raw(tuple(str(d) for d in dirs), str(field), str(match or ""), tuple(mt),
                      int(limit))


# ------------------------------------------------------------------ the one entry point
def raw(dataset: str, field: str, *, match: str = "", root: Path | None = None) -> pd.Series | None:
    """The dataset's field as UNSHAPED values on its availability clock (UTC). None = UNMEASURED.

    `root` redirects the kind's base directory (tests): the lake series dir, the data dir for
    cot, or a single intelligence root."""
    kind = kind_of(dataset)
    rest = str(dataset).partition(":")[2]
    if kind == "cot":
        return cot_raw(rest, field, data=root)
    if kind == "intel":
        return intel_raw(rest, field, match=match, roots=(root,) if root else None)
    if kind == "lake":
        from mt5desk.family_exogenous_conditioner import conditioner
        return conditioner(rest, field, "level", lag_hours=0, root=root)
    return None


def conditioned(dataset: str, field: str, *, transform: str = "level_z", match: str = "",
                lag_hours: int = DEFAULT_LAG_HOURS, z_window: int = DEFAULT_Z_WINDOW,
                root: Path | None = None) -> pd.Series | None:
    """The field transformed on its own clock, held back `lag_hours`: ready to join to bars."""
    s = raw(dataset, field, match=match, root=root)
    if s is None or s.empty:
        return None
    return shape(s, transform, z_window=z_window, lag_hours=lag_hours)


def on_bars(series: pd.Series, index: pd.DatetimeIndex) -> np.ndarray:
    """The series as of each bar: the last value available STRICTLY before the bar opened."""
    s = series[~series.index.duplicated(keep="last")].sort_index()
    if s.index.tz is None:
        s.index = s.index.tz_localize(UTC)
    idx = index if index.tz is not None else index.tz_localize(UTC)
    pos = s.index.searchsorted(idx, side="left") - 1
    vals = s.to_numpy(dtype=float)
    out = np.full(len(idx), np.nan)
    ok = pos >= 0
    out[ok] = vals[pos[ok]]
    return out
