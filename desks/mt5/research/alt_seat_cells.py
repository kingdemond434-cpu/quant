"""THE ALT SEATS' ROWS AS MT5 CELLS: each seat's readings become a point-in-time series, and the
series becomes an `exogenous_conditioner` state on the instrument the row names.

WHAT WAS MEASURED (PRODUCER_YIELD, box, 2026-10-13, 3-day window). Six seats on a clock, writing
rows every hour, emitting ZERO cells per hour:

    youtube        12,171 rows    sec_edgar   4,758    shipping   688
    fear_greed        600 rows    aaii          273    google_trends 45

WHY NONE OF THEM BECAME A CELL. Every row reached `miner_candidate_compiler.compile_row` and fell
through every structured branch to the PROSE path, because none of them carries a family, a rule
or a parameter: "Fear & Greed: 33.3 (fear)", "BDI: 3507 (strong_expansion)", "'gold price'
search volume +12% vs 4-week avg", a video title naming XAUUSD. The prose reader looks for a
family phrase, finds none, and files the row NEEDS_EXACT_RULE_EXTRACTION -- a deepening task an
LLM cannot finish, because the row is not a rule. It is a READING. One reading is not a strategy;
a SERIES of readings, stamped when the desk could first know each one, is exactly the input the
desk's `exogenous_conditioner` family already trades: "take a stance on this instrument while
this published statistic is at an extreme of its own history".

So the conversion is two steps, both deterministic, no model anywhere:

  1. SERIES. This organ (hourly leg `alt_seat_cells`, before the intake catch-up) reads every
     seat row on disk and writes `data/lake/series/seat_<seat>.csv` in the lake's PIT envelope
     (`event_time`, `available_time`, ... and the value columns). `available_time` is the row's
     own door stamp (`libs.data.pit.stamp` writes it at the moment the miner saved the row), else
     the capture time in the file name, else the file's mtime -- each one only ever LATER than the
     moment the reading was public, never earlier. A reading repeated by an hourly scrape of a
     weekly survey is ONE point, at its first sighting.
  2. CELL. `miner_candidate_compiler.compile_row` calls `row_cells` below for a seat row and mints
     `exogenous_conditioner` cells on the row's own declared instruments (resolved against the
     registry, two-lane mandate applied), H1 only, deduplicated on the executable spec by the
     compiler exactly like every other candidate. One cell is one trial; the gauntlet decides.
     The family itself holds the series back a full publication day (`lag_hours=24`) before it
     may touch a bar, because the bar clock is broker time and these stamps are UTC.

THE SIDE IS THE ROW'S OWN CLAIM, never fitted: the sentiment seats state "contrarian" in their
own description (high greed -> short), the freight seat states expansion (rising BDI -> long the
commodity currencies and indices it names), an attention spike on a named instrument is read as
retail exhaustion (contrarian), and a search-attention spike follows the term's polarity ("stock
market crash" up -> contrarian long). The gauntlet judges the stated side; nothing here searches
for the one that would have worked.

WHAT IS REFUSED, BY NAME (`REFUSALS`), and every refusal is counted in the report:

    NO_INFORMATION       sec_edgar `13f_filing`: the miner emits it whenever the fund's EDGAR page
                         contains the string "13F", which every such page always does. No filing
                         date, accession or holding -- a constant, and a constant conditions
                         nothing. The EDGAR lane that does carry information is Form 4
                         (`research/form4_lane.py`).
    IMPOSSIBLE_READING   a number the instrument cannot print: an AAII bull% + bear% above 100
                         (the miner's regex matched two unrelated percentages), a Fear & Greed
                         score outside [0, 100], a non-positive BDI.
    LANE_EVENT_ONLY      every instrument the row names is a share CFD, and `exogenous_conditioner`
                         is a statistical family the two-lane mandate keeps off single names.
    NO_MT5_INSTRUMENT    the row names no instrument the Fusion registry holds (after the seat's
                         own aliases: USOIL -> XTIUSD, COPPER -> XCUUSD).
    OPERATIONAL_ROW      a fetch error, not a reading.
    UNRECOGNISED_SHAPE   a row of a type this module does not parse. Not a refusal of the data --
                         a converter owed, and the report names the type.

AND ONE PENDING STATE, which is not a refusal: SERIES_ACCRUING. A conditioner's z-score needs
history (`exogenous_conditioner.MIN_OBSERVATIONS` points after a 5-point warm-up); a cell minted
before it exists would build, fire nothing, and be banked UNKNOWN -- a spent trial that tested
nothing. The row's reading is already IN the series; the cell is minted the pass the column has
`MIN_POINTS` points. The report publishes how many each column has.

THE FENCE. `scripts/check_conversion_debt.py` reads `reports/ALT_SEAT_CELLS.json` and goes RED
when a seat holds a convertible row (its series is ready and its instrument is admissible) whose
cell is not in the compiler's output more than one cycle after the row arrived.

    python desks/mt5/research/alt_seat_cells.py --once [--dry-run]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

INTEL = DESK / "data" / "intelligence"
SERIES_DIR = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe"
COMPILED = DESK / "data" / "hypotheses" / "miner_candidates.json"
REPORT = DESK / "reports" / "ALT_SEAT_CELLS.json"

UNMEASURED = "UNMEASURED"
FAMILY = "exogenous_conditioner"
SERIES_PREFIX = "seat_"

#: The cycle this organ and the compiler run on, and the grace a row is allowed past it before
#: the fence calls it held. Same numbers as the L8 converter's fence.
CYCLE_H = 1.0
GRACE_H = 0.25

#: Points a column needs before a cell is minted on it: the family's own MIN_OBSERVATIONS (30)
#: plus the five-point warm-up its rolling z-score spends before the first value exists.
MIN_POINTS = 35

#: Every seat this organ converts, and the `source` spellings its rows carry. A seat is a
#: directory under data/intelligence; the row's own `source` is what the compiler is handed.
SOURCE_SEAT: dict[str, str] = {
    "fear_greed": "fear_greed", "cnn_fear_greed": "fear_greed",
    "aaii": "aaii", "aaii_sentiment": "aaii",
    "shipping": "shipping",
    "google_trends": "google_trends",
    "youtube": "youtube",
    "sec_edgar": "sec_edgar",
}
SEATS: tuple[str, ...] = tuple(sorted(set(SOURCE_SEAT.values())))

#: Seat vocabulary -> the Fusion registry's name. None means the seat names an instrument the
#: broker does not list, which is NO_MT5_INSTRUMENT for that target, never a guess.
ALIASES: dict[str, str | None] = {
    "USOIL": "XTIUSD", "WTI": "XTIUSD", "UKOIL": "XBRUSD", "BRENT": "XBRUSD",
    "COPPER": "XCUUSD", "NATGAS": None, "SPX": "US500", "SP500": "US500", "NDX": "NAS100",
    "DJI": "US30", "RUT": "US2000", "GOLD": "XAUUSD", "SILVER": "XAGUSD",
}

REFUSALS = ("NO_INFORMATION", "IMPOSSIBLE_READING", "LANE_EVENT_ONLY", "OPERATIONAL_ROW")
#: Reasons that are not refusals of the data: the compiler keeps its existing path for these.
NOT_REFUSED = ("NO_MT5_INSTRUMENT", "UNRECOGNISED_SHAPE")
ACCRUING = "SERIES_ACCRUING"

#: Search terms whose attention rises in fear: a spike is read contrarian LONG. Every other term
#: is read as euphoria or plain attention: a spike is contrarian SHORT.
FEAR_TERMS = ("crash", "bear market", "recession", "sell ")

_STAMP_RE = re.compile(r"(\d{8})_(\d{4})")


# ------------------------------------------------------------------------------- small helpers

def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_time(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else t.replace(tzinfo=UTC)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:40]


def file_stamp(path: Path) -> datetime | None:
    """The capture time a seat file's name carries (`discoveries_YYYYMMDD_HHMM`), else mtime."""
    m = _STAMP_RE.search(path.name)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M").replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def seat_of(source: str, row: dict[str, Any] | None = None) -> str | None:
    """The seat a compiler `source` belongs to, or None for every other producer."""
    s = str(source or "").strip().lower()
    if s in SOURCE_SEAT:
        return SOURCE_SEAT[s]
    if isinstance(row, dict):
        r = str(row.get("source") or "").strip().lower()
        return SOURCE_SEAT.get(r)
    return None


