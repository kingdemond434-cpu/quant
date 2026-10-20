"""Spread-recovery half-life: how fast the bid-ask spread decays back to normal after a shock.

THREE SCHEDULED SHOCKS, each located on the bar clock by its own rule:

    sunday_open   the first bar after the weekend gap (a gap of more than 30 hours)
    rollover      broker server midnight -- stamp 00:00 on the bars' own clock, which IS the
                  server clock (New York wall time + 7 h, labelled UTC), excluding the week open
    tokyo_open    00:00 true UTC, placed on the server clock by `session_clock.utc_to_server`
                  (03:00 server in New York summer time, 02:00 in winter) -- never a fixed hour

THE MEASUREMENT. For each occurrence t0 the excess spread is spread[t0+k] / baseline[t0] - 1,
where the baseline is the trailing median spread of the `baseline_bars` bars BEFORE t0 (shift 1,
so the shock never sets its own normal). The median excess over occurrences at each k is the
recovery profile, and an exponential A * exp(-lambda * k) is fitted to its positive part:
half-life = ln 2 / lambda bars. A profile whose excess is gone by the next bar cannot resolve a
half-life on that bar size; it is reported BELOW_RESOLUTION with the bar length as an upper
bound, never as a fitted number. The organ prefers ticks, then M15, then H1.

TWO USES, BOTH CAUSAL:

  gate_waits   the ENTRY WAIT behind the declared cell modifier `spread_recovery_wait`
               (`mt5desk.cell_modifiers`). It replaces the cell's fixed one-bar wait with a
               MEASURED one: `k:<mult>` enters at the first bar whose spread is back within
               <mult> x the pre-signal baseline; `hl:<h>` waits <h> half-lives, the half-life
               estimated only from shocks BEFORE the signal. Recovered already at the signal
               bar -> wait 0, i.e. one bar EARLIER than the fixed wait; still wide -> later. Two
               sided by construction, and no signal is ever dropped: a spread that never
               recovers inside `max_wait` enters at `max_wait`.
  family_spread_recovery_fade
               fades the price displacement made while the spread was wide, entered once the
               spread has normalised, targeting the pre-shock price.

Nothing here reads a return to decide anything. The spread column is the venue's own record of
each bar (MT5 `MqlRates.spread`, in points), known at the bar's close.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

EVENTS: tuple[str, ...] = ("sunday_open", "tokyo_open", "rollover")
WEEKEND_GAP = pd.Timedelta(hours=30)
#: Excess below this at t0 is not a shock worth timing (10% over the trailing median).
MIN_SHOCK = 0.10
#: Bars of the recovery profile the fit reads.
PROFILE_BARS = 12
#: Prior shocks a PIT half-life needs before the `hl:` gate trusts it.
MIN_PRIOR_SHOCKS = 5
DEFAULT_MAX_WAIT = 6


def _baseline_bars(index: pd.DatetimeIndex) -> int:
    """Five trading days of bars at this bar size (120 H1, 480 M15, 7200 M1)."""
    return max(20, round(5 * 24 * 3600 / max(bar_seconds(index), 1.0)))


def _ns(index: Any) -> pd.DatetimeIndex:
    """The index at nanosecond resolution: `asi8` is in the index's OWN unit (ms on the desk's
    parquet), so every integer read goes through this first."""
    return pd.DatetimeIndex(index).as_unit("ns")


def bar_seconds(index: pd.DatetimeIndex) -> float:
    if len(index) < 3:
        return 3600.0
    d = np.diff(_ns(index).asi8[: min(len(index), 5000)]) / 1e9
    d = d[d > 0]
    return float(np.median(d)) if d.size else 3600.0


def baseline(spread: pd.Series, window: int) -> pd.Series:
    """Trailing median spread of the `window` bars BEFORE each bar (shift 1)."""
    return spread.rolling(window, min_periods=max(5, window // 4)).median().shift(1)


_TOKYO_CACHE: dict[tuple[int, int], frozenset[int]] = {}


def _tokyo_stamps(index: pd.DatetimeIndex) -> frozenset[int]:
    """The server stamps (int64 ns) of every 00:00 true-UTC instant the index spans."""
    from libs.regime.session_clock import utc_to_server

    index = _ns(index)
    lo, hi = int(index.asi8[0]), int(index.asi8[-1])
    key = (lo, hi)
    if key not in _TOKYO_CACHE:
        start = pd.Timestamp(lo, tz="UTC").normalize() - pd.Timedelta(days=1)
        end = pd.Timestamp(hi, tz="UTC").normalize() + pd.Timedelta(days=1)
        out = set()
        for day in pd.date_range(start, end, freq="D"):
            st = utc_to_server(day)
            if st is not None:
                out.add(int(pd.Timestamp(st).value))
        if len(_TOKYO_CACHE) > 64:
            _TOKYO_CACHE.clear()
        _TOKYO_CACHE[key] = frozenset(out)
    return _TOKYO_CACHE[key]


def event_positions(index: pd.DatetimeIndex, event: str) -> np.ndarray:
    """Bar positions of every occurrence of `event` on a server-stamped index."""
    idx = _ns(index)
    if len(idx) < 2:
        return np.zeros(0, dtype=int)
    gaps = np.r_[np.inf, np.diff(idx.asi8) / 1e9]
    week_open = gaps > WEEKEND_GAP.total_seconds()
    if event == "sunday_open":
        mask = week_open
        mask[0] = False
    elif event == "rollover":
        mask = (idx.hour == 0) & (idx.minute == 0) & ~week_open
    elif event == "tokyo_open":
        stamps = _tokyo_stamps(idx)
        mask = np.fromiter((int(v) in stamps for v in idx.asi8), dtype=bool, count=len(idx))
        mask &= ~week_open
    else:
        raise ValueError(f"unknown spread event {event!r}; known: {EVENTS}")
    return np.flatnonzero(mask)


def excess_matrix(spread: pd.Series, positions: np.ndarray, window: int,
                  k_bars: int = PROFILE_BARS) -> np.ndarray:
    """Rows = occurrences, columns = k: spread[t0+k] / baseline[t0] - 1 (NaN past the end)."""
    sp = spread.to_numpy(dtype=float)
    base = baseline(spread, window).to_numpy(dtype=float)
    out = np.full((len(positions), k_bars), np.nan)
    for r, p in enumerate(positions):
        b = base[p]
        if not np.isfinite(b) or b <= 0:
            continue
        seg = sp[p:p + k_bars]
        out[r, :seg.size] = seg / b - 1.0
    return out[np.isfinite(out[:, 0])] if out.size else out


def fit_half_life(profile: Sequence[float], bar_hours: float) -> dict[str, Any]:
    """Exponential fit of a median-excess profile. Never a number the bars cannot resolve."""
    p = np.asarray(profile, dtype=float)
    if p.size == 0 or not np.isfinite(p[0]):
        return {"state": "UNMEASURED", "half_life_h": None, "excess_t0": None}
    a0 = float(p[0])
    if a0 < MIN_SHOCK:
        return {"state": "NO_SHOCK", "half_life_h": None, "excess_t0": round(a0, 4)}
    # The decaying run: from t0 while the excess stays positive.
    run = [a0]
    for v in p[1:]:
        if not np.isfinite(v) or v <= 0.01 * a0:
            break
        run.append(float(v))
    if len(run) < 2:
        return {"state": "BELOW_RESOLUTION", "half_life_h": None,
                "half_life_upper_bound_h": round(bar_hours, 4), "excess_t0": round(a0, 4),
                "why": "the excess is gone by the next bar: this bar size cannot resolve it"}
    k = np.arange(len(run), dtype=float)
    y = np.log(np.asarray(run))
    slope, icpt = np.polyfit(k, y, 1)
    resid = y - (slope * k + icpt)
    ss = float(((y - y.mean()) ** 2).sum())
    # Two points always fit exactly: their r2 says nothing, so none is reported for them.
    r2: float | None = (1.0 - float((resid ** 2).sum()) / ss if ss > 0 else None) \
        if len(run) >= 3 else None
    if slope >= 0:
        return {"state": "NO_DECAY", "half_life_h": None, "excess_t0": round(a0, 4),
                "fit_bars": len(run), "why": "the excess does not fall across the fitted run"}
    hl_bars = math.log(2.0) / -float(slope)
    if hl_bars < 1.0:
        # A decay faster than one bar is a number the bars cannot resolve: the fit is reading the
        # first step, not the curve. Reported with the bar length as its upper bound.
        return {"state": "BELOW_RESOLUTION", "half_life_h": None,
                "half_life_upper_bound_h": round(bar_hours, 4), "excess_t0": round(a0, 4),
                "fit_bars": len(run),
                "why": (f"the fitted half-life is {hl_bars:.3f} bars, under one bar: this bar "
                        "size cannot resolve it")}
    return {"state": "FITTED" if len(run) >= 3 else "TWO_POINT",
            "half_life_h": round(hl_bars * bar_hours, 4),
            "half_life_bars": round(hl_bars, 4), "excess_t0": round(a0, 4),
            "fit_excess_t0": round(math.exp(float(icpt)), 4), "fit_bars": len(run),
            "r2": None if r2 is None else round(r2, 4)}


def recovery_bars(excess: np.ndarray, k_mult: float) -> list[int | None]:
    """Per occurrence, the first k at which spread <= k_mult x baseline (None: not inside)."""
    out: list[int | None] = []
    for row in excess:
        hit = np.flatnonzero(np.isfinite(row) & (row + 1.0 <= k_mult))
        out.append(int(hit[0]) if hit.size else None)
    return out


def measure(df: pd.DataFrame, event: str, *, k_mults: Sequence[float] = (1.25, 1.5)
            ) -> dict[str, Any]:
    """One (symbol, event) reading on these bars: half-life, excess at t0, n, k-recoveries."""
    if "spread" not in df.columns:
        return {"state": "UNMEASURED", "why": "no spread column on these bars", "n": 0}
    spread = pd.to_numeric(df["spread"], errors="coerce").astype(float)
    spread = spread.where(spread > 0)
    idx = pd.DatetimeIndex(df.index)
    window = _baseline_bars(idx)
    pos = event_positions(idx, event)
    ex = excess_matrix(spread, pos, window)
    bh = bar_seconds(idx) / 3600.0
    if ex.shape[0] == 0:
        return {"state": "UNMEASURED", "why": "no occurrence with a readable baseline", "n": 0,
                "bar_hours": round(bh, 4)}
    prof = np.nanmedian(ex, axis=0)
    fit = fit_half_life(prof, bh)
    rec = {}
    for km in k_mults:
        rb = [r for r in recovery_bars(ex, km) if r is not None]
        rec[f"k{km:g}"] = {"median_bars": (float(np.median(rb)) if rb else None),
                           "recovered_share": round(len(rb) / ex.shape[0], 4)}
    return {**fit, "n": int(ex.shape[0]), "bar_hours": round(bh, 4),
            "profile": [round(float(v), 4) if np.isfinite(v) else None for v in prof],
            "recovery": rec}


# ===================================================================== the entry gate (modifier)
def parse_gate(value: Any) -> tuple[str, float] | None:
    """`k:<mult>` (mult > 1) or `hl:<half-lives>` (> 0) -> (form, value), else None."""
    text = str(value if value is not None else "").strip().lower()
    form, _, num = text.partition(":")
    try:
        v = float(num)
    except ValueError:
        return None
    if form == "k" and v > 1.0 and math.isfinite(v):
        return "k", v
    if form == "hl" and v > 0.0 and math.isfinite(v):
        return "hl", v
    return None


def _pit_half_lives(sp: np.ndarray, base: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(shock positions, bars for the excess to halve) for every shock bar, in time order."""
    ex = sp / base - 1.0
    shocks = np.flatnonzero(np.isfinite(ex) & (ex >= MIN_SHOCK))
    hl = np.full(shocks.size, np.nan)
    for j, p in enumerate(shocks):
        half = ex[p] / 2.0
        seg = ex[p + 1:p + 1 + PROFILE_BARS]
        hit = np.flatnonzero(np.isfinite(seg) & (seg <= half))
        hl[j] = float(hit[0] + 1) if hit.size else float(PROFILE_BARS)
    return shocks, hl


