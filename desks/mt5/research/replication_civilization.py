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
import hashlib
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
#: THE VERDICT BOOK (2026-09-30): the last verdict per CERTIFICATE, with the spec fingerprint it
#: was judged under. `research/admission_integrity.py` reads it: a new certificate starts a
#: forward clock only when this book says REPLICATED under its current spec.
VERDICTS_NAME = "verdicts.json"

BUDGET_S = 900.0
#: Breadth-per-run bound so a pass finishes; the cursor rotates through both lanes so every row
#: is reached across passes (LAWS 2: a count is never a ceiling).
MAX_PER_PASS = 16
#: Certificates judged UNMEASURED before their family had a rule, re-judged per pass on top of the
#: lane's share; each is one bar file and one rebuild, about a second.
PENDING_PER_PASS = 64
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
    "mt5desk.engine", "mt5desk.family_call", "proposer_common", "external_gauntlet",
    "lead_replication", "shadow_forward", "external_shadow", "mt5desk.family_formula",
    "mt5desk.families_vector", "libs.research.alpha_grammar", "alpha_grammar",
    "mt5desk.families_orthogonal", "mt5desk.causal_residual", "mt5desk.cell_modifiers")

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
    #: The broker's per-bar spread and tick count, when the file carries them (the formula rule's
    #: `spread`, `activity` and `flow` terminals); None when absent, and a rule reading None stands
    #: aside rather than inventing a series.
    spread: np.ndarray | None = None
    volume: np.ndarray | None = None

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
                     c: np.ndarray, spread: np.ndarray | None = None,
                     volume: np.ndarray | None = None) -> Bars:
    t = np.asarray(t_ns, dtype="int64")
    order = np.argsort(t, kind="stable")
    t = t[order]
    gaps = np.diff(t) if len(t) > 1 else np.asarray([3_600_000_000_000])
    gaps = gaps[gaps > 0]
    step = int(np.median(gaps)) if len(gaps) else 3_600_000_000_000

    def _opt(x: np.ndarray | None) -> np.ndarray | None:
        return None if x is None else np.asarray(x, dtype="float64")[order]

    return Bars(t, np.asarray(o, dtype="float64")[order], np.asarray(h, dtype="float64")[order],
                np.asarray(low, dtype="float64")[order], np.asarray(c, dtype="float64")[order],
                max(1, step // 60_000_000_000), _opt(spread), _opt(volume))


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
        extra = [frame[cols[k]].to_numpy(dtype="float64")[keep]
                 if k in cols and cols[k] in frame.columns else None
                 for k in ("spread", "tick_volume")]
    except Exception:
        return None
    if len(t_ns) < 2:
        return None
    return bars_from_arrays(np.asarray(t_ns, dtype="int64"), *arrs, *extra)


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
    #: The session comes from the cell's own `session` PARAMETER (the generic session axis the
    #: gauntlet's shared call applies), never from the certificate's selector: the sweep stamps
    #: "asia" on every certificate whose params name no window, which is a lie for a family with
    #: no session semantics -- such a cell was judged on EVERY hour.
    session_from_params: bool = False
    #: The rule applies the session itself (at the signal bar, before any entry delay), so the
    #: rebuild must not filter the orders' (possibly delayed) bar hours a second time.
    session_in_build: bool = False

    def __post_init__(self) -> None:
        if self.session_from_params and "own session parameter" not in self.text:
            self.text = f"{self.text} {SESSION_FROM_PARAMS_TEXT}"


#: Stated in every rule whose session is the cell's own parameter (RuleSpec.__post_init__).
SESSION_FROM_PARAMS_TEXT = (
    "Signals are kept only in the cell's own session parameter (asia [0,8), london [8,16), ny "
    "[14,22) broker hours; none or any other name: every hour) and in a selector parameter's "
    "session when the cell carries one; the certificate's stamped selector is never a session.")


def rule_fingerprint(family: str) -> str | None:
    """What the written rule IS: its text and the flags that change how it is read. A verdict
    taken under another rule fingerprint is a verdict on a different rule."""
    spec = SPEC_BOOK.get(str(family or ""))
    if spec is None:
        return None
    blob = json.dumps([spec.text, spec.selector_params, spec.session_from_params,
                       spec.session_in_build, sorted(spec.defaults)], default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


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
        _build_overnight_gap_decay, session_from_params=True),
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
        _build_dow_effect, session_from_params=True),
    "monday_gap": RuleSpec(
        "monday_gap",
        "At Monday hour 0, gap = open - the last Friday bar's close; if |gap| >= min_gap_atr x "
        "ATR(atr_n) trade with the gap (mode momentum) or against it (mode fade): entry next "
        "open, stop 1.2 x ATR, target rr x that, time exit after ttl_bars.",
        {"atr_n": 20, "ttl_bars": 12, "rr": 1.8, "mode": "momentum", "min_gap_atr": 0.2},
        _build_monday_gap, session_from_params=True),
    "mean_reversion_rsi": RuleSpec(
        "mean_reversion_rsi",
        "RSI(rsi_n) crossing up through oversold is a long, crossing down through overbought a "
        "short; entry next open, stop 1.2 x ATR(atr_n), target rr x that, time exit after "
        "ttl_bars.",
        {"rsi_n": 14, "oversold": 30, "overbought": 70, "atr_n": 20, "ttl_bars": 12, "rr": 1.8},
        _build_mean_reversion_rsi, session_from_params=True),
    "overnight_drift": RuleSpec(
        "overnight_drift",
        "At anchor_hour, drift = (close - close hold_bars ago) / ATR(atr_n); if |drift| >= 0.3 "
        "fade it: entry next open, stop 1.2 x ATR, target rr x that, time exit after ttl_bars.",
        {"anchor_hour": 0, "hold_bars": 8, "atr_n": 20, "ttl_bars": 12, "rr": 1.8},
        _build_overnight_drift, session_from_params=True),
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
        _build_hunt16_cell, session_from_params=True),
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
        _build_carry, session_from_params=True),
})