def first_seen(row: dict[str, Any], fallback: datetime | None) -> datetime | None:
    """When the desk could first have known this row: the latest of its stamps, never earlier.

    `available_time` from `libs.data.pit.stamp` is the save instant unless the producer named a
    publication time; `ingested_time` is the save instant; `fallback` is the file's own capture
    stamp. The LATEST is used, so neither a producer-claimed publication stamp nor a row stamp
    alone can move a reading earlier than the file that holds it was written.
    """
    stamps = [t for t in (_parse_time(row.get("available_time")),
                          _parse_time(row.get("ingested_time")), fallback) if t is not None]
    return max(stamps) if stamps else None


# ------------------------------------------------------------------------------- the universe

def known_universe(universe_dir: Path | None = None) -> set[str]:
    """The registry's symbols in its own casing: the stems of the H1 parquets."""
    base = universe_dir or UNIVERSE
    return {p.stem.removesuffix("_H1") for p in base.glob("*_H1.parquet")}


def resolve(token: str, universe: set[str]) -> str | None:
    """A seat's instrument word -> the registry's spelling, or None."""
    t = str(token or "").replace("/", "").strip()
    if not t:
        return None
    up = t.upper()
    if up in ALIASES:
        alias = ALIASES[up]
        if alias is None:
            return None
        t, up = alias, alias.upper()
    folded = {s.upper(): s for s in universe}
    return t if t in universe else folded.get(up)


