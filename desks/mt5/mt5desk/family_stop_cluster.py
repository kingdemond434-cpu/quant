"""The retail stop-cluster map, and the two ways to trade it (Tier-1 gap #9, A26/B13, 2026-11-03).

THE CLAIM. Retail stops are not spread evenly. They sit just beyond the levels the crowd is
taught to watch: round numbers, the prior day's high and low, the Asian session range and recent
swing points. Where several of those levels coincide, the resting stop orders pile up. Price that
reaches the pile fills those stops as market orders. Two things can follow:

  revert   the stops were the liquidity someone larger needed. The sweep pierces the cluster,
           the stop orders are absorbed, and the bar closes back inside within `n_fail` bars. We
           fade the move from the next bar's open.
  cascade  the filled stops push price further and set off the next ones. The bar closes beyond
           the cluster with momentum and we go with it from the next bar's open.

Both families read the SAME map. They make opposite bets about what the pile does, so the
gauntlet decides which (if either) is true per symbol and chart. The desk predicts where these
clusters sit and positions around them. It never places orders to trigger them.

THE PAYER. The retail trader whose stop is filled at the worst price of the swing (revert), or
whose stop adds to the move that fills the next one (cascade). Neither trades on a forecast.

WHAT IS IN THE MAP, ALL CAUSAL (every level is known strictly before the bar that tests it):
  round      the nearest big figure above and below the previous close
  half       the nearest half figure above and below it (1.0950 between 1.09 and 1.10)
             (step = 10**floor(log10(price)) / 100: 0.01 on EURUSD, 1.0 on USDJPY, 10 on gold,
             100 on US30/NAS100/GER40)
  prior_day  yesterday's high and low on the broker clock (known from today's first bar)
  asia       today's Asian-session high and low (broker hours < `asia_end_h`), usable only
             once the session has closed
  swing      the latest `n_swings` swing highs and lows from `failed_breakout.swing_levels`,
             each usable only after its `k_swing` confirmation bars have closed
Density is the number of DISTINCT sources within `tol_atr` ATR of a level. A cluster needs
`min_confluence` sources. The stops are assumed to sit `buffer_atr` beyond its outermost level.

WHAT IS DELIBERATELY MISSING, AND SAYS SO.
  * Crowd weighting (the A1 retail-positioning recorder) is UNMEASURED: no recorder exists yet,
    so every source counts 1. No parameter pretends otherwise, because a weight axis with
    nothing behind it would be charged as a trial and test nothing.
  * Public broker order-book pages are UNMEASURED: none is recorded lawfully on this desk yet.
    When one is, it becomes a new source with its own name, not a re-tuning of these.

EVERY PARAMETER COUNTS AGAINST THE TRIAL BUDGET. The sweep runs the defaults only, so each
family is one cell per (symbol, chart). The grid is kept small on purpose.
"""
from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
from mt5desk.engine import Signal

from libs.research.failed_breakout import atr as _atr
from libs.research.failed_breakout import swing_levels

_SOURCES = ("round", "half", "prior_day", "asia", "swing")


def round_step(price: float) -> float:
    """The big-figure step for `price`: 0.01 at 1.08, 1.0 at 150, 10 at 2600, 100 at 42000."""
    if not (math.isfinite(price) and price > 0):
        return float("nan")
    return float(10.0 ** math.floor(math.log10(price)) / 100.0)


def _last_n_confirmed(flags: np.ndarray, values: np.ndarray, k: int, n_keep: int
                      ) -> np.ndarray:
    """(len, n_keep) array: the latest n_keep swing prices USABLE at each bar (NaN if fewer).

    A swing marked at i is confirmed when bar i+k closes, so it is usable from bar i+k+1 on.
    """
    n = flags.size
    out = np.full((n, n_keep), np.nan)
    kept: list[float] = []
    pending = {int(i) + k + 1: float(values[i]) for i in np.flatnonzero(flags)}
    for t in range(n):
        v = pending.get(t)
        if v is not None:
            kept.append(v)
            if len(kept) > n_keep:
                kept.pop(0)
        for j, x in enumerate(reversed(kept)):
            out[t, j] = x
    return out