def gate_waits(df: pd.DataFrame, positions: Sequence[int], gate: tuple[str, float], *,
               max_wait: int = DEFAULT_MAX_WAIT) -> list[int]:
    """Bars to wait after each signal bar under the gate. Causal: bar j's spread is read at j."""
    spread = pd.to_numeric(df["spread"], errors="coerce").astype(float)
    spread = spread.where(spread > 0)
    sp = spread.to_numpy(dtype=float)
    base = baseline(spread, _baseline_bars(pd.DatetimeIndex(df.index))).to_numpy(dtype=float)
    form, val = gate
    shocks = hls = None
    if form == "hl":
        shocks, hls = _pit_half_lives(sp, base)
    out: list[int] = []
    n = len(sp)
    for p in positions:
        b = base[p] if 0 <= p < n else float("nan")
        if not np.isfinite(b) or b <= 0 or not np.isfinite(sp[p]):
            out.append(1)          # nothing measured: the fixed one-bar wait stands
            continue
        if form == "k":
            w = max_wait
            for k in range(0, max_wait + 1):
                q = p + k
                if q < n and np.isfinite(sp[q]) and sp[q] <= val * b:
                    w = k
                    break
            out.append(w)
            continue
        assert shocks is not None and hls is not None
        if sp[p] / b - 1.0 < MIN_SHOCK:
            out.append(0)          # no shock at the signal bar: nothing to wait out
            continue
        # PIT: only shocks whose halving was observable before this bar.
        prior = hls[(shocks + hls <= p)]
        if prior.size < MIN_PRIOR_SHOCKS:
            out.append(1)
            continue
        out.append(int(min(max_wait, math.ceil(val * float(np.median(prior))))))
    return out