def _may_hypothesise(symbol: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:                                     # pragma: no cover - layout
        try:
            from universe_policy import may_hypothesise  # type: ignore[no-redef,import-not-found]
        except ImportError:
            return False                 # FAIL CLOSED: no lane check, no hypothesis
    try:
        return bool(may_hypothesise(symbol, FAMILY))
    except Exception:
        return False


def targets(row: dict[str, Any], universe: set[str]) -> tuple[list[str], str | None]:
    """The admissible instruments the row names, or the named reason there are none."""
    raw = row.get("symbols") if isinstance(row.get("symbols"), list) else []
    if row.get("symbol"):
        raw = [row["symbol"], *raw]
    resolved = [s for s in (resolve(str(t), universe) for t in raw) if s]
    resolved = list(dict.fromkeys(resolved))
    if not resolved:
        return [], "NO_MT5_INSTRUMENT"
    ok = [s for s in resolved if _may_hypothesise(s)]
    if not ok:
        return [], "LANE_EVENT_ONLY"
    return ok, None


# ------------------------------------------------------------------------------- per-seat parse

def readings(seat: str, row: dict[str, Any]) -> tuple[dict[str, float], str | None]:
    """The row's value columns for the seat's series, or the named reason it carries none.

    youtube is not here: its value is a COUNT of rows per day, built in `build_series`.
    """
    kind = str(row.get("kind") or row.get("type") or "").lower()
    if kind in {"fetch_error", "error", "walled", "stub", "probe", "skipped"}:
        return {}, "OPERATIONAL_ROW"
    if seat == "fear_greed":
        # `rapid_change` carries the same reading with yesterday's close beside it: the score
        # is the information, the day-on-day change is derivable from the series itself.
        if kind not in {"sentiment_reading", "extreme_sentiment", "rapid_change"}:
            return {}, "UNRECOGNISED_SHAPE"
        score = _num(row.get("score"))
        if score is None or not 0.0 <= score <= 100.0:
            return {}, "IMPOSSIBLE_READING"
        return {"score": score}, None
    if seat == "aaii":
        if kind not in {"sentiment_reading", "extreme_sentiment"}:
            return {}, "UNRECOGNISED_SHAPE"
        bull, bear = _num(row.get("bullish_pct")), _num(row.get("bearish_pct"))
        if bull is None or bear is None or bull < 0 or bear < 0 or bull + bear > 100.5:
            return {}, "IMPOSSIBLE_READING"
        return {"bullish_pct": bull, "bearish_pct": bear,
                "bull_bear_spread": round(bull - bear, 4)}, None
    if seat == "shipping":
        if kind != "bdi":
            return {}, "UNRECOGNISED_SHAPE"
        v = _num(row.get("value"))
        if v is None or v <= 0:
            return {}, "IMPOSSIBLE_READING"
        return {"bdi": v}, None
    if seat == "google_trends":
        if kind != "search_volume" or not row.get("term"):
            return {}, "UNRECOGNISED_SHAPE"
        trend = _num(row.get("trend_pct"))
        if trend is None:
            return {}, "IMPOSSIBLE_READING"
        return {_slug(str(row["term"])): trend}, None
    if seat == "sec_edgar":
        if kind == "13f_filing":
            return {}, "NO_INFORMATION"
        return {}, "UNRECOGNISED_SHAPE"
    if seat == "youtube":
        # A SIGHTING NEEDS A VIDEO. The count dedupes on the video, so a row that names none
        # (a bare claim such as {"patterns": ["scalping"]}) cannot be counted once; it is a
        # claim, and the prose path's deepening owns it.
        if not _video_id(row):
            return {}, "UNRECOGNISED_SHAPE"
        return {}, None
    return {}, "UNRECOGNISED_SHAPE"


def _video_id(row: dict[str, Any]) -> str:
    return str(row.get("url") or row.get("video_id") or "")


def _youtube_column(symbol: str) -> str:
    return f"n_{symbol}"


def cell_specs(seat: str, row: dict[str, Any], universe: set[str]
               ) -> tuple[list[tuple[str, dict[str, Any], str]], str | None]:
    """Every (symbol, params, mechanism) this row supports BEFORE readiness, or the reason none.

    The params are the executable identity: the compiler dedupes on (symbol, family, params), so
    a thousand hourly readings of one survey are one cell per instrument, charged once.
    """
    cols, why = readings(seat, row)
    if why:
        return [], why
    syms, why = targets(row, universe)
    if why:
        return [], why
    series = f"{SERIES_PREFIX}{seat}"
    base = {"source": series, "transform": "level_z", "threshold": 1.0, "lag_hours": 24,
            "timeframe": "H1"}
    out: list[tuple[str, dict[str, Any], str]] = []
    if seat == "fear_greed":
        for s in syms:
            out.append((s, {**base, "signal": "score", "side_when_high": -1},
                        "CNN Fear & Greed at an extreme of its own history is crowd positioning "
                        "that mean-reverts: extreme greed is sold, extreme fear bought (the "
                        "row's own contrarian claim), one publication day after the reading"))
    elif seat == "aaii":
        for s in syms:
            out.append((s, {**base, "signal": "bull_bear_spread", "side_when_high": -1},
                        "the AAII bull-bear spread at an extreme is retail positioning that the "
                        "survey's own literature reads contrarian: a crowded bull is sold"))
    elif seat == "shipping":
        for s in syms:
            out.append((s, {**base, "signal": "bdi", "transform": "delta_z",
                            "side_when_high": 1},
                        "a sharp rise in the Baltic Dry Index is real-economy demand for "
                        "bulk freight that commodity currencies and cyclical indices reprice "
                        "after: a z-scored jump is bought, a collapse sold"))
    elif seat == "google_trends":
        term = str(row.get("term") or "").lower()
        col = next(iter(cols))
        side = 1 if any(t in f"{term} " for t in FEAR_TERMS) else -1
        for s in syms:
            out.append((s, {**base, "signal": col, "side_when_high": side},
                        f"a spike in public search attention for '{term}' marks a crowd that "
                        f"has already acted; the extreme is faded "
                        f"({'fear search -> long' if side > 0 else 'euphoria search -> short'})"))
    elif seat == "youtube":
        for s in syms:
            out.append((s, {**base, "signal": _youtube_column(s), "threshold": 1.5,
                            "side_when_high": -1},
                        f"a burst of retail trading videos about {s} (new videos first seen "
                        f"per day, z-scored on its own history) marks attention that arrives "
                        f"late; the burst is faded"))
    return out, None


# ------------------------------------------------------------------------------- series readiness

_READY_CACHE: dict[str, tuple[float, dict[str, int]]] = {}


def column_counts(series: str, root: Path | None = None) -> dict[str, int]:
    """Non-null points per value column of one lake series, cached on the file's mtime."""
    path = (root or SERIES_DIR) / f"{series}.csv"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    key = str(path)
    hit = _READY_CACHE.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    counts: dict[str, int] = {}
    try:
        import csv
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for rec in reader:
                for k, v in rec.items():
                    if k in _ENVELOPE or v in (None, ""):
                        continue
                    counts[k] = counts.get(k, 0) + 1
    except (OSError, ValueError):
        return {}
    _READY_CACHE[key] = (mtime, counts)
    return counts


def row_cells(seat: str, row: dict[str, Any], universe: set[str], root: Path | None = None
              ) -> tuple[list[tuple[str, dict[str, Any], str]], str | None]:
    """What the compiler mints for this row NOW: ready cells, or the named reason for none."""
    specs, why = cell_specs(seat, row, universe)
    if why:
        return [], why
    ready = [sp for sp in specs
             if column_counts(str(sp[1]["source"]), root).get(str(sp[1]["signal"]), 0)
             >= MIN_POINTS]
    return (ready, None) if ready else ([], ACCRUING)


def identity(symbol: str, params: dict[str, Any]) -> str:
    """The compiler's own dedupe key, so the report and the compiler agree on 'the same cell'."""
    return json.dumps({"symbol": symbol, "family": FAMILY, "params": params}, sort_keys=True,
                      default=str)


# ------------------------------------------------------------------------------- reading the seats

def _iter_file(path: Path) -> Iterator[dict[str, Any]]:
    try:
        if path.name.endswith(".jsonl.gz"):
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        yield r
            return
        if path.suffix == ".jsonl":
            with path.open(encoding="utf-8", errors="replace") as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        yield r
            return
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, EOFError):
        return
    rows = doc if isinstance(doc, list) else (
        doc.get("discoveries") if isinstance(doc, dict) else None)
    if isinstance(doc, dict) and not isinstance(rows, list):
        rows = [doc] if doc.get("source") or doc.get("type") or doc.get("kind") else []
    for r in rows or []:
        if isinstance(r, dict):
            yield r


