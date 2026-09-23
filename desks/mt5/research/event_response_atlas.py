#!/usr/bin/env python3
"""EVENT-RESPONSE ATLAS -- what the tape ACTUALLY did after the dated events the desk knows.

WHY A LOOKUP TABLE AND NOT A MODEL (blueprint item C11 / Global Organization W8)

"NFP came in hot with USD positioning at an extreme" is answered on this desk today by somebody
remembering -- an answer nobody can audit, over a sample nobody counted. THE ATLAS ASKS THE BARS
THE SAME QUESTION: for every event kind the desk has a DATE for, on every instrument that event
names, at four horizons, under six conditioners -- what happened, how often, with what dispersion,
and does the mean survive the spread. Nothing is fitted. Every number is a sample statistic, and
its count rides on the row so a cell of fourteen cannot be read as one of four hundred.

WHERE THE DATES COME FROM, AND WHAT IS MISSING (L1.28a). `data/forced_flow_calendar.json` is
rule-derived and dense; `data/macro/event_ledger.jsonl` is the macro desk's own record; a
repository-root `data/events.jsonl` joins them when it exists. All three are read TOLERANTLY: a
row with no usable stamp or no instrument contributes nothing and is COUNTED, and an absent
source is reported as absent rather than as a clean zero.

THE SURPRISE AXIS IS THE HONEST ONE, and it is what the artifact's rule line is about. A macro
surprise is (actual - consensus) / sigma of THIS release's own historical surprises
(`macro/surprise.py`), and the desk's vintages carry forecast and previous but NO ACTUAL. So the
atlas asks `z_score` for every row carrying both -- the count is published -- and conditions
everything else on the REALISED FIRST BAR, its sign and its size in the instrument's own trailing
volatility. That is labelled `surprise_proxy` in every cell it makes and is never called a
surprise anywhere.

WHAT MAKES THIS CAUSAL RATHER THAN FLATTERING

  * THE EVENT IS MOVED INTO THE BARS' CLOCK, NEVER THE OTHER WAY. Bars are broker-stamped under a
    UTC tzinfo (+2 winter, +3 summer, measured); `libs/research/bar_clock.to_bar_time` converts
    and a shoulder-month instant it cannot place is DROPPED and counted. That costs roughly half
    the calendar year; the alternative is a two-hour look-ahead that would make every cell here
    better than the trade.
  * THE CONDITIONER IS STRICTLY BEFORE THE RESPONSE. The first bar at or after the event gives
    the orientation (its own open-to-close move) and the response is measured from THAT BAR'S
    CLOSE forward. Trend, volatility and positioning close before the event bar opens -- the
    volatility terciles are trailing rolling quantiles, never the whole sample's, because a
    tercile taken over the future is a ranking nobody could have had.
  * ORIENTED, SO CONTINUATION AND REVERSAL ARE ONE NUMBER. Each response is multiplied by the
    sign of the first-bar move: a positive mean says following the reaction paid, a negative one
    says fading it paid, and the hit rate is the share of events that agreed with the first bar.

MULTIPLICITY IS PAID, NOT MENTIONED: the Bonferroni threshold for the exact number of cells
tested is published, every cell carries whether it clears it, and only a cell that clears it AND
whose |mean| beats the instrument's cost proxy is donated.

THE TWO-LANE MANDATE IS ENFORCED AT INTAKE rather than at the door on the way out. Single-name
equities are traded on news and earnings, never hunted for statistical hypotheses, and an equity
cell does not merely fail to help -- it enlarges the family-wise error budget every FX and metals
cell then has to clear. So it is set aside BEFORE it can reach the denominator and named in the
artifact; `proposer_common.donate` fences it again afterwards.

WHAT THIS MODULE DOES NOT DO. It does not fit, rank, weight or size anything, and it does not
decide which reaction is worth trading -- the ten gates do.

CLI
    python event_response_atlas.py              # measure, write the artifact, donate
    python event_response_atlas.py --dry-run    # measure and print; write nothing, donate nothing
    python event_response_atlas.py --days 400 --budget-s 240 --max-donations 15
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
UNIVERSE = BASE / "data" / "universe"
CALENDAR = BASE / "data" / "forced_flow_calendar.json"
MACRO_LEDGER = BASE / "data" / "macro" / "event_ledger.jsonl"
ROOT_EVENTS = ROOT / "data" / "events.jsonl"
COT = BASE / "data" / "axes" / "cot.json"
REGIME_STATE = BASE / "data" / "regime_state.json"
COST_SURFACE = BASE / "data" / "cost_surface.json"
REPORT = BASE / "reports" / "EVENT_RESPONSE_ATLAS.json"

SOURCE = "event_response_atlas"
FAMILY = "event_reaction"

#: Events a cell needs before its mean is a number rather than an anecdote. The blueprint's floor.
MIN_EVENTS = 12
#: Two-sided family-wise error budget the Bonferroni threshold divides across every cell tested.
ALPHA = 0.05
#: Cells published in the artifact, ranked by |t|. The FULL count rides on `n_cells` -- the cap is
#: a file-size bound on the report, never on what was tested or on what the threshold divides.
MAX_PUBLISHED = 300

#: The four horizons, in minutes. Converted to BAR COUNTS on whichever chart the symbol has, so a
#: horizon finer than the chart is UNMEASURED for that symbol rather than silently rounded up.
HORIZON_MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1d": 1440}

#: The desk's session encoding, identical to `research/alpha_habitat.SESSIONS` and
#: `research/regime_discovery.SESSIONS`, by UTC hour of the event itself.
SESSIONS = {"asia": (0, 6), "london_am": (7, 12), "ny_open": (13, 15), "afternoon": (16, 23)}

TREND_DAYS = 3
VOL_DAYS = 10
#: Trailing window the volatility terciles are cut from, and the minimum before they are cut at
#: all. Rolling and shifted: a tercile taken over the whole sample is a rank nobody could have had.
VOL_QUANTILE_BARS = 2000
VOL_QUANTILE_MIN = 250

RULE = ("an atlas of measured reactions; consensus-based surprise UNMEASURED until the calendar "
        "carries actuals")


# =============================================================================================
# Small readers. Every one of them is tolerant and every absence is counted by the caller.
# =============================================================================================

def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return out if out.tzinfo else out.replace(tzinfo=UTC)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


@cache
def _importable() -> None:
    """Put the desk and the repository root on the path, whatever directory this was run from.

    MEASURED THE FIRST TIME THIS RAN AS A SCRIPT: from `desks/mt5/research/` the interpreter's
    sys.path[0] is the research directory, so `mt5desk` and `research.*` do not resolve -- and
    the module read that as "event_reaction is not registered on this tree" and donated nothing,
    while reporting a perfectly healthy 2,010 cells. An import that depends on the caller's
    working directory is a silent verdict, which is the one thing a refusal must never be.
    """
    for entry in (str(BASE), str(ROOT)):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def bar_time(when: datetime) -> tuple[datetime | None, str]:
    """The event instant in the BARS' OWN frame, or (None, why) -- never the raw stamp.

    An unconverted UTC stamp lands on a bar that opened two to three hours before the information
    existed. Dropping the event removes an observation; using it raw invents one.
    """
    _importable()
    try:
        from libs.research.bar_clock import to_bar_time
    except ImportError:                                  # pragma: no cover - import-context only
        return None, "NO_BAR_CLOCK"
    moved, status, _why = to_bar_time(when)
    return moved, status


@cache
def _lane_ok(symbol: str) -> bool | None:
    """True when this lane may hypothesise on `symbol`; None when the policy is unreadable.

    None is NOT permission. An unclassifiable symbol is named in the artifact and measured by
    nothing -- the registry is the only thing that may put an instrument in this lane.
    """
    _importable()
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:                                  # pragma: no cover - import-context only
        return None
    try:
        return bool(may_hypothesise(symbol))
    except Exception:                                    # pragma: no cover - policy is pure json
        return None


# =============================================================================================
# The events
# =============================================================================================

_TIME_KEYS = ("window_start_utc", "happened_at", "published_at", "at", "time", "date")
_INSTRUMENT_KEYS = ("instruments", "symbols", "symbol")


def _normalise(row: Any, source: str) -> dict[str, Any] | None:
    """One event row from any of the three shapes, or None with nothing claimed about it."""
    if not isinstance(row, dict):
        return None
    when = next((t for t in (_parse_time(row.get(k)) for k in _TIME_KEYS) if t is not None), None)
    if when is None:
        return None
    instruments: list[str] = []
    for key in _INSTRUMENT_KEYS:
        value = row.get(key)
        if isinstance(value, str):
            instruments.append(value)
        elif isinstance(value, list):
            instruments.extend(str(v) for v in value if isinstance(v, str))
    if not instruments:
        return None
    kind = str(row.get("kind") or row.get("category") or row.get("event_kind") or "").strip()
    if not kind:
        return None
    name = str(row.get("name") or row.get("title") or row.get("event_id") or kind)
    actual, consensus = row.get("actual"), row.get("consensus")
    return {"kind": kind.lower(), "name": name, "at": when, "source": source,
            "instruments": list(dict.fromkeys(instruments)),
            "actual": actual if isinstance(actual, int | float) else None,
            "consensus": consensus if isinstance(consensus, int | float) else None}


def _rows_from(path: Path, source: str) -> tuple[list[dict], str]:
    """Rows from a `.json` calendar or a `.jsonl` ledger, and the status of the read."""
    path = Path(path)
    if not path.exists():
        return [], "ABSENT"
    if path.suffix == ".jsonl":
        rows: list[dict] = []
        try:
            text = path.read_text("utf-8")
        except OSError:
            return [], "UNREADABLE"
        for line in text.splitlines():
            if line.strip():
                with suppress(ValueError):
                    rows.append(json.loads(line))
        return rows, "READ"
    doc = _read_json(path)
    if isinstance(doc, dict) and isinstance(doc.get("events"), list):
        return list(doc["events"]), "READ"
    if isinstance(doc, list):
        return list(doc), "READ"
    return [], "UNREADABLE"


def load_events(days: int, now: datetime) -> tuple[list[dict], dict[str, Any]]:
    """Every dated event in the window, from all three grounds, with the accounting."""
    cutoff = now - timedelta(days=int(days))
    events: list[dict] = []
    accounting: dict[str, Any] = {}
    for path, source in ((CALENDAR, "forced_flow_calendar"), (MACRO_LEDGER, "macro_event_ledger"),
                         (ROOT_EVENTS, "root_events_jsonl")):
        raw, status = _rows_from(path, source)
        kept, unusable = 0, 0
        for row in raw:
            got = _normalise(row, source)
            if got is None:
                unusable += 1
                continue
            if cutoff <= got["at"] <= now:
                events.append(got)
                kept += 1
        accounting[source] = {"path": str(path), "status": status, "rows": len(raw),
                              "in_window": kept, "unusable_rows": unusable}
    events.sort(key=lambda e: (e["at"], e["kind"], e["name"]))
    return events, accounting


def surprise_z(events: list[dict]) -> dict[int, float]:
    """`id(event) -> z` for rows carrying actual AND consensus, via `macro/surprise.z_score`.

    Each release's sigma comes from ITS OWN PAST surprises and nothing else -- the history handed
    to `z_score` is the strictly earlier rows of the same release name, so the z of the first ten
    prints of a release is UNMEASURED rather than computed against a pooled sigma. Empty today
    because the desk's vintages carry no actuals; the count is published either way.
    """
    try:
        from macro.surprise import z_score
    except ImportError:                                  # pragma: no cover - import-context only
        return {}
    by_release: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        if event["actual"] is not None and event["consensus"] is not None:
            by_release[event["name"]].append(event)
    out: dict[int, float] = {}
    for name, rows in by_release.items():
        rows.sort(key=lambda e: e["at"])
        for i, row in enumerate(rows):
            history = [float(r["actual"]) - float(r["consensus"]) for r in rows[:i]]
            est = z_score(float(row["actual"]), float(row["consensus"]), history, release_id=name)
            if est.z is not None and math.isfinite(est.z):
                out[id(row)] = float(est.z)
    return out


# =============================================================================================
# The conditioners that do not come from the bars
# =============================================================================================

def cot_percentiles() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per symbol: knowable instants (epoch seconds) and the EXPANDING percentile of net_pct_oi.

    Expanding, not full-sample: the percentile at a date uses only rows knowable by that date,
    which is the only version of "positioning is extreme" anybody could have acted on.

    EPOCH SECONDS, NOT datetime64. A tz-aware datetime handed to numpy is a deprecation the desk's
    `filterwarnings = error` turns into a test failure, and a silently-naive one is an hour of
    error in the shoulder months. Floats compare the same on both boxes.
    """
    doc = _read_json(COT)
    rows = doc.get("rows") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return {}
    grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            continue
        when = _parse_time(row.get("knowable_at"))
        value = row.get("net_pct_oi")
        if when is None or not isinstance(value, int | float):
            continue
        grouped[str(row.get("symbol", "")).upper()].append((when, float(value)))
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for symbol, pairs in grouped.items():
        if not symbol:
            continue
        pairs.sort(key=lambda p: p[0])
        values = np.array([p[1] for p in pairs], dtype=float)
        pct = np.array([float(np.mean(values[: i + 1] <= values[i])) for i in range(values.size)])
        out[symbol] = (np.array([p[0].timestamp() for p in pairs], dtype=float), pct)
    return out