def apply_gate(sigs: list[Any], df: pd.DataFrame, value: Any, *,
               max_wait: int = DEFAULT_MAX_WAIT) -> list[Any]:
    """Move each signal to its gated bar. A signal whose gated bar is past the end is dropped
    exactly as `entry_timing=delayed` drops a last-bar signal -- there is no bar to fill on.

    FORWARD/BACKTEST PARITY. Dropping it is not losing it: the wait is causal (bar q's spread is
    read at q), so the forward pass re-run on the bar the wait lands on emits the SAME signal on
    that bar as its newest -- the backtest's signal at idx[p + w] and the forward pass's newest
    signal at idx[p + w] are one signal (tests/research/test_spread_recovery.py pins it)."""
    gate = parse_gate(value)
    if gate is None or "spread" not in df.columns or not sigs:
        return list(sigs or [])
    idx = pd.DatetimeIndex(df.index)
    pos = {t: i for i, t in enumerate(idx)}
    keep = [(s, pos.get(s.time)) for s in sigs]
    waits = gate_waits(df, [p for _, p in keep if p is not None], gate, max_wait=max_wait)
    out: list[Any] = []
    it = iter(waits)
    for s, p in keep:
        if p is None:
            out.append(s)
            continue
        w = next(it)
        if p + w < len(idx):
            out.append(replace(s, time=idx[p + w]))
    return out