def seat_rows(seat: str, intel: Path | None = None
              ) -> Iterator[tuple[dict[str, Any], datetime | None]]:
    """(row, first-seen instant) for every row on disk for one seat, exact duplicates once."""
    for row, seen, _paths in seat_rows_at(seat, intel):
        yield row, seen


def seat_rows_at(seat: str, intel: Path | None = None
                 ) -> Iterator[tuple[dict[str, Any], datetime | None, tuple[Path, ...]]]:
    """`seat_rows` with EVERY file holding each row, earliest capture first.

    A row repeated across files is one row, first seen at the EARLIEST file stamp that holds it
    -- never the alphabetically first file (audit 2026-10-14). All its files are returned, so the
    intake-window test asks whether ANY copy is one the compiler still reads.
    """
    base = (intel or INTEL) / seat
    if not base.is_dir():
        return
    far = datetime.max.replace(tzinfo=UTC)
    stamped = sorted(((file_stamp(p), p) for p in base.rglob("*") if p.is_file()
                      and (p.suffix in {".json", ".jsonl"} or p.name.endswith(".jsonl.gz"))),
                     key=lambda sp: (sp[0] or far, str(sp[1])))
    held: dict[str, tuple[dict[str, Any], datetime | None, list[Path]]] = {}
    for stamp, path in stamped:
        for row in _iter_file(path):
            h = hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()
            if h in held:
                held[h][2].append(path)
                continue
            held[h] = (row, stamp, [path])
    for row, stamp, paths in held.values():
        yield row, first_seen(row, stamp), tuple(paths)