def regime_timeline() -> tuple[list[tuple[float, str]], str]:
    """A DATED regime label series as (epoch seconds, label), and the reason when there is none.

    A single current label applied backwards over a year of events is not a conditioner, it is a
    look-ahead wearing one, so only a dated series is accepted here. `data/regime_state.json` as
    the box writes it today is a sleeve statistics file and carries no such series, which is why
    the regime axis reads UNMEASURED in the artifact rather than quietly collapsing to one bucket.
    """
    doc = _read_json(REGIME_STATE)
    if not isinstance(doc, dict):
        return [], f"{REGIME_STATE.name} absent or unreadable"
    for key in ("history", "regimes", "timeline"):
        rows = doc.get(key)
        if not isinstance(rows, list):
            continue
        out: list[tuple[float, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            when = next((t for t in (_parse_time(row.get(k)) for k in ("at", "time", "date"))
                         if t is not None), None)
            label = row.get("regime") or row.get("label") or row.get("state")
            if when is not None and isinstance(label, str) and label:
                out.append((when.timestamp(), label))
        if out:
            out.sort(key=lambda p: p[0])
            return out, "measured"
    return [], (f"{REGIME_STATE.name} carries no dated regime series (keys: "
                f"{sorted(doc)[:6]}); the regime axis is UNMEASURED, not neutral")


def cost_surface() -> dict[str, Any]:
    """The cost surface's per-symbol block, read ONCE -- it is three quarters of a megabyte."""
    doc = _read_json(COST_SURFACE)
    surface = doc.get("symbols") if isinstance(doc, dict) else None
    return surface if isinstance(surface, dict) else {}


def cost_fraction(symbol: str, close: np.ndarray, surface: dict[str, Any]) -> tuple[float, str]:
    """Round-trip cost proxy as a fraction of price, and where it came from."""
    row = surface.get(symbol)
    price = float(np.median(close)) if close.size else 0.0
    if isinstance(row, dict) and price > 0:
        pts, tick = row.get("pooled_median_spread_pts"), row.get("tick_size")
        if isinstance(pts, int | float) and isinstance(tick, int | float) and pts > 0 and tick > 0:
            return float(pts) * float(tick) / price, "cost_surface pooled median spread"
    if close.size > 2:
        moves = np.abs(np.diff(np.log(close)))
        if moves.size:
            return float(np.median(moves)) / 4.0, "fallback: median |bar return| / 4"
    return 0.0, "UNMEASURED: no cost surface entry and no bars to fall back on"


# =============================================================================================
# The bars
# =============================================================================================

def chart(symbol: str) -> tuple[pd.DataFrame, str, int] | None:
    """The finest chart the desk holds for `symbol`: (frame, timeframe, minutes per bar)."""
    for timeframe, minutes in (("M15", 15), ("H1", 60)):
        path = UNIVERSE / f"{symbol}_{timeframe}.parquet"
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path)
        except (OSError, ValueError, ImportError):
            continue
        if frame.empty or not {"open", "close"} <= set(frame.columns):
            continue
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~frame.index.isna()].sort_index()
        if len(frame) > 10:
            return frame, timeframe, minutes
    return None