def level_map(df: pd.DataFrame, *, k_swing: int = 10, n_swings: int = 2,
              asia_end_h: int = 9, atr_n: int = 14) -> dict[str, np.ndarray]:
    """Every level source, as arrays aligned to `df`. Row t holds what was known BEFORE bar t.

    Returned so a test can truncate the frame and prove each row is unchanged.
    """
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    n = len(df)
    prev_close = np.concatenate(([np.nan], close[:-1]))

    day = df.index.floor("D")
    daily = pd.DataFrame({"h": high, "l": low}, index=df.index).groupby(day).agg(
        {"h": "max", "l": "min"})
    prior = daily.shift(1)
    pdh = prior["h"].reindex(day).to_numpy(dtype=float)
    pdl = prior["l"].reindex(day).to_numpy(dtype=float)

    # The Asian range. A bar stamped at asia_end_h opens after the session, so the range built from
    # bars stamped < asia_end_h is complete and closed by then.
    hours = np.asarray(df.index.hour)
    in_asia = hours < asia_end_h
    a_hi = pd.Series(np.where(in_asia, high, np.nan), index=df.index).groupby(day).transform("max")
    a_lo = pd.Series(np.where(in_asia, low, np.nan), index=df.index).groupby(day).transform("min")
    after = ~in_asia
    asia_hi = np.where(after, a_hi.to_numpy(dtype=float), np.nan)
    asia_lo = np.where(after, a_lo.to_numpy(dtype=float), np.nan)

    is_hi, is_lo = swing_levels(high, low, k_swing)
    sw_hi = _last_n_confirmed(is_hi, high, k_swing, n_swings)
    sw_lo = _last_n_confirmed(is_lo, low, k_swing, n_swings)

    step = np.array([round_step(p) for p in prev_close])
    with np.errstate(invalid="ignore"):
        r_up = np.ceil(prev_close / step) * step
        r_dn = np.floor(prev_close / step) * step
        # The half figure strictly BETWEEN big figures (1.0950, never 1.1000 again), so a big
        # figure is one source and not two by counting itself twice.
        h_up = (np.ceil(prev_close / step - 0.5) + 0.5) * step
        h_dn = (np.floor(prev_close / step - 0.5) + 0.5) * step

    a = _atr(high, low, close, atr_n)
    prev_atr = np.concatenate(([np.nan], a[:-1]))
    return {
        "prev_close": prev_close, "prev_atr": prev_atr, "n": np.array([n]),
        "round": np.stack([r_up, r_dn], axis=1), "half": np.stack([h_up, h_dn], axis=1),
        "prior_day": np.stack([pdh, pdl], axis=1), "asia": np.stack([asia_hi, asia_lo], axis=1),
        "swing": np.concatenate([sw_hi, sw_lo], axis=1),
    }


def nearest_cluster(levels: list[tuple[float, str]], ref: float, side: int, tol: float,
                    min_confluence: int, max_dist: float) -> tuple[float, int] | None:
    """The nearest dense cluster beyond `ref` on `side` (+1 above, -1 below).

    Returns (outermost level of the cluster, number of distinct sources), or None.
    """
    beyond = sorted(((p, s) for p, s in levels
                     if (p - ref) * side > 0 and abs(p - ref) <= max_dist),
                    key=lambda x: abs(x[0] - ref))
    for p0, _s0 in beyond:
        group = [(p, s) for p, s in beyond if abs(p - p0) <= tol]
        srcs = {s for _p, s in group}
        if len(srcs) >= min_confluence:
            edge = max(p for p, _ in group) if side > 0 else min(p for p, _ in group)
            return float(edge), len(srcs)
    return None


def _levels_at(m: dict[str, np.ndarray], t: int) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for src in _SOURCES:
        for v in m[src][t]:
            if np.isfinite(v):
                out.append((float(v), src))
    return out