def _compiler() -> Any:
    try:
        from research import miner_candidate_compiler as mcc
    except ImportError:                                     # pragma: no cover - layout
        import miner_candidate_compiler as mcc  # type: ignore[no-redef,import-not-found]
    return mcc


def in_intake_window(path: Path, cutoff: datetime) -> bool:
    """Would the compiler's intake read this file on the pass whose window opens at `cutoff`?
    The same two tests the intake applies: its file kinds and its mtime window."""
    if path.suffix.lower() not in _compiler().INTAKE_SUFFIXES:
        return False
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) >= cutoff
    except OSError:
        return False


# ------------------------------------------------------------------------------- the series

_ENVELOPE = ("event_time", "available_time", "published_time", "retrieval_time",
             "revision_time", "ingested_time", "source_id", "vintage_id")


def build_series(seat: str, rows: Iterable[tuple[dict[str, Any], datetime | None]],
                 universe: set[str], now: datetime) -> list[dict[str, Any]]:
    """The seat's PIT points, oldest first: one point per NEW reading, at its first sighting.

    youtube is a count: per UTC day, how many NEW videos (first seen that day) named each
    instrument, for every complete day on which the seat captured anything. A zero on such a day
    is a reading; a day the collector never ran has no point at all.
    """
    if seat == "youtube":
        per_day: dict[str, Counter[str]] = defaultdict(Counter)
        symbols: set[str] = set()
        videos: set[str] = set()
        covered: set[str] = set()
        for row, seen in sorted(((r, t) for r, t in rows if t is not None),
                                key=lambda x: x[1]):
            covered.add(seen.date().isoformat())
            # ONE VIDEO, ONE SIGHTING. The miner re-finds the same video on every pass inside
            # its 7-day search window, and each save carries fresh door stamps, so the row is
            # not an exact duplicate -- the video is. Counted on the pass it was first seen.
            vid = _video_id(row)
            if not vid or vid in videos:
                continue
            videos.add(vid)
            syms, why = targets(row, universe)
            if why:
                continue
            day = seen.date().isoformat()
            for s in syms:
                per_day[day][s] += 1
                symbols.add(s)
        if not per_day:
            return []
        first = datetime.fromisoformat(min(per_day)).date()
        last = (now - timedelta(days=1)).date()
        pts: list[dict[str, Any]] = []
        d = first
        while d <= last:
            key = d.isoformat()
            if key not in covered:
                # THE SEAT DID NOT RUN THAT DAY. A zero there would be a reading nobody took --
                # a quiet day invented out of a dead collector -- so the day carries no point.
                d += timedelta(days=1)
                continue
            avail = datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1)
            rec: dict[str, Any] = {"event_time": key, "available_time": avail.isoformat()}
            for s in sorted(symbols):
                rec[_youtube_column(s)] = int(per_day.get(key, Counter()).get(s, 0))
            pts.append(rec)
            d += timedelta(days=1)
        return pts
    last_val: dict[str, float] = {}
    out: list[dict[str, Any]] = []
    stamped = sorted(((seen, row) for row, seen in rows if seen is not None),
                     key=lambda x: x[0])
    for seen, row in stamped:
        cols, why = readings(seat, row)
        if why or not cols:
            continue
        fresh = {k: v for k, v in cols.items() if last_val.get(k) != v}
        if not fresh:
            continue                     # the same reading scraped again: no new information
        last_val.update(fresh)
        out.append({"event_time": str(row.get("event_time") or seen.isoformat()),
                    "available_time": seen.isoformat(), **fresh})
    return out


