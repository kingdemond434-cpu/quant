"""Fast signal emission for the families that cost the judge the most CPU (2026-10-28).

SPEED ONLY, AND PROVABLY SO. Each function here replaces the per-row Python loop of one family
with a vectorised CANDIDATE SELECTION followed by the family's own scalar emission code, run only
on the bars that can emit. The candidate mask is built from exactly the comparisons the original
loop uses to `continue`, negated the same way (so a NaN takes the same branch), and every value
that reaches a `Signal` is computed by the same scalar expression on the same scalar types as the
original (`np.float64` from the same arrays, Python `float` where the original called `float`).
So the Signal lists are identical: same signals, same order, every field bit-identical, every
Timestamp the same object value with the same tz. `tests/test_families_vector_identity.py`
(wave 1) and `tests/test_families_vector_identity_wave2.py` (wave 2) pin it on real parquets, old
against new, field by field and type by type; `scripts/check_vector_families.py` re-runs it on
whichever box it is on.

Wave 1: formula, session_range_breakout, failed_breakout, ict_fvg, multi_speed_trend, `_atr`.
Wave 2: level_breakout, engulfing_reversal, momentum_volgate, adx_channel_hybrid,
mean_reversion_rsi, mean_reversion_bollinger, trend_ma_cross, pullback_entry, range_reversion,
vol_transition, vol_mean_reversion, spread_state, htf_anchor_trend, and regime_transition's
emission after its (already memoised) hazard path.

THE OLD LOOPS ARE KEPT, VERBATIM, IN THE FAMILY FUNCTIONS, behind `enabled()`:

    MT5_VECTOR_FAMILIES=0     every family runs its original per-row loop (the revert switch)
    anything else / unset     the fast path below -- unless the box has measured a mismatch

FAIL CLOSED (v1.4, audit should-fix of 2026-10-28). The daily drift monitor
(`daily_cycle:vector_families_check`) re-proves identity on the box's own pandas/numpy. On a
MISMATCH it writes `data/VECTOR_FAMILIES_MISMATCH.json` with the evidence, and while that marker
exists `enabled()` is False in every process that reads it (the judge's workers and the live
gateway alike, within `MARKER_TTL_S`), so the original loops answer without anyone setting the
switch. A later IDENTICAL check removes it; an UNMEASURED one leaves it exactly as it was.

A fast function that meets ANY input it was not written for (a parameter of an unexpected type,
an index that is not the tz-aware UTC nanosecond clock `_h1` promises or holds NaT, a missing,
duplicated, nullable, extension or object column) returns
`None`, and the caller then runs its original loop. So an input that made the old code raise still
raises the old exception from the old code, and no input can take a different branch here than it
would have there. Nothing is fitted, gated, counted or charged in this module.

THIS FILE IS PART OF THE SERIES-CACHE REPLAY IDENTITY (`external_gauntlet._replay_code_identity`
hashes `mt5desk/famil*.py`), deliberately: an edit to the fast path re-keys the cache exactly as an
edit to a family does. Landing it therefore re-keys the cache once.

Measured cost per built cell, family code only, before -> after: see
`reports/judge/VECTOR_FAMILIES_2026-10-28.md` in the project files.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

ENV = "MT5_VECTOR_FAMILIES"

#: Scalar parameter types the fast paths accept as-is. Anything else (a string, a list, None,
#: numpy scalars of exotic kinds) goes to the original loop, which decides what it means.
_NUM = (int, float, np.integer, np.floating)


#: Spellings of OFF, compared case-insensitively after stripping. Any number equal to zero
#: ("0", "00", "0.0", "-0") is off too, so an operator's "0.0" never silently reads as on.
OFF_WORDS = frozenset({"0", "false", "off", "no", "disabled"})


def is_off(value: str | None) -> bool:
    """True when `value` is one of OFF_WORDS or a number equal to zero. Unset is ON."""
    if value is None:
        return False
    v = value.strip().lower()
    if v in OFF_WORDS:
        return True
    try:
        return float(v) == 0.0
    except ValueError:
        return False


def env_enabled() -> bool:
    """The operator's switch alone: True unless `MT5_VECTOR_FAMILIES` is an off spelling."""
    return not is_off(os.environ.get(ENV))


#: The box's own MISMATCH verdict, written by the daily drift monitor and read here. Box state:
#: under `desks/mt5/data/` (a `libs.ops.release.STATE_PREFIXES` path, so adoption keeps the box's
#: copy) and gitignored, so no sync publishes it and no checkout carries one box's verdict to
#: another machine.
MARKER = Path(__file__).resolve().parents[1] / "data" / "VECTOR_FAMILIES_MISMATCH.json"
#: How long one process trusts its last look at the marker. `enabled()` runs once per family
#: call, so it must not stat the disk every time; ten seconds is nothing against a daily check.
MARKER_TTL_S = 10.0
_MARKER_SEEN: list[float | bool] = [float("-inf"), False]   # [checked_at (monotonic), present]

#: Set only inside `scripts/check_vector_families.py`, which must reach the fast path to prove
#: it -- otherwise a marker could never be cleared, because the check would compare the original
#: loop with itself. No other caller sets it, and it is never read from the environment.
_PROVING = False


def mismatch_marked() -> bool:
    """True while the marker exists, as seen within the last `MARKER_TTL_S` seconds."""
    now = time.monotonic()
    if now - float(_MARKER_SEEN[0]) >= MARKER_TTL_S:
        _MARKER_SEEN[0], _MARKER_SEEN[1] = now, MARKER.exists()
    return bool(_MARKER_SEEN[1])


def _forget_marker() -> None:
    _MARKER_SEEN[0], _MARKER_SEEN[1] = float("-inf"), False


