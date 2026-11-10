"""THE INDEPENDENT REPLICATION CIVILIZATION (LAWS 5m): a second implementation of every
certificate and every forward-enrolled row, from the WRITTEN SPECIFICATION and the raw bars only.

    python research/replication_civilization.py --once --budget-s 900 [--dry-run]

THE RULE OF THIS LANE, and the test pins it: NOTHING HERE IMPORTS THE ORIGINAL IMPLEMENTATION.
Not `mt5desk.families`, not `mt5desk.engine`, not `proposer_common`, not the gauntlet, not the
shadow engine. The lane is handed a candidate's written specification -- the family's rule text
in `SPEC_BOOK`, the cell's parameters, the data name (`<SYM>_<TF>.parquet`) and the cost terms
from the universe registry -- and rebuilds the signal, the fills, the exits and the costs in its
own code from that text. Then it compares outcomes with what the desk recorded:

    certificates      the ten-gate row's in-sample Sharpe (UNIVERSAL_SURVIVORS.json)
    forward rows      the forward ledger's trades (reports/shadow/ledger_*.json): fills,
                      per-trade R, summed P&L, whether a position is open, and the cost terms
                      the registry froze

and QUARANTINES on a material disagreement -- `replication_mismatch` in research memory, the
cell in `data/replication_civilization/quarantine.json`, and `replication_verdict` on every
queued registry candidate of the same (symbol, family) -- with the divergence named. Agreement
is REPLICATED; a family the book has no written rule for, a cell with no bars, or a forward row
with no ledger is UNMEASURED by name (a value, never a pass).

Rotation: a cursor over both lanes so every certificate and every forward row is reached across
passes; each pass takes a bounded slice so it finishes inside its budget. `--dry-run` rebuilds,
compares and prints, and writes nothing. Artifact: `reports/REPLICATION.json`.

WHY A SECOND IMPLEMENTATION AND NOT A SECOND READING. `lead_replication` re-derives a LEAD from
its frozen text and reproduces it with the desk's own family and screen; that catches a lead
that was never what its text said. This lane catches the other failure: an implementation that
does not do what its specification says -- a fill rule, an exit, a cost unit -- which a second
reading through the same engine can only faithfully reproduce twice.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "replication_civilization"
UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
SLEEVE_REGISTRY = DESK / "data" / "sleeve_registry.json"
SHADOW_DIR = DESK / "reports" / "shadow"
STATE_DIR = DESK / "data" / "replication_civilization"
CURSOR = STATE_DIR / "cursor.json"
QUARANTINE = STATE_DIR / "quarantine.json"
REPORT = DESK / "reports" / "REPLICATION.json"
#: THE VERDICT BOOK (2026-09-30): the last verdict per CERTIFICATE, with the spec fingerprint it
#: was judged under. `research/admission_integrity.py` reads it: a new certificate starts a
#: forward clock only when this book says REPLICATED under its current spec.
VERDICTS_NAME = "verdicts.json"

BUDGET_S = 900.0
#: Breadth-per-run bound so a pass finishes; the cursor rotates through both lanes so every row
#: is reached across passes (LAWS 2: a count is never a ceiling).
MAX_PER_PASS = 16
MIN_BARS = 300
# MEASURED over 433 deals (reports/COST_TRUTH.json 2026-09-23): 2.00 in ACCOUNT CURRENCY
# per lot per side. Mirrors libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE.
COMMISSION_PER_LOT_PER_SIDE = 2.00
#: MATERIAL DISAGREEMENT, written down. A Sharpe of the other sign (when the recorded one is
#: not itself noise), or outside half-to-double of the recorded one; forward fills off by more
#: than half, fewer than half the ledger's trades matched, a matched trade's R off by more than
#: a quarter of a unit at the median, the summed P&L of the other sign, a position open on one
#: side and closed on the other, or a cost term off by more than 2x.
SHARPE_NOISE = 0.05
SHARPE_RATIO = (0.5, 2.0)
SHARPE_METRIC_VERSION = "daily-r-per-period-v2"
FILL_SHARE = 0.5
MATCH_SHARE = 0.5
R_TOLERANCE = 0.25
COST_RATIO = (0.5, 2.0)
MATCH_BARS = 1

REPLICATED = "REPLICATED"
MISMATCH = "MISMATCH"
UNMEASURED = "UNMEASURED"

#: Modules this lane must never import: the original implementations and their doors. The test
#: reads this tuple and the source.
FORBIDDEN_IMPORTS: tuple[str, ...] = (
    "mt5desk.families", "mt5desk.families_orthogonal", "mt5desk.families_edge_queue",
    "mt5desk.family_state_space", "mt5desk.engine", "mt5desk.family_call", "proposer_common",
    "external_gauntlet", "lead_replication", "shadow_forward", "external_shadow")

RULE = ("a second implementation from the written specification and the raw bars only; a "
        "material disagreement on fills, P&L, position state or costs is quarantined by name")

BARS_READ: list[str] = []


# ----------------------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    os.replace(tmp, path)


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


# ------------------------------------------------------------------------------------- bars
@dataclass
class Bars:
    """The lane's own bar frame: epoch-ns UTC, OHLC, and the clock fields the rules read."""

    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    low: np.ndarray
    c: np.ndarray
    minutes: int
    #: The broker's own per-bar columns when the file carries them (`spread`, `tick_volume`),
    #: aligned to `t`. Only the rules that read the venue's state use them.
    cols: dict[str, np.ndarray] = field(default_factory=dict)

    def __len__(self) -> int:
        return int(self.t.size)

    @property
    def hour(self) -> np.ndarray:
        return ((self.t // 3_600_000_000_000) % 24).astype("int64")

    @property
    def day(self) -> np.ndarray:
        return (self.t // 86_400_000_000_000).astype("int64")

    @property
    def dow(self) -> np.ndarray:
        return ((self.day + 3) % 7).astype("int64")        # 1970-01-01 was a Thursday


def bars_from_arrays(t_ns: np.ndarray, o: np.ndarray, h: np.ndarray, low: np.ndarray,
                     c: np.ndarray, cols: Mapping[str, np.ndarray] | None = None) -> Bars:
    t = np.asarray(t_ns, dtype="int64")
    order = np.argsort(t, kind="stable")
    t = t[order]
    gaps = np.diff(t) if len(t) > 1 else np.asarray([3_600_000_000_000])
    gaps = gaps[gaps > 0]
    step = int(np.median(gaps)) if len(gaps) else 3_600_000_000_000
    return Bars(t, np.asarray(o, dtype="float64")[order], np.asarray(h, dtype="float64")[order],
                np.asarray(low, dtype="float64")[order], np.asarray(c, dtype="float64")[order],
                max(1, step // 60_000_000_000),
                {k: np.asarray(v, dtype="float64")[order] for k, v in dict(cols or {}).items()})


#: The broker's per-bar columns the lane carries beside OHLC when a file holds them.
VENUE_COLUMNS = ("spread", "tick_volume")


def load_bars(symbol: str, timeframe: str = "H1", universe: Path | None = None) -> Bars | None:
    """`<SYM>_<TF>.parquet` opened by THIS module through pyarrow, normalised by THIS module."""
    path = Path(universe or UNIVERSE_DIR) / f"{symbol.upper()}_{str(timeframe).upper()}.parquet"
    if not path.exists():
        return None
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(path)
    except Exception:
        return None
    BARS_READ.append(str(path))
    cols = {name.lower(): name for name in table.column_names}
    need = ("open", "high", "low", "close")
    if any(k not in cols for k in need):
        return None
    try:
        import pandas as pd
        frame = table.to_pandas()
        # THE TIME COLUMN IS USUALLY THE INDEX, AND THAT COST THIS LANE ITS ENTIRE LIFE
        # (measured 2026-09-24). `pq.read_table().column_names` lists `time`, because the file
        # stores it as a column; but the desk writes these parquets with pandas metadata naming
        # `time` the index, so `to_pandas()` moves it to the DatetimeIndex and DROPS it from
        # `frame.columns`. `frame["time"]` then raised KeyError, the bare `except` below turned
        # that into `return None`, and the caller reported "<SYM> bars absent or shorter than 300
        # rows" -- of a file holding 43,655 of them. Every verdict this lane has ever published
        # was UNMEASURED with a reason that was false, which is worse than an error: an organ
        # that says "no data" is believed. Look in `columns` first, and fall back to the index.
        tcol = cols.get("time")
        if tcol is not None and tcol not in frame.columns:
            tcol = None
        raw = frame[tcol] if tcol is not None else frame.index.to_series()
        stamps = pd.to_datetime(raw, utc=True, errors="coerce")
        # EPOCH-NANOSECONDS, WHATEVER UNIT THE FILE WAS WRITTEN IN. pandas 2 keeps a parquet's
        # own resolution (ms, us), and `astype("int64")` below then returns THOSE units: every
        # hour and day this lane derives was off by 1000x or 1e6x and `minutes` read 1 on an H1
        # file. Normalising the unit first makes the int64 the nanoseconds `Bars` is defined in.
        stamps = stamps.astype("datetime64[ns, UTC]")
        keep = ~stamps.isna().to_numpy()
        # nanoseconds by construction: pandas 3 parses to microsecond resolution, so a bare
        # int64 cast read hourly bars as 3,600,000 ns apart and the bar clock as 1 minute
        t_ns = (stamps[keep].dt.as_unit("ns").astype("int64").to_numpy()
                if hasattr(stamps, "dt") else None)
        if t_ns is None:
            return None
        arrs = [frame[cols[k]].to_numpy(dtype="float64")[keep] for k in need]
        extra = {k: frame[cols[k]].to_numpy(dtype="float64")[keep]
                 for k in VENUE_COLUMNS if k in cols and cols[k] in frame.columns}
    except Exception:
        return None
    if len(t_ns) < 2:
        return None
    return bars_from_arrays(np.asarray(t_ns, dtype="int64"), arrs[0], arrs[1], arrs[2], arrs[3],
                            cols=extra)


# ------------------------------------------------------------------------------ indicators
def atr(bars: Bars, n: int) -> np.ndarray:
    """Average true range, as the rule book writes it: the mean of max(h-l, |h-prev c|,
    |l-prev c|) over the trailing n bars, fewer allowed at the start."""
    prev = np.concatenate([[np.nan], bars.c[:-1]])
    tr = np.maximum(bars.h - bars.low,
                    np.fmax(np.abs(bars.h - prev), np.abs(bars.low - prev)))
    tr = np.where(np.isfinite(tr), tr, bars.h - bars.low)
    out = np.empty(len(tr))
    csum = np.cumsum(tr)
    for i in range(len(tr)):
        lo = max(0, i - n + 1)
        out[i] = (csum[i] - (csum[lo - 1] if lo > 0 else 0.0)) / (i - lo + 1)
    return out


def rsi(close: np.ndarray, n: int) -> np.ndarray:
    """RSI as written: mean gain / mean loss over the trailing n bars (fewer at the start);
    no losses in the window reads as undefined, never as 100."""
    d = np.diff(close)
    gain = np.concatenate([[0.0], np.where(d > 0, d, 0.0)])
    loss = np.concatenate([[0.0], np.where(d < 0, -d, 0.0)])
    cg, cl = np.cumsum(gain), np.cumsum(loss)
    out = np.full(len(close), np.nan)
    for i in range(1, len(close)):
        lo = max(1, i - n + 1)
        span = i - lo + 1
        g = (cg[i] - cg[lo - 1]) / span
        ls = (cl[i] - cl[lo - 1]) / span
        out[i] = 100.0 - 100.0 / (1.0 + g / ls) if ls > 0 else np.nan
    return out


# ------------------------------------------------------------------------------- the rules
@dataclass
class Order:
    """One signal as the rule book states it: the bar it is known at, the side, the protective
    stop, the target, the bars it may live, and (breakouts) the resting trigger and its life."""

    t_ns: int
    side: int
    stop: float
    target: float
    ttl_bars: int
    trigger: float | None = None
    wait_bars: int = 1


@dataclass
class RuleSpec:
    """A family's WRITTEN specification: the text is the contract, `build` is this lane's own
    reading of it, and `defaults` are the parameters the text names."""

    family: str
    text: str
    defaults: dict[str, Any]
    build: Callable[[Bars, dict[str, Any]], list[Order]]
    selector_params: bool = False
    #: The rule itself decides each order's side (a fade reverses the move it reads), so the
    #: certificate's single `side` field must not filter its orders.
    rule_sets_side: bool = False
    #: The session is the certificate's own `session` PARAMETER, never its selector: the desk
    #: builds these cells with no window (`_selector` stamps them "continuous", and older rows
    #: carry the "asia" fallback the gauntlet records as a lie for families with no session).
    session_in_params: bool = False


def _build_overnight_gap_decay(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    day = b.day
    first = np.concatenate([[True], day[1:] != day[:-1]])
    out: list[Order] = []
    for i in range(int(p["atr_n"]), len(b) - 1):
        if not first[i] or not (a[i] > 0):
            continue
        gap = float(b.o[i] - b.c[i - 1])
        if abs(gap) < float(p["gap_atr"]) * a[i]:
            continue
        side = -1 if gap > 0 else 1
        px = float(b.o[i])
        out.append(Order(int(b.t[i]), side, px - side * float(p["stop_atr"]) * a[i],
                         px + side * abs(gap) * float(p["rr"]), int(p["ttl_bars"])))
    return out


def _build_session_range_breakout(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    hour, day = b.hour, b.day
    rs, re_ = int(p["range_start"]), p.get("range_end")
    if re_ is None:
        in_range = hour < rs
        sig_h = int(p["signal_at"]) if p.get("signal_at") is not None else rs
    else:
        in_range = (hour >= rs) & (hour < int(re_))
        sig_h = int(p["signal_at"]) if p.get("signal_at") is not None else int(re_)
    hi: dict[int, float] = {}
    lo: dict[int, float] = {}
    for i in np.nonzero(in_range)[0]:
        d = int(day[i])
        hi[d] = max(hi.get(d, -np.inf), float(b.h[i]))
        lo[d] = min(lo.get(d, np.inf), float(b.low[i]))
    out: list[Order] = []
    rr, ttl, wait = float(p["rr"]), int(p["ttl_bars"]), int(p["wait_bars"])
    for i in range(1, len(b) - 2):
        if hour[i] != sig_h or not (a[i] > 0) or not np.isfinite(b.o[i]):
            continue
        d = int(day[i])
        if d not in hi:
            continue
        span = hi[d] - lo[d]
        if span <= 0:
            continue
        dist = max(1.2 * float(a[i]), span)
        out.append(Order(int(b.t[i]), 1, hi[d] - dist, hi[d] + dist * rr, ttl, hi[d], wait))
        out.append(Order(int(b.t[i]), -1, lo[d] + dist, lo[d] - dist * rr, ttl, lo[d], wait))
    return out


def _build_dow_effect(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    hour, dow = b.hour, b.dow
    out: list[Order] = []
    for i in range(2, len(b) - 2):
        if hour[i] != 0 or not (a[i] > 0):
            continue
        side = 1 if dow[i] == int(p["dow_long"]) else -1 if dow[i] == int(p["dow_short"]) else 0
        if not side:
            continue
        entry, sd = float(b.o[i]), 1.2 * float(a[i])
        out.append(Order(int(b.t[i]), side, entry - side * sd, entry + side * sd * float(p["rr"]),
                         int(p["ttl_bars"])))
    return out


def _build_monday_gap(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    hour, dow = b.hour, b.dow
    out: list[Order] = []
    for i in range(2, len(b) - 2):
        if dow[i] != 0 or hour[i] != 0 or not (a[i] > 0):
            continue
        j = i - 1
        while j > 0 and dow[j] != 4:
            j -= 1
        if j <= 0:
            continue
        gap = float(b.o[i] - b.c[j])
        if abs(gap) < float(p["min_gap_atr"]) * a[i]:
            continue
        side = 1 if gap > 0 else -1
        if str(p["mode"]) == "fade":
            side = -side
        entry, sd = float(b.o[i]), 1.2 * float(a[i])
        out.append(Order(int(b.t[i]), side, entry - side * sd, entry + side * sd * float(p["rr"]),
                         int(p["ttl_bars"])))
    return out


def _build_mean_reversion_rsi(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    r = rsi(b.c, int(p["rsi_n"]))
    os_, ob = float(p["oversold"]), float(p["overbought"])
    out: list[Order] = []
    for i in range(max(int(p["rsi_n"]), int(p["atr_n"])) + 1, len(b) - 2):
        if not (a[i] > 0) or not np.isfinite(r[i]) or not np.isfinite(r[i - 1]):
            continue
        side = 1 if (r[i - 1] < os_ <= r[i]) else -1 if (r[i - 1] > ob >= r[i]) else 0
        if not side:
            continue
        entry, sd = float(b.o[i]), 1.2 * float(a[i])
        out.append(Order(int(b.t[i]), side, entry - side * sd, entry + side * sd * float(p["rr"]),
                         int(p["ttl_bars"])))
    return out


def _build_overnight_drift(b: Bars, p: dict[str, Any]) -> list[Order]:
    a = atr(b, int(p["atr_n"]))
    hour, hb = b.hour, int(p["hold_bars"])
    out: list[Order] = []
    for i in range(hb + 2, len(b) - 2):
        if hour[i] != int(p["anchor_hour"]) or not (a[i] > 0):
            continue
        drift = float(b.c[i] - b.c[i - hb]) / float(a[i])
        if abs(drift) < 0.3:
            continue
        side = -1 if drift > 0 else 1
        entry, sd = float(b.o[i]), 1.2 * float(a[i])
        out.append(Order(int(b.t[i]), side, entry - side * sd, entry + side * sd * float(p["rr"]),
                         int(p["ttl_bars"])))
    return out


SPEC_BOOK: dict[str, RuleSpec] = {
    "overnight_gap_decay": RuleSpec(
        "overnight_gap_decay",
        "On the first bar of each day, if |open - previous close| >= gap_atr x ATR(atr_n), fade "
        "the gap: side against it, entry at the NEXT bar's open, stop stop_atr x ATR from the "
        "signal bar's open, target the signal bar's open plus |gap| x rr in the trade's favour, "
        "time exit after ttl_bars.",
        {"gap_atr": 0.75, "atr_n": 20, "stop_atr": 1.5, "rr": 1.0, "ttl_bars": 8},
        _build_overnight_gap_decay),
    "session_range_breakout": RuleSpec(
        "session_range_breakout",
        "At the signal hour, take the day's range over the session window (hours before "
        "range_start, or [range_start, range_end)); dist = max(1.2 x ATR(atr_n), range span). "
        "A resting buy stop at the range high (stop high - dist, target high + dist x rr) and a "
        "resting sell stop at the range low (stop low + dist, target low - dist x rr), each alive "
        "wait_bars bars from the next bar; time exit after ttl_bars. The selector names the "
        "window: asia = hours before 7; london_am = [10,13) signalled at 13; ny_open = [13,14) "
        "at 14; afternoon = [14,17) at 17.",
        {"range_start": 7, "range_end": None, "signal_at": None, "wait_bars": 8, "atr_n": 20,
         "ttl_bars": 12, "rr": 2.0}, _build_session_range_breakout, selector_params=True),
    "dow_effect": RuleSpec(
        "dow_effect",
        "At hour 0, long on weekday dow_long and short on weekday dow_short (Monday = 0); entry "
        "next open, stop 1.2 x ATR(atr_n), target rr x that distance, time exit after ttl_bars.",
        {"dow_long": 0, "dow_short": 3, "atr_n": 20, "ttl_bars": 12, "rr": 1.8},
        _build_dow_effect),
    "monday_gap": RuleSpec(
        "monday_gap",
        "At Monday hour 0, gap = open - the last Friday bar's close; if |gap| >= min_gap_atr x "
        "ATR(atr_n) trade with the gap (mode momentum) or against it (mode fade): entry next "
        "open, stop 1.2 x ATR, target rr x that, time exit after ttl_bars.",
        {"atr_n": 20, "ttl_bars": 12, "rr": 1.8, "mode": "momentum", "min_gap_atr": 0.2},
        _build_monday_gap),
    "mean_reversion_rsi": RuleSpec(
        "mean_reversion_rsi",
        "RSI(rsi_n) crossing up through oversold is a long, crossing down through overbought a "
        "short; entry next open, stop 1.2 x ATR(atr_n), target rr x that, time exit after "
        "ttl_bars.",
        {"rsi_n": 14, "oversold": 30, "overbought": 70, "atr_n": 20, "ttl_bars": 12, "rr": 1.8},
        _build_mean_reversion_rsi),
    "overnight_drift": RuleSpec(
        "overnight_drift",
        "At anchor_hour, drift = (close - close hold_bars ago) / ATR(atr_n); if |drift| >= 0.3 "
        "fade it: entry next open, stop 1.2 x ATR, target rr x that, time exit after ttl_bars.",
        {"anchor_hour": 0, "hold_bars": 8, "atr_n": 20, "ttl_bars": 12, "rr": 1.8},
        _build_overnight_drift),
}

#: Breakout selector -> window parameters, written into the spec text above.
WINDOWS: dict[str, dict[str, Any]] = {
    "asia": {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12,
                "rr": 2.0, "ttl_bars": 12},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
}

# ------------------------------------------------ rules for hunt16 cells and carry (2026-09-30)
# WHY THESE THREE. The admission door holds a NEW certificate until this lane says REPLICATED under
# its spec, and a family with no written rule here can only ever be UNMEASURED -- so it is held for
# ever. `dav_range_filter_adx` (hunt16), `hunt16_cell` (the registry door the sealed gauntlet builds
# a hunt16 cell through) and `carry` had none. Each rule below is written from the family's stated
# behaviour and rebuilt in THIS module's own code; nothing is imported from the implementations
# (FORBIDDEN_IMPORTS, and `run_hunt16`/`run_hunt12` are read by no line here either).

#: hunt16 selector -> the hour its signals are kept at (the window's signal hour, else its start).
HUNT16_SIGNAL_HOUR: dict[str, int] = {"asia": 7, "london_am": 13, "ny_open": 14, "afternoon": 17}


def _sma_strict(x: np.ndarray, n: int) -> np.ndarray:
    """Trailing mean over exactly n values; undefined (NaN) until n are available or when any
    of them is undefined."""
    out = np.full(len(x), np.nan)
    if n <= 0 or len(x) < n:
        return out
    ok = np.isfinite(x)
    xs = np.where(ok, x, 0.0)
    cs = np.concatenate([[0.0], np.cumsum(xs)])
    cn = np.concatenate([[0], np.cumsum(ok.astype("int64"))])
    for i in range(n - 1, len(x)):
        if cn[i + 1] - cn[i + 1 - n] == n:
            out[i] = (cs[i + 1] - cs[i + 1 - n]) / n
    return out


def _roll_strict(x: np.ndarray, n: int, fn: Callable[[np.ndarray], float]) -> np.ndarray:
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if np.all(np.isfinite(w)):
            out[i] = fn(w)
    return out


def _true_range(b: Bars) -> np.ndarray:
    prev = np.concatenate([[np.nan], b.c[:-1]])
    tr = np.fmax(b.h - b.low, np.fmax(np.abs(b.h - prev), np.abs(b.low - prev)))
    return np.asarray(tr, dtype="float64")


def _adx_strict(b: Bars, n: int) -> np.ndarray:
    """ADX as written: +DM = up move when it exceeds the down move and is positive, -DM the
    mirror; DI = 100 x mean(DM, n) / mean(TR, n); DX = 100 x |DI+ - DI-| / (DI+ + DI-); ADX =
    mean(DX, n). Every mean is a strict n-bar trailing mean; a zero denominator is undefined."""
    up = np.concatenate([[np.nan], np.diff(b.h)])
    dn = np.concatenate([[np.nan], -np.diff(b.low)])
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    atr_ = _sma_strict(_true_range(b), n)
    atr_ = np.where(atr_ == 0, np.nan, atr_)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100.0 * _sma_strict(plus, n) / atr_
        mdi = 100.0 * _sma_strict(minus, n) / atr_
        den = pdi + mdi
        dx = 100.0 * np.abs(pdi - mdi) / np.where(den == 0, np.nan, den)
    return _sma_strict(dx, n)


def _prior_ny_day_state(b: Bars) -> dict[int, str]:
    """Day number -> the label of the most recent COMPLETED New York session strictly before it.

    As written: a New York day is the bars stamped 13:00..22:00 inclusive; its range is compared
    with the median range of the last 20 such days (at least 10): above 1.5x is TREND_DAY, below
    0.75x RANGE_DAY, else NORMAL_DAY. It is FAILED_BREAK instead when the whole day's high broke
    the previous New York day's whole-day high and the session closed back below it, or the low
    mirror. A day with no earlier labelled session has no label."""
    hour, day = b.hour, b.day
    ny = (hour >= 13) & (hour <= 22)
    days = sorted({int(d) for d in day[ny]})
    if not days:
        return {}
    ny_hi: dict[int, float] = {}
    ny_lo: dict[int, float] = {}
    ny_close: dict[int, float] = {}
    full_hi: dict[int, float] = {}
    full_lo: dict[int, float] = {}
    for i in range(len(b)):
        d = int(day[i])
        full_hi[d] = max(full_hi.get(d, -np.inf), float(b.h[i]))
        full_lo[d] = min(full_lo.get(d, np.inf), float(b.low[i]))
        if ny[i]:
            ny_hi[d] = max(ny_hi.get(d, -np.inf), float(b.h[i]))
            ny_lo[d] = min(ny_lo.get(d, np.inf), float(b.low[i]))
            ny_close[d] = float(b.c[i])
    rng = np.asarray([ny_hi[d] - ny_lo[d] for d in days])
    labels: dict[int, str] = {}
    for k, d in enumerate(days):
        w = rng[max(0, k - 19):k + 1]
        if len(w) < 10:
            continue
        med = float(np.median(w))
        if not med or not np.isfinite(med):
            continue
        st = ("TREND_DAY" if rng[k] > 1.5 * med
              else "RANGE_DAY" if rng[k] < 0.75 * med else "NORMAL_DAY")
        if k > 0:
            ph, pl = full_hi[days[k - 1]], full_lo[days[k - 1]]
            yc = ny_close[d]
            if ph and pl and ((full_hi[d] > ph and yc < ph) or (full_lo[d] < pl and yc > pl)):
                st = "FAILED_BREAK"
        labels[d] = st
    out: dict[int, str] = {}
    labelled = sorted(labels)
    li, prev = 0, None
    for d in sorted({int(x) for x in day}):
        while li < len(labelled) and labelled[li] < d:
            prev = labels[labelled[li]]
            li += 1
        if prev is not None:
            out[d] = prev
    return out


def _direction(p: Mapping[str, Any]) -> int:
    raw = p.get("direction")
    if raw is None:
        raw = p.get("_side") or 1
    return -1 if str(raw).strip().upper() in ("SHORT", "-1", "SELL") else 1


def _range_filter_adx_orders(b: Bars, side: int) -> list[Order]:
    """The written rule of `dav_range_filter_adx`, both sides, every hour."""
    n = 14
    a = _sma_strict(_true_range(b), n)
    dx = _adx_strict(b, n)
    hi_ch = _roll_strict(b.c, n, np.max)
    lo_ch = _roll_strict(b.c, n, np.min)
    chan = 2.0 * a
    out: list[Order] = []
    with np.errstate(invalid="ignore"):
        cond = ((b.c < lo_ch + 0.2 * chan) if side > 0 else (b.c > hi_ch - 0.2 * chan)) & (dx > 25)
    for i in np.nonzero(cond)[0]:
        stop = float(b.c[i] - side * 1.5 * a[i])
        target = float(b.c[i] + side * 3.0 * a[i])
        if np.isfinite(stop) and np.isfinite(target) and stop > 0 and target > 0:
            out.append(Order(int(b.t[i]), side, stop, target, 12))
    return out


def _keep_hour_state(b: Bars, orders: list[Order], hour: int | None,
                     state: str | None) -> list[Order]:
    if hour is not None:
        orders = [o for o in orders if (o.t_ns // 3_600_000_000_000) % 24 == int(hour)]
    if state:
        labels = _prior_ny_day_state(b)
        want = str(state).upper()
        orders = [o for o in orders if labels.get(int(o.t_ns // 86_400_000_000_000)) == want]
    return orders


def _build_dav_range_filter_adx(b: Bars, p: dict[str, Any]) -> list[Order]:
    sel = str(p.get("_selector") or "").lower()
    hour = p.get("signal_at")
    if hour is None:
        hour = HUNT16_SIGNAL_HOUR.get(sel)
    state = p.get("day_state") or p.get("_condition")
    return _keep_hour_state(b, _range_filter_adx_orders(b, _direction(p)), hour, state)


def _build_hunt16_cell(b: Bars, p: dict[str, Any]) -> list[Order]:
    base = str(p.get("base_family") or "")
    builder = HUNT16_RULES.get(base)
    if builder is None:
        return []
    return _keep_hour_state(b, builder(b, _direction(p)), p.get("signal_at"), p.get("day_state"))


#: hunt16 base families with a written rule, for `hunt16_cell`. Adding a hunt16 family here is
#: adding its rule text to `dav_range_filter_adx`'s shape; an absent base is no fill, UNMEASURED.
HUNT16_RULES: dict[str, Callable[[Bars, int], list[Order]]] = {
    "dav_range_filter_adx": _range_filter_adx_orders,
}

#: The venue's recorded contract terms (swap_long, swap_short, swap_mode, point, contract_size),
#: one parquet vintage per day. Read by this module through pyarrow, latest observation wins.
CONTRACT_TERMS = DESK / "data" / "tape" / "contract_terms"
SWAP_MODE_POINTS = 1


def swap_terms(symbol: str, terms_dir: Path | None = None) -> dict[str, Any] | None:
    folder = Path(terms_dir or CONTRACT_TERMS)
    if not symbol or not folder.exists():
        return None
    latest: dict[str, Any] | None = None
    try:
        import pyarrow.parquet as pq
    except ImportError:
        return None
    for f in sorted(folder.glob("*.parquet")):
        try:
            rows = pq.read_table(f).to_pylist()
        except Exception:
            continue
        rows = [r for r in rows if str(r.get("symbol") or "").upper() == symbol.upper()]
        rows.sort(key=lambda r: str(r.get("observed_at") or ""))
        if rows:
            latest = rows[-1]
    return latest


def _build_carry(b: Bars, p: dict[str, Any]) -> list[Order]:
    terms = swap_terms(str(p.get("symbol") or p.get("_symbol") or ""))
    if not terms:
        return []
    try:
        mode = int(terms["swap_mode"])
        point = float(terms.get("point") or 0.0)
        contract = float(terms.get("contract_size") or 0.0)
        lo_sw, sh_sw = float(terms["swap_long"]), float(terms["swap_short"])
    except (KeyError, TypeError, ValueError):
        return []
    if mode != SWAP_MODE_POINTS or point <= 0 or contract <= 0:
        return []
    lo_m, sh_m = lo_sw * point * contract, sh_sw * point * contract
    side = 1 if lo_m > sh_m else -1
    if abs(lo_m - sh_m) < float(p["min_edge_bp_per_day"]):
        return []
    n = int(p["atr_n"])
    a = atr(b, n)
    rng = _sma_strict(b.h - b.low, n)
    med = _roll_strict(rng, n * 5, lambda w: float(np.median(w)))
    quiet_req = bool(p.get("require_quiet", True))
    stop_atr, rr, hold = float(p["stop_atr"]), float(p["rr"]), int(p["hold_bars"])
    out: list[Order] = []
    for i in range(n * 5, len(b) - 1):
        if quiet_req and not (rng[i] < med[i]):
            continue
        ai = float(a[i])
        if not np.isfinite(ai) or ai <= 0:
            continue
        px = float(b.c[i])
        out.append(Order(int(b.t[i]), side, px - side * stop_atr * ai,
                         px + side * stop_atr * ai * rr, hold))
    return out


SPEC_BOOK.update({
    "dav_range_filter_adx": RuleSpec(
        "dav_range_filter_adx",
        "ATR = strict 14-bar mean of true range; ADX(14) from strict 14-bar means of +DM, -DM and "
        "TR. hi/lo = the highest/lowest CLOSE of the last 14 bars, chan = 2 x ATR. LONG when close "
        "< lo + 0.2 x chan and ADX > 25, SHORT when close > hi - 0.2 x chan and ADX > 25 (the "
        "certificate's side picks one); entry next open, stop 1.5 x ATR and target 3 x ATR from "
        "the signal close, time exit after 12 bars. Kept only at the selector's signal hour "
        "(asia 7, london_am 13, ny_open 14, afternoon 17) and, when the certificate names a "
        "condition, only on days whose most recent completed New York session (13:00-22:00) "
        "carries that label (range vs its 20-day median: >1.5x TREND_DAY, <0.75x RANGE_DAY, "
        "else NORMAL_DAY; FAILED_BREAK on a broken-and-rejected prior-day extreme).",
        {"direction": None, "signal_at": None, "day_state": None},
        _build_dav_range_filter_adx),
    "hunt16_cell": RuleSpec(
        "hunt16_cell",
        "The named hunt16 base family's written rule (base_family; dav_range_filter_adx as "
        "above) on the side `direction`, kept only at hour signal_at and only on days whose "
        "most recent completed New York session carries day_state (same labelling as above).",
        {"base_family": "", "direction": None, "signal_at": None, "day_state": None},
        _build_hunt16_cell),
    "carry": RuleSpec(
        "carry",
        "Side = the side with the larger nightly swap in money per lot (swap x point x "
        "contract_size, from the venue's latest recorded contract terms; any swap_mode but "
        "POINTS stands aside, as does a differential below min_edge_bp_per_day). On every bar "
        "from 5 x atr_n on where the mean bar range over atr_n bars is below its own median over "
        "5 x atr_n bars (require_quiet), a signal at the bar close: stop stop_atr x ATR(atr_n), "
        "target rr x that, entry next open, time exit after hold_bars.",
        {"symbol": "", "min_edge_bp_per_day": 0.5, "atr_n": 20, "hold_bars": 120,
         "stop_atr": 2.0, "rr": 1.5, "require_quiet": True},
        _build_carry),
})


#: The plumbing moments a clock_transition certificate may name. The lane reads the STAMP HOUR the
#: certificate carries, never a time-zone conversion, so only the names are needed here.
CLOCK_LABELS = frozenset({"london_fix", "ny_option_cut", "cme_fx_close", "cash_equity_close",
                          "comex_settle", "tokyo_open", "london_open", "ny_open",
                          "broker_rollover"})
CLOCK_MODES = ("into", "out_of", "fade")


def _build_clock_transition(b: Bars, p: dict[str, Any]) -> list[Order]:
    label, mode = str(p.get("label") or ""), str(p.get("mode") or "")
    side, hour = int(p.get("side") or 0), int(p.get("stamp_hour", -1))
    if label not in CLOCK_LABELS or mode not in CLOCK_MODES or side not in (1, -1):
        return []
    if not 0 <= hour <= 23 or len(b) < max(1, 1440 // max(1, b.minutes)) * 60:
        return []
    at = np.flatnonzero(b.hour == hour)
    if at.size < 40:
        return []
    lead, hold = int(p["lead_bars"]), int(p["hold_bars"])
    stop_atr, rr = float(p["stop_atr"]), float(p["rr"])
    a = atr(b, int(p["atr_n"]))
    out: list[Order] = []
    for i in at:
        if mode == "into":
            entry, ttl, s = int(i) - lead, lead, side
            if entry < 1:
                continue
        elif mode == "out_of":
            entry, ttl, s = int(i), hold, side
        else:
            j = int(i) - lead
            if j < 1:
                continue
            move = float(b.c[i] - b.c[j])
            if move == 0.0:
                continue
            entry, ttl, s = int(i), hold, (-1 if move > 0 else 1) * side
        ai = float(a[entry])
        if not np.isfinite(ai) or ai <= 0:
            continue
        px = float(b.c[entry])
        out.append(Order(int(b.t[entry]), s, px - s * stop_atr * ai,
                         px + s * stop_atr * ai * rr, max(1, ttl)))
    return out


SPEC_BOOK["clock_transition"] = RuleSpec(
    "clock_transition",
    "One named plumbing moment (label: london_fix, ny_option_cut, cme_fx_close, "
    "cash_equity_close, comex_settle, tokyo_open, london_open, ny_open, broker_rollover) at the "
    "broker STAMP hour the certificate names (stamp_hour). Stands aside on fewer than 60 days of "
    "bars or fewer than 40 bars at that hour. At every bar i stamped at that hour: into -- signal "
    "at bar i - lead_bars on `side`, time exit after lead_bars; out_of -- signal at bar i on "
    "`side`, time exit after hold_bars; fade -- signal at bar i against the sign of close[i] - "
    "close[i - lead_bars] (times `side`; no move, no signal), time exit after hold_bars. Stop "
    "stop_atr x ATR(atr_n) and target rr x that from the signal close, entry next open; ATR "
    "is the trailing mean true range, fewer bars allowed at the start.",
    {"label": "", "stamp_hour": -1, "mode": "out_of", "side": 1, "lead_bars": 2,
     "hold_bars": 4, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5},
    _build_clock_transition, rule_sets_side=True)


#: Where a factor's bars come from. `load_bars` on the desk's universe store, the same chart the
#: target is read from; a test hands in its own frames here.
FACTOR_BARS: Callable[[str, str], Bars | None] = load_bars
RESIDUAL_SIDE_MODES = frozenset({"revert", "continue"})


def _causal_ols_residual(y: np.ndarray, x: np.ndarray, win: int) -> np.ndarray:
    """eps[t] = y[t] - (a + x[t] . b), with (a, b) the least-squares fit on rows t-win .. t-1
    only; NaN before row `win`. Written as the plain loop on purpose: this lane is the second
    implementation, so it does not borrow the desk's cumulative-sum solver."""
    n, k = x.shape
    eps = np.full(n, np.nan)
    if win < k + 2:
        return eps
    for t in range(win, n):
        z = np.column_stack([np.ones(win), x[t - win:t]])
        coef, *_ = np.linalg.lstsq(z, y[t - win:t], rcond=None)
        eps[t] = y[t] - float(coef[0] + x[t] @ coef[1:])
    return eps


def _trailing_z(v: np.ndarray, n: int) -> np.ndarray:
    """(v - mean) / sd (ddof 1) over the trailing n values; NaN unless all n are finite."""
    out = np.full(v.size, np.nan)
    if n < 2 or v.size < n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(v, n)
    full = np.isfinite(w).all(axis=1)
    mu = np.where(full, np.nanmean(np.where(np.isfinite(w), w, 0.0), axis=1), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        sd = np.where(full, np.std(np.where(np.isfinite(w), w, 0.0), axis=1, ddof=1), np.nan)
        out[n - 1:] = (v[n - 1:] - mu) / sd
    return out


def _build_cross_asset_residual(b: Bars, p: dict[str, Any]) -> list[Order]:
    names = [str(s) for s in (p.get("factor_symbols") or []) if str(s)]
    mode = str(p.get("side_mode") or "")
    if not names or mode not in RESIDUAL_SIDE_MODES:
        return []
    tf = str(p.get("timeframe") or "H1")
    loaded = [FACTOR_BARS(s, tf) for s in names]
    factors = [f for f in loaded if f is not None]
    if len(factors) != len(loaded):
        return []                               # a partial basket is a different model
    lookback = int(p["lookback"])
    bwin = int(p.get("beta_win") or 0) or lookback
    # the bars every leg printed: the target's stamps, intersected with each factor's
    common = np.unique(b.t)
    for f in factors:
        common = np.intersect1d(common, f.t)
    yc = b.c[np.searchsorted(b.t, common)]
    xc = np.column_stack([f.c[np.searchsorted(f.t, common)] for f in factors])
    keep = np.isfinite(yc) & np.isfinite(xc).all(axis=1)
    common, yc, xc = common[keep], yc[keep], xc[keep]
    if len(common) < bwin + lookback * 2:
        return []
    with np.errstate(invalid="ignore", divide="ignore"):
        ry = np.concatenate([[np.nan], np.diff(np.log(yc))])
        rx = np.vstack([np.full((1, xc.shape[1]), np.nan), np.diff(np.log(xc), axis=0)])
    ok = np.isfinite(ry) & np.isfinite(rx).all(axis=1)
    if int(ok.sum()) < bwin + lookback * 2:
        return []
    t_ok = common[ok]
    eps = _causal_ols_residual(ry[ok], rx[ok], bwin)
    cum = np.where(np.isfinite(eps), np.cumsum(np.where(np.isfinite(eps), eps, 0.0)), np.nan)
    z = _trailing_z(cum, lookback)
    a = atr(b, int(p["atr_n"]))[np.searchsorted(b.t, t_ok)]
    hours = {int(h) for h in p["active_hours"]} if p.get("active_hours") else None
    stop_atr, rr, ttl = float(p["stop_atr"]), float(p["rr"]), int(p["ttl_bars"])
    out: list[Order] = []
    for i in range(bwin + lookback, len(cum) - 1):
        zi = float(z[i])
        if not np.isfinite(zi) or abs(zi) < float(p["entry_z"]):
            continue
        if hours is not None and int((t_ok[i] // 3_600_000_000_000) % 24) not in hours:
            continue
        if not (np.isfinite(a[i]) and a[i] > 0):
            continue
        side = (-1 if zi > 0 else 1) if mode == "revert" else (1 if zi > 0 else -1)
        # THE ANCHOR IS ROW i OF THE JOINED FRAME, NOT OF THE RETURN SERIES, as the family
        # indexes it: the first joined row has no return, so this is the close one row BEFORE
        # the signal row. Mirrored, not corrected: the certificates were minted on it.
        px, sd = float(yc[i]), stop_atr * float(a[i])
        out.append(Order(int(t_ok[i]), side, px - side * sd, px + side * sd * rr, ttl))
    return out


SPEC_BOOK["cross_asset_residual"] = RuleSpec(
    "cross_asset_residual",
    "The target's close and each named factor's close (factor_symbols, same chart) on the bars "
    "every leg printed. Log returns bar to bar; the residual at row t is the target's return "
    "less an intercept and the factors' returns weighted by a least-squares fit on rows "
    "t - beta_win .. t - 1 only (beta_win defaults to lookback). Cumulative residual, z-scored "
    "over the trailing lookback rows (sample sd). Stands aside on a missing factor, an unknown "
    "side_mode, or fewer than beta_win + 2 x lookback rows. From row beta_win + lookback on, "
    "|z| >= entry_z on a stamp hour in active_hours (every hour when none) signals: revert "
    "fades the sign of z, continue follows it. Stop stop_atr x ATR(atr_n) (at the signal row) "
    "and target rr x that from the close of joined row i -- the row before the signal row, as "
    "the family indexes it -- entry next open, time exit after ttl_bars. The session is the "
    "certificate's `session` parameter, never its selector.",
    {"factor_symbols": [], "timeframe": "H1", "lookback": 240, "beta_win": None,
     "entry_z": 2.0, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5, "ttl_bars": 72,
     "side_mode": "revert", "active_hours": None},
    _build_cross_asset_residual, rule_sets_side=True, session_in_params=True)


SPREAD_MODES = frozenset({"spike_reversion", "calm_continuation"})


def _ffill(v: np.ndarray) -> np.ndarray:
    """Each NaN takes the last finite value before it; leading NaNs stay NaN."""
    ok = np.isfinite(v)
    pos = np.where(ok, np.arange(v.size), -1)
    np.maximum.accumulate(pos, out=pos)
    return np.where(pos >= 0, v[np.maximum(pos, 0)], np.nan)


def _trailing_rank(v: np.ndarray, n: int) -> np.ndarray:
    """At row i >= n: the share of the n values before row i that are <= the value at row i
    (a NaN compares false, so it counts in the denominator only); NaN before row n."""
    out = np.full(v.size, np.nan)
    if v.size <= n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(v, n + 1)
    with np.errstate(invalid="ignore"):
        out[n:] = (w[:, :-1] <= w[:, -1:]).mean(axis=1)
    return out


def _build_spread_state(b: Bars, p: dict[str, Any]) -> list[Order]:
    mode, nw = str(p.get("mode") or ""), int(p["norm_window"])
    if mode not in SPREAD_MODES or "spread" not in b.cols or len(b) < nw * 3:
        return []
    spread = _ffill(b.cols["spread"])
    fin = spread[np.isfinite(spread)]
    if fin.size == 0 or not (fin.size > 1 and float(np.std(fin, ddof=1)) > 0):
        return []
    ret = np.concatenate([[np.nan], np.diff(b.c)])
    a = atr(b, int(p["atr_n"]))
    sp_rank = _trailing_rank(spread, nw)
    has_vol = "tick_volume" in b.cols
    act_rank = _trailing_rank(_ffill(b.cols["tick_volume"]), nw) if has_vol else None
    hold, min_mv = int(p["hold_bars"]), float(p["min_move_atr"])
    stop_atr, rr = float(p["stop_atr"]), float(p["rr"])
    out: list[Order] = []
    last = -10 ** 9
    for i in range(nw, len(b) - 1):
        if i - last < hold or not (np.isfinite(a[i]) and a[i] > 0):
            continue
        mv = float(ret[i])
        if not np.isfinite(mv) or abs(mv) < min_mv * a[i] or not np.isfinite(sp_rank[i]):
            continue
        if mode == "spike_reversion":
            if sp_rank[i] < float(p["spike_pct"]):
                continue
            side = -1 if mv > 0 else 1
        else:
            if sp_rank[i] > float(p["calm_pct"]):
                continue
            if act_rank is not None and not (np.isfinite(act_rank[i])
                                             and act_rank[i] >= float(p["active_pct"])):
                continue
            side = 1 if mv > 0 else -1
        px, sd = float(b.c[i]), stop_atr * float(a[i])
        out.append(Order(int(b.t[i]), side, px - side * sd, px + side * sd * rr, hold))
        last = i
    return out


SPEC_BOOK["spread_state"] = RuleSpec(
    "spread_state",
    "The broker's own per-bar spread (forward-filled over gaps) and, when the file has it, "
    "tick_volume. Each is ranked at row i as the share of the norm_window values before it at "
    "or below it. Stands aside with no spread column, a flat spread, an unknown mode, or fewer "
    "than 3 x norm_window bars. From row norm_window on, a bar whose close-to-close move is at "
    "least min_move_atr x ATR(atr_n) signals -- spike_reversion: spread rank >= spike_pct, "
    "against the move; calm_continuation: spread rank <= calm_pct and (with volume) activity "
    "rank >= active_pct, with the move -- then nothing for hold_bars bars. Stop stop_atr x ATR "
    "and target rr x that from the signal close, entry next open, time exit after hold_bars.",
    {"mode": "spike_reversion", "norm_window": 240, "spike_pct": 0.95, "calm_pct": 0.20,
     "active_pct": 0.80, "min_move_atr": 0.5, "hold_bars": 6, "atr_n": 20, "stop_atr": 2.0,
     "rr": 1.5},
    _build_spread_state, rule_sets_side=True, session_in_params=True)


def _trailing_mean(v: np.ndarray, n: int) -> np.ndarray:
    """Mean of rows i-n+1 .. i; NaN unless all n are finite."""
    out = np.full(v.size, np.nan)
    if n < 1 or v.size < n:
        return out
    w = np.lib.stride_tricks.sliding_window_view(v, n)
    full = np.isfinite(w).all(axis=1)
    out[n - 1:] = np.where(full, np.where(np.isfinite(w), w, 0.0).mean(axis=1), np.nan)
    return out


def _build_jump(b: Bars, p: dict[str, Any]) -> list[Order]:
    mode, lb, atr_n = str(p.get("mode") or ""), int(p["lookback"]), int(p["atr_n"])
    if mode not in ("continue", "revert") or lb < 4 or len(b) < lb + atr_n + 3:
        return []
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.concatenate([[np.nan], np.diff(np.log(b.c))])
        absr = np.abs(r)
        bip = _trailing_mean(absr * np.concatenate([[np.nan], absr[:-1]]), lb)
        sigma = np.sqrt(np.concatenate([[np.nan], bip[:-1]]) * (np.pi / 2.0))
        stat = absr / sigma
    a = atr(b, atr_n)
    flip = 1 if mode == "continue" else -1
    k, cool = float(p["jump_k"]), int(p["cooldown_bars"])
    stop_atr, rr, ttl = float(p["stop_atr"]), float(p["rr"]), int(p["ttl_bars"])
    out: list[Order] = []
    last = -(10 ** 9)
    for i in range(lb + 1, len(b) - 1):
        if not (np.isfinite(stat[i]) and stat[i] >= k and np.isfinite(r[i]) and r[i] != 0.0
                and np.isfinite(a[i]) and a[i] > 0) or i - last < cool:
            continue
        last = i
        side = flip * (1 if r[i] > 0 else -1)
        px, sd = float(b.c[i]), stop_atr * float(a[i])
        out.append(Order(int(b.t[i]), side, px - side * sd, px + side * sd * rr, ttl))
    return out


SPEC_BOOK["jump"] = RuleSpec(
    "jump",
    "Log close-to-close returns r. At bar i the jump statistic is |r_i| / sigma_i, with "
    "sigma_i^2 = (pi/2) x the mean of |r_j||r_j-1| over the lookback bars ending at i - 1 "
    "(bipower variation, bar i excluded; NaN unless every term exists). Stands aside on an "
    "unknown mode, lookback < 4, or fewer than lookback + atr_n + 3 bars. From bar lookback + 1, "
    "a statistic >= jump_k on a non-zero return with a positive ATR(atr_n) signals -- continue "
    "with the return's sign, revert against it -- and no further signal for cooldown_bars "
    "bars. Stop stop_atr x ATR and target rr x that from the signal close, entry next open, "
    "time exit after ttl_bars. The session is the certificate's parameter.",
    {"mode": "continue", "lookback": 48, "jump_k": 4.0, "cooldown_bars": 8, "atr_n": 20,
     "stop_atr": 1.5, "rr": 1.5, "ttl_bars": 8},
    _build_jump, rule_sets_side=True, session_in_params=True)


# --------------------------------------------------------------- the state-space rule book
# Five written rules for the framework families of 2026-11-10 (GARCH, Kalman trend and pair,
# copula pair, OU half-life). None takes a `side`: the rule decides it. Each fires on the bar
# its condition BECOMES true, and never on the last bar of the file.
def _rising(cond: np.ndarray) -> np.ndarray:
    """Rows where `cond` is true and was not true on the row before."""
    c = np.asarray(cond, dtype=bool)
    return np.flatnonzero(c & ~np.concatenate([[False], c[:-1]]))


def _log_returns(c: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(log close, its bar-to-bar change); a non-positive close is undefined."""
    with np.errstate(invalid="ignore", divide="ignore"):
        lc = np.log(np.where(c > 0, c, np.nan))
    return lc, np.concatenate([[np.nan], np.diff(lc)])


def _gjr_variance(x: np.ndarray, omega: float, alpha: float, gamma: float, beta: float,
                  v0: float) -> np.ndarray:
    """v[0] = v0 and v[t+1] = omega + (alpha + gamma [x_t < 0]) x_t^2 + beta v[t], each value
    floored at 1e-12 after the pass: len(x) + 1 values, the last being the next-bar forecast."""
    from scipy.signal import lfilter

    v = np.empty(x.size + 1)
    v[0] = max(v0, 1e-12)
    if x.size:
        shock = omega + (alpha + gamma * (x < 0)) * x * x
        v[1:], _ = lfilter([1.0], [1.0, -beta], shock, zi=[beta * v[0]])
    return np.maximum(v, 1e-12)


GARCH_STARTS = ((0.05, 0.05, 0.05, 0.85), (0.02, 0.08, 0.02, 0.9))


def _gjr_fit(r: np.ndarray) -> tuple[float, float, float, float] | None:
    """The written fit: finite returns (250 or more), demeaned and divided by their own sd;
    Gaussian likelihood of the GJR recursion started at 1; Nelder-Mead from the two written
    starts (600 iterations, xatol 1e-5, fatol 1e-4); the lower likelihood wins."""
    from scipy.optimize import minimize

    r = r[np.isfinite(r)]
    if r.size < 250:
        return None
    r = r - r.mean()
    s = float(r.std())
    if not np.isfinite(s) or s <= 0:
        return None
    x = r / s

    def loss(q: np.ndarray) -> float:
        om, al, ga, be = q
        if om <= 0 or al < 0 or ga < 0 or be < 0 or al + be + 0.5 * ga >= 0.999:
            return 1e10
        v = _gjr_variance(x, om, al, ga, be, 1.0)[:-1]
        return float(0.5 * np.sum(np.log(v) + x * x / v))

    best = None
    for start in GARCH_STARTS:
        try:
            res = minimize(loss, np.array(start), method="Nelder-Mead",
                           options={"maxiter": 600, "xatol": 1e-5, "fatol": 1e-4})
        except (ValueError, FloatingPointError):
            continue
        if res.fun < 1e9 and (best is None or res.fun < best.fun):
            best = res
    if best is None:
        return None
    om, al, ga, be = (float(q) for q in best.x)
    return om * s * s, al, ga, be


def _build_garch_shock(b: Bars, p: dict[str, Any]) -> list[Order]:
    mode, state = str(p.get("side_mode") or ""), str(p.get("vol_state") or "")
    window, refit = int(p["window"]), int(p["refit"])
    if (mode not in ("fade", "follow") or state not in ("any", "calm", "stressed")
            or window < 1 or refit < 1 or len(b) < window + refit):
        return []
    _, r = _log_returns(b.c)
    n = len(b)
    sigma, ratio = np.full(n, np.nan), np.full(n, np.nan)
    k = window
    while k < n:
        end = min(n, k + refit)
        past = r[k - window:k]
        fit = _gjr_fit(past)
        if fit is not None:
            om, al, ga, be = fit
            longrun = om / (1.0 - (al + be + 0.5 * ga))
            seg = np.nan_to_num(r[k - window:end] - np.nanmean(past))
            v = _gjr_variance(seg, om, al, ga, be, float(np.nanvar(past)))
            sigma[k:end] = np.sqrt(v[window:window + (end - k)])
            if np.isfinite(longrun) and longrun > 0:
                ratio[k:end] = v[window + 1:window + 1 + (end - k)] / longrun
        k = end
    with np.errstate(invalid="ignore", divide="ignore"):
        z = r / sigma
    cond = np.isfinite(z) & (np.abs(z) >= float(p["entry_z"]))
    if state == "calm":
        cond &= np.isfinite(ratio) & (ratio < 1.0)
    elif state == "stressed":
        cond &= np.isfinite(ratio) & (ratio >= 1.0)
    a = atr(b, int(p["atr_n"]))
    stop_atr, rr, ttl = float(p["stop_atr"]), float(p["rr"]), int(p["ttl_bars"])
    out: list[Order] = []
    for i in _rising(cond):
        if i >= n - 1 or not (np.isfinite(a[i]) and a[i] > 0):
            continue
        move = 1 if r[i] > 0 else -1
        side = -move if mode == "fade" else move
        px, sd = float(b.c[i]), stop_atr * float(a[i])
        out.append(Order(int(b.t[i]), side, px - side * sd, px + side * rr * sd, ttl))
    return out


SPEC_BOOK["garch_shock"] = RuleSpec(
    "garch_shock",
    "Log close-to-close returns r. Walk forward in blocks of refit bars from bar window: each "
    "block is labelled by a zero-mean GJR-GARCH(1,1) fitted on the window returns before it "
    "(finite ones, 250 or more; demeaned and scaled to unit sd; Gaussian likelihood with the "
    "variance started at 1; omega > 0, alpha, gamma, beta >= 0, alpha + beta + gamma/2 < 0.999; "
    "Nelder-Mead from (0.05, 0.05, 0.05, 0.85) and (0.02, 0.08, 0.02, 0.9), 600 iterations, "
    "xatol 1e-5, fatol 1e-4, lower likelihood wins; omega rescaled by the sd squared). The "
    "recursion v' = omega + (alpha + gamma [r < 0]) r^2 + beta v is run over the window and "
    "the block on returns less the window's mean (missing as 0), started at the window's "
    "variance, floored at 1e-12; sigma_i is the forecast FOR bar i, and the ratio at i is the "
    "forecast for bar i + 1 over the long-run variance omega / (1 - alpha - beta - gamma/2). A "
    "block whose fit fails has neither. Stands aside on an unknown side_mode or vol_state or "
    "fewer than window + refit bars. The condition is |r_i / sigma_i| >= entry_z, and for calm "
    "a ratio < 1, for stressed a ratio >= 1. A bar on which the condition becomes true, with a "
    "positive ATR(atr_n), signals: fade against the return's sign, follow with it. Stop "
    "stop_atr x ATR and target rr x that from the signal close, entry next open, time exit "
    "after ttl_bars. The session is the certificate's parameter.",
    {"window": 1000, "refit": 250, "entry_z": 2.5, "vol_state": "any", "side_mode": "fade",
     "atr_n": 20, "stop_atr": 1.5, "rr": 1.5, "ttl_bars": 24},
    _build_garch_shock, rule_sets_side=True, session_in_params=True)


def _prior_ewma_var(r: np.ndarray, lam: float) -> np.ndarray:
    """out[t] = the exponentially weighted mean of r^2 over the finite returns BEFORE t (the
    first one seeds it); NaN until one exists."""
    out = np.full(r.size, np.nan)
    acc = float("nan")
    for t in range(r.size):
        out[t] = acc
        if np.isfinite(r[t]):
            sq = float(r[t]) * float(r[t])
            acc = sq if not np.isfinite(acc) else lam * acc + (1.0 - lam) * sq
    return out


STATE_SPACE_LAMBDA = 0.97


def _build_kalman_trend(b: Bars, p: dict[str, Any]) -> list[Order]:
    mode, warmup = str(p.get("side_mode") or ""), int(p["warmup"])
    ql, qs = float(p["q_level"]), float(p["q_slope"])
    if mode not in ("follow", "fade") or qs <= 0 or ql < 0 or len(b) < warmup + 100:
        return []
    y, r = _log_returns(b.c)
    noise = _prior_ewma_var(r, STATE_SPACE_LAMBDA)
    n = len(b)
    tstat = np.full(n, np.nan)
    started = False
    level = slope = p00 = p01 = p11 = 0.0
    for t in range(n):
        obs, rv = float(y[t]), float(noise[t])
        if not (np.isfinite(obs) and np.isfinite(rv) and rv > 0):
            continue
        if not started:
            level, slope, p00, p01, p11, started = obs, 0.0, rv, 0.0, rv, True
            continue
        # predict: the level takes the slope, both variances grow by their stated noise
        a00 = p00 + 2 * p01 + p11 + ql * rv
        a01 = p01 + p11
        a11 = p11 + qs * rv
        gain0, gain1 = a00 / (a00 + rv), a01 / (a00 + rv)
        miss = obs - (level + slope)
        level, slope = level + slope + gain0 * miss, slope + gain1 * miss
        p00, p01, p11 = a00 - gain0 * a00, a01 - gain0 * a01, a11 - gain1 * a01
        sd = float(np.sqrt(max(p11, 0.0)))
        if sd > 0:
            tstat[t] = slope / sd
    tstat[:warmup] = np.nan
    limit = float(p["entry_t"])
    a = atr(b, int(p["atr_n"]))
    stop_atr, rr, ttl = float(p["stop_atr"]), float(p["rr"]), int(p["ttl_bars"])
    out: list[Order] = []
    for trend, rows in ((1, _rising(np.isfinite(tstat) & (tstat >= limit))),
                        (-1, _rising(np.isfinite(tstat) & (tstat <= -limit)))):
        for i in rows:
            if i >= n - 1 or not (np.isfinite(a[i]) and a[i] > 0):
                continue
            side = trend if mode == "follow" else -trend
            px, sd_px = float(b.c[i]), stop_atr * float(a[i])
            out.append(Order(int(b.t[i]), side, px - side * sd_px, px + side * rr * sd_px, ttl))
    out.sort(key=lambda o: o.t_ns)
    return out


SPEC_BOOK["kalman_trend"] = RuleSpec(
    "kalman_trend",
    "A local-linear-trend Kalman filter on log close: level' = level + slope + noise, slope' = "
    "slope + noise, close = level + noise. The observation variance R at bar t is the 0.97 "
    "exponentially weighted mean of squared one-bar log returns BEFORE t; the level and slope "
    "noises are q_level x R and q_slope x R. Bars without a positive R are skipped; the first "
    "usable bar starts level = log close, slope = 0, both variances R. The statistic is the "
    "filtered slope over its posterior sd, undefined for the first warmup bars. Stands aside on "
    "an unknown side_mode, q_slope <= 0, q_level < 0 or fewer than warmup + 100 bars. A bar on "
    "which the statistic becomes >= entry_t (up) or <= -entry_t (down), with a positive "
    "ATR(atr_n), signals: follow with the slope, fade against it. Stop stop_atr x ATR and "
    "target rr x that from the signal close, entry next open, time exit after ttl_bars. The "
    "session is the certificate's parameter.",
    {"q_level": 0.1, "q_slope": 1e-3, "entry_t": 2.0, "side_mode": "follow", "warmup": 500,
     "atr_n": 20, "stop_atr": 2.0, "rr": 2.0, "ttl_bars": 48},
    _build_kalman_trend, rule_sets_side=True, session_in_params=True)


def _paired_closes(b: Bars, p: Mapping[str, Any]
                   ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """(rows of `b`, this leg's close, the peer's close) on the stamps BOTH printed, exactly --
    no carried peer close. None with no pair_symbol, off the H1 chart, or no peer bars."""
    name = str(p.get("pair_symbol") or "")
    if not name or b.minutes != 60:
        return None
    peer = FACTOR_BARS(name, "H1")
    if peer is None:
        return None
    common = np.intersect1d(np.unique(b.t), peer.t)
    rows = np.searchsorted(b.t, common)
    mine, theirs = b.c[rows], peer.c[np.searchsorted(peer.t, common)]
    keep = np.isfinite(mine) & np.isfinite(theirs)
    return rows[keep], mine[keep], theirs[keep]


def _build_kalman_pair(b: Bars, p: dict[str, Any]) -> list[Order]:
    delta, warmup = float(p["delta"]), int(p["warmup"])
    if not 0 < delta < 1:
        return []
    joined = _paired_closes(b, p)
    if joined is None or len(joined[0]) < warmup + 100:
        return []
    rows, mine, theirs = joined
    with np.errstate(invalid="ignore", divide="ignore"):
        ya, yb = np.log(mine), np.log(theirs)
    n = len(rows)
    gap, z = np.full(n, np.nan), np.full(n, np.nan)
    started = False
    icpt = hedge = 0.0
    c00, c01, c11 = 1.0, 0.0, 1.0
    meas = float("nan")
    for t in range(n):
        u, w = float(ya[t]), float(yb[t])
        if not (np.isfinite(u) and np.isfinite(w)):
            continue
        if not started:
            icpt, hedge, c00, c01, c11, started = u - w, 1.0, 1.0, 0.0, 1.0, True
            continue
        miss = u - (icpt + hedge * w)
        ve = meas if np.isfinite(meas) else miss * miss + 1e-12
        d00, d01, d11 = c00 + delta * ve, c01, c11 + delta * ve
        g0, g1 = d00 + d01 * w, d01 + d11 * w            # state covariance times (1, peer)
        spread_var = g0 + w * g1 + ve
        gap[t], z[t] = miss, miss / np.sqrt(spread_var)
        k0, k1 = g0 / spread_var, g1 / spread_var
        icpt, hedge = icpt + k0 * miss, hedge + k1 * miss
        c00, c01, c11 = d00 - k0 * g0, d01 - k0 * g1, d11 - k1 * g1
        meas = STATE_SPACE_LAMBDA * ve + (1.0 - STATE_SPACE_LAMBDA) * miss * miss
    z[:warmup] = np.nan
    limit, frac = float(p["entry_z"]), float(p["target_frac"])
    a = atr(b, int(p["atr_n"]))[rows]
    stop_atr, ttl = float(p["stop_atr"]), int(p["ttl_bars"])
    out: list[Order] = []
    for hits in (_rising(np.isfinite(z) & (z >= limit)), _rising(np.isfinite(z) & (z <= -limit))):
        for i in hits:
            if i >= n - 1 or not (np.isfinite(a[i]) and a[i] > 0):
                continue
            side = -1 if z[i] > 0 else 1
            px = float(mine[i])
            out.append(Order(int(b.t[rows[i]]), side, px - side * stop_atr * float(a[i]),
                             px * float(np.exp(-frac * gap[i])), ttl))
    out.sort(key=lambda o: o.t_ns)
    return out


SPEC_BOOK["kalman_pair"] = RuleSpec(
    "kalman_pair",
    "This leg's and the peer's (pair_symbol) H1 closes on the stamps both printed. Log close of "
    "this leg = intercept + hedge x log close of the peer + noise, intercept and hedge random "
    "walks tracked by a Kalman filter: started on the first joined row at intercept = the log "
    "difference, hedge = 1, identity covariance; each later row's innovation e is this leg less "
    "the prediction, the measurement variance is the 0.97 exponentially weighted mean of "
    "squared innovations BEFORE the row (the first row uses its own e^2 + 1e-12), the state "
    "noise is delta x that, and z = e over the sd of the predicted spread; undefined for the "
    "first warmup rows. Stands aside with no pair_symbol, no peer bars, off H1, delta outside "
    "(0, 1) or fewer than warmup + 100 joined rows. A row on which z becomes >= entry_z "
    "(short) or <= -entry_z (long), with a positive ATR(atr_n) of this leg, signals. Stop "
    "stop_atr x ATR from the signal close; target = close x exp(-target_frac x e); entry next "
    "open, time exit after ttl_bars. The session is the certificate's parameter.",
    {"pair_symbol": None, "delta": 1e-4, "entry_z": 2.0, "target_frac": 1.0, "warmup": 500,
     "atr_n": 20, "stop_atr": 2.5, "ttl_bars": 48},
    _build_kalman_pair, rule_sets_side=True, session_in_params=True)


def _trailing_pct_rank(v: np.ndarray, n: int) -> np.ndarray:
    """The last value's average rank among the trailing n (itself included) over n, scaled by
    n / (n + 1) so it is never 1; NaN unless all n are finite."""
    out = np.full(v.size, np.nan)
    for t in range(n - 1, v.size):
        w = v[t - n + 1:t + 1]
        if np.isfinite(w).all():
            rank = float((w < w[-1]).sum()) + (float((w == w[-1]).sum()) + 1.0) / 2.0
            out[t] = (rank / n) * n / (n + 1)
    return out


def _trailing_corr(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """Pearson correlation over the trailing n rows; NaN unless all n pairs are finite."""
    out = np.full(x.size, np.nan)
    for t in range(n - 1, x.size):
        u, w = x[t - n + 1:t + 1], y[t - n + 1:t + 1]
        if not (np.isfinite(u).all() and np.isfinite(w).all()):
            continue
        du, dw = u - u.mean(), w - w.mean()
        den = float(np.sqrt((du * du).sum() * (dw * dw).sum()))
        if den > 0:
            out[t] = float((du * dw).sum()) / den
    return out


def _build_copula_pair(b: Bars, p: dict[str, Any]) -> list[Order]:
    kind, nu = str(p.get("kind") or ""), float(p["nu"])
    window, cum = int(p["window"]), int(p["cum_bars"])
    if kind not in ("gauss", "t") or nu <= 2 or window < 2 or cum < 1:
        return []
    joined = _paired_closes(b, p)
    if joined is None or len(joined[0]) < 2 * window + cum:
        return []
    from scipy import stats

    rows, mine, theirs = joined
    _, ra = _log_returns(mine)
    _, rb = _log_returns(theirs)
    ua, ub = _trailing_pct_rank(ra, window), _trailing_pct_rank(rb, window)
    if kind == "t":
        xa, xb = stats.t.ppf(ua, nu), stats.t.ppf(ub, nu)
    else:
        xa, xb = stats.norm.ppf(ua), stats.norm.ppf(ub)
    rho = np.clip(_trailing_corr(xa, xb, window), -0.995, 0.995)
    with np.errstate(invalid="ignore", divide="ignore"):
        if kind == "t":
            scale = np.sqrt((nu + xb * xb) * (1 - rho * rho) / (nu + 1))
            cond_p = stats.t.cdf((xa - rho * xb) / scale, nu + 1)
        else:
            cond_p = stats.norm.cdf((xa - rho * xb) / np.sqrt(1 - rho * rho))
    excess = np.where(np.isfinite(rho), cond_p, np.nan) - 0.5
    n = len(rows)
    index = np.full(n, np.nan)
    for t in range(cum - 1, n):
        w = excess[t - cum + 1:t + 1]
        if np.isfinite(w).all():
            index[t] = float(w.sum())
    tied = np.isfinite(rho) & (np.abs(rho) >= float(p["min_rho"]))
    limit = float(p["entry_m"])
    a = atr(b, int(p["atr_n"]))[rows]
    stop_atr, rr, ttl = float(p["stop_atr"]), float(p["rr"]), int(p["ttl_bars"])
    out: list[Order] = []
    for hits in (_rising(tied & np.isfinite(index) & (index >= limit)),
                 _rising(tied & np.isfinite(index) & (index <= -limit))):
        for i in hits:
            if i >= n - 1 or not (np.isfinite(a[i]) and a[i] > 0):
                continue
            side = -1 if index[i] > 0 else 1
            px, sd = float(mine[i]), stop_atr * float(a[i])
            out.append(Order(int(b.t[rows[i]]), side, px - side * sd, px + side * rr * sd, ttl))
    out.sort(key=lambda o: o.t_ns)
    return out


SPEC_BOOK["copula_pair"] = RuleSpec(
    "copula_pair",
    "This leg's and the peer's (pair_symbol) H1 closes on the stamps both printed; log returns "
    "row to row. Each return's percentile u is its average rank among the trailing window "
    "returns (itself included) over window, times window / (window + 1). x = the inverse CDF "
    "of u (Student-t with nu degrees for kind t, normal for gauss); rho = the correlation of "
    "the two x series over the trailing window rows, clipped to +/-0.995. The conditional "
    "probability of this leg given the peer is, for t, T_{nu+1}((xa - rho xb) / sqrt((nu + "
    "xb^2)(1 - rho^2) / (nu + 1))), for gauss Phi((xa - rho xb) / sqrt(1 - rho^2)). The index "
    "is the sum of (probability - 0.5) over the last cum_bars rows, all defined. Stands aside "
    "with no pair_symbol, no peer bars, off H1, an unknown kind, nu <= 2 or fewer than 2 x "
    "window + cum_bars joined rows. A row with |rho| >= min_rho on which the index becomes >= "
    "entry_m (short) or <= -entry_m (long), with a positive ATR(atr_n) of this leg, signals. "
    "Stop stop_atr x ATR and target rr x that from the signal close, entry next open, time "
    "exit after ttl_bars. The session is the certificate's parameter.",
    {"pair_symbol": None, "window": 500, "kind": "t", "nu": 4.0, "cum_bars": 12,
     "entry_m": 2.0, "min_rho": 0.3, "atr_n": 20, "stop_atr": 2.0, "rr": 1.5, "ttl_bars": 24},
    _build_copula_pair, rule_sets_side=True, session_in_params=True)


def _build_ou_reversion(b: Bars, p: dict[str, Any]) -> list[Order]:
    window = int(p["window"])
    hl_min, hl_max = float(p["hl_min"]), float(p["hl_max"])
    hold, frac = float(p["hold_mult"]), float(p["target_frac"])
    if (not 0 < hl_min < hl_max or hold < 1 or not 0 < frac <= 1 or window < 3
            or len(b) < 2 * window):
        return []
    x, _ = _log_returns(b.c)
    n = len(b)
    half, dist, z = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    for t in range(window, n):
        now, was = x[t - window + 1:t + 1], x[t - window:t]
        if not (np.isfinite(now).all() and np.isfinite(was[0])):
            continue
        dn, dw = now - now.mean(), was - was.mean()
        var_was = float((dw * dw).sum()) / (window - 1)
        if not var_was > 0:
            continue
        slope = float((dn * dw).sum()) / (window - 1) / var_was
        if not 0 < slope < 1:
            continue
        resid = max(float((dn * dn).sum()) / (window - 1) - slope * slope * var_was, 0.0)
        mu = (float(now.mean()) - slope * float(was.mean())) / (1 - slope)
        sd = float(np.sqrt(resid / (1 - slope * slope)))
        half[t] = -np.log(2.0) / np.log(slope)
        dist[t] = float(x[t]) - mu
        if sd > 0:
            z[t] = dist[t] / sd
    inside = np.isfinite(half) & (half >= hl_min) & (half <= hl_max) & np.isfinite(z)
    limit, max_ttl = float(p["entry_z"]), int(p["max_ttl"])
    a = atr(b, int(p["atr_n"]))
    stop_atr = float(p["stop_atr"])
    out: list[Order] = []
    for hits in (_rising(inside & (z >= limit)), _rising(inside & (z <= -limit))):
        for i in hits:
            if i >= n - 1 or not (np.isfinite(a[i]) and a[i] > 0):
                continue
            side = -1 if z[i] > 0 else 1
            px = float(b.c[i])
            ttl = int(min(max_ttl, np.ceil(hold * half[i])))
            out.append(Order(int(b.t[i]), side, px - side * stop_atr * float(a[i]),
                             px * float(np.exp(-frac * dist[i])), ttl))
    out.sort(key=lambda o: o.t_ns)
    return out


SPEC_BOOK["ou_reversion"] = RuleSpec(
    "ou_reversion",
    "Log close x. At bar t, the least-squares line x_s = a + b x_{s-1} over the window bars "
    "ending at t (sample variances and covariance). Only 0 < b < 1 is mean-reverting: half-life "
    "= -ln 2 / ln b bars, equilibrium mu = a / (1 - b), stationary sd = sqrt(residual variance "
    "/ (1 - b^2)) with residual variance = var(x) - b^2 var(lagged x), floored at 0; z = (x_t - "
    "mu) / sd. Stands aside unless 0 < hl_min < hl_max, hold_mult >= 1, 0 < target_frac <= 1 "
    "and there are 2 x window bars. A bar with hl_min <= half-life <= hl_max on which z becomes "
    ">= entry_z (short) or <= -entry_z (long), with a positive ATR(atr_n), signals. Stop "
    "stop_atr x ATR from the signal close; target = close x exp(-target_frac x (x_t - mu)); "
    "entry next open; time exit after ceil(hold_mult x half-life) bars, at most max_ttl. The "
    "session is the certificate's parameter.",
    {"window": 500, "entry_z": 2.0, "hl_min": 4.0, "hl_max": 96.0, "hold_mult": 2.0,
     "target_frac": 0.5, "atr_n": 20, "stop_atr": 2.5, "max_ttl": 240},
    _build_ou_reversion, rule_sets_side=True, session_in_params=True)


#: Session selector -> [start, end) broker hours a non-breakout signal must fall in.
SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None, "continuous": None,
}


# ---------------------------------------------------------------------------------- costs
@dataclass
class CostSpec:
    """Round trip in price units, as written: spread points x tick size, plus two commissions
    of COMMISSION_PER_LOT_PER_SIDE converted from account currency into price units through
    contract_size x tick_size / tick_value, all divided by the contract size."""

    spread_per_lot: float
    commission_per_lot: float
    contract_size: float
    quote_per_account: float
    basis: str

    @property
    def price_units(self) -> float:
        if self.contract_size <= 0:
            return 0.0
        return (self.spread_per_lot + 2.0 * self.commission_per_lot * self.quote_per_account) \
            / self.contract_size


def cost_spec(meta: Mapping[str, Any]) -> CostSpec:
    cs = float(meta.get("contract_size") or 1e5)
    ts = float(meta.get("tick_size") or 0.0)
    pts = float(meta.get("median_spread_pts") or 0.0)
    tv = _num(meta.get("tick_value"))
    qpa = (cs * ts / tv) if tv and tv > 0 and ts > 0 else 1.0
    basis = "universe_registry" if meta else "UNMEASURED: the registry does not price this symbol"
    return CostSpec(pts * ts * cs, COMMISSION_PER_LOT_PER_SIDE, cs, qpa, basis)


# ------------------------------------------------------------------------------- simulate
@dataclass
class Fill:
    entry_t: int
    exit_t: int
    side: int
    entry: float
    exit: float
    r: float
    reason: str
    bars_held: int
    open_at_end: bool = False


def simulate(b: Bars, orders: Sequence[Order], cost_price_units: float) -> list[Fill]:
    """The written fill rule: entry at the open of the first bar STRICTLY after the signal bar
    (or at the resting trigger if it is touched within wait_bars bars from there); the stop is
    checked before the target on every bar, both intrabar; a target is not taken on the fill bar
    of a limit entry; time exit at the open of bar fill+ttl; one position at a time; R is the
    move over the initial stop distance less the round-trip cost over the same distance."""
    n = len(b)
    out: list[Fill] = []
    last_exit = -1
    locs = np.searchsorted(b.t, np.asarray([o.t_ns for o in orders], dtype="int64"),
                           side="right")
    for order, i in zip(orders, locs, strict=True):
        i = int(i)
        if i <= 0 or i >= n - 1 or i <= last_exit:
            continue
        entry = float(b.o[i])
        if not np.isfinite(entry) or entry <= 0:
            continue
        fill_bar, limit_entry = i, False
        if order.trigger is not None:
            tgt = float(order.trigger)
            limit_entry = (order.side > 0 and tgt < entry) or (order.side < 0 and tgt > entry)
            hit = -1
            for j in range(i, min(i + max(1, order.wait_bars), n)):
                if b.h[j] >= tgt >= b.low[j]:
                    hit = j
                    break
            if hit < 0:
                continue
            fill_bar, entry = hit, tgt
        side, stop, target = order.side, float(order.stop), float(order.target)
        sd = abs(entry - stop)
        if sd <= 0:
            continue
        exit_px: float | None = None
        reason, held = "ttl", 0
        for j in range(fill_bar, min(n, fill_bar + max(1, order.ttl_bars))):
            held = j - fill_bar + 1
            hi, lo = float(b.h[j]), float(b.low[j])
            if side > 0:
                if lo <= stop:
                    exit_px, reason = stop, "stop"
                    break
                if hi >= target and not (limit_entry and j == fill_bar):
                    exit_px, reason = target, "target"
                    break
            else:
                if hi >= stop:
                    exit_px, reason = stop, "stop"
                    break
                if lo <= target and not (limit_entry and j == fill_bar):
                    exit_px, reason = target, "target"
                    break
        open_at_end = False
        if exit_px is None:
            exit_idx = min(fill_bar + max(1, order.ttl_bars), n - 1)
            exit_px, held = float(b.o[exit_idx]), exit_idx - fill_bar + 1
            open_at_end = exit_idx == n - 1 and fill_bar + max(1, order.ttl_bars) > n - 1
        last_exit = min(fill_bar + held - 1, n - 1)
        r = (exit_px - entry) / sd * side - cost_price_units / sd
        out.append(Fill(int(b.t[fill_bar]), int(b.t[last_exit]), side, entry, exit_px,
                        float(r), reason, held, open_at_end))
    return out


def sharpe(fills: Sequence[Fill]) -> tuple[float | None, int]:
    """Per-day Sharpe of active-day R, in the certificate screen's units.

    The gauntlet's in_sample_screen uses libs.validation.dsr.sharpe_ratio on
    daily_series, which groups trades by entry date and does not annualise.
    Comparing an annualised rebuild with that screen falsely quarantined
    otherwise matching certificates by a factor of sqrt(252).
    """
    if not fills:
        return None, 0
    days: dict[int, float] = {}
    for f in fills:
        d = int(f.entry_t // 86_400_000_000_000)
        days[d] = days.get(d, 0.0) + f.r
    x = np.asarray(list(days.values()), dtype="float64")
    if len(x) < 2 or float(np.std(x, ddof=1)) == 0:
        return 0.0, len(x)
    return float(np.mean(x) / np.std(x, ddof=1)), len(x)


# -------------------------------------------------------------------------------- rebuild
def resolve_spec(family: str, params: Mapping[str, Any] | None, selector: str | None,
                 side: str | int | None, *, symbol: str | None = None,
                 condition: str | None = None) -> tuple[dict[str, Any] | None, str]:
    """The parameters the written rule names, with the selector's window (breakouts) or session
    (everything else) applied, or the reason there is no written rule."""
    spec = SPEC_BOOK.get(str(family or ""))
    if spec is None:
        return None, f"no written specification in the spec book for family {family!r}"
    p = dict(spec.defaults)
    sel = str(selector or "").lower()
    if spec.selector_params and sel in WINDOWS:
        p.update(WINDOWS[sel])
    for k, v in dict(params or {}).items():
        if k in p or k in ("range_start", "range_end", "signal_at", "wait_bars"):
            p[k] = v
    s = str(side or "").upper()
    p["_side"] = 1 if s in ("LONG", "1") else -1 if s in ("SHORT", "-1") else 0
    p["_session"] = SESSIONS.get(sel) if not spec.selector_params else None
    # The rules that need them read these; every other rule ignores them (hunt16 selectors name
    # a signal hour, a hunt16 condition a prior-session day label, carry a symbol's swap terms).
    p["_selector"], p["_symbol"], p["_condition"] = sel, str(symbol or ""), condition
    if family in HUNT16_FAMILIES:
        p["_session"] = None
    if spec.session_in_params:
        p["_session"] = SESSIONS.get(str(dict(params or {}).get("session") or "").lower())
    return p, "ok"


#: Families whose selector names a hunt16 signal hour, not a session window to filter on.
HUNT16_FAMILIES = frozenset({"dav_range_filter_adx", "hunt16_cell"})


def rebuild(family: str, bars: Bars, p: Mapping[str, Any], cost_units: float
            ) -> tuple[list[Order], list[Fill]]:
    orders = SPEC_BOOK[family].build(bars, dict(p))
    side = 0 if SPEC_BOOK[family].rule_sets_side else int(p.get("_side") or 0)
    if side:
        orders = [o for o in orders if o.side == side]
    win = p.get("_session")
    if win is not None:
        lo, hi = win
        hours = ((np.asarray([o.t_ns for o in orders], dtype="int64") // 3_600_000_000_000)
                 % 24)
        orders = [o for o, h in zip(orders, hours, strict=True) if lo <= int(h) < hi]
    return orders, simulate(bars, orders, cost_units)


def judge_certificate(recorded_sharpe: float | None, ours: float | None, n_fills: int
                      ) -> tuple[str, list[str]]:
    if ours is None or n_fills == 0:
        return UNMEASURED, ["the rebuild produced no fill"]
    if recorded_sharpe is None:
        return UNMEASURED, ["the certificate records no in-sample Sharpe to compare against"]
    why: list[str] = []
    if abs(recorded_sharpe) >= SHARPE_NOISE and np.sign(ours) != np.sign(recorded_sharpe):
        why.append(f"Sharpe SIGN disagrees: recorded {recorded_sharpe:+.3f}, rebuilt "
                   f"{ours:+.3f}")
    elif abs(recorded_sharpe) >= 2 * SHARPE_NOISE:
        ratio = ours / recorded_sharpe
        if not (SHARPE_RATIO[0] <= ratio <= SHARPE_RATIO[1]):
            why.append(f"Sharpe MAGNITUDE disagrees: rebuilt/recorded = {ratio:.2f} outside "
                       f"[{SHARPE_RATIO[0]:g}, {SHARPE_RATIO[1]:g}]")
    if why:
        return MISMATCH, why
    return REPLICATED, [f"in-sample Sharpe comes back: rebuilt {ours:+.3f} vs recorded "
                        f"{recorded_sharpe:+.3f} on {n_fills} fill(s)"]


def judge_forward(ledger: Sequence[Mapping[str, Any]], fills: Sequence[Fill], bar_minutes: int,
                  cost_ours: CostSpec, cost_theirs: Mapping[str, Any] | None
                  ) -> tuple[str, list[str], dict[str, Any]]:
    """Fills, per-trade R, summed P&L, position state and cost terms, compared."""
    theirs = [r for r in ledger if _num(r.get("r_multiple")) is not None]
    div: dict[str, Any] = {"n_ledger": len(theirs), "n_rebuilt": len(fills)}
    if not theirs:
        return UNMEASURED, ["the forward ledger holds no trade with an R to compare"], div
    if not fills:
        return MISMATCH, [f"the rebuild produced NO fill against {len(theirs)} ledger "
                          f"trade(s)"], div
    why: list[str] = []
    tol = MATCH_BARS * bar_minutes * 60_000_000_000
    ours_t = np.asarray([f.entry_t for f in fills], dtype="int64")
    matched: list[tuple[float, float]] = []
    for row in theirs:
        try:
            t = int(np.datetime64(str(row.get("entry_time")).replace(" ", "T")
                                  .replace("+00:00", ""), "ns").astype("int64"))
        except (ValueError, TypeError):
            continue
        k = int(np.argmin(np.abs(ours_t - t))) if len(ours_t) else -1
        if k >= 0 and abs(int(ours_t[k]) - t) <= tol and \
                int(fills[k].side) == int(row.get("side") or fills[k].side):
            matched.append((float(row["r_multiple"]), fills[k].r))
    div["matched"] = len(matched)
    share = len(matched) / len(theirs)
    div["match_share"] = round(share, 3)
    fill_ratio = len(fills) / len(theirs)
    div["fill_ratio"] = round(fill_ratio, 3)
    if not (1 - FILL_SHARE <= fill_ratio <= 1 + FILL_SHARE):
        why.append(f"FILLS disagree: {len(fills)} rebuilt vs {len(theirs)} in the ledger")
    if share < MATCH_SHARE:
        why.append(f"only {len(matched)}/{len(theirs)} ledger trades have a rebuilt fill on the "
                   f"same bar and side")
    if matched:
        dr = float(np.median([abs(a - b) for a, b in matched]))
        div["median_abs_dR"] = round(dr, 4)
        if dr > R_TOLERANCE:
            why.append(f"per-trade R disagrees: median |dR| = {dr:.3f} > {R_TOLERANCE}")
    pnl_t, pnl_o = sum(float(r["r_multiple"]) for r in theirs), sum(f.r for f in fills)
    div["pnl_ledger_R"], div["pnl_rebuilt_R"] = round(pnl_t, 3), round(pnl_o, 3)
    if abs(pnl_t) >= 1.0 and np.sign(pnl_t) != np.sign(pnl_o):
        why.append(f"summed P&L disagrees in SIGN: ledger {pnl_t:+.2f}R, rebuilt {pnl_o:+.2f}R")
    open_theirs = any(r.get("exit_time") in (None, "") or str(r.get("phase")) == "open"
                      for r in theirs[-1:])
    open_ours = bool(fills[-1].open_at_end)
    div["open_ledger"], div["open_rebuilt"] = open_theirs, open_ours
    if open_theirs != open_ours:
        why.append(f"POSITION STATE disagrees: ledger open={open_theirs}, rebuilt "
                   f"open={open_ours}")
    if cost_theirs:
        for key, ours_v in (("spread_per_lot", cost_ours.spread_per_lot),
                            ("commission_per_lot", cost_ours.commission_per_lot),
                            ("quote_per_account", cost_ours.quote_per_account)):
            tv = _num(cost_theirs.get(key))
            if tv is None or tv == 0 or ours_v == 0:
                continue
            ratio = ours_v / tv
            div[f"cost_ratio_{key}"] = round(ratio, 3)
            if not (COST_RATIO[0] <= ratio <= COST_RATIO[1]):
                why.append(f"COST term {key} disagrees: rebuilt {ours_v:.4g} vs frozen "
                           f"{tv:.4g}")
    if why:
        return MISMATCH, why, div
    return REPLICATED, [f"{len(matched)}/{len(theirs)} trades matched, P&L {pnl_o:+.2f}R vs "
                        f"{pnl_t:+.2f}R, position state and costs agree"], div


# -------------------------------------------------------------------------------- the rows
def certificate_rows(path: Path = SURVIVORS) -> list[dict[str, Any]]:
    """Every certificate with a spec, each carrying its canon id as `certificate` -- the key the
    admission door looks its replication verdict up by."""
    doc = _read_json(path, {}) or {}
    rows = doc.get("survivors") if isinstance(doc, dict) else doc
    items = (list(rows.items()) if isinstance(rows, dict)
             else [(None, r) for r in (rows or [])])
    return [{**r, "certificate": str(name) if name is not None else r.get("certificate")}
            for name, r in items
            if isinstance(r, dict) and isinstance(r.get("shadow_spec"), dict)]


def certificate_id(row: Mapping[str, Any]) -> str:
    spec = row.get("shadow_spec") or {}
    return str(row.get("certificate") or row.get("cell")
               or f"{spec.get('symbol')} {spec.get('family')}")


def certificate_fp(row: Mapping[str, Any]) -> str:
    """The spec fingerprint, computed by the SAME function the admission door uses. The door is
    a reader of this lane's output, not an implementation it replicates, so this import does not
    breach the independence rule (FORBIDDEN_IMPORTS)."""
    from admission_integrity import spec_fingerprint
    spec = row.get("shadow_spec") or {}
    return spec_fingerprint(spec.get("symbol") or row.get("sym"), spec.get("family"),
                            spec.get("selector"), spec.get("side"), spec.get("params"))


def forward_rows(path: Path = SLEEVE_REGISTRY) -> list[dict[str, Any]]:
    doc = _read_json(path, {}) or {}
    rows = doc.get("sleeves") if isinstance(doc, dict) else {}
    out: list[dict[str, Any]] = []
    for key, row in (rows or {}).items():
        if isinstance(row, dict) and isinstance(row.get("identity"), dict):
            out.append({"key": str(key), **row})
    return out


def ledger_for(key: str, identity: Mapping[str, Any], shadow_dir: Path = SHADOW_DIR
               ) -> list[dict[str, Any]]:
    """`ledger_<SYM>_<family>_<selector>.json` (breakout clocks: `ledger_<SYM>_<selector>`)."""
    sym, fam = str(identity.get("symbol") or ""), str(identity.get("family") or "")
    sel = str(identity.get("selector") or "")
    names = [f"ledger_{sym}_{fam}_{sel}.json", f"ledger_{sym}_{sel}.json",
             f"ledger_{key.replace('.', '_').replace('#', '_')}.json"]
    for name in names:
        rows = _read_json(shadow_dir / name, None)
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
        if isinstance(rows, dict) and isinstance(rows.get("trades"), list):
            return [r for r in rows["trades"] if isinstance(r, dict)]
    return []


def replicate_certificate(row: Mapping[str, Any], *, meta: Mapping[str, Any],
                          bars: Bars | None) -> dict[str, Any]:
    spec = dict(row.get("shadow_spec") or {})
    fam, sym = str(spec.get("family") or ""), str(spec.get("symbol") or row.get("sym") or "")
    out: dict[str, Any] = {"lane": "certificate", "key": str(row.get("cell") or f"{sym} {fam}"),
                           "certificate": certificate_id(row), "fp": certificate_fp(row),
                           "symbol": sym, "family": fam, "verdict": UNMEASURED, "why": [],
                           "ours": {}, "theirs": {}}
    p, why = resolve_spec(fam, spec.get("params"), spec.get("selector"), spec.get("side"),
                          symbol=sym, condition=spec.get("condition"))
    if p is None:
        out["why"] = [why]
        return out
    if bars is None or len(bars) < MIN_BARS:
        out["why"] = [f"{sym} bars absent or shorter than {MIN_BARS} rows"]
        return out
    cost = cost_spec(meta)
    _orders, fills = rebuild(fam, bars, p, cost.price_units)
    ours, n_days = sharpe(fills)
    gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
    iss = gates.get("in_sample_screen") if isinstance(gates.get("in_sample_screen"), dict) else {}
    recorded = _num(iss.get("sharpe"))
    verdict, reasons = judge_certificate(recorded, ours, len(fills))
    out.update(verdict=verdict, why=reasons,
               ours={"sharpe": None if ours is None else round(ours, 4), "n_fills": len(fills),
                     "n_days": n_days, "cost_price_units": cost.price_units,
                     "cost_basis": cost.basis, "spec": SPEC_BOOK[fam].text,
                     "params": {k: v for k, v in p.items() if not k.startswith("_")}},
               theirs={"sharpe": recorded, "days": row.get("days")})
    return out


def replicate_forward(row: Mapping[str, Any], *, meta: Mapping[str, Any], bars: Bars | None,
                      ledger: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ident = dict(row.get("identity") or {})
    fam, sym = str(ident.get("family") or ""), str(ident.get("symbol") or "")
    out: dict[str, Any] = {"lane": "forward", "key": str(row.get("key") or ""), "symbol": sym,
                           "family": fam, "verdict": UNMEASURED, "why": [], "ours": {},
                           "theirs": {}, "divergence": {}}
    p, why = resolve_spec(fam, ident.get("params"), ident.get("selector"),
                          ident.get("direction"), symbol=sym,
                          condition=ident.get("condition") or ident.get("state"))
    if p is None:
        out["why"] = [why]
        return out
    if not ledger:
        out["why"] = ["no forward ledger on this box for this row"]
        return out
    if bars is None or len(bars) < MIN_BARS:
        out["why"] = [f"{sym} bars absent or shorter than {MIN_BARS} rows"]
        return out
    cost = cost_spec(meta)
    _orders, fills = rebuild(fam, bars, p, cost.price_units)
    start = str(row.get("forward_start") or "")
    try:
        t0 = int(np.datetime64(start.replace(" ", "T").split("+")[0], "ns").astype("int64"))
    except (ValueError, TypeError):
        t0 = int(bars.t[0])
    window = [f for f in fills if f.entry_t >= t0]
    verdict, reasons, div = judge_forward(ledger, window, bars.minutes, cost,
                                          row.get("cost_fields"))
    out.update(verdict=verdict, why=reasons, divergence=div,
               ours={"n_fills": len(window), "pnl_R": round(sum(f.r for f in window), 3),
                     "cost": {"spread_per_lot": cost.spread_per_lot,
                              "commission_per_lot": cost.commission_per_lot,
                              "quote_per_account": round(cost.quote_per_account, 6),
                              "basis": cost.basis}, "spec": SPEC_BOOK[fam].text},
               theirs={"n_trades": len(ledger), "cost_fields": row.get("cost_fields"),
                       "forward_start": start})
    return out


# ------------------------------------------------------------------------------- recording
def record(rows: Sequence[Mapping[str, Any]], *, conn: Any, dry_run: bool,
           quarantine_path: Path = QUARANTINE) -> dict[str, int]:
    out = {"quarantined": 0, "memory": 0, "candidates": 0}
    mismatches = [r for r in rows if r.get("verdict") == MISMATCH]
    if dry_run:
        return out
    definitive = [r for r in rows if r.get("verdict") in (MISMATCH, REPLICATED)]
    if definitive:
        doc = _read_json(quarantine_path, {}) or {}
        old = [r for r in (doc.get("rows") or []) if isinstance(r, dict)]
        keys = {(r.get("lane"), r.get("key")) for r in definitive}
        kept = [r for r in old if (r.get("lane"), r.get("key")) not in keys]
        for r in mismatches:
            kept.append({"key": r["key"], "lane": r["lane"], "symbol": r["symbol"],
                         "family": r["family"], "why": r["why"],
                         "divergence": r.get("divergence") or {}, "at": _now()})
        _write_atomic(quarantine_path, {"at": _now(), "rule": RULE, "rows": kept[-500:]})
        out["quarantined"] = len(mismatches)
    try:
        from libs.moat import registry as R
    except Exception:
        return out
    c = conn
    opened = False
    try:
        if c is None:
            c = R.connect()
            opened = True
        for r in rows:
            if r.get("verdict") == UNMEASURED:
                continue
            kind = "replication_mismatch" if r["verdict"] == MISMATCH else "replication"
            try:
                R.remember("replication", f"{r['lane']} {r['key']}: {r['verdict']} -- "
                           + "; ".join(r.get("why") or []), kind=kind,
                           memory_key=f"{SOURCE}:{r['key']}", result=str(r["verdict"]),
                           payload={"ours": r.get("ours"), "theirs": r.get("theirs"),
                                    "divergence": r.get("divergence")},
                           evidence={"rule": RULE, "at": _now()}, conn=c)
                out["memory"] += 1
            except Exception:
                continue
            if r["verdict"] != MISMATCH:
                continue
            try:
                hits = c.execute("SELECT id, status FROM research_candidates WHERE symbol=? AND "
                                 "family=? AND status IN ('queued','claimed')",
                                 (r["symbol"], r["family"])).fetchall()
            except Exception:
                hits = []
            for hit in hits:
                if R.mark_candidate(str(hit["id"]), str(hit["status"]), conn=c,
                                    replication_verdict=MISMATCH,
                                    replication_mismatch_json=json.dumps(
                                        {"why": r["why"], "divergence": r.get("divergence")},
                                        default=str),
                                    replication_judged_at=_now()):
                    out["candidates"] += 1
    finally:
        if opened and c is not None:
            with contextlib.suppress(Exception):
                c.close()
    return out


# ------------------------------------------------------------------------------- the pass
def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, conn: Any = None,
          certificates: Sequence[Mapping[str, Any]] | None = None,
          forward: Sequence[Mapping[str, Any]] | None = None,
          universe_meta: Mapping[str, Mapping[str, Any]] | None = None,
          bars_loader: Callable[[str, str], Bars | None] = load_bars,
          ledger_loader: Callable[[str, Mapping[str, Any]], list[dict[str, Any]]] = ledger_for,
          cursor_path: Path = CURSOR, quarantine_path: Path = QUARANTINE,
          report: Path = REPORT, max_per_pass: int = MAX_PER_PASS,
          priority_certificates: Sequence[str] = ()) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(budget_s))
    meta_all = dict(universe_meta) if universe_meta is not None else (
        _read_json(UNIVERSE_JSON, {}) or {})
    certs = list(certificates if certificates is not None else certificate_rows())
    fwd = list(forward if forward is not None else forward_rows())
    cursor = _read_json(cursor_path, {}) or {}
    ci = int(cursor.get("certificates") or 0) % max(1, len(certs)) if certs else 0
    fi = int(cursor.get("forward") or 0) % max(1, len(fwd)) if fwd else 0
    rows: list[dict[str, Any]] = []
    notes: list[str] = []
    per_lane = max(1, int(max_per_pass) // 2)
    verdicts_path = cursor_path.parent / VERDICTS_NAME
    book_doc = _read_json(verdicts_path, {}) or {}
    book = dict(book_doc.get("certificates") or {}) if isinstance(book_doc, dict) else {}
    # NEVER-JUDGED FIRST. A certificate the book has no verdict for -- or a verdict under a
    # different spec -- cannot start a forward clock (the admission door), so it is judged ahead
    # of the rotation: a new certificate waits about one pass, never a full cycle of the canon.
    # Recheck every old verdict under the corrected unit before judging new
    # certificates. A historical MISMATCH cannot remain a capital veto after
    # its checker changed, and its removal must come from a real rerun.
    old_metric = [i for i, r in enumerate(certs)
                  if book.get(certificate_id(r)) and
                  (book[certificate_id(r)].get("sharpe_metric_version")
                   != SHARPE_METRIC_VERSION)]
    pending = old_metric + [i for i, r in enumerate(certs)
                            if i not in set(old_metric) and
                            (book.get(certificate_id(r)) or {}).get("fp")
                            != certificate_fp(r)]
    rotation = [(ci + k) % len(certs) for k in range(len(certs))] if certs else []
    wanted = set(priority_certificates)
    priority = [i for i, r in enumerate(certs) if certificate_id(r) in wanted]
    first = list(dict.fromkeys(priority + pending))
    order = first + [i for i in rotation if i not in set(first)]
    for n, idx in enumerate(order[:per_lane]):
        if time.monotonic() > deadline:
            notes.append("budget: certificates left for the next pass")
            break
        row = certs[idx]
        spec = row.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or row.get("sym") or "")
        tf = str((spec.get("params") or {}).get("timeframe") or "H1")
        rows.append(replicate_certificate(row, meta=dict(meta_all.get(sym) or {}),
                                          bars=bars_loader(sym, tf)))
        if n >= len(first):
            cursor["certificates"] = (idx + 1) % len(certs)
    for k in range(min(per_lane, len(fwd))):
        if time.monotonic() > deadline:
            notes.append("budget: forward rows left for the next pass")
            break
        row = fwd[(fi + k) % len(fwd)]
        ident = row.get("identity") or {}
        sym, tf = str(ident.get("symbol") or ""), str(ident.get("timeframe") or "H1")
        rows.append(replicate_forward(row, meta=dict(meta_all.get(sym) or {}),
                                      bars=bars_loader(sym, tf),
                                      ledger=ledger_loader(str(row.get("key") or ""), ident)))
        cursor["forward"] = (fi + k + 1) % len(fwd)
    recorded = record(rows, conn=conn, dry_run=dry_run, quarantine_path=quarantine_path)
    counts = {v: sum(1 for r in rows if r["verdict"] == v)
              for v in (REPLICATED, MISMATCH, UNMEASURED)}
    doc = {
        "at": _now(), "rule": RULE, "dry_run": bool(dry_run),
        "sharpe_metric_version": SHARPE_METRIC_VERSION,
        "population": {"certificates": len(certs), "forward_rows": len(fwd),
                       "spec_book": sorted(SPEC_BOOK)},
        "n": len(rows), "counts": counts, "verdicts": rows,
        "quarantined": [r["key"] for r in rows if r["verdict"] == MISMATCH],
        "unmeasured": [{"what": r["key"], "why": "; ".join(r["why"])} for r in rows
                       if r["verdict"] == UNMEASURED],
        "recorded": recorded, "cursor": cursor, "notes": notes,
        "independence": {"forbidden_imports": list(FORBIDDEN_IMPORTS),
                         "bars_read_by_this_module": list(BARS_READ[-50:]),
                         "why": ("the lane is handed the written rule, the parameters, the data "
                                 "name and the cost terms; signal, fills, exits and costs are "
                                 "rebuilt here and never imported")},
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        _write_atomic(cursor_path, {**cursor, "at": _now()})
        _write_atomic(report, doc)
        for r in rows:
            if r.get("lane") == "certificate" and r.get("certificate"):
                book[str(r["certificate"])] = {"verdict": r["verdict"], "fp": r.get("fp"),
                                               "sharpe_metric_version": SHARPE_METRIC_VERSION,
                                               "why": list(r.get("why") or [])[:4],
                                               "key": r.get("key"), "at": _now()}
        _write_atomic(verdicts_path, {"at": _now(), "rule": RULE, "certificates": book})
    doc["verdict_book"] = {"path": str(verdicts_path.name), "n": len(book),
                           "judged_first_this_pass": min(len(pending), per_lane)}
    return doc


def render(doc: Mapping[str, Any]) -> list[str]:
    c, pop = doc.get("counts") or {}, doc.get("population") or {}
    lines = [f"REPLICATION  {doc.get('n')} row(s) of {pop.get('certificates')} certificate(s) + "
             f"{pop.get('forward_rows')} forward row(s): {c.get(REPLICATED, 0)} REPLICATED, "
             f"{c.get(MISMATCH, 0)} MISMATCH (quarantined), {c.get(UNMEASURED, 0)} UNMEASURED"]
    for r in (doc.get("verdicts") or [])[:16]:
        lines.append(f"  {r['verdict']:<11} {r['lane']:<11} {str(r['key'])[:52]:<52} "
                     f"{'; '.join(r.get('why') or [])[:90]}")
    for note in doc.get("notes") or []:
        lines.append(f"  note: {note}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="independent re-implementation of certificates "
                                             "and forward rows from their written specification")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="rebuild, compare, print; write "
                                                            "nothing")
    ap.add_argument("--max-per-pass", type=int, default=MAX_PER_PASS)
    ap.add_argument("--priority-certificate", action="append", default=[],
                    help="judge an exact certificate first in this bounded pass")
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run, max_per_pass=a.max_per_pass,
                priority_certificates=a.priority_certificate)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: no cursor, quarantine, report or registry row written")
    else:
        print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