def write_series(seat: str, points: list[dict[str, Any]], root: Path | None = None
                 ) -> Path | None:
    """`data/lake/series/seat_<seat>.csv`, atomically, in the envelope the family reads."""
    if not points:
        return None
    import csv
    base = root or SERIES_DIR
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{SERIES_PREFIX}{seat}.csv"
    cols = sorted({k for p in points for k in p if k not in _ENVELOPE})
    head = ["event_time", "available_time", "source_id", "vintage_id", *cols]
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=head)
        w.writeheader()
        for p in points:
            w.writerow({"source_id": f"{SERIES_PREFIX}{seat}",
                        "vintage_id": p.get("available_time"),
                        **{k: p.get(k, "") for k in head if k not in ("source_id",
                                                                       "vintage_id")}})
    os.replace(tmp, target)
    _READY_CACHE.pop(str(target), None)
    return target


# ------------------------------------------------------------------- the compiler's output

def compiled_identities(path: Path | None = None) -> tuple[set[str] | None, str | None]:
    """Identities of every seat cell in the compiler's last output, or (None, why)."""
    p = path or COMPILED
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{p.name} unreadable ({type(exc).__name__})"
    hyps = doc.get("hypotheses") if isinstance(doc, dict) else None
    if not isinstance(hyps, list):
        return None, f"{p.name} carries no hypotheses list"
    out: set[str] = set()
    for h in hyps:
        if not isinstance(h, dict) or h.get("family") != FAMILY:
            continue
        params = h.get("params")
        if isinstance(params, dict) and str(params.get("source", "")).startswith(SERIES_PREFIX):
            out.add(identity(str(h.get("symbol")), params))
    return out, (str(doc.get("compiled_at") or "") if isinstance(doc, dict) else None)


