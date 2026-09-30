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
    macro:<name>   `data/axes/<name>.json`, an axis record: rows stamped `knowable_at` (the axis
                   organ's own knowability stamp; a month is known at its END), or dated series
                   points read a day after their date.
    grounds:<name> `data/<name>.jsonl`, an append-only grounds journal: rows mined per UTC day,
                   known at the end of the day. A grounds LIST with no row stamps has no series.
    acquired:<feed> `data/acquired/<feed>_<column>.parquet`, written by `acquire_datasets` for the
                   repo-mined feeds (#166, libs/data/repo_mined_feeds): each value already sits
                   at its FIRST-PRINT `available_time` (the frame's index), so it is read as is.
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
#: Name-stamped digests `libs/research/seat_stamper` writes for a seat whose own files carry no
#: time in their names (a state file rewritten in place). A third root, OUTSIDE data/intelligence
#: on purpose: the compiler reads data/intelligence/** and a digest is a reading, not a claim.
STAMPS_ROOT = DATA / "dataset_stamps"
INTEL_ROOTS: tuple[Path, ...] = (DATA / "intelligence", ROOT / "data" / "intelligence",
                                 STAMPS_ROOT)
AXES = DATA / "axes"

KINDS: tuple[str, ...] = ("lake", "cot", "intel", "macro", "grounds", "acquired")
ACQUIRED = DATA / "acquired"
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

#: THE ACTIVITY FIELD. A text-only intelligence seat (claims, posts, filings) carries no numeric
#: reading, and before this it could feed no conditioner and no state input: stored, never used.
#: Every name-stamped snapshot still says HOW MUCH the seat saw at the moment the desk knew it, so
#: `_rows` is the count of rows (matching `match`, when given) in each stamped snapshot -- an
#: attention/activity series on the same honest clock as every other intelligence field. A
#: snapshot with no matching row reads 0, which is a measurement, not an absence.
ROW_COUNT_FIELD = "_rows"

_STAMPED = re.compile(r"(20\d{2})(\d{2})(\d{2})(?:[_T-](\d{2})(\d{2})(\d{2})?)?")
_SNAPSHOT_SUFFIXES = (".json", ".jsonl", ".jsonl.gz", ".json.gz", ".yaml", ".yml")


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
    if path.name.endswith((".yaml", ".yml")):
        # A seat that writes one YAML document per record (`H-YYYYMMDD-NNN.yaml`): one row.
        try:
            import yaml
            doc = yaml.safe_load(text)
        except Exception:
            return
        if isinstance(doc, dict):
            yield doc
        elif isinstance(doc, list):
            yield from (r for r in doc if isinstance(r, dict))
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
    # ONE READING PER STAMP, over every file that carries it (2026-09-30). A seat that writes one
    # file per RECORD (`H-YYYYMMDD-NNN.yaml`, `REC-YYYYMMDD-<hash>.json`) stamps many files with
    # the same day; read file-by-file, `_rows` was 1 for each and the series a constant the
    # z-score cannot read, while the honest reading -- how many records the seat made that day --
    # sat in the file count. A numeric field is the mean over every matching row at the stamp.
    counts: dict[datetime, float] = {}
    sums: dict[datetime, list[float]] = {}
    for t, p in snapshot_files(dirs, limit):
        if field == ROW_COUNT_FIELD:
            counts[t] = counts.get(t, 0.0) + float(sum(1 for r in rows_in(p) if _matches(r, match)))
            continue
        got = [v for r in rows_in(p) if _matches(r, match)
               for v in [_reading(r, field)] if v is not None]
        if got:
            sums.setdefault(t, []).extend(got)
    if field == ROW_COUNT_FIELD:
        items = sorted(counts.items())
    else:
        items = sorted((t, float(np.mean(v))) for t, v in sums.items())
    if not items:
        return None
    return pd.Series([v for _t, v in items], index=pd.DatetimeIndex([t for t, _v in items]))


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


# ------------------------------------------------------------------ macro axis records
#: Row keys of an axis record that are coordinates or flags, never readings.
AXIS_NON_SIGNAL: frozenset[str] = frozenset({"inverted"})


@lru_cache(maxsize=8)
def _axis_doc(path: str, mtime_ns: int) -> dict[str, Any] | None:
    try:
        doc = json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def axis_doc(name: str, root: Path | None = None) -> dict[str, Any] | None:
    base = root or AXES
    name = str(name or "").strip()
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    p = base / f"{name}.json"
    try:
        return _axis_doc(str(p), p.stat().st_mtime_ns)
    except OSError:
        return None


def _knowable(v: Any) -> pd.Timestamp | None:
    """An axis row's `knowable_at` as the instant the desk could first read it. A month
    (`1999-01`) is knowable at the END of that month -- never its first day."""
    s = str(v or "").strip()
    if not s:
        return None
    try:
        if len(s) == 7:
            return pd.Period(s, freq="M").end_time.tz_localize(UTC).ceil("D")
        t = pd.Timestamp(s)
    except (ValueError, TypeError):
        return None
    return t.tz_localize(UTC) if t.tzinfo is None else t.tz_convert(UTC)


def macro_fields(name: str, root: Path | None = None,
                 max_matches: int = 12) -> list[dict[str, str]]:
    """The fields an axis record carries: each numeric row key split by `symbol` (rows-shaped
    records: bis, cot), or each named series (series-shaped: ecb, fred). [] when it holds none."""
    doc = axis_doc(name, root)
    if not doc:
        return []
    rows = doc.get("rows")
    if isinstance(rows, list) and rows:
        keys: dict[str, int] = {}
        syms: dict[str, int] = {}
        for r in rows:
            if isinstance(r, dict) and isinstance(r.get("symbol"), str):
                syms[r["symbol"]] = syms.get(r["symbol"], 0) + 1
        for r in rows[:5000]:
            if not isinstance(r, dict):
                continue
            for k, v in r.items():
                if k in NON_SIGNAL_KEYS or k in AXIS_NON_SIGNAL or isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    keys[k] = keys.get(k, 0) + 1
        # The record's own `shape` names the reading its family uses (`carry_differential`,
        # `net_pct_oi`): that field leads, the rest follow by frequency.
        shape_txt = str(doc.get("shape") or "")
        names = sorted(keys, key=lambda k: (k not in shape_txt, -keys[k], k))
        if syms:
            top = [s for s, _ in sorted(syms.items(), key=lambda kv: -kv[1])][:max_matches]
            # Field-major: the lead reading on every symbol before a second reading on any, so
            # the first few fields a producer takes span instruments, not one symbol's columns.
            return [{"field": f, "match": f"symbol={s}"} for f in names for s in top]
        return [{"field": f, "match": ""} for f in names]
    series = doc.get("series")
    if isinstance(series, dict):
        return [{"field": str(k), "match": ""} for k, v in series.items()
                if isinstance(v, dict) and v.get("points")]
    return []


#: Days after a period's END before a monthly / quarterly print without its own `k` is read
#: (conservative: later costs a little edge, earlier invents it).
MONTHLY_RELEASE_LAG_DAYS = 45
QUARTERLY_RELEASE_LAG_DAYS = 95
WEEKLY_RELEASE_LAG_DAYS = 10


def series_release_rule(dates: list[str]) -> str:
    """D / W / M / Q from a series-shaped record's point dates (median spacing)."""
    ts = sorted(t for t in (pd.to_datetime(d[:10], errors="coerce") for d in dates[-60:] if d)
                if pd.notna(t))
    gaps = sorted((b - a).days for a, b in zip(ts, ts[1:], strict=False))
    if not gaps:
        return "D"
    g = gaps[len(gaps) // 2]
    return "D" if g <= 4 else "W" if g <= 10 else "M" if g <= 40 else "Q"


def _release_knowable(d: Any, rule: str) -> pd.Timestamp | None:
    """A series point's knowable time by its frequency's release rule: a daily print at the END
    of the next business day, a weekly one 10 days on, a monthly / quarterly one (dated at the
    period's first day) its period END plus the release lag."""
    s = str(d or "").strip()[:10]
    t = pd.to_datetime(s, errors="coerce")
    if pd.isna(t):
        return None
    t = pd.Timestamp(t).tz_localize(UTC) if pd.Timestamp(t).tzinfo is None else pd.Timestamp(t)
    if rule == "D":
        return (t + pd.offsets.BDay(1)).normalize() + pd.Timedelta(days=1)
    if rule == "W":
        return t + pd.Timedelta(days=WEEKLY_RELEASE_LAG_DAYS)
    if rule == "M":
        return (t + pd.offsets.MonthBegin(1)).normalize() + pd.Timedelta(
            days=MONTHLY_RELEASE_LAG_DAYS)
    return (t + pd.offsets.QuarterBegin(1, startingMonth=1)).normalize() + pd.Timedelta(
        days=QUARTERLY_RELEASE_LAG_DAYS)


def macro_raw(name: str, field: str, *, match: str = "",
              root: Path | None = None) -> pd.Series | None:
    """An axis record's field on its availability clock: a rows-shaped record's `knowable_at`
    (the axis organ's own knowability stamp), a series-shaped record's point `k` (its own
    knowable_at) or else its frequency's release rule (`_release_knowable`). None when the record
    or field is absent."""
    doc = axis_doc(name, root)
    if not doc or not field:
        return None
    stamps: list[Any] = []
    vals: list[float] = []
    rows = doc.get("rows")
    if isinstance(rows, list) and rows:
        for r in rows:
            if not isinstance(r, dict) or not _matches(r, match):
                continue
            v = _reading(r, field)
            t = _knowable(r.get("knowable_at"))
            if v is None or t is None:
                continue
            stamps.append(t)
            vals.append(v)
    else:
        sd = (doc.get("series") or {}).get(field) if isinstance(doc.get("series"), dict) else None
        pts = [pt for pt in (sd or {}).get("points") or [] if isinstance(pt, dict)]
        rule = series_release_rule([str(pt.get("d") or "") for pt in pts])
        for pt in pts:
            v = _num(pt.get("v"))
            # THE POINT'S OWN knowable_at FIRST (`k`, written by research/fred_fetch.py from
            # ALFRED's first release or the series' release rule). A point without one is stamped
            # by its FREQUENCY's release rule, never `date + 1 day`: FRED dates a monthly print at
            # the period's FIRST day, and +1 day read it weeks before it was published.
            t = _knowable(pt.get("k")) if pt.get("k") else _release_knowable(pt.get("d"), rule)
            if v is None or t is None:
                continue
            stamps.append(t)
            vals.append(v)
    if not vals:
        return None
    return pd.Series(vals, index=pd.DatetimeIndex(stamps)).sort_index()


# ------------------------------------------------------------------ grounds journals
#: Keys a grounds journal row may carry its own recording time under, most specific first.
JOURNAL_TIME_KEYS: tuple[str, ...] = ("at", "recorded_at", "observed_at", "timestamp", "ts")


def grounds_raw(name: str, field: str = ROW_COUNT_FIELD, *,
                root: Path | None = None) -> pd.Series | None:
    """An APPEND-ONLY grounds journal (`data/<name>.jsonl`, one row per ground or claim mined,
    each stamped when it was recorded) as its daily activity: `_rows` per UTC day, known at the
    END of that day. A grounds LIST with no row stamps has no series (None)."""
    if field != ROW_COUNT_FIELD:
        return None
    p = (root or DATA) / f"{name}.jsonl"
    if not p.is_file():
        return None
    per_day: dict[pd.Timestamp, int] = {}
    for r in rows_in(p):
        t = None
        for k in JOURNAL_TIME_KEYS:
            if r.get(k):
                try:
                    t = pd.Timestamp(str(r[k]))
                except (ValueError, TypeError):
                    t = None
                if t is not None:
                    break
        if t is None:
            continue
        t = t.tz_localize(UTC) if t.tzinfo is None else t.tz_convert(UTC)
        day = t.normalize() + pd.Timedelta(days=1)
        per_day[day] = per_day.get(day, 0) + 1
    if not per_day:
        return None
    idx = pd.date_range(min(per_day), max(per_day), freq="D")
    # A day the journal recorded nothing reads 0: a measurement of the miner's day, not a gap.
    return pd.Series([float(per_day.get(d, 0)) for d in idx], index=idx)


# ------------------------------------------------------------------ the one entry point
def acquired_files(feed: str, root: Path | None = None) -> list[Path]:
    """A repo-mined feed's per-column files (`<feed>_<column>.parquet`)."""
    base = root or ACQUIRED
    feed = str(feed or "").strip()
    if not feed or "/" in feed or "\\" in feed or feed.startswith(".") or not base.is_dir():
        return []
    return sorted(p for p in base.glob(f"{feed}_*.parquet") if p.is_file())


def acquired_raw(feed: str, field: str, *, root: Path | None = None) -> pd.Series | None:
    """One column of a repo-mined feed on its first-print availability clock (the file's index,
    written by `repo_mined_feeds.as_available`). `field` is the file's stem."""
    base = root or ACQUIRED
    if not str(field or "").startswith(f"{feed}_"):
        return None
    p = base / f"{field}.parquet"
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if df.empty:
        return None
    col = "value" if "value" in df.columns else df.columns[0]
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, errors="coerce", utc=True))
    s = pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float), index=idx)
    return s[s.index.notna()].dropna().sort_index()


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
    if kind == "macro":
        return macro_raw(rest, field, match=match, root=root)
    if kind == "grounds":
        return grounds_raw(rest, field, root=root)
    if kind == "acquired":
        return acquired_raw(rest, field, root=root)
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
