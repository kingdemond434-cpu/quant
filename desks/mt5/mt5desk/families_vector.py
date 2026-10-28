"""Fast signal emission for the families that cost the judge the most CPU (2026-10-28).

SPEED ONLY, AND PROVABLY SO. Each function here replaces the per-row Python loop of one family
with a vectorised CANDIDATE SELECTION followed by the family's own scalar emission code, run only
on the bars that can emit. The candidate mask is built from exactly the comparisons the original
loop uses to `continue`, negated the same way (so a NaN takes the same branch), and every value
that reaches a `Signal` is computed by the same scalar expression on the same scalar types as the
original (`np.float64` from the same arrays, Python `float` where the original called `float`).
So the Signal lists are identical: same signals, same order, every field bit-identical, every
Timestamp the same object value with the same tz. `tests/test_families_vector_identity.py` pins
it on real parquets, old against new, field by field and type by type.

THE OLD LOOPS ARE KEPT, VERBATIM, IN THE FAMILY FUNCTIONS, behind `enabled()`:

    MT5_VECTOR_FAMILIES=0     every family runs its original per-row loop (the revert switch)
    anything else / unset     the fast path below

A fast function that meets ANY input it was not written for (a parameter of an unexpected type,
an index that is not the tz-aware UTC nanosecond clock `_h1` promises, a missing column) returns
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

import logging
import os
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

ENV = "MT5_VECTOR_FAMILIES"

#: Scalar parameter types the fast paths accept as-is. Anything else (a string, a list, None,
#: numpy scalars of exotic kinds) goes to the original loop, which decides what it means.
_NUM = (int, float, np.integer, np.floating)


def enabled() -> bool:
    """True unless `MT5_VECTOR_FAMILIES` is set to an off spelling. Read per call, so a test or
    an operator can flip it without restarting the process."""
    return os.environ.get(ENV, "1").strip().lower() not in ("0", "false", "off", "no")


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
            "fallbacks": fallback_counts()}


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