# ------------------------------------------------------------------------------- the pass

def measure(seat: str, rows: list[tuple[dict[str, Any], datetime | None]], universe: set[str],
            compiled: set[str] | None, root: Path | None) -> dict[str, Any]:
    """Per-seat: convertible vs converted, the reasons for the rest, and the oldest held row."""
    reasons: Counter[str] = Counter()
    types: Counter[str] = Counter()
    convertible = converted = accruing = 0
    cells: set[str] = set()
    missing: set[str] = set()
    oldest: datetime | None = None
    for row, seen in rows:
        specs, why = row_cells(seat, row, universe, root)
        if why:
            reasons[why] += 1
            if why == "UNRECOGNISED_SHAPE":
                types[str(row.get("kind") or row.get("type") or "?")] += 1
            if why == ACCRUING:
                accruing += 1
            continue
        convertible += 1
        ids = [identity(s, p) for s, p, _m in specs]
        cells.update(ids)
        if compiled is None:
            continue
        absent = [i for i in ids if i not in compiled]
        if absent:
            missing.update(absent)
            if seen is not None and (oldest is None or seen < oldest):
                oldest = seen
        else:
            converted += 1
    counts = column_counts(f"{SERIES_PREFIX}{seat}", root)
    return {"rows": len(rows), "convertible": convertible,
            "converted": (converted if compiled is not None else None),
            "unconverted": (convertible - converted if compiled is not None else None),
            "series_accruing": accruing,
            "unconvertible_by_reason": dict(reasons.most_common()),
            "unrecognised_types": dict(types.most_common(10)),
            "cells": len(cells), "cells_not_compiled": len(missing),
            "oldest_unconverted_first_seen": oldest.isoformat() if oldest else None,
            "series": f"{SERIES_PREFIX}{seat}",
            "series_points_by_column": dict(sorted(counts.items())),
            "min_points": MIN_POINTS}