def _bars(minutes: int, per_bar: int) -> int:
    return max(1, round(minutes / per_bar))


def features(frame: pd.DataFrame, per_bar: int) -> dict[str, np.ndarray] | None:
    """Everything the bars themselves condition on, each one ending BEFORE the event bar opens."""
    close = frame["close"].to_numpy(dtype=float)
    open_ = frame["open"].to_numpy(dtype=float)
    if close.size < 64 or not np.all(np.isfinite(close)) or not np.all(close > 0):
        return None
    if not np.all(np.isfinite(open_)) or not np.all(open_ > 0):
        return None
    log_close = np.log(close)
    returns = np.empty_like(log_close)
    returns[0] = 0.0
    returns[1:] = np.diff(log_close)
    vol_bars = _bars(VOL_DAYS * 1440, per_bar)
    series = pd.Series(returns)
    vol = series.rolling(vol_bars, min_periods=max(20, vol_bars // 4)).std(ddof=1).shift(1)
    quantile_min = min(VOL_QUANTILE_MIN, max(30, close.size // 4))
    low = vol.rolling(VOL_QUANTILE_BARS, min_periods=quantile_min).quantile(1 / 3).shift(1)
    high = vol.rolling(VOL_QUANTILE_BARS, min_periods=quantile_min).quantile(2 / 3).shift(1)
    span = _bars(TREND_DAYS * 1440, per_bar) + 1
    previous = np.concatenate(([np.nan], log_close[:-1]))
    past = np.concatenate((np.full(span, np.nan), log_close[:-span]))
    return {"log_close": log_close, "first_bar": np.log(close / open_),
            "vol": vol.to_numpy(), "vol_low": low.to_numpy(), "vol_high": high.to_numpy(),
            "trend": previous - past, "close": close, "min_pos": float(max(vol_bars, span) + 1)}


def _response(log_close: np.ndarray, horizon_bars: int) -> np.ndarray:
    out = np.full(log_close.size, np.nan)
    if horizon_bars < log_close.size:
        out[: log_close.size - horizon_bars] = log_close[horizon_bars:] - log_close[:-horizon_bars]
    return out


# =============================================================================================
# The buckets
# =============================================================================================

def _move_bucket(z: float, prefix: str) -> str:
    size = "ge1sigma" if abs(z) >= 1.0 else "lt1sigma"
    return f"{prefix}_{'up' if z > 0 else 'dn'}_{size}"


def _session_of(hour: int) -> str | None:
    for name, (lo, hi) in SESSIONS.items():
        if lo <= hour <= hi:
            return name
    return None


def _positioning(symbol: str, when: datetime,
                 table: dict[str, tuple[np.ndarray, np.ndarray]]) -> str | None:
    got = table.get(symbol.upper())
    if got is None:
        return None
    stamps, pct = got
    pos = int(np.searchsorted(stamps, when.timestamp(), side="right")) - 1
    if pos < 0:
        return None
    value = float(pct[pos])
    if value <= 0.2:
        return "short_extreme"
    return "long_extreme" if value >= 0.8 else "neutral"


def _regime_at(when: datetime, timeline: list[tuple[float, str]]) -> str | None:
    if not timeline:
        return None
    pos = bisect_right(timeline, when.timestamp(), key=lambda row: row[0]) - 1
    return timeline[pos][1] if pos >= 0 else None


# =============================================================================================
# The measurement
# =============================================================================================

def _stats(values: list[float]) -> dict[str, Any] | None:
    array = np.asarray(values, dtype=float)
    if array.size < MIN_EVENTS:
        return None
    mean, sd = float(np.mean(array)), float(np.std(array, ddof=1))
    if not math.isfinite(mean) or not math.isfinite(sd) or sd <= 0:
        return None
    t = mean / (sd / math.sqrt(array.size))
    return {"n": int(array.size), "mean_bp": round(mean * 1e4, 3),
            "median_bp": round(float(np.median(array)) * 1e4, 3), "sd_bp": round(sd * 1e4, 3),
            "hit_rate": round(float(np.mean(array > 0)), 4), "t": round(float(t), 3),
            "direction": "continuation" if mean > 0 else "reversal"}


def bonferroni_t(n_cells: int, alpha: float = ALPHA) -> float:
    """The two-sided |t| a cell must clear once the budget is divided across every cell tested."""
    if n_cells <= 0:
        return float("inf")
    return float(NormalDist().inv_cdf(1.0 - alpha / (2.0 * n_cells)))


def build(days: int = 400, budget_s: float = 240.0, now: datetime | None = None) -> dict[str, Any]:
    """Measure every cell and return the payload, touching nothing on disk."""
    started = time.monotonic()
    now = now or datetime.now(UTC)
    events, sources = load_events(days, now)
    zs = surprise_z(events)
    cot = cot_percentiles()
    timeline, regime_note = regime_timeline()

    by_symbol: dict[str, list[dict]] = defaultdict(list)
    set_aside: set[str] = set()
    unclassified: set[str] = set()
    for event in events:
        for symbol in event["instruments"]:
            verdict = _lane_ok(symbol)
            if verdict is None:
                unclassified.add(symbol)
            elif verdict:
                by_symbol[symbol].append(event)
            else:
                set_aside.add(symbol)

    cells: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    surface = cost_surface()
    costs: dict[str, tuple[float, str]] = {}
    timeframes: dict[str, str] = {}
    charts: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    placements: Counter[str] = Counter()
    no_chart: list[str] = []
    symbols = sorted(by_symbol)
    reached = 0
    for symbol in symbols:
        if time.monotonic() - started > budget_s:
            break
        reached += 1
        got = chart(symbol)
        if got is None:
            no_chart.append(symbol)
            continue
        frame, timeframe, per_bar = got
        feats = features(frame, per_bar)
        if feats is None:
            dropped["unusable_bars"] += 1
            continue
        charts[timeframe] += 1
        timeframes[symbol] = timeframe
        costs[symbol] = cost_fraction(symbol, feats["close"], surface)
        horizons = {name: _bars(minutes, per_bar)
                    for name, minutes in HORIZON_MINUTES.items() if minutes >= per_bar}
        dropped["horizon_finer_than_chart"] += len(HORIZON_MINUTES) - len(horizons)
        responses = {name: _response(feats["log_close"], bars) for name, bars in horizons.items()}
        index = frame.index
        longest = max(horizons.values())
        for event in by_symbol[symbol]:
            moved, status = bar_time(event["at"])
            if moved is None:
                dropped[f"clock_{status}"] += 1
                continue
            pos = int(index.searchsorted(pd.Timestamp(moved), side="left"))
            if pos < feats["min_pos"] or pos + longest >= index.size:
                dropped["outside_chart"] += 1
                continue
            first, sigma = float(feats["first_bar"][pos]), float(feats["vol"][pos])
            if first == 0.0 or not math.isfinite(first) or not math.isfinite(sigma) or sigma <= 0:
                dropped["no_orientation"] += 1
                continue
            sign = 1.0 if first > 0 else -1.0
            buckets: dict[str, str] = {"all": "all"}
            z = zs.get(id(event))
            buckets["surprise_z" if z is not None else "surprise_proxy"] = _move_bucket(
                z if z is not None else first / sigma,
                "z" if z is not None else "move")
            trend = float(feats["trend"][pos])
            if math.isfinite(trend) and trend != 0.0:
                buckets["trend_3d"] = "up" if trend > 0 else "down"
            low, high = float(feats["vol_low"][pos]), float(feats["vol_high"][pos])
            if math.isfinite(low) and math.isfinite(high):
                buckets["vol_tercile"] = ("low" if sigma <= low
                                          else "high" if sigma >= high else "mid")
            session = _session_of(event["at"].hour)
            if session:
                buckets["session"] = session
            positioning = _positioning(symbol, event["at"], cot)
            if positioning:
                buckets["positioning"] = positioning
            regime = _regime_at(event["at"], timeline)
            if regime:
                buckets["regime"] = regime
            placements[event["kind"]] += 1
            for name in horizons:
                value = float(responses[name][pos])
                if not math.isfinite(value):
                    continue
                for axis, bucket in buckets.items():
                    cells[(event["kind"], symbol, name, axis, bucket)].append(sign * value)

    rows: list[dict[str, Any]] = []
    for (kind, symbol, horizon, axis, bucket), values in cells.items():
        stats = _stats(values)
        if stats is None:
            continue
        cost, cost_source = costs.get(symbol, (0.0, "UNMEASURED"))
        net = abs(stats["mean_bp"]) - cost * 1e4
        rows.append({"cell": f"{kind}.{symbol}.{horizon}.{axis}={bucket}", "kind": kind,
                     "symbol": symbol, "horizon": horizon, "axis": axis, "bucket": bucket,
                     "tf": timeframes.get(symbol, ""),
                     **stats, "cost_bp": round(cost * 1e4, 3), "cost_source": cost_source,
                     "edge_net_bp": round(net, 3),
                     "verdict": "CLEARS_COST" if net > 0 else "BELOW_COST"})
    threshold = bonferroni_t(len(rows))
    for row in rows:
        row["clears_bonferroni"] = bool(abs(row["t"]) >= threshold)
    rows.sort(key=lambda r: -abs(r["t"]))
    clearing = [r for r in rows if r["clears_bonferroni"] and r["verdict"] == "CLEARS_COST"]

    return {
        "at": now.isoformat(),
        "rule": RULE,
        "days": int(days),
        "elapsed_s": round(time.monotonic() - started, 2),
        "sources": sources,
        "n_events": len(events),
        "n_events_by_kind": dict(sorted(Counter(e["kind"] for e in events).items())),
        "n_placements_by_kind": dict(sorted(placements.items())),
        "n_cells": len(rows),
        "threshold_t": round(threshold, 4),
        "alpha": ALPHA,
        "horizons": dict(HORIZON_MINUTES),
        "conditioners": ["all", "surprise_proxy", "surprise_z", "trend_3d", "vol_tercile",
                         "session", "positioning", "regime"],
        "charts": dict(charts),
        "cells": rows[:MAX_PUBLISHED],
        "clearing": clearing[:MAX_PUBLISHED],
        "donated": {"n": 0, "path": None, "status": "not attempted", "cells": []},
        "budget": {"budget_s": float(budget_s), "symbols": len(symbols), "reached": reached,
                   "stopped": reached < len(symbols)},
        "unmeasured": {
            "surprise_z_events": len(zs),
            "surprise_note": ("z needs actual AND consensus and this desk's vintages carry "
                              "neither; every other event is bucketed on the realised first bar, "
                              "labelled surprise_proxy and never called a surprise"),
            "dropped": dict(sorted(dropped.items())),
            "symbols_without_chart": sorted(no_chart)[:20],
            "n_symbols_without_chart": len(no_chart),
            "instruments_set_aside_event_lane": sorted(set_aside),
            "instruments_unclassified": sorted(unclassified),
            "symbols_not_reached": max(0, len(symbols) - reached),
            "regime_axis": regime_note,
            "positioning_axis": f"{len(cot)} symbols carry a COT series",
            "note": ("a dropped event is an observation the desk could not place, never a "
                     "reaction of zero; a cell below n=12 is absent from this artifact"),
        },
    }


# =============================================================================================
# Donation -- the family's own parameter names, and nothing this atlas invented
# =============================================================================================

def _registered_family(name: str) -> bool:
    _importable()
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    except ImportError:                                  # pragma: no cover - import-context only
        return False
    return name in ORTHOGONAL_FAMILIES


def _donate(candidates: list[dict], tests_run: int) -> Path | None:
    _importable()
    from research.proposer_common import donate
    return donate(SOURCE, candidates, tests_run)


def donation_params(horizon: str, direction: str) -> dict[str, Any]:
    """`mt5desk.family_event_reaction` parameters ONLY -- hold in H1 bars, which is its clock.

    `mode` carries the measured claim (continuation -> drift, reversal -> fade). `side` is the
    direction the EVENT implies and the family takes it as a CONSTANT, while this atlas oriented
    every response on the first bar's own sign -- so the donated cell is the weaker, unconditional
    expression of what was measured, and the mechanism line says so rather than implying the
    gauntlet is testing the conditional claim.
    """
    hold = max(1, round(HORIZON_MINUTES[horizon] / 60))
    return {"mode": "drift" if direction == "continuation" else "fade", "side": 1,
            "hold_bars": hold, "ttl_bars": 2 * hold, "cooldown_bars": hold,
            "atr_n": 20, "stop_atr": 2.0, "rr": 1.5}


def donate_clearing(payload: dict[str, Any], max_donations: int) -> dict[str, Any]:
    """Donate the clearing cells as `event_reaction` hypotheses. Never an equity, never a guess."""
    clearing = payload.get("clearing") or []
    if not clearing:
        return {"n": 0, "path": None, "status": "no cell cleared both bars", "cells": []}
    if not _registered_family(FAMILY):
        return {"n": 0, "path": None, "cells": [],
                "status": f"{FAMILY} is not in ORTHOGONAL_FAMILIES on this tree; donated nothing"}
    candidates: list[dict[str, Any]] = []
    for row in clearing:
        if len(candidates) >= max_donations:
            break
        if _lane_ok(row["symbol"]) is not True:
            continue
        params = donation_params(row["horizon"], row["direction"])
        candidates.append({
            "kind": "hypothesis", "symbol": row["symbol"], "symbols": [row["symbol"]],
            "family": FAMILY, "params": params, "cell": row["cell"],
            "title": f"{row['kind']} reaction on {row['symbol']} at {row['horizon']}",
            "mechanism": (f"measured over {row['n']} {row['kind']} events with "
                          f"{row['axis']}={row['bucket']}: mean {row['mean_bp']}bp at "
                          f"{row['horizon']} oriented on the first bar's move, t={row['t']}, "
                          f"hit {row['hit_rate']}, cost {row['cost_bp']}bp "
                          f"({row['cost_source']}). The donated cell is the UNCONDITIONAL "
                          "expression: the family's side is constant and cannot read the "
                          "first-bar sign the atlas oriented on"),
            "why": (f"clears the Bonferroni threshold {payload.get('threshold_t')} over "
                    f"{payload.get('n_cells')} cells tested and its |mean| exceeds the cost "
                    "proxy -- a hypothesis for the ten gates, not a claim"),
            "n_events": row["n"], "t": row["t"], "horizon": row["horizon"],
            "conditioner": f"{row['axis']}={row['bucket']}", "event_time": payload.get("at"),
        })
    if not candidates:
        return {"n": 0, "path": None, "cells": [],
                "status": "every clearing cell was set aside by the two-lane mandate"}
    try:
        path = _donate(candidates, int(payload.get("n_cells") or len(candidates)))
    except Exception as exc:                             # pragma: no cover - intake write failure
        return {"n": 0, "path": None, "cells": [],
                "status": f"donation refused: {type(exc).__name__}: {exc}"}
    return {"n": len(candidates) if path else 0, "path": str(path) if path else None,
            "cells": [c["cell"] for c in candidates],
            "status": "donated" if path else "the donation door refused every row"}


# =============================================================================================
# CLI
# =============================================================================================

def run(days: int = 400, budget_s: float = 240.0, max_donations: int = 15,
        dry_run: bool = False, path: Path | str | None = None) -> dict[str, Any]:
    payload = build(days=days, budget_s=budget_s)
    if dry_run:
        payload["donated"] = {"n": 0, "path": None, "cells": [],
                              "status": "dry run: nothing donated, nothing written"}
        return payload
    payload["donated"] = donate_clearing(payload, max_donations)
    _atomic_json(Path(path or REPORT), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    parser.add_argument("--days", type=int, default=400, help="lookback window for events")
    parser.add_argument("--budget-s", type=float, default=240.0, help="wall-clock budget")
    parser.add_argument("--max-donations", type=int, default=15)
    parser.add_argument("--path", default=None, help="artifact path")
    args = parser.parse_args(argv)

    out = Path(args.path or REPORT)
    payload = run(days=args.days, budget_s=args.budget_s, max_donations=args.max_donations,
                  dry_run=args.dry_run, path=out)
    kinds = ", ".join(f"{k}={v}"
                      for k, v in list(payload["n_placements_by_kind"].items())[:4])
    sources = ", ".join(f"{k}={v['status']}/{v['in_window']}"
                        for k, v in payload["sources"].items())
    budget, top = payload["budget"], (payload["cells"] or [{}])[0]
    print(f"event_response_atlas at={payload['at']} days={payload['days']} "
          f"elapsed={payload['elapsed_s']}s")
    print(f"  sources      {sources}")
    print(f"  events       loaded={payload['n_events']} placements_by_kind[{kinds}]")
    print(f"  charts       {payload['charts']} dropped={payload['unmeasured']['dropped']}")
    print(f"  cells        tested={payload['n_cells']} published={len(payload['cells'])} "
          f"threshold_t={payload['threshold_t']} (bonferroni alpha={payload['alpha']})")
    print(f"  top          {top.get('cell', 'NONE')} t={top.get('t')} "
          f"mean={top.get('mean_bp')}bp n={top.get('n')}")
    print(f"  clearing     {len(payload['clearing'])} -> donated="
          f"{payload['donated']['n']} ({payload['donated']['status']})")
    print(f"  budget       {budget['reached']}/{budget['symbols']} symbols, "
          f"stopped={budget['stopped']}; "
          + ("dry run: nothing written" if args.dry_run else f"wrote {out}"))
    return 0


if __name__ == "__main__":                                       # pragma: no cover - CLI
    raise SystemExit(main())