# ------------------------------------------------------------- the formula rule (2026-11-04)
# WHY. 582 `formula` certificates (plus 104 others with no rule) sat out of forward clocks with
# "no written specification in the spec book for family 'formula'" (FORWARD_ENROLMENT 16:21Z
# 2026-11-04): the admission door holds a certificate until this lane says REPLICATED, and a
# family with no rule here can only ever be UNMEASURED. The rule below is the family's stated
# behaviour (the expression grammar's operator definitions and the family's entry/exit text)
# rebuilt in THIS module's own numpy; nothing is imported from the grammar or the family. An
# expression naming a terminal or operator this rule does not define stands aside (no orders, so
# UNMEASURED), never a guess.

#: Bars of log return the `vol` terminal is measured over (the grammar's stated one trading day).
FX_VOL_N = 24
#: Rows per block for the windowed reductions that need the whole window (ts_rank, bars_since):
#: bounds their temporary arrays to ~FX_CHUNK x window floats on any chart.
FX_CHUNK = 4096
FX_BAR_TERMINALS = frozenset({"close", "open", "high", "low", "ret", "range", "body", "atr",
                              "vol", "spread", "activity", "flow"})
FX_UNARY = frozenset({"neg", "abs", "sign"})
FX_WINDOWED = frozenset({"delay", "delta", "mean", "std", "min", "max", "sum", "ts_rank",
                         "zscore", "decay", "bars_since_max", "bars_since_min", "atr_norm",
                         "ts_backfill", "scale"})
FX_BINARY = frozenset({"add", "sub", "mul", "div", "max2", "min2", "trade_when"})
FX_BINARY_WINDOWED = frozenset({"corr", "cov", "residual", "group_rank", "group_zscore"})


class FormulaUndefined(ValueError):
    """The expression names something this rule does not define: the rule stands aside."""


def _fx_parse(text: str) -> Any:
    """A rendered call, `op(arg, arg, 5)`, back to the prefix list; a bare name stays a name."""
    toks: list[str] = []
    cur = ""
    for ch in str(text):
        if ch in "(),":
            if cur.strip():
                toks.append(cur.strip())
            toks.append(ch)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        toks.append(cur.strip())
    pos = 0

    def node() -> Any:
        nonlocal pos
        if pos >= len(toks) or toks[pos] in "(),":
            raise FormulaUndefined(f"unparseable expression {text!r}")
        name = toks[pos]
        pos += 1
        if pos < len(toks) and toks[pos] == "(":
            pos += 1
            args: list[Any] = [name]
            while True:
                args.append(node())
                if pos >= len(toks):
                    raise FormulaUndefined(f"unclosed call in {text!r}")
                if toks[pos] == ",":
                    pos += 1
                    continue
                if toks[pos] == ")":
                    pos += 1
                    return args
                raise FormulaUndefined(f"unexpected {toks[pos]!r} in {text!r}")
        try:
            return int(name)
        except ValueError:
            return name

    out = node()
    if pos != len(toks):
        raise FormulaUndefined(f"trailing tokens in {text!r}")
    return out