def write_mismatch_marker(evidence: dict[str, Any]) -> Path:
    """Fail closed: record a measured MISMATCH so every process takes the original loops."""
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    tmp = MARKER.with_suffix(MARKER.suffix + ".tmp")
    tmp.write_text(json.dumps(evidence, indent=1, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, MARKER)
    _forget_marker()
    return MARKER


def clear_mismatch_marker() -> bool:
    """A measured IDENTICAL lifts the fail-closed state. True when a marker was removed."""
    try:
        MARKER.unlink()
        removed = True
    except FileNotFoundError:
        removed = False
    _forget_marker()
    return removed


def enabled() -> bool:
    """True unless the switch is off (`is_off`) or this box has measured a MISMATCH (`MARKER`).
    The switch is read per call, so a test or an operator can flip it without restarting the
    process; the marker within `MARKER_TTL_S`."""
    if not env_enabled():
        return False
    return _PROVING or not mismatch_marked()


def _num(*values: Any) -> bool:
    return all(isinstance(v, _NUM) for v in values)


def _utc_ns(index: Any) -> bool:
    """The clock `_h1` promises: a tz-aware UTC DatetimeIndex at nanoseconds, with no NaT.

    A NaT stamp survives `_h1` and the originals give it meaning of their own (`ts.hour` and
    `ts.date()` on NaT, a NaN day key in a groupby); the integer day numbers here would make it
    a fake first day instead (audit 2026-10-28, must-fix 1). Such a frame takes the original.
    """
    return (isinstance(index, pd.DatetimeIndex) and index.tz is not None
            and str(index.tz) == "UTC" and str(index.unit) == "ns" and not index.hasnans)


def _plain(values: Any) -> bool:
    """A numpy int or float Series/array: the only dtypes the fast paths are proved on.

    pandas' nullable and extension dtypes (`Float64`, `Int64`, `float64[pyarrow]`), object and
    bool columns behave differently under the originals' arithmetic and comparisons, and
    differently again between pandas versions -- the original raised `TypeError` on nullable
    EURUSD_H1 where a fast path returned 856 signals (audit 2026-10-28, must-fix 2). They all
    take the original loop, which decides what they mean.
    """
    dtype = getattr(values, "dtype", None)
    return isinstance(dtype, np.dtype) and dtype.kind in "fiu"


def _plain_frame(frame: Any, columns: tuple[str, ...], *optional: str) -> bool:
    """Unique column labels, every named column present as a plain numpy int/float Series, and
    each optional column (when present) the same. A duplicated label makes `frame[col]` a
    DataFrame, which the originals handle (or raise on) in their own way."""
    if not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique:
        return False
    for col in columns:
        if col not in frame.columns or not _plain(frame[col]):
            return False
    return all(col not in frame.columns or _plain(frame[col]) for col in optional)


_OHLC = ("open", "high", "low", "close")

#: Fast-path exceptions, per family, for the life of the process. A fast path that raises is
#: never the answer: the caller runs the original loop, so the signals are the original's either
#: way. But a fast path that raises on real inputs is a path that is not doing its job, so it is
#: counted here and logged ONCE per family per process (audit 2026-10-28, should-fix 1).
_FALLBACKS: dict[str, int] = {}
_LOG = logging.getLogger("mt5desk.families_vector")


def fell_back(family: str, exc: BaseException) -> None:
    """Record that `family`'s fast path raised and the original loop is answering instead."""
    seen = _FALLBACKS.get(family, 0)
    _FALLBACKS[family] = seen + 1
    if seen == 0:
        _LOG.warning("families_vector: %s fast path raised %s (%s); the original loop answered. "
                     "Counted per process, logged once per family.", family,
                     type(exc).__name__, str(exc)[:200])


def fallback_counts() -> dict[str, int]:
    return dict(_FALLBACKS)


def mode() -> dict[str, Any]:
    """What this process is running, for an attestation or report: the switch as read now, its
    raw value, and the fast-path exceptions counted so far. The replay cache key is sealed
    (`external_gauntlet._replay_code_identity`) and does not carry this; whoever attests a run
    records it from here."""
    return {"env": ENV, "raw": os.environ.get(ENV), "enabled": enabled(),
            "env_enabled": env_enabled(), "mismatch_marker": MARKER.exists(),
            "marker_path": str(MARKER), "fallbacks": fallback_counts()}


def _hours(index: pd.DatetimeIndex) -> np.ndarray:
    """`ts.hour` for every stamp, as int64. Same numbers as `index.hour` on a UTC index."""
    return np.asarray(index.hour, dtype=np.int64)


#: Nanoseconds in a day. On a UTC nanosecond index, `stamp // NS_DAY` numbers the calendar days
#: exactly as `index.date` names them (floor division, so it holds before 1970 too), in the same
#: order, which is all a `groupby("date")` uses its keys for.
NS_DAY = 86_400_000_000_000


def _dayno(index: pd.DatetimeIndex) -> np.ndarray:
    return index.asi8 // NS_DAY


def _day_frame(h1: pd.DataFrame, rows: np.ndarray | None, dayno: np.ndarray) -> pd.DataFrame:
    """`h1[rows].groupby("date").agg(hi=("high", "max"), lo=("low", "min"))`, keyed by day number.

    The same rows fall in the same groups in the same (sorted) order, and a group max/min is the
    same comparison over the same values, so `hi`/`lo` are the original's values exactly; only
    the labels are integers instead of `datetime.date`, and callers use positions, not labels.
    """
    cols = h1[["high", "low"]]
    if rows is not None:
        cols = cols.loc[rows]
        dayno = dayno[rows]
    return cols.groupby(dayno).agg(hi=("high", "max"), lo=("low", "min"))


def _positions(keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Position of each value in the sorted unique `keys`, or -1 where it is absent."""
    if keys.size == 0:
        return np.full(values.shape, -1, dtype=np.intp)
    pos = np.searchsorted(keys, values)
    pos[pos >= keys.size] = 0
    pos[keys[pos] != values] = -1
    return pos


def _signals(index: pd.DatetimeIndex, pending: list[tuple[int, dict]]) -> list[Signal]:
    """Signals from (bar position, fields) rows, in order, with every stamp boxed in one pass.

    Iterating a DatetimeIndex yields the same Timestamps (value, unit, tz) as `index[i]` and as
    the `list(h1.index)[i]` the original loops read, at a fraction of the per-item cost.
    """
    if not pending:
        return []
    times = list(index[np.asarray([p for p, _ in pending], dtype=np.intp)])
    return [Signal(time=ts, **fields) for ts, (_, fields) in zip(times, pending, strict=False)]


# ------------------------------------------------------------------------------------------------
# _atr (shared by most families)
# ------------------------------------------------------------------------------------------------

def true_range(df: pd.DataFrame) -> pd.Series | None:
    """The true-range Series `families._atr` builds with a three-column concat and a row max.

    Original: `pd.concat([(h - l), (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)` with
    `c = close.shift(1)`. The row max skips NaN and is NaN only where all three are NaN; that is
    `np.fmax` applied twice, element for element, and a max of the same IEEE values is exact.
    The differences and absolute values are the same numpy operations pandas performs. Same
    index, same (absent) name, float64. Only float64 columns on a unique index take this path.
    """
    if not isinstance(df, pd.DataFrame) or not df.columns.is_unique:
        return None                      # a duplicated label: the original raises its own error
    try:
        h_s, l_s, c_s = df["high"], df["low"], df["close"]
    except KeyError:
        return None
    if not (isinstance(h_s.dtype, np.dtype) and isinstance(l_s.dtype, np.dtype)
            and isinstance(c_s.dtype, np.dtype)):
        return None
    if not (h_s.dtype == np.float64 and l_s.dtype == np.float64 and c_s.dtype == np.float64):
        return None
    if not df.index.is_unique or len(df) == 0:
        return None
    h = h_s.to_numpy()
    lo = l_s.to_numpy()
    c = np.empty_like(h)
    c[0] = np.nan
    c[1:] = c_s.to_numpy()[:-1]
    with np.errstate(invalid="ignore"):
        tr = np.fmax(np.fmax(h - lo, np.abs(h - c)), np.abs(lo - c))
    return pd.Series(tr, index=df.index)


# ------------------------------------------------------------------------------------------------
# formula
# ------------------------------------------------------------------------------------------------

def formula_emit(*, z: np.ndarray, atr: np.ndarray, close: np.ndarray, idx: pd.DatetimeIndex,
                 norm: Any, entry_z: Any, hold_bars: Any, flip: int, side_mode: str,
                 stop_atr: Any, rr: Any) -> list[Signal] | None:
    """The emission loop of `family_formula`, over the bars that can pass its filters only.

    Original: for i in range(int(norm), len(idx) - 1): skip while `i - last < hold_bars`; skip
    unless z and ATR are finite, |z| >= entry_z and ATR > 0; skip a zero side. A bar that fails
    the filters never moves `last`, so visiting only the bars that pass them, in order, visits
    exactly the bars at which the original could emit and with the same `last` at each.
    """
    if not _num(norm, entry_z, hold_bars, stop_atr, rr):
        return None
    if not (isinstance(z, np.ndarray) and isinstance(atr, np.ndarray)
            and isinstance(close, np.ndarray)):
        return None
    if not (_plain(z) and _plain(atr) and _plain(close)):
        return None
    lo = int(norm)
    hi = len(idx) - 1
    hb = int(hold_bars)
    ez = float(entry_z)
    if lo < 0 or hi <= lo:
        return None                      # negative or empty ranges: leave them to the original
    zz = z[lo:hi]
    aa = atr[lo:hi]
    with np.errstate(invalid="ignore"):
        # `zz != 0` is the original's `side == 0` skip: sign(z) * flip is 0 only for z == 0.
        keep = (np.isfinite(zz) & ~(np.abs(zz) < ez) & np.isfinite(aa) & ~(aa <= 0)
                & (zz != 0))
    cand = (np.flatnonzero(keep) + lo).tolist()
    # Pass 1, integers only: the bars at which the original emits (every candidate passes the
    # filters, so only the hold-bars spacing decides, against the last bar that emitted).
    emitted: list[int] = []
    last = -10 ** 9
    for i in cand:
        if i - last < hb:
            continue
        emitted.append(i)
        last = i
    if not emitted:
        return []
    # Pass 2: box the stamps in one go (iterating a DatetimeIndex yields the same Timestamps as
    # `idx[i]`), then the original's scalar expressions per signal.
    times = list(idx[np.asarray(emitted, dtype=np.intp)])
    tag = f"formula:{side_mode}"
    ttl = int(hold_bars)
    signals: list[Signal] = []
    for i, ts in zip(emitted, times, strict=False):
        zi = z[i]
        a = atr[i]
        side = int(np.sign(zi)) * flip
        px = close[i]
        signals.append(Signal(time=ts, side=side, stop=px - side * stop_atr * a,
                              target=px + side * stop_atr * a * rr, ttl_bars=ttl,
                              tag=tag, trigger=None, wait_bars=1))
    return signals


# ------------------------------------------------------------------------------------------------
# session_range_breakout
# ------------------------------------------------------------------------------------------------

def session_range_breakout_emit(*, h1: pd.DataFrame, atr: pd.Series, range_start: Any,
                                range_end: Any, signal_at: Any, wait_bars: Any, ttl_bars: Any,
                                rr: Any, spread_gate: Any, trend_filter: Any, range_filter: Any,
                                vol_filter: Any, midpoint_filter: Any) -> list[Signal] | None:
    """`family_session_range_breakout` from `h1 = _h1(df)` and `atr = _atr(h1, atr_n)` on.

    The original's first loop test is `ts.hour != signal_hour`, so only those bars can emit
    (one in 24 on H1). Every later test runs here unchanged, in the original order, on numpy
    arrays of the same Series the original reads with `.iloc` / `.at` / `.get`. The per-day
    frames are the original's groupbys keyed by day number (`_day_frame`), and each bar's day is
    found by position (`_positions`), which is the original's `key in index` / `.at[key]` /
    `.get(key)` on a unique sorted index.

    The three rolling series the
    original always computes are built here only when a branch reads them (`spread_med` under
    `spread_gate`, `atr_med` under a vol filter, `ema20` under `trend_filter="aligned"`): a value
    nobody reads cannot change a signal, and the rolling medians are most of what is left.
    """
    index = h1.index
    if not _utc_ns(index) or not _num(range_start) or isinstance(range_start, bool):
        return None
    if range_end is not None and (not _num(range_end) or isinstance(range_end, bool)):
        return None
    if signal_at is not None and (not _num(signal_at) or isinstance(signal_at, bool)):
        return None
    if not _plain_frame(h1, _OHLC, "spread") or not _plain(atr):
        return None                      # the original decides what these dtypes mean
    has_spread = "spread" in h1.columns
    if spread_gate and not has_spread:
        return None                      # the original raises here; let it
    n = len(h1)
    if n < 4:
        return None
    hours = _hours(index)
    dayno = _dayno(index)
    if range_end is None:
        in_window = hours < range_start
        signal_hour = signal_at if signal_at is not None else range_start
    else:
        in_window = (hours >= range_start) & (hours < range_end)
        signal_hour = signal_at if signal_at is not None else range_end
    range_by_day = _day_frame(h1, in_window, dayno)
    span_by_day = (range_by_day["hi"] - range_by_day["lo"]).rename("span")
    span_med = span_by_day.rolling(20, min_periods=10).median()
    cand = np.flatnonzero(hours[1:n - 2] == signal_hour) + 1
    if cand.size == 0:
        return []
    o = h1["open"].to_numpy()
    a_arr = atr.to_numpy()
    c_arr = h1["close"].to_numpy()
    rhi = range_by_day["hi"].to_numpy()
    rlo = range_by_day["lo"].to_numpy()
    smed = span_med.to_numpy()
    rpos = _positions(range_by_day.index.to_numpy(), dayno)
    sm_arr = sp_arr = am_arr = e_arr = None
    if spread_gate:
        sm_arr = h1["spread"].rolling(96).median().to_numpy()
        sp_arr = h1["spread"].to_numpy()
    if vol_filter in ("low", "high"):
        am_arr = atr.rolling(200, min_periods=60).median().to_numpy()
    if trend_filter == "aligned":
        e_arr = h1["close"].ewm(span=20, min_periods=10).mean().to_numpy()
    mid_pos = mid_arr = None
    if midpoint_filter == "prev_day":
        day = _day_frame(h1, None, dayno)
        mid_pos = _positions(day.index.to_numpy(), dayno)
        mid_arr = ((day["hi"] + day["lo"]) / 2.0).shift(1).to_numpy()
    pending: list[tuple[int, dict]] = []
    for i in cand.tolist():
        if np.isnan(o[i]):
            continue
        a = a_arr[i]
        if not (a > 0):
            continue
        if spread_gate:
            sm = sm_arr[i]
            if np.isnan(sm) or sp_arr[i] > sm:
                continue
        p = rpos[i]
        if p < 0:
            continue
        hi, lo = float(rhi[p]), float(rlo[p])
        span = hi - lo
        if span <= 0:
            continue
        sm2 = smed[p]
        if range_filter == "small" and not (np.isnan(sm2) or span < sm2):
            continue
        if range_filter == "large" and not (np.isnan(sm2) or span > sm2):
            continue
        if vol_filter == "low" and not (np.isnan(am_arr[i]) or a < am_arr[i]):
            continue
        if vol_filter == "high" and not (np.isnan(am_arr[i]) or a > am_arr[i]):
            continue
        slope = 0.0
        if trend_filter == "aligned" and i >= 5:
            slope = float(e_arr[i] - e_arr[i - 4])
        allow_long = allow_short = True
        if midpoint_filter == "prev_day":
            q = mid_pos[i]
            if q < 0:
                continue
            mid = mid_arr[q]
            if np.isnan(mid):
                continue
            px = float(c_arr[i])
            allow_long, allow_short = px > mid, px < mid
        dist = max(1.2 * a, span)
        if allow_long and (trend_filter != "aligned" or slope >= 0):
            pending.append((i, {"side": 1, "stop": hi - dist, "target": hi + dist * rr,
                                "ttl_bars": ttl_bars, "tag": "session_range_breakout",
                                "trigger": hi, "wait_bars": wait_bars}))
        if allow_short and (trend_filter != "aligned" or slope < 0):
            pending.append((i, {"side": -1, "stop": lo + dist, "target": lo - dist * rr,
                                "ttl_bars": ttl_bars, "tag": "session_range_breakout",
                                "trigger": lo, "wait_bars": wait_bars}))
    return _signals(index, pending)


# ------------------------------------------------------------------------------------------------
# failed_breakout
# ------------------------------------------------------------------------------------------------

def failed_breakout_emit(*, h1: pd.DataFrame, atr: pd.Series, signal_hours: Any,
                         spread_gate: Any, min_pierce_atr: Any, ttl_bars: Any, rr: Any,
                         level: Any) -> list[Signal] | None:
    """`family_failed_breakout` from `h1 = _h1(df)` and `atr = _atr(h1, atr_n)` on, over its
    signal-hour bars only.

    The per-day frame is the original's groupby keyed by day number (`_day_frame`), with the
    same `shift(1)`. The rolling spread median, which the original always computes, is computed
    only under `spread_gate`, the one branch that reads it.
    """
    index = h1.index
    if not _utc_ns(index) or not isinstance(signal_hours, (tuple, list)):
        return None
    if not _plain_frame(h1, _OHLC, "spread") or not _plain(atr):
        return None
    has_spread = "spread" in h1.columns
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    c = h1["close"].to_numpy()
    hh = h1["high"].to_numpy()
    ll = h1["low"].to_numpy()
    sp = sm = None
    if spread_gate and has_spread:
        sp = h1["spread"].to_numpy()
        sm = h1["spread"].rolling(96).median().to_numpy()
    if not all(isinstance(x, _NUM) and not isinstance(x, bool) for x in signal_hours):
        return None
    n = len(h1)
    if n < 5:
        return None
    dayno = _dayno(index)
    d = _day_frame(h1, None, dayno)
    hours = _hours(index)
    want = np.zeros(n, dtype=bool)
    for hv in signal_hours:
        want |= hours == hv
    want[:2] = False
    want[n - 2:] = False
    cand = np.flatnonzero(want)
    if cand.size == 0:
        return []
    dpos = _positions(d.index.to_numpy(), dayno)
    phi_arr = d["hi"].shift(1).to_numpy()
    plo_arr = d["lo"].shift(1).to_numpy()
    pending: list[tuple[int, dict]] = []
    for i in cand.tolist():
        p = dpos[i]
        if p < 0:
            continue
        phi, plo = float(phi_arr[p]), float(plo_arr[p])
        ai = a[i]
        if not (ai > 0) or np.isnan(ai):
            continue
        if spread_gate and (sm is None or np.isnan(sm[i]) or sp[i] > sm[i]):
            continue
        side = 0
        pierce = 0.0
        if hh[i] > phi and c[i] < phi and phi > 0:
            side = -1
            pierce = hh[i] - phi
        elif ll[i] < plo and c[i] > plo and plo > 0:
            side = 1
            pierce = plo - ll[i]
        if side == 0:
            continue
        if pierce < min_pierce_atr * ai:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": f"failed_breakout.{level}"}))
    return _signals(index, pending)


# ------------------------------------------------------------------------------------------------
# ict_fvg
# ------------------------------------------------------------------------------------------------

def ict_fvg_emit(*, h1: pd.DataFrame, a: np.ndarray, f: np.ndarray, s: np.ndarray,
                 o_arr: np.ndarray, h_arr: np.ndarray, l_arr: np.ndarray, c_arr: np.ndarray,
                 ema_slow: Any, atr_n: Any, ttl_bars: Any, rr: Any) -> list[Signal] | None:
    """The per-bar loop of `family_ict_fvg`, over the bars whose gap and trend agree.

    Every test of the original is a comparison of array elements at i and i-2, so the whole
    side decision is a vector expression; the scalar emission then runs on the hits in order.
    """
    index = h1.index
    if not _utc_ns(index) or not (isinstance(ema_slow, int) and isinstance(atr_n, int)):
        return None
    if isinstance(ema_slow, bool) or isinstance(atr_n, bool):
        return None
    if not _plain_frame(h1, _OHLC) or not all(_plain(x) for x in (a, f, s, o_arr, h_arr, l_arr,
                                                                    c_arr)):
        return None
    n = len(h1)
    start = max(ema_slow, atr_n) + 1
    stop_i = n - 2
    start = max(start, 2)                # the original's `if i < 2: continue`
    if stop_i <= start:
        return []
    sl = slice(start, stop_i)
    am = sl.start - 2
    with np.errstate(invalid="ignore"):
        ok = (a[sl] > 0) & ~np.isnan(f[sl]) & ~np.isnan(s[sl])
        bull = (h_arr[am:stop_i - 2] < l_arr[sl]) & (f[sl] > s[sl])
        bear = (l_arr[am:stop_i - 2] > h_arr[sl]) & (f[sl] < s[sl])
    cand = (np.flatnonzero(ok & (bull | bear)) + start).tolist()
    pending: list[tuple[int, dict]] = []
    for i in cand:
        ai = a[i]
        if not (ai > 0) or np.isnan(f[i]) or np.isnan(s[i]):
            continue
        side = 0
        if h_arr[i - 2] < l_arr[i] and f[i] > s[i]:
            side = 1
        elif l_arr[i - 2] > h_arr[i] and f[i] < s[i]:
            side = -1
        if side == 0:
            continue
        entry = o_arr[i + 1] if i + 1 < n else c_arr[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i, {"side": side, "stop": stop, "target": target,
                            "ttl_bars": ttl_bars, "tag": "ict_fvg"}))
    return _signals(index, pending)


# ------------------------------------------------------------------------------------------------
# multi_speed_trend
# ------------------------------------------------------------------------------------------------

def multi_speed_trend_emit(*, d: pd.DataFrame, close: pd.Series, daily: pd.Series,
                           agree: np.ndarray, fastest: np.ndarray, slowest: np.ndarray,
                           atr: pd.Series, speeds: tuple[int, ...], min_agreement: Any,
                           crisis_only: Any, hold_days: Any, stop_atr: Any, rr: Any,
                           bpd: int) -> list[Signal] | None:
    """The daily loop of `family_multi_speed_trend` without its per-signal O(bars) scans.

    The original finds each day's last bar through a dict built by iterating every stamp, then
    the entry bar as `d.index[d.index > ts_last][0]`, and reads ATR and close with one-label
    `reindex` calls. On a strictly increasing index those are: the last position of the day's
    run of stamps, the next position, and `.iloc` at it. A non-monotonic or duplicated index
    returns None and the original runs.
    """
    index = d.index
    if not _utc_ns(index) or not index.is_monotonic_increasing or not index.is_unique:
        return None
    if not (close.index is index or close.index.equals(index)):
        return None
    if not (atr.index.equals(index)):
        return None
    if not (_plain_frame(d, ("close",)) and _plain(close) and _plain(atr) and _plain(daily)):
        return None
    n = len(index)
    ns = index.asi8
    dayno = ns // 86_400_000_000_000
    # Last position of each calendar day's run; the days appear in increasing order, which is
    # also the (sorted) order of `daily`'s groupby index.
    ends = np.flatnonzero(np.diff(dayno) != 0)
    last_pos = np.append(ends, n - 1)
    if last_pos.size != daily.size:
        return None
    a_arr = atr.to_numpy()
    c_arr = close.to_numpy()
    tag = f"multi_speed_trend:{'crisis' if crisis_only else 'all'}"
    signals: list[Signal] = []
    last_entry_day = -10 ** 9
    for i in range(max(speeds), daily.size - 1):
        a = float(agree[i])
        if abs(a) < min_agreement:
            continue
        if crisis_only and not (fastest[i] != 0 and slowest[i] != 0 and fastest[i] != slowest[i]):
            continue
        if i - last_entry_day < hold_days:
            continue
        side = 1 if a > 0 else -1
        if crisis_only:
            side = int(fastest[i])
        p = int(last_pos[i]) + 1
        if p >= n:
            continue
        entry = index[p]
        at = float(a_arr[p])
        if not np.isfinite(at) or at <= 0:
            continue
        px = float(c_arr[p])
        signals.append(Signal(time=entry, side=side, stop=px - side * stop_atr * at,
                              target=px + side * stop_atr * at * rr,
                              ttl_bars=int(hold_days) * bpd,
                              tag=tag, trigger=None, wait_bars=1))
        last_entry_day = i
    return signals


# ================================================================================================
# WAVE 2 (2026-10-28): the per-bar array loops of the breakout / reversion families.
#
# THE ARGUMENT IS A SUPERSET, NOT AN EQUIVALENCE, which is what makes it cheap to trust. Each
# function below builds a vector mask that is a NECESSARY condition for its family to emit at a
# bar (any bar where the original could emit is in the mask; extra bars are harmless), then runs
# the original per-bar body -- copied, every test still in it -- on the masked bars only, in
# order. A bar outside the mask would have hit a `continue` in the original, so skipping it is
# exact; and every bar inside it takes exactly the original's branches. Loops that carry state
# (`last`, `last_side`, `last_exit`) update it only on bars that pass the masked tests, so the
# state seen at each visited bar is the original's too. NaN in a mask comparison is False, the
# same as in the scalar comparison it mirrors, and where a NaN could make the original pass a
# test the vector form would not (Python `max` over a window holding NaN), the mask admits the
# bar outright.
# ================================================================================================

def _lag(x: np.ndarray, k: int = 1) -> np.ndarray:
    """x shifted forward by k bars as float64 with NaN in front (x[i - k] at position i)."""
    out = np.full(x.shape, np.nan, dtype=np.float64)
    if k < x.size:
        out[k:] = x[:x.size - k]
    return out


def _span(start: Any, stop: int, lag: int) -> tuple[int, int] | None:
    """The original's `range(start, stop)` (raising as it would), or None when its first index
    reaches behind the array (negative indexing is the original's business, not ours)."""
    r = range(start, stop)
    if r.start < lag:
        return None
    return r.start, r.stop


def _visit(mask: np.ndarray, lo: int, hi: int) -> list[int]:
    if hi <= lo:
        return []
    return (np.flatnonzero(mask[lo:hi]) + lo).tolist()


def _floats(*arrays: Any) -> bool:
    return all(isinstance(x, np.ndarray) and x.dtype == np.float64 for x in arrays)


def _frame_ok(frame: Any) -> bool:
    """The wave-2 entry guard, the same classes as wave 1's (audit 2026-10-28): a UTC ns index
    with no NaT, unique column labels, and plain numpy int/float OHLC (and spread, if present).
    Anything else takes the original loop."""
    return (isinstance(frame, pd.DataFrame) and _utc_ns(frame.index)
            and _plain_frame(frame, _OHLC, "spread"))


def momentum_volgate_emit(*, h1: pd.DataFrame, a: np.ndarray, vm: np.ndarray, m: np.ndarray,
                          c: np.ndarray, o: np.ndarray, mom_n: Any, vol_gate_q: Any,
                          mom_thresh: Any, ttl_bars: Any, rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _num(vol_gate_q, mom_thresh) or not _floats(a, vm, m, c, o):
        return None
    sp = _span(mom_n + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    with np.errstate(invalid="ignore"):
        mask = (a > 0) & ~(np.abs(m) < mom_thresh)
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        if np.isnan(c[i]):
            continue
        ai = a[i]
        v = vm[i]
        if not (ai > 0) or np.isnan(v) or ai < vol_gate_q * v:
            continue
        mi = m[i]
        if np.isnan(mi) or abs(mi) < mom_thresh:
            continue
        if abs(mi) < 0.35 * (ai / c[i]):
            continue
        side = 1 if mi > 0 else -1
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": "momentum_volgate"}))
    return _signals(h1.index, pending)


def level_breakout_emit(*, h1: pd.DataFrame, atr: pd.Series, level: Any, signal_hour: Any,
                        wait_bars: Any, ttl_bars: Any, rr: Any, vol_filter: Any,
                        vol_gate_q: Any, range_filter: Any,
                        spread_gate: Any) -> list[Signal] | None:
    """`family_level_breakout` from `h1 = _h1(df)` and `atr` on, over its signal-hour bars.

    `pdh`: the per-day frame by day number (`_day_frame`). Any other level: the original's ISO
    week key and groupby, unchanged, looked up by position. `atr_med` and the spread median are
    computed only when the branch that reads them is on.
    """
    if not _frame_ok(h1):
        return None
    index = h1.index
    if not _utc_ns(index) or not _num(signal_hour) or isinstance(signal_hour, bool):
        return None
    if not _num(vol_gate_q):
        return None
    if not _plain(atr):
        return None
    has_spread = "spread" in h1.columns
    n = len(h1)
    if n < 4:
        return None
    if level == "pdh":
        dayno = _dayno(index)
        d = _day_frame(h1, None, dayno)
        keys = dayno
    else:
        iso = index.isocalendar()
        wkey = (iso.year.astype(int) * 100 + iso.week.astype(int)).to_numpy()
        d = h1[["high", "low"]].groupby(wkey).agg(hi=("high", "max"), lo=("low", "min"))
        keys = wkey
    phi_arr = d["hi"].shift(1).to_numpy()
    plo_arr = d["lo"].shift(1).to_numpy()
    span_med = (d["hi"] - d["lo"]).rolling(20, min_periods=10).median().to_numpy()
    dpos = _positions(d.index.to_numpy(), np.asarray(keys))
    hours = _hours(index)
    mask = hours == signal_hour
    if level == "week":
        mask &= np.asarray(index.dayofweek) == 0
    a = atr.to_numpy()
    o = h1["open"].to_numpy()
    am = sm = sp = None
    if vol_filter == "high":
        am = atr.rolling(200, min_periods=60).median().to_numpy()
    if spread_gate and has_spread:
        sp = h1["spread"].to_numpy()
        sm = h1["spread"].rolling(96).median().to_numpy()
    tag = f"level_breakout.{level}"
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, 1, n - 2):
        if np.isnan(o[i]):
            continue
        ai = a[i]
        if not (ai > 0):
            continue
        if vol_filter == "high":
            v = am[i]
            if np.isnan(v) or ai < vol_gate_q * v:
                continue
        if spread_gate and (sm is None or np.isnan(sm[i]) or sp[i] > sm[i]):
            continue
        p = dpos[i]
        if p < 0:
            continue
        hi, lo = float(phi_arr[p]), float(plo_arr[p])
        if not (hi > 0) or not (lo > 0) or hi <= lo:
            continue
        span = hi - lo
        if span <= 0:
            continue
        if range_filter == "small":
            sm2 = span_med[p]
            if np.isnan(sm2) or span >= sm2:
                continue
        dist = max(1.2 * ai, span)
        pending.append((i, {"side": 1, "stop": hi - dist, "target": hi + dist * rr,
                            "ttl_bars": ttl_bars, "tag": tag, "trigger": hi,
                            "wait_bars": wait_bars}))
        pending.append((i, {"side": -1, "stop": lo + dist, "target": lo - dist * rr,
                            "ttl_bars": ttl_bars, "tag": tag, "trigger": lo,
                            "wait_bars": wait_bars}))
    return _signals(index, pending)


def mean_reversion_rsi_emit(*, h1: pd.DataFrame, a: np.ndarray, r: np.ndarray, o: np.ndarray,
                            rsi_n: Any, atr_n: Any, oversold: Any, overbought: Any,
                            ttl_bars: Any, rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _num(oversold, overbought) or not _floats(a, r, o):
        return None
    sp = _span(max(rsi_n, atr_n) + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    rp = _lag(r)
    with np.errstate(invalid="ignore"):
        mask = ((rp < oversold) & (r >= oversold)) | ((rp > overbought) & (r <= overbought))
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0) or np.isnan(r[i]) or np.isnan(r[i - 1]):
            continue
        side = 0
        if r[i - 1] < oversold and r[i] >= oversold:
            side = 1
        elif r[i - 1] > overbought and r[i] <= overbought:
            side = -1
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i, {"side": side, "stop": stop, "target": target,
                            "ttl_bars": ttl_bars, "tag": "mean_reversion_rsi"}))
    return _signals(h1.index, pending)


def mean_reversion_bollinger_emit(*, h1: pd.DataFrame, a: np.ndarray, c: np.ndarray,
                                  o: np.ndarray, lo_arr: np.ndarray, hi_arr: np.ndarray,
                                  bb_n: Any, atr_n: Any, ttl_bars: Any,
                                  rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _floats(a, c, o, lo_arr, hi_arr):
        return None
    sp = _span(max(bb_n, atr_n) + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    cp = _lag(c)
    with np.errstate(invalid="ignore"):
        mask = ((cp < lo_arr) & (c >= lo_arr)) | ((cp > hi_arr) & (c <= hi_arr))
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0) or np.isnan(lo_arr[i]) or np.isnan(hi_arr[i]):
            continue
        if np.isnan(c[i - 1]):
            continue
        side = 0
        if c[i - 1] < lo_arr[i] and c[i] >= lo_arr[i]:
            side = 1
        elif c[i - 1] > hi_arr[i] and c[i] <= hi_arr[i]:
            side = -1
        if side == 0:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": "mean_reversion_bollinger"}))
    return _signals(h1.index, pending)


def trend_ma_cross_emit(*, h1: pd.DataFrame, a: np.ndarray, f: np.ndarray, s: np.ndarray,
                        o: np.ndarray, slow_ema: Any, atr_n: Any, ttl_bars: Any,
                        rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _floats(a, f, s, o):
        return None
    sp = _span(max(slow_ema, atr_n) + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    fp, spv = _lag(f), _lag(s)
    with np.errstate(invalid="ignore"):
        mask = ((fp < spv) & (f >= s)) | ((fp > spv) & (f <= s))
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0) or np.isnan(f[i]) or np.isnan(s[i]):
            continue
        if np.isnan(f[i - 1]) or np.isnan(s[i - 1]):
            continue
        side = 0
        if f[i - 1] < s[i - 1] and f[i] >= s[i]:
            side = 1
        elif f[i - 1] > s[i - 1] and f[i] <= s[i]:
            side = -1
        if side == 0:
            continue
        entry = o[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i, {"side": side, "stop": stop, "target": target,
                            "ttl_bars": ttl_bars, "tag": "trend_ma_cross"}))
    return _signals(h1.index, pending)


def pullback_entry_emit(*, h1: pd.DataFrame, a: np.ndarray, r: np.ndarray, e: np.ndarray,
                        c: np.ndarray, o: np.ndarray, trend_ema: Any, rsi_n: Any, atr_n: Any,
                        rsi_pullback: Any, rsi_bounce: Any, ttl_bars: Any,
                        rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _num(rsi_pullback, rsi_bounce) or not _floats(a, r, e, c, o):
        return None
    sp = _span(max(trend_ema, rsi_n, atr_n) + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    rp = _lag(r)
    with np.errstate(invalid="ignore"):
        mask = (((c > e) & (rp < rsi_pullback) & (r >= rsi_bounce))
                | ((c < e) & (rp > (100 - rsi_pullback)) & (r <= (100 - rsi_bounce))))
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0) or np.isnan(r[i]) or np.isnan(e[i]):
            continue
        if np.isnan(r[i - 1]) or np.isnan(c[i - 1]):
            continue
        side = 0
        if c[i] > e[i] and r[i - 1] < rsi_pullback and r[i] >= rsi_bounce:
            side = 1
        elif c[i] < e[i] and r[i - 1] > (100 - rsi_pullback) and r[i] <= (100 - rsi_bounce):
            side = -1
        if side == 0:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": "pullback_entry"}))
    return _signals(h1.index, pending)


def range_reversion_emit(*, h1: pd.DataFrame, a: np.ndarray, c: np.ndarray, o: np.ndarray,
                         range_n: Any, threshold_pct: Any, ttl_bars: Any,
                         rr: Any) -> list[Signal] | None:
    if not _frame_ok(h1):
        return None
    if not _num(threshold_pct) or not isinstance(range_n, int) or isinstance(range_n, bool):
        return None
    if not _floats(a, c, o) or range_n < 1:
        return None
    sp = _span(range_n + 1, len(h1) - 2, 1)
    if sp is None:
        return None
    cl = _lag(c, range_n)
    with np.errstate(invalid="ignore", divide="ignore"):
        mask = (a > 0) & ~(np.abs((c - cl) / cl) < threshold_pct)
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0) or np.isnan(c[i]) or np.isnan(c[i - range_n]):
            continue
        move = (c[i] - c[i - range_n]) / c[i - range_n]
        if abs(move) < threshold_pct:
            continue
        entry = o[i + 1]
        stop_dist = 1.2 * ai
        side = -1 if move > 0 else 1
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": "range_reversion"}))
    return _signals(h1.index, pending)


def engulfing_reversal_emit(*, h1: pd.DataFrame, a: np.ndarray, o_arr: np.ndarray,
                            h_arr: np.ndarray, l_arr: np.ndarray, c_arr: np.ndarray, n: Any,
                            ttl_bars: Any, rr: Any) -> list[Signal] | None:
    """Original: `prev_h = max(h_arr[i - n:i])` with Python's `max`. On a window holding NaN,
    Python's `max` is order-dependent, so such windows are admitted outright; on a NaN-free
    window it equals the numpy max of the same values."""
    if not _frame_ok(h1):
        return None
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return None
    if not _floats(a, o_arr, h_arr, l_arr, c_arr):
        return None
    N = len(h1)
    sp = _span(n + 1, N - 2, n)
    if sp is None:
        return None
    from numpy.lib.stride_tricks import sliding_window_view
    mask = np.zeros(N, dtype=bool)
    if n < N:
        hw = sliding_window_view(h_arr, n)[:N - n]      # row j = h[j : j + n] = window of i=j+n
        lw = sliding_window_view(l_arr, n)[:N - n]
        bad = np.isnan(hw).any(axis=1) | np.isnan(lw).any(axis=1)
        with np.errstate(invalid="ignore"):
            hit = ((h_arr[n:] > np.max(hw, axis=1)) & (l_arr[n:] < np.min(lw, axis=1))
                   & (c_arr[n:] != o_arr[n:]))
        mask[n:] = bad | hit
        mask &= a > 0
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        ai = a[i]
        if not (ai > 0):
            continue
        if np.isnan(c_arr[i]) or np.isnan(o_arr[i]):
            continue
        prev_h = max(h_arr[i - n:i])
        prev_l = min(l_arr[i - n:i])
        curr_h = h_arr[i]
        curr_l = l_arr[i]
        side = 0
        if curr_h > prev_h and curr_l < prev_l and c_arr[i] > o_arr[i]:
            side = 1
        elif curr_h > prev_h and curr_l < prev_l and c_arr[i] < o_arr[i]:
            side = -1
        if side == 0:
            continue
        entry = o_arr[i + 1] if i + 1 < N else c_arr[i]
        stop_dist = 1.2 * ai
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i, {"side": side, "stop": stop, "target": target,
                            "ttl_bars": ttl_bars, "tag": "engulfing_reversal"}))
    return _signals(h1.index, pending)


def adx_channel_hybrid_emit(*, h1: pd.DataFrame, c: np.ndarray, a: np.ndarray,
                            hi_a: np.ndarray, lo_a: np.ndarray, st: np.ndarray, ok: np.ndarray,
                            stop_atr: Any, ttl_bars: Any, rr: Any) -> list[Signal] | None:
    """Stateful (`last_side`), but the state moves only on bars at exactly one channel extreme
    with `ok` and ATR > 0, which is the mask; every other bar `continue`s before touching it."""
    if not _frame_ok(h1):
        return None
    if not _floats(c, a, hi_a, lo_a):
        return None
    o = h1["open"].to_numpy()
    N = len(h1)
    with np.errstate(invalid="ignore"):
        mask = ok & (a > 0) & ((c >= hi_a) | (c <= lo_a))
    pending: list[tuple[int, dict]] = []
    last_side = 0
    for i in _visit(mask, 0, N - 2):
        if not ok[i] or not (a[i] > 0):
            continue
        at_high = c[i] >= hi_a[i]
        at_low = c[i] <= lo_a[i]
        if not (at_high or at_low):
            continue
        if at_high and at_low:
            continue
        side = 1 if (at_high == bool(st[i])) else -1
        if side == last_side:
            continue
        last_side = side
        entry = o[i + 1]
        if not (entry > 0):
            continue
        stop_dist = stop_atr * a[i]
        stop = entry - side * stop_dist
        target = entry + side * stop_dist * rr
        pending.append((i + 1, {"side": side, "stop": stop, "target": target,
                                "ttl_bars": ttl_bars, "tag": "adx_channel_hybrid"}))
    return _signals(h1.index, pending)


def vol_transition_emit(*, d: pd.DataFrame, vf: np.ndarray, vs: np.ndarray, at: np.ndarray,
                        cl: np.ndarray, ret: np.ndarray, slow: Any, ratio_in: Any,
                        stop_atr: Any, rr: Any, ttl_bars: Any) -> list[Signal] | None:
    if not _frame_ok(d):
        return None
    if not _num(ratio_in) or not _floats(vf, vs, at, cl, ret):
        return None
    sp = _span(slow + 1, len(d) - 1, 1)
    if sp is None:
        return None
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = vf / vs
        mask = (_lag(ratio) < ratio_in) & (ratio >= ratio_in)
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        prev = float(vf[i - 1] / vs[i - 1]) if vs[i - 1] else np.nan
        now = float(vf[i] / vs[i]) if vs[i] else np.nan
        if not (np.isfinite(prev) and np.isfinite(now)):
            continue
        if not (prev < ratio_in <= now):
            continue
        a = float(at[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(cl[i])
        side = 1 if float(ret[i]) >= 0 else -1
        pending.append((i, {"side": side, "stop": px - side * stop_atr * a,
                            "target": px + side * stop_atr * a * rr, "ttl_bars": ttl_bars,
                            "tag": "vol_transition", "trigger": None, "wait_bars": 1}))
    return _signals(d.index, pending)


def vol_mean_reversion_emit(*, d: pd.DataFrame, z: np.ndarray, at: np.ndarray, cl: np.ndarray,
                            ret: np.ndarray, lookback: Any, z_in: Any, stop_atr: Any, rr: Any,
                            ttl_bars: Any) -> list[Signal] | None:
    if not _frame_ok(d):
        return None
    if not _num(z_in) or not _floats(z, at, cl, ret):
        return None
    sp = _span(lookback + 1, len(d) - 1, 0)
    if sp is None:
        return None
    with np.errstate(invalid="ignore"):
        mask = np.isfinite(z) & ~(z > z_in)
    pending: list[tuple[int, dict]] = []
    for i in _visit(mask, *sp):
        zi = float(z[i]) if np.isfinite(z[i]) else np.nan
        if not np.isfinite(zi) or zi > z_in:
            continue
        a = float(at[i])
        if not np.isfinite(a) or a <= 0:
            continue
        px = float(cl[i])
        side = 1 if float(ret[i]) >= 0 else -1
        pending.append((i, {"side": side, "stop": px - side * stop_atr * a,
                            "target": px + side * stop_atr * a * rr, "ttl_bars": ttl_bars,
                            "tag": "vol_mean_reversion", "trigger": None, "wait_bars": 1}))
    return _signals(d.index, pending)


def spread_state_emit(*, frame: pd.DataFrame, idx: pd.DatetimeIndex, at: np.ndarray,
                      ret: np.ndarray,
                      sp_rank: np.ndarray, act_rank: np.ndarray, close: np.ndarray,
                      has_vol: bool, norm_window: Any, hold_bars: Any, min_move_atr: Any,
                      mode: str, spike_pct: Any, calm_pct: Any, active_pct: Any,
                      stop_atr: Any, rr: Any) -> list[Signal] | None:
    """Stateful (`last`, hold spacing) like `formula`: the mask is the stateless filters, which a
    bar must pass before it can move `last`, so the hold test sees the original's `last`."""
    if not _frame_ok(frame):
        return None
    if not _num(min_move_atr, spike_pct, calm_pct, active_pct, hold_bars):
        return None
    if not _floats(at, ret, sp_rank, close):
        return None
    sp = _span(norm_window, len(idx) - 1, 0)
    if sp is None:
        return None
    with np.errstate(invalid="ignore"):
        mask = (np.isfinite(at) & ~(at <= 0) & np.isfinite(ret)
                & ~(np.abs(ret) < min_move_atr * at) & np.isfinite(sp_rank))
        if mode == "spike_reversion":
            mask &= ~(sp_rank < spike_pct)
        else:
            mask &= ~(sp_rank > calm_pct)
    pending: list[tuple[int, dict]] = []
    last = -10 ** 9
    tag = f"spread_state:{mode}"
    for i in _visit(mask, *sp):
        if i - last < hold_bars:
            continue
        a = float(at[i])
        if not np.isfinite(a) or a <= 0:
            continue
        mv = float(ret[i])
        if not np.isfinite(mv) or abs(mv) < min_move_atr * a:
            continue
        sr = float(sp_rank[i])
        if not np.isfinite(sr):
            continue
        if mode == "spike_reversion":
            if sr < spike_pct:
                continue
            side = -1 if mv > 0 else 1
        else:
            ar = float(act_rank[i]) if has_vol else np.nan
            if sr > calm_pct or (has_vol and (not np.isfinite(ar) or ar < active_pct)):
                continue
            side = 1 if mv > 0 else -1
        px = float(close[i])
        pending.append((i, {"side": side, "stop": px - side * stop_atr * a,
                            "target": px + side * stop_atr * a * rr, "ttl_bars": int(hold_bars),
                            "tag": tag, "trigger": None, "wait_bars": 1}))
        last = i
    return _signals(idx, pending)


def htf_anchor_trend_emit(*, frame: pd.DataFrame, idx: pd.DatetimeIndex, diff: np.ndarray,
                          anch: np.ndarray,
                          atr: np.ndarray, px: np.ndarray, stop_atr: Any, rr: Any,
                          max_hold_bars: Any, anchor_mult: Any) -> list[Signal] | None:
    """Stateful (`last_exit`), which moves only on an emitting cross; the mask is the cross."""
    if not _frame_ok(frame):
        return None
    if not _floats(diff, anch, atr, px):
        return None
    n = len(idx)
    dp = _lag(diff)
    with np.errstate(invalid="ignore"):
        mask = ((dp <= 0.0) & (diff > 0.0)) | ((dp >= 0.0) & (diff < 0.0))
    pending: list[tuple[int, dict]] = []
    last_exit = -1
    tag = f"htf_anchor_trend:x{anchor_mult}"
    for i in _visit(mask, 1, n - 1):
        prev, cur = diff[i - 1], diff[i]
        if not (np.isfinite(prev) and np.isfinite(cur)):
            continue
        if prev <= 0.0 < cur:
            side = 1
        elif prev >= 0.0 > cur:
            side = -1
        else:
            continue
        if anch[i] * side <= 0.0:
            continue
        if i <= last_exit:
            continue
        a = float(atr[i])
        if not np.isfinite(a) or a <= 0:
            continue
        entry = float(px[i])
        pending.append((i, {"side": side, "stop": entry - side * stop_atr * a,
                            "target": entry + side * stop_atr * a * rr,
                            "ttl_bars": int(max_hold_bars), "tag": tag, "trigger": None,
                            "wait_bars": 1}))
        last_exit = i + int(max_hold_bars)
    return _signals(idx, pending)


# ------------------------------------------------------------------------------------------------
# regime_transition: the emission after the (memoised) hazard path
# ------------------------------------------------------------------------------------------------

def regime_transition_emit(*, d: pd.DataFrame, p_leave: pd.Series, age: pd.Series,
                           move: pd.Series, atr: pd.Series, entry_p_leave: Any, min_age: Any,
                           side_mode: Any, stop_atr: Any, rr: Any, ttl_bars: Any,
                           ) -> list[Signal] | None:
    """`family_regime_transition`'s per-day loop over a hazard path it was handed.

    The original builds {date: last bar of that date} by boxing every bar's Timestamp, then per
    qualifying day scans the whole index for the first bar after that day's last one and
    `reindex`es ATR and close at it. On a strictly increasing, unique index the first bar after
    position p is position p + 1 and `reindex([entry])` is the value at that position, so this
    reads them by position; the per-day tests and every float expression are the original's, in
    its order. Any other index shape returns None (the original runs).
    """
    if not _frame_ok(d):
        return None
    if not all(_plain(x) for x in (p_leave, age, move, atr)):
        return None
    idx = d.index
    if not (isinstance(idx, pd.DatetimeIndex) and idx.is_monotonic_increasing and idx.is_unique):
        return None
    if not (p_leave.index.equals(age.index) and p_leave.index.equals(move.index)
            and p_leave.index.is_unique and atr.index.equals(idx)):
        return None
    n = len(idx)
    last = dict(zip(idx.date, range(n), strict=True))
    a_arr = atr.to_numpy()
    c_arr = d["close"].to_numpy()
    pl_v, age_v, mv_v = p_leave.to_numpy(), age.to_numpy(), move.to_numpy()
    pending: list[tuple[int, dict]] = []
    for k, day in enumerate(p_leave.index):
        pl = pl_v[k]
        if not np.isfinite(pl) or pl < entry_p_leave:
            continue
        a_days = age_v[k]
        if not np.isfinite(a_days) or a_days < min_age:
            continue
        mv = mv_v[k]
        if not np.isfinite(mv) or mv == 0.0:
            continue
        pos = last.get(day)
        if pos is None:
            continue
        j = pos + 1
        if j >= n:
            continue
        a = float(a_arr[j])
        if not np.isfinite(a) or a <= 0:
            continue
        trend = 1 if mv > 0 else -1
        side = -trend if side_mode == "exhaustion" else trend
        px = float(c_arr[j])
        pending.append((j, {"side": side, "stop": px - side * stop_atr * a,
                            "target": px + side * stop_atr * a * rr, "ttl_bars": ttl_bars,
                            "tag": f"regime_transition:{side_mode}", "trigger": None,
                            "wait_bars": 1}))
    return _signals(idx, pending)
