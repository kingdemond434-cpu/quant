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
from dataclasses import dataclass
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
    "mt5desk.engine", "mt5desk.family_call", "proposer_common", "external_gauntlet",
    "lead_replication", "shadow_forward", "external_shadow")

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
                     c: np.ndarray) -> Bars:
    t = np.asarray(t_ns, dtype="int64")
    order = np.argsort(t, kind="stable")
    t = t[order]
    gaps = np.diff(t) if len(t) > 1 else np.asarray([3_600_000_000_000])
    gaps = gaps[gaps > 0]
    step = int(np.median(gaps)) if len(gaps) else 3_600_000_000_000
    return Bars(t, np.asarray(o, dtype="float64")[order], np.asarray(h, dtype="float64")[order],
                np.asarray(low, dtype="float64")[order], np.asarray(c, dtype="float64")[order],
                max(1, step // 60_000_000_000))


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
        keep = ~stamps.isna().to_numpy()
        t_ns = stamps[keep].astype("int64").to_numpy() if hasattr(stamps, "astype") else None
        if t_ns is None:
            return None
        arrs = [frame[cols[k]].to_numpy(dtype="float64")[keep] for k in need]
    except Exception:
        return None
    if len(t_ns) < 2:
        return None
    return bars_from_arrays(np.asarray(t_ns, dtype="int64"), *arrs)


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
    """Annualised Sharpe of the DAILY sums of R (sqrt 252), as the certificate's screen states."""
    if not fills:
        return None, 0
    days: dict[int, float] = {}
    for f in fills:
        d = int(f.entry_t // 86_400_000_000_000)
        days[d] = days.get(d, 0.0) + f.r
    x = np.asarray(list(days.values()), dtype="float64")
    if len(x) < 2 or float(np.std(x)) == 0:
        return 0.0, len(x)
    return float(np.mean(x) / np.std(x) * np.sqrt(252.0)), len(x)


# -------------------------------------------------------------------------------- rebuild
def resolve_spec(family: str, params: Mapping[str, Any] | None, selector: str | None,
                 side: str | int | None) -> tuple[dict[str, Any] | None, str]:
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
    return p, "ok"


def rebuild(family: str, bars: Bars, p: Mapping[str, Any], cost_units: float
            ) -> tuple[list[Order], list[Fill]]:
    orders = SPEC_BOOK[family].build(bars, dict(p))
    side = int(p.get("_side") or 0)
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
    doc = _read_json(path, {}) or {}
    rows = doc.get("survivors") if isinstance(doc, dict) else doc
    items = list(rows.values()) if isinstance(rows, dict) else list(rows or [])
    return [r for r in items if isinstance(r, dict) and isinstance(r.get("shadow_spec"), dict)]


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
                           "symbol": sym, "family": fam, "verdict": UNMEASURED, "why": [],
                           "ours": {}, "theirs": {}}
    p, why = resolve_spec(fam, spec.get("params"), spec.get("selector"), spec.get("side"))
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
                          ident.get("direction"))
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
    if mismatches:
        doc = _read_json(quarantine_path, {}) or {}
        kept = [r for r in (doc.get("rows") or []) if isinstance(r, dict)]
        keys = {r.get("key") for r in mismatches}
        kept = [r for r in kept if r.get("key") not in keys]
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
          report: Path = REPORT, max_per_pass: int = MAX_PER_PASS) -> dict[str, Any]:
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
    for k in range(min(per_lane, len(certs))):
        if time.monotonic() > deadline:
            notes.append("budget: certificates left for the next pass")
            break
        row = certs[(ci + k) % len(certs)]
        spec = row.get("shadow_spec") or {}
        sym = str(spec.get("symbol") or row.get("sym") or "")
        tf = str((spec.get("params") or {}).get("timeframe") or "H1")
        rows.append(replicate_certificate(row, meta=dict(meta_all.get(sym) or {}),
                                          bars=bars_loader(sym, tf)))
        cursor["certificates"] = (ci + k + 1) % len(certs)
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
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run, max_per_pass=a.max_per_pass)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: no cursor, quarantine, report or registry row written")
    else:
        print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