def _fx_shift(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if 0 <= k < x.size:
        out[k:] = x[:x.size - k]
    return out


def _fx_origin(x: np.ndarray) -> float:
    """The series' first defined value: the window sums are taken about it, which keeps the
    squares free of the price level and keeps an integer series (spread points, ticks) exact."""
    ok = np.flatnonzero(np.isfinite(x))
    return float(x[ok[0]]) if ok.size else 0.0


def _fx_flat(x: np.ndarray, w: int) -> np.ndarray:
    """True where the trailing w values are all the SAME defined value. Such a window's mean is
    that value and its deviation exactly 0, so z there is 0/0, undefined -- never the ratio of
    two rounding residues."""
    same = np.concatenate([[False], x[1:] == x[:-1]]) if x.size else np.zeros(0, dtype=bool)
    run = np.zeros(x.size, dtype="int64")
    if x.size:
        idx = np.arange(x.size)
        start = np.where(same, 0, idx)
        start = np.maximum.accumulate(start)
        run = idx - start + 1
    return (run >= w) & np.isfinite(x)


def _fx_roll_sums(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per bar: whether the trailing w values are all defined, and their sum and sum of squares
    about `_fx_origin` (window statistics are shift-invariant)."""
    ok = np.isfinite(x)
    mu = _fx_origin(x)
    xs = np.where(ok, x - mu, 0.0)
    c1 = np.concatenate([[0.0], np.cumsum(xs)])
    c2 = np.concatenate([[0.0], np.cumsum(xs * xs)])
    cn = np.concatenate([[0], np.cumsum(ok.astype("int64"))])
    full = np.zeros(x.size, dtype=bool)
    s1 = np.full(x.size, np.nan)
    s2 = np.full(x.size, np.nan)
    if w <= x.size:
        i = np.arange(w - 1, x.size)
        full[i] = (cn[i + 1] - cn[i + 1 - w]) == w
        s1[i] = c1[i + 1] - c1[i + 1 - w]
        s2[i] = c2[i + 1] - c2[i + 1 - w]
    return full, s1, s2


def _fx_mean(x: np.ndarray, w: int) -> np.ndarray:
    """Trailing mean of exactly w defined values; undefined otherwise."""
    full, s1, _ = _fx_roll_sums(x, w)
    out = np.where(full, s1 / w + _fx_origin(x), np.nan)
    return np.where(_fx_flat(x, w), x, out)


def _fx_sum(x: np.ndarray, w: int) -> np.ndarray:
    return _fx_mean(x, w) * w


def _fx_std(x: np.ndarray, w: int) -> np.ndarray:
    """Trailing sample standard deviation (n - 1) of exactly w defined values."""
    if w < 2:
        return np.full(x.size, np.nan)
    full, s1, s2 = _fx_roll_sums(x, w)
    with np.errstate(invalid="ignore"):
        var = (s2 - s1 * s1 / w) / (w - 1)
    out = np.where(full, np.sqrt(np.maximum(var, 0.0)), np.nan)
    return np.where(_fx_flat(x, w), 0.0, out)


def _fx_z(x: np.ndarray, w: int) -> np.ndarray:
    """(x - strict w-bar mean) / strict w-bar sample std; a window with no deviation reads 0 --
    the value IS its mean -- never 0/0 and never the ratio of two rounding residues."""
    mu, sd = _fx_mean(x, w), _fx_std(x, w)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (x - mu) / sd
    return np.where(np.isfinite(mu) & (sd == 0) & np.isfinite(x), 0.0, z)


def _fx_extreme(x: np.ndarray, w: int, fn: Callable[..., np.ndarray]) -> np.ndarray:
    out = np.full(x.size, np.nan)
    if w > x.size:
        return out
    from numpy.lib.stride_tricks import sliding_window_view
    out[w - 1:] = fn(sliding_window_view(x, w), axis=1)   # a NaN in the window stays NaN
    return out


def _fx_ts_rank(x: np.ndarray, w: int) -> np.ndarray:
    """Share of the previous w values at or below the current one (an undefined previous value
    counts as not below; the current one undefined compares as nothing)."""
    out = np.full(x.size, np.nan)
    if x.size <= w:
        return out
    for a in range(w, x.size, FX_CHUNK):
        b = min(x.size, a + FX_CHUNK)
        prev = np.stack([x[a - w + j:b - w + j] for j in range(w)], axis=1)
        with np.errstate(invalid="ignore"):
            out[a:b] = (prev <= x[a:b, None]).mean(axis=1)
    return out


def _fx_bars_since(x: np.ndarray, w: int, high: bool) -> np.ndarray:
    """Bars since the window's extreme (the most recent w values, first occurrence wins);
    undefined values never win."""
    out = np.full(x.size, np.nan)
    if x.size < w:
        return out
    fill = -np.inf if high else np.inf
    for a in range(w - 1, x.size, FX_CHUNK):
        b = min(x.size, a + FX_CHUNK)
        win = np.stack([x[a - w + 1 + j:b - w + 1 + j] for j in range(w)], axis=1)
        win = np.where(np.isfinite(win), win, fill)
        pos = np.argmax(win, axis=1) if high else np.argmin(win, axis=1)
        out[a:b] = (w - 1) - pos
    return out


def _fx_ffill(x: np.ndarray, limit: int | None = None) -> np.ndarray:
    """Carry the last defined value forward, at most `limit` bars (None: without bound)."""
    ok = np.isfinite(x)
    last = np.where(ok, np.arange(x.size), -1)
    last = np.maximum.accumulate(last) if x.size else last
    out = np.where(last >= 0, x[np.maximum(last, 0)], np.nan)
    if limit is not None:
        out = np.where((np.arange(x.size) - last) <= limit, out, np.nan)
    return out


def _fx_roll_cov(a: np.ndarray, b: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray,
                                                                 np.ndarray]:
    """Trailing sample covariance and both variances over the w bars where BOTH are defined
    (exactly w of them, else undefined)."""
    both = np.isfinite(a) & np.isfinite(b)
    aa, bb = np.where(both, a, np.nan), np.where(both, b, np.nan)
    ma, mb = _fx_mean(aa, w), _fx_mean(bb, w)
    mab = _fx_mean(aa * bb, w)
    cov = (mab - ma * mb) * w / (w - 1)
    va, vb = _fx_std(aa, w) ** 2, _fx_std(bb, w) ** 2
    return cov, va, vb


def _fx_group(x: np.ndarray, g: np.ndarray, w: int, rank: bool) -> np.ndarray:
    """Against the current bar's PEERS: the past w bars (this one included) whose g sits on the
    same side of g's own window mean as the current bar's, both defined. rank = share of peers
    at or below the current value (needs 2+ peers); else its z-score against the peers'
    population mean and deviation (needs 3+ peers and a deviation above 1e-12)."""
    out = np.full(x.size, np.nan)
    if x.size < w or w < 2:
        return out
    for i in range(w - 1, x.size):
        xw, gw = x[i - w + 1:i + 1], g[i - w + 1:i + 1]
        fin = np.isfinite(gw)
        if not fin.any():
            continue
        side = np.sign(gw - np.mean(gw[fin]))
        peers = (side == side[-1]) & np.isfinite(xw) & fin
        n = int(peers.sum())
        cur = xw[-1]
        if rank:
            if n > 1:
                out[i] = float(np.sum(peers & (xw <= cur))) / n
        else:
            ps = xw[peers]
            sd = float(np.std(ps)) if n else 0.0
            if n > 2 and sd > 1e-12:
                out[i] = (cur - float(np.mean(ps))) / sd
    return out


def _fx_terminals(b: Bars, atr_n: int) -> dict[str, np.ndarray]:
    c, o, h, lo = b.c, b.o, b.h, b.low
    with np.errstate(all="ignore"):
        ret = np.concatenate([[np.nan], np.diff(np.log(c))])
        prev = np.concatenate([[np.nan], c[:-1]])
        tr = np.fmax(h - lo, np.fmax(np.abs(h - prev), np.abs(lo - prev)))
        body = (c - o) / c
        out = {"close": c, "open": o, "high": h, "low": lo, "ret": ret, "range": (h - lo) / c,
               "body": body, "atr": _fx_mean(tr, int(atr_n)), "vol": _fx_std(ret, FX_VOL_N)}
    if b.spread is not None:
        out["spread"] = b.spread
    if b.volume is not None:
        out["activity"] = b.volume
        out["flow"] = np.where(np.isfinite(body), np.sign(body), 0.0) * b.volume
    return out


def _fx_eval(expr: Any, T: dict[str, np.ndarray], n: int) -> np.ndarray:
    """The expression as a float per bar; NaN where undefined; infinities read as undefined."""
    with np.errstate(all="ignore"):
        v = _fx_node(expr, T, n)
    return np.where(np.isfinite(v), v, np.nan)


def _fx_node(e: Any, T: dict[str, np.ndarray], n: int) -> np.ndarray:
    if isinstance(e, str):
        if e not in FX_BAR_TERMINALS:
            raise FormulaUndefined(f"terminal {e!r} is not a bar terminal")
        if e not in T:
            raise FormulaUndefined(f"terminal {e!r} is not in this file")
        return np.asarray(T[e], dtype="float64")
    if not isinstance(e, (list, tuple)) or not e:
        raise FormulaUndefined(f"not an expression: {e!r}")
    op = str(e[0])
    if op in FX_UNARY:
        a = _fx_eval(e[1], T, n)
        return -a if op == "neg" else np.abs(a) if op == "abs" else np.sign(a)
    if op in FX_WINDOWED:
        a, w = _fx_eval(e[1], T, n), int(e[2])
        if w < 1 or w > n:
            return np.full(n, np.nan)
        if op == "delay":
            return _fx_shift(a, w)
        if op == "delta":
            return a - _fx_shift(a, w)
        if op == "mean":
            return _fx_mean(a, w)
        if op == "sum":
            return _fx_sum(a, w)
        if op == "std":
            return _fx_std(a, w)
        if op in ("min", "max"):
            return _fx_extreme(a, w, np.min if op == "min" else np.max)
        if op == "ts_rank":
            return _fx_ts_rank(a, w)
        if op == "zscore":
            return _fx_z(a, w)
        if op == "decay":
            wt = np.arange(w, 0, -1, dtype=float)
            acc = np.zeros(n)
            for k in range(w):
                acc = acc + _fx_shift(a, k) * wt[k]
            return acc / wt.sum()
        if op in ("bars_since_max", "bars_since_min"):
            return _fx_bars_since(a, w, op == "bars_since_max")
        if op == "atr_norm":
            if "atr" not in T:
                raise FormulaUndefined("atr_norm needs the atr terminal")
            at = T["atr"]
            den = np.full(n, np.nan)
            okv = np.isfinite(at)
            cs = np.concatenate([[0.0], np.cumsum(np.where(okv, at, 0.0))])
            cn = np.concatenate([[0], np.cumsum(okv.astype("int64"))])
            i = np.arange(n)
            lo = np.maximum(0, i - w + 1)
            cnt = cn[i + 1] - cn[lo]
            den = np.where(cnt > 0, (cs[i + 1] - cs[lo]) / np.maximum(cnt, 1), np.nan)
            return a / den
        if op == "ts_backfill":
            return _fx_ffill(a, w)
        if op == "scale":
            den = _fx_sum(np.abs(a), w)
            return a / np.where(den > 1e-12, den, np.nan)
    if op in FX_BINARY:
        a, b2 = _fx_eval(e[1], T, n), _fx_eval(e[2], T, n)
        if op == "trade_when":
            return _fx_ffill(np.where(a > 0, b2, np.nan))
        if op == "add":
            return a + b2
        if op == "sub":
            return a - b2
        if op == "mul":
            return a * b2
        if op == "div":
            return a / np.where(np.abs(b2) > 1e-12, b2, np.nan)
        return np.fmax(a, b2) if op == "max2" else np.fmin(a, b2)
    if op in FX_BINARY_WINDOWED:
        a, b2, w = _fx_eval(e[1], T, n), _fx_eval(e[2], T, n), int(e[3])
        if w < 3 or w > n:
            return np.full(n, np.nan)
        if op in ("group_rank", "group_zscore"):
            return _fx_group(a, b2, w, op == "group_rank")
        cov, va, vb = _fx_roll_cov(a, b2, w)
        if op == "cov":
            return cov
        if op == "corr":
            return cov / np.sqrt(va * vb)
        beta = cov / np.where(vb > 1e-18, vb, np.nan)
        both = np.isfinite(a) & np.isfinite(b2)
        return np.where(both, a - beta * b2, np.nan)
    raise FormulaUndefined(f"operator {op!r} is not defined by this rule")


def _build_formula(b: Bars, p: dict[str, Any]) -> list[Order]:
    expr = p.get("expr")
    if isinstance(expr, str) and "(" in expr:
        try:
            expr = _fx_parse(expr)
        except FormulaUndefined:
            return []
    mode = str(p.get("side_mode") or "")
    norm, hold = int(p["norm"]), int(p["hold_bars"])
    if expr is None or mode not in ("follow", "fade") or len(b) < max(2 * norm, 300):
        return []
    try:
        v = _fx_eval(expr, _fx_terminals(b, int(p["atr_n"])), len(b))
    except (FormulaUndefined, TypeError, ValueError, IndexError):
        return []
    z = _fx_z(v, norm)
    z = np.where(np.isfinite(z), z, np.nan)
    if np.isfinite(z).sum() < 0.05 * z.size:
        return []
    a = atr(b, int(p["atr_n"]))
    flip = 1 if mode == "follow" else -1
    ez, sa, rr = float(p["entry_z"]), float(p["stop_atr"]), float(p["rr"])
    out: list[Order] = []
    last = -10 ** 9
    for i in range(norm, len(b) - 1):
        if i - last < hold:
            continue
        zi, ai = z[i], float(a[i])
        if not np.isfinite(zi) or abs(zi) < ez or not np.isfinite(ai) or ai <= 0 or zi == 0:
            continue
        side = int(np.sign(zi)) * flip
        px = float(b.c[i])
        out.append(Order(int(b.t[i]), side, px - side * sa * ai, px + side * sa * ai * rr, hold))
        last = i
    return out


SPEC_BOOK["formula"] = RuleSpec(
    "formula",
    "Evaluate the stored expression over the bars: terminals close, open, high, low, ret (log "
    "return), range ((h-l)/c), body ((c-o)/c), atr (strict atr_n mean of true range), vol "
    "(strict 24-bar sample std of ret), spread and activity (the broker's per-bar spread and "
    "tick count) and flow (sign(body) x activity); unary neg/abs/sign; windowed delay, delta, "
    "mean/std/sum/min/max (exactly w defined values, std n-1), ts_rank (share of the previous w "
    "at or below the current), zscore, decay (linear weights w..1), bars_since_max/min, "
    "atr_norm (over the mean of atr's last w defined values), ts_backfill (forward fill at most "
    "w bars), scale (over the sum of |x| over w); binary add/sub/mul/div (|den| > 1e-12), "
    "max2/min2 (an undefined side yields the other), trade_when (the second where the first "
    "is > 0, else the last such value); zscore and the normalisation read 0 on a window "
    "with no deviation (the value is its mean); corr/cov/residual over w bars where both "
    "are defined; "
    "group_rank/group_zscore against the window's bars on the same side of g's window mean. "
    "Infinities are undefined. z = (value - its strict norm-bar mean) / its strict norm-bar "
    "sample std; stand aside on fewer than max(2 x norm, 300) bars or under 5% defined z. From "
    "bar norm on, at least hold_bars after the last signal: when |z| >= entry_z and ATR(atr_n) "
    "> 0, a signal at the bar close on side sign(z) (follow) or against it (fade); stop "
    "stop_atr x ATR, target rr x that, entry next open, time exit after hold_bars. The session "
    "is the cell's own session parameter (none: every hour), never the certificate's selector. "
    "Anything the expression names outside this list stands aside.",
    {"expr": None, "norm": 240, "entry_z": 1.5, "side_mode": "follow", "hold_bars": 8,
     "atr_n": 20, "stop_atr": 2.0, "rr": 1.5},
    _build_formula, session_from_params=True)


# ------------------------------------------------- the cross_asset_residual rule (2026-11-04)
# WHY. 28 cross_asset_residual certificates (the desk's one non-directional, multi-factor
# mechanism) sat out of forward clocks for want of a written rule (FORWARD_ENROLMENT 16:21Z
# 2026-11-04). Written from the family's stated behaviour and the transformation miners' declared
# modifiers, rebuilt here; nothing imported from the family, its residual helper or the modifier
# module (FORBIDDEN_IMPORTS).

#: Ridge added to the window's normal equations, as a share of their mean diagonal: numerical
#: insurance only (a collinear window still solves), far below any economic effect.
CAR_RIDGE_FRAC = 1e-10
CAR_VOL_REGIMES = {"high_vol": 1, "high_volatility": 1, "low_vol": -1}
CAR_NO_OP_REGIMES = frozenset({"", "unconditional", "all", "any"})
#: Where stop and target are measured from. prev_row is what the certified family does (Auditor
#: and CRO ruling 2026-11-04: the family stays as certified and is judged against what it does);
#: signal_close is the corrected reading, a separate spec with its own certificates.
CAR_REFERENCES = ("prev_row", "signal_close")


def _car_causal_residual(y: np.ndarray, X: np.ndarray, win: int) -> np.ndarray:
    """eps[t] = y[t] - [1, X[t]] . beta[t], beta[t] the least-squares fit WITH a constant over
    rows [t-win, t-1] only (ridge CAR_RIDGE_FRAC x mean diagonal); undefined before row win or
    with fewer than k+2 rows in the window."""
    n, k = y.size, X.shape[1]
    k1 = k + 1
    eps = np.full(n, np.nan)
    if win < k1 + 1 or n <= win:
        return eps
    Z = np.column_stack([np.ones(n), X])
    for t in range(win, n):
        Zw, yw = Z[t - win:t], y[t - win:t]
        A = Zw.T @ Zw
        A = A + CAR_RIDGE_FRAC * max(float(np.trace(A)) / k1, 1e-300) * np.eye(k1)
        try:
            beta = np.linalg.solve(A, Zw.T @ yw)
        except np.linalg.LinAlgError:
            beta = np.linalg.pinv(A) @ (Zw.T @ yw)
        eps[t] = y[t] - float(Z[t] @ beta)
    return eps


def _car_roll(x: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Trailing mean and sample std (n - 1) over exactly w defined values; NaN otherwise."""
    mu = np.full(x.size, np.nan)
    sd = np.full(x.size, np.nan)
    for i in range(w - 1, x.size):
        win = x[i - w + 1:i + 1]
        if np.all(np.isfinite(win)):
            mu[i] = float(np.mean(win))
            sd[i] = float(np.std(win, ddof=1)) if w > 1 else np.nan
    return mu, sd


def _car_vol_mask(b: Bars, sign: int) -> np.ndarray:
    """high_vol: the 20-bar sample std of simple returns above its own 100-bar median (low_vol:
    below), both strict; undefined reads False."""
    with np.errstate(all="ignore"):
        ret = np.concatenate([[np.nan], b.c[1:] / b.c[:-1] - 1.0])
    _, rv = _car_roll(ret, 20)
    med = _roll_strict(rv, 100, lambda w: float(np.median(w)))
    with np.errstate(invalid="ignore"):
        return (rv > med) if sign > 0 else (rv < med)


def _build_cross_asset_residual(b: Bars, p: dict[str, Any]) -> list[Order]:
    names = [str(s) for s in (p.get("factor_symbols") or [])]
    mode = str(p.get("side_mode") or "revert").lower()
    regime = str(p.get("regime") or "").strip().lower()
    timing = str(p.get("entry_timing") or "").strip().lower()
    style = str(p.get("execution_style") or p.get("entry_style") or "").strip().lower()
    ref = str(p.get("reference") or "prev_row").strip().lower()
    if (not names or mode not in ("revert", "continue") or ref not in CAR_REFERENCES
            or (regime not in CAR_NO_OP_REGIMES and regime not in CAR_VOL_REGIMES)
            or timing not in ("", "instant", "delayed") or style not in ("", "market")):
        return []
    tf = str(p.get("timeframe") or "H1")
    facs = [load_bars(s, tf) for s in names]
    if any(f is None for f in facs):
        return []                          # every named factor is part of the certified model
    look = int(p["lookback"])
    bwin = int(p.get("beta_win") or look)
    # The target's and every factor's closes on the timestamps ALL of them carry.
    common = b.t
    for f in facs:
        common = np.intersect1d(common, f.t)  # type: ignore[union-attr]
    if common.size < bwin + 2 * look:
        return []
    cols = [b.c[np.searchsorted(b.t, common)]]
    cols += [f.c[np.searchsorted(f.t, common)] for f in facs]  # type: ignore[union-attr]
    M = np.column_stack(cols)
    # Rows where every close is a number (the family's dropna); a non-positive close stays in the
    # frame and its log return is dropped by `ok` below, exactly as the family does.
    keep = np.all(np.isfinite(M), axis=1)
    common, M = common[keep], M[keep]
    with np.errstate(all="ignore"):
        R = np.diff(np.log(M), axis=0)
    ok = np.all(np.isfinite(R), axis=1)
    rt = common[1:][ok]
    R = R[ok]
    if rt.size < bwin + 2 * look:
        return []
    eps = _car_causal_residual(R[:, 0], R[:, 1:], bwin)
    cum = np.where(np.isfinite(eps), np.cumsum(np.where(np.isfinite(eps), eps, 0.0)), np.nan)
    mu, sd = _car_roll(cum, look)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = (cum - mu) / sd
    a = atr(b, int(p["atr_n"]))
    loc = np.searchsorted(b.t, rt)          # every residual bar is a target bar
    vol = _car_vol_mask(b, CAR_VOL_REGIMES[regime]) if regime in CAR_VOL_REGIMES else None
    win = p.get("_session")
    ez, sa, rr, ttl = (float(p["entry_z"]), float(p["stop_atr"]), float(p["rr"]),
                       int(p["ttl_bars"]))
    out: list[Order] = []
    for i in range(bwin + look, rt.size - 1):
        zi = z[i]
        if not np.isfinite(zi) or abs(zi) < ez:
            continue
        j = int(loc[i])
        ai = float(a[j])
        if not np.isfinite(ai) or ai <= 0:
            continue
        if win is not None and not (win[0] <= int(b.hour[j]) < win[1]):
            continue                           # the session is judged at the SIGNAL bar
        if vol is not None and not bool(vol[j]):
            continue
        side = (-1 if zi > 0 else 1) if mode == "revert" else (1 if zi > 0 else -1)
        # The certified family prices stop and target off the joined frame's close at the SAME
        # position index as the residual row, which is at least one joined row before the signal
        # (the residual series starts after the first return): reference=prev_row, the default,
        # reproduces it. signal_close is the corrected variant, certified as its own spec.
        px = float(M[i, 0]) if ref == "prev_row" else float(b.c[j])
        at = j + 1 if timing == "delayed" else j
        if at >= len(b):
            continue
        out.append(Order(int(b.t[at]), side, px - side * sa * ai, px + side * sa * ai * rr, ttl))
    return out


SPEC_BOOK["cross_asset_residual"] = RuleSpec(
    "cross_asset_residual",
    "Join the target's closes with every named factor's closes (same chart) on the timestamps all "
    "of them carry; every factor is required. Log returns; eps[t] = r[t] - [1, f[t]] . beta[t], "
    "beta[t] least squares with a constant over the previous beta_win rows only (beta_win "
    "defaults to lookback). cum = running sum of eps (undefined where eps is); z = (cum - its "
    "strict lookback mean) / its strict lookback sample std. Stand aside under beta_win + 2 x "
    "lookback joined rows. From row beta_win + lookback on, every bar with |z| >= entry_z and "
    "ATR(atr_n) > 0 is a signal at that bar's close: revert takes the side against z, continue "
    "with it; stop stop_atr x ATR, target rr x that, entry next open, time exit after "
    "ttl_bars. Stop and target are measured from the reference: prev_row (the default, what the "
    "certified family does) is the joined frame's close at the residual row's own position "
    "index, at least one joined row before the signal; signal_close is the signal bar's close; "
    "any other reference stands aside. A non-positive close stays in the joined frame and only "
    "its log return is dropped. "
    "The session (the cell's own session parameter; none: every hour) is judged at "
    "the signal bar. Modifiers: regime high_vol (high_volatility) / low_vol keeps a signal "
    "only where the 20-bar std of simple returns is above / below its "
    "own 100-bar median; entry_timing delayed moves the signal one target bar later with the "
    "same stop and target; execution_style market changes nothing; any other regime, timing or "
    "style stands aside.",
    {"factor_symbols": [], "lookback": 240, "beta_win": None, "entry_z": 2.0, "atr_n": 20,
     "stop_atr": 2.0, "rr": 1.5, "ttl_bars": 72, "side_mode": "revert", "regime": "",
     "entry_timing": "", "execution_style": "", "timeframe": "H1", "reference": "prev_row"},
    _build_cross_asset_residual, session_from_params=True, session_in_build=True)


#: Session selector -> [start, end) broker hours a non-breakout signal must fall in.
SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None, "continuous": None,
}
#: The session names the shared call and the miners' selector modifier know (`family_call`).
MODIFIER_SESSIONS: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "all": None,
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
    if spec.session_from_params:
        raw = dict(params or {})
        p["_session"] = SESSIONS.get(str(raw.get("session") or "").lower())
        # A `selector` PARAMETER is the miners' session modifier (`cell_modifiers`), applied on
        # top of the session: the hours both allow. One naming no session is refused there, so
        # it is refused here.
        if "selector" in raw and "selector" not in spec.defaults:
            mod = str(raw.get("selector") or "").strip().lower()
            if mod not in MODIFIER_SESSIONS:
                return None, (f"selector modifier {raw.get('selector')!r} names no session "
                              "window; the gauntlet refuses the cell, so no rule applies")
            p["_session"] = _window_and(p["_session"], MODIFIER_SESSIONS[mod])
    # The rules that need them read these; every other rule ignores them (hunt16 selectors name
    # a signal hour, a hunt16 condition a prior-session day label, carry a symbol's swap terms).
    p["_selector"], p["_symbol"], p["_condition"] = sel, str(symbol or ""), condition
    if family in HUNT16_FAMILIES and not spec.session_from_params:
        p["_session"] = None
    return p, "ok"


def _window_and(a: tuple[int, int] | None, b: tuple[int, int] | None
                ) -> tuple[int, int] | None:
    """The hours two [start, end) windows both allow; None is every hour, (0, 0) is none."""
    if a is None or b is None:
        return b if a is None else a
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return (lo, hi) if lo < hi else (0, 0)


#: Families whose selector names a hunt16 signal hour, not a session window to filter on.
HUNT16_FAMILIES = frozenset({"dav_range_filter_adx", "hunt16_cell"})


def rebuild(family: str, bars: Bars, p: Mapping[str, Any], cost_units: float
            ) -> tuple[list[Order], list[Fill]]:
    orders = SPEC_BOOK[family].build(bars, dict(p))
    side = int(p.get("_side") or 0)
    if side:
        orders = [o for o in orders if o.side == side]
    win = None if SPEC_BOOK[family].session_in_build else p.get("_session")
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
    # A VERDICT TAKEN WITH NO RULE IS NOT A VERDICT ON THE RULE (2026-11-04). "no written
    # specification" is recorded UNMEASURED under the certificate's own fingerprint, so when the
    # family's rule is written the fingerprint has not moved and the certificate would wait a
    # whole rotation of the canon (8 a pass, ~1,800 certificates) to be judged by it. It is
    # re-judged ahead of the rotation instead, once.
    no_rule = [i for i, r in enumerate(certs)
               if str(((book.get(certificate_id(r)) or {}).get("why") or [""])[0]).startswith(
                   "no written specification")
               and str((r.get("shadow_spec") or {}).get("family") or "") in SPEC_BOOK]
    # A VERDICT AGAINST A RULE THAT HAS SINCE CHANGED IS NOT A VERDICT ON THE RULE EITHER
    # (2026-11-04). The session fix moved what seven old rules mean (the stamped selector was read
    # as a session), so a hold those rules raised is suspect until the corrected rule re-judges
    # it. Every verdict that is not REPLICATED and was taken under another rule fingerprint (none
    # recorded counts as another) joins the backlog's extra slots once; a REPLICATED verdict is
    # re-judged by the rotation as usual, since it holds nothing back.
    for i, r in enumerate(certs):
        entry = book.get(certificate_id(r)) or {}
        fam = str((r.get("shadow_spec") or {}).get("family") or "")
        if (entry and entry.get("verdict") != REPLICATED and fam in SPEC_BOOK
                and entry.get("rule_fp") != rule_fingerprint(fam) and i not in set(no_rule)):
            no_rule.append(i)
    pending = old_metric + [i for i, r in enumerate(certs)
                            if i not in set(old_metric) and
                            (book.get(certificate_id(r)) or {}).get("fp")
                            != certificate_fp(r)]
    no_rule = [i for i in no_rule if i not in set(pending)]
    rotation = [(ci + k) % len(certs) for k in range(len(certs))] if certs else []
    wanted = set(priority_certificates)
    priority = [i for i, r in enumerate(certs) if certificate_id(r) in wanted]
    # THE NO-RULE BACKLOG IS NOT HELD TO THE ROTATION'S SHARE: a held certificate cannot start a
    # forward clock until it is judged, so up to PENDING_PER_PASS of those run each pass ON TOP of
    # the lane's share, inside the same budget. The extra slots are theirs alone (audit should-fix
    # of c59ce8879): the lane's share is taken first in the usual order, then the backlog's own
    # extra, so moved fingerprints queued ahead can never absorb them.
    head = list(dict.fromkeys(priority + pending + no_rule))[:per_lane]
    extra = [i for i in no_rule if i not in set(head)][:PENDING_PER_PASS]
    first = list(dict.fromkeys(head + extra + priority + pending + no_rule))
    order = first + [i for i in rotation if i not in set(first)]
    lane_n = per_lane + len(extra)
    for n, idx in enumerate(order[:lane_n]):
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
                                               "rule_fp": rule_fingerprint(str(r.get("family") or "")),
                                               "sharpe_metric_version": SHARPE_METRIC_VERSION,
                                               "why": list(r.get("why") or [])[:4],
                                               "key": r.get("key"), "at": _now()}
        _write_atomic(verdicts_path, {"at": _now(), "rule": RULE, "certificates": book})
    doc["verdict_book"] = {"path": str(verdicts_path.name), "n": len(book),
                           "judged_first_this_pass": min(len(first), lane_n),
                           "pending": len(pending), "no_rule_backlog": len(no_rule)}
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