def run(*, intel: Path | None = None, series_root: Path | None = None,
        universe_dir: Path | None = None, compiled_path: Path | None = None,
        now: datetime | None = None, dry_run: bool = False,
        intake_cutoff: datetime | None = None) -> dict[str, Any]:
    """The series are built from EVERY row on disk (history is the input); conversion is judged
    only on rows inside the compiler's intake window, since a row the compiler will never read
    again cannot be converted by it and would hold the fence red forever."""
    now = now or _now()
    cutoff = intake_cutoff or _compiler().intake_cutoff(now)
    universe = known_universe(universe_dir)
    report: dict[str, Any] = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "law": ("EVERY MINED ROW ENDS AS A TESTABLE CELL OR A NAMED REFUSAL (LAWS 5b). A seat "
                "row is a READING; its seat's series is the input, the cell is an "
                "exogenous_conditioner state on the instrument it names, one trial per cell."),
        "cycle_h": CYCLE_H, "grace_h": GRACE_H, "family": FAMILY,
        "universe_symbols": len(universe), "seats": {},
        "intake_window": {"cutoff_utc": cutoff.isoformat(timespec="seconds"),
                          "window_days": _compiler().WINDOW_DAYS,
                          "why": "conversion is judged on the rows the compiler reads"}}
    if not universe:
        report.update({"status": UNMEASURED,
                       "why": "no H1 parquet under data/universe: no instrument can be resolved"})
        return report
    compiled, compiled_at = compiled_identities(compiled_path)
    report["compiler"] = ({"available": True, "compiled_at": compiled_at}
                          if compiled is not None else
                          {"available": False, "why": compiled_at})
    root = series_root or SERIES_DIR
    for seat in SEATS:
        located = list(seat_rows_at(seat, intel))
        rows = [(r, t) for r, t, _p in located]
        window = [(r, t) for r, t, ps in located
                  if any(in_intake_window(p, cutoff) for p in ps)]
        pts = build_series(seat, rows, universe, now)
        # A dry run writes series only under an explicit scratch root, never the live lake.
        written = (write_series(seat, pts, root)
                   if (not dry_run or series_root is not None) else None)
        entry = measure(seat, window, universe, compiled, root)
        entry["rows_on_disk"] = len(rows)
        entry["series_points"] = len(pts)
        entry["series_written"] = str(written) if written else None
        report["seats"][seat] = entry
    totals = Counter[str]()
    for e in report["seats"].values():
        for k in ("rows", "rows_on_disk", "convertible", "series_accruing", "cells"):
            totals[k] += int(e.get(k) or 0)
        totals["converted"] += int(e.get("converted") or 0)
        totals["unconverted"] += int(e.get("unconverted") or 0)
    report["totals"] = dict(totals)
    report["status"] = "OK" if compiled is not None else UNMEASURED
    return report


def held_seats(report: dict[str, Any], now: datetime | None = None) -> list[dict[str, Any]]:
    """Seats holding a convertible row whose cell is not compiled, older than one cycle.

    Measured against the report's own clock: a row that arrived after `generated_utc - cycle`
    has not yet had its cycle. Shared by the fence, so the organ and the gate cannot disagree.
    """
    at = _parse_time(report.get("generated_utc")) or now or _now()
    limit = at - timedelta(hours=CYCLE_H + GRACE_H)
    out: list[dict[str, Any]] = []
    for seat, e in sorted((report.get("seats") or {}).items()):
        oldest = _parse_time((e or {}).get("oldest_unconverted_first_seen"))
        if oldest is not None and oldest < limit and int(e.get("unconverted") or 0) > 0:
            out.append({"seat": seat, "unconverted": int(e["unconverted"]),
                        "oldest_unconverted_first_seen": oldest.isoformat(),
                        "cells_not_compiled": int(e.get("cells_not_compiled") or 0)})
    return out


def _write_report(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or REPORT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg's call)")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and print; write series under --series-root only")
    ap.add_argument("--series-root", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.dry_run and a.series_root is None:
        ap.error("--dry-run writes series only under an explicit --series-root")
    doc = run(series_root=a.series_root, dry_run=a.dry_run)
    if not a.dry_run:
        _write_report(doc, a.report)
    t = doc.get("totals") or {}
    print(f"alt_seat_cells: {doc.get('status')} -- rows {t.get('rows', 0)}, convertible "
          f"{t.get('convertible', 0)}, converted {t.get('converted', 0)}, accruing "
          f"{t.get('series_accruing', 0)}, cells {t.get('cells', 0)}")
    for seat, e in sorted((doc.get("seats") or {}).items()):
        print(f"  {seat:14s} rows {e['rows']:>6} convertible {e['convertible']:>6} "
              f"converted {e['converted']!s:>6} accruing {e['series_accruing']:>6} "
              f"cells {e['cells']:>3}  refused {e['unconvertible_by_reason']}")
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