# ============================================================================ the FADE family
def _atr(d: pd.DataFrame, n: int) -> np.ndarray:
    h, lo, c = (d[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
    return pd.Series(tr).rolling(n, min_periods=n).mean().shift(1).to_numpy()


def family_spread_recovery_fade(
    df: pd.DataFrame,
    *,
    event: str = "rollover",
    k_mult: float = 1.5,
    min_disp_atr: float = 0.25,
    hold_bars: int = 4,
    max_wait: int = DEFAULT_MAX_WAIT,
    stop_atr: float = 1.5,
    atr_n: int = 20,
) -> list[Signal]:
    """Fade the move made while the spread was wide, once it is back within k_mult x normal.

    Mechanism: at a scheduled liquidity hole (week open, Tokyo open, broker rollover) the few
    quotes that print are a thin book's, and the price displacement they make is a concession to
    whoever had to trade through the gap, not information. When the spread normalises, liquidity
    providers return and the concession is unwound toward the pre-shock price. The signal fires at
    the first bar whose spread is back within `k_mult` x the pre-shock baseline (read at that
    bar's close), fading close[last wide bar] - close[t0 - 1] when it is at least `min_disp_atr`
    ATRs, targeting the pre-shock close.
    """
    if "spread" not in df.columns or len(df) < atr_n + 3:
        return []
    d = df
    idx = pd.DatetimeIndex(d.index)
    spread = pd.to_numeric(d["spread"], errors="coerce").astype(float)
    spread = spread.where(spread > 0)
    sp = spread.to_numpy(dtype=float)
    base = baseline(spread, _baseline_bars(idx)).to_numpy(dtype=float)
    close = d["close"].to_numpy(dtype=float)
    atr = _atr(d, atr_n)
    n = len(d)
    out: list[Signal] = []
    for p in event_positions(idx, event):
        if p < 1 or p + 1 >= n:
            continue
        b = base[p]
        if not np.isfinite(b) or b <= 0 or not np.isfinite(sp[p]) or sp[p] / b - 1.0 < MIN_SHOCK:
            continue
        j = None
        for k in range(1, max_wait + 1):
            q = p + k
            # The recovery bar may be the NEWEST bar: its spread is known at its close, so the
            # forward pass fires on it exactly as the backtest does (no one-bar look-ahead guard).
            if q >= n:
                break
            if np.isfinite(sp[q]) and sp[q] <= k_mult * b:
                j = q
                break
        if j is None:
            continue
        a = atr[j]
        pre = close[p - 1]
        disp = close[j - 1] - pre
        if not np.isfinite(a) or a <= 0 or not np.isfinite(disp) or abs(disp) < min_disp_atr * a:
            continue
        side = -1 if disp > 0 else 1
        px = close[j]
        if (pre - px) * side <= 0:
            continue          # the move already unwound past the pre-shock price
        out.append(Signal(time=idx[j], side=side, stop=px - side * stop_atr * a, target=pre,
                          ttl_bars=int(hold_bars), tag=f"spread_recovery_fade.{event}",
                          trigger=None, wait_bars=1))
    return out