def _stop_cluster(df: pd.DataFrame, *, mode: str, k_swing: int, n_swings: int, asia_end_h: int,
                  tol_atr: float, buffer_atr: float, min_confluence: int, max_dist_atr: float,
                  n_fail: int, momentum_atr: float, stop_atr: float, rr: float,
                  hold_bars: int, atr_n: int) -> list[Signal]:
    if mode not in ("revert", "cascade"):
        raise ValueError(f"mode must be revert or cascade, not {mode!r}")
    if len(df) < max(atr_n, 2 * k_swing) + 5:
        return []
    m = level_map(df, k_swing=k_swing, n_swings=n_swings, asia_end_h=asia_end_h, atr_n=atr_n)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    idx = df.index
    out: list[Signal] = []
    busy_until = -1
    # A revert sweep waiting to fail: [side swept, cluster level, sweep extreme, last bar, atr].
    pending: list[float] | None = None
    # The last bar is never a signal bar: its entry would be the bar after the data ends.
    for t in range(1, len(df) - 1):
        a = float(m["prev_atr"][t])
        ref = float(m["prev_close"][t])
        if pending is None and t > busy_until and np.isfinite(a) and a > 0 and np.isfinite(ref):
            levels = _levels_at(m, t)
            for side in (1, -1):
                hit = nearest_cluster(levels, ref, side, tol_atr * a, min_confluence,
                                      max_dist_atr * a)
                if hit is None:
                    continue
                level = hit[0]
                edge = level + side * buffer_atr * a          # where the stops actually rest
                if not (high[t] >= edge if side > 0 else low[t] <= edge):
                    continue
                if mode == "revert":
                    pending = [side, level, high[t] if side > 0 else low[t], t + n_fail, a]
                    break
                # cascade: a close beyond the stops, on a bar that moved hard enough to be them
                if (close[t] - edge) * side > 0 and (close[t] - ref) * side >= momentum_atr * a:
                    px = float(close[t])
                    out.append(Signal(time=idx[t], side=side, stop=px - side * stop_atr * a,
                                      target=px + side * stop_atr * a * rr,
                                      ttl_bars=int(hold_bars), tag="stop_cluster:cascade",
                                      trigger=None, wait_bars=1))
                    busy_until = t + hold_bars
                    break
        elif pending is not None:
            side = int(pending[0])
            pending[2] = max(pending[2], high[t]) if side > 0 else min(pending[2], low[t])
        if pending is None:
            continue
        side = int(pending[0])
        level, extreme, last_t, a0 = pending[1], pending[2], int(pending[3]), pending[4]
        if (close[t] - level) * side < 0:                     # closed back inside: it failed
            px = float(close[t])
            stop = extreme + side * stop_atr * a0
            risk = abs(stop - px)
            if risk > 0:
                out.append(Signal(time=idx[t], side=-side, stop=float(stop),
                                  target=px - side * rr * risk, ttl_bars=int(hold_bars),
                                  tag="stop_cluster:revert", trigger=None, wait_bars=1))
                busy_until = t + hold_bars
            pending = None
        elif t >= last_t:
            pending = None
    return out


def family_stop_cluster_revert(
    df: pd.DataFrame,
    *,
    k_swing: int = 10,          # bars either side confirming a swing point
    n_swings: int = 2,          # swing highs and lows kept per side
    asia_end_h: int = 9,        # broker hour the Asian range is complete
    tol_atr: float = 0.25,      # how close two levels must be to share stops, in ATR
    buffer_atr: float = 0.10,   # how far beyond the level the stops rest, in ATR
    min_confluence: int = 2,    # distinct sources needed for a cluster
    max_dist_atr: float = 1.5,  # clusters further than this from the last close are ignored
    n_fail: int = 3,            # bars allowed for the sweep to close back inside
    stop_atr: float = 0.25,     # protective stop beyond the sweep extreme, in ATR
    rr: float = 1.5,
    hold_bars: int = 12,
    atr_n: int = 14,
) -> list[Signal]:
    """Fade a sweep of a predicted stop cluster once it closes back inside."""
    return _stop_cluster(df, mode="revert", k_swing=k_swing, n_swings=n_swings,
                         asia_end_h=asia_end_h, tol_atr=tol_atr, buffer_atr=buffer_atr,
                         min_confluence=min_confluence, max_dist_atr=max_dist_atr, n_fail=n_fail,
                         momentum_atr=0.0, stop_atr=stop_atr, rr=rr, hold_bars=hold_bars,
                         atr_n=atr_n)


def family_stop_cluster_cascade(
    df: pd.DataFrame,
    *,
    k_swing: int = 10,
    n_swings: int = 2,
    asia_end_h: int = 9,
    tol_atr: float = 0.25,
    buffer_atr: float = 0.10,
    min_confluence: int = 2,
    max_dist_atr: float = 1.5,
    momentum_atr: float = 0.5,  # the bar's close-to-close move that marks a cascade, in ATR
    stop_atr: float = 1.0,
    rr: float = 1.5,
    hold_bars: int = 12,
    atr_n: int = 14,
) -> list[Signal]:
    """Follow a close through a predicted stop cluster on a bar that moved hard."""
    return _stop_cluster(df, mode="cascade", k_swing=k_swing, n_swings=n_swings,
                         asia_end_h=asia_end_h, tol_atr=tol_atr, buffer_atr=buffer_atr,
                         min_confluence=min_confluence, max_dist_atr=max_dist_atr, n_fail=0,
                         momentum_atr=momentum_atr, stop_atr=stop_atr, rr=rr,
                         hold_bars=hold_bars, atr_n=atr_n)


STOP_CLUSTER_FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    "stop_cluster_revert": family_stop_cluster_revert,
    "stop_cluster_cascade": family_stop_cluster_cascade,
}
