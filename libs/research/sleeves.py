"""Relative-value and positioning sleeve cores for the MT5 alpha portfolio.

These are the *orthogonal* building blocks -- relative-value (ratio mean-reversion) and positioning
(CFTC COT) signals are economically distinct from price-trend/momentum, so they are the legitimate
diversifiers that can lift a portfolio's robustness without overfitting. Pure functions; decisions
use only lagged information (``.shift(1)``); net of realistic per-side cost. No parameter mining.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ratio_meanrev_returns(
    a_close: pd.Series,
    b_close: pd.Series,
    *,
    lookback: int,
    vol_window: int = 30,
    cost: float = 2.0e-4,
    band: float = 0.05,
    z_cap: float = 1.0,
) -> np.ndarray:
    """Daily net return of a dollar-neutral A/B ratio mean-reversion spread.

    Signal is the lagged z-score of ``log(A/B)`` over ``lookback``; position = ``-z`` (buy the cheap
    leg, sell the rich), clipped to +/-``z_cap``, split 0.5 long / 0.5 short (dollar-neutral). A
    turnover band holds the position unless the target moves materially. Cost is charged per side on
    turnover. Flat whenever either leg is missing.
    """
    a, b = a_close.align(b_close, join="outer")
    ret_a = a.pct_change(fill_method=None)
    ret_b = b.pct_change(fill_method=None)
    lr = np.log(a / b)
    z = ((lr - lr.rolling(lookback).mean()) / lr.rolling(lookback).std()).shift(1)
    pos = (-z).clip(-z_cap, z_cap)
    out = np.zeros(len(a), dtype="float64")
    prev = 0.0
    for t in range(1, len(a)):
        p = pos.iloc[t]
        ra, rb = ret_a.iloc[t], ret_b.iloc[t]
        if not (np.isfinite(p) and np.isfinite(ra) and np.isfinite(rb)):
            out[t] = 0.0
            continue
        if abs(p - prev) <= band:
            p = prev                                   # turnover band: hold
        turn = abs(p - prev) * cost                    # per-side cost on the change (both legs)
        out[t] = 0.5 * p * ra - 0.5 * p * rb - turn
        prev = p
    return out


def calendar_event_returns(
    index_close: pd.DataFrame,
    *,
    cost: float = 1.0e-4,
    vol_window: int = 30,
    tom_first: int = 3,
    min_names: int = 1,
) -> np.ndarray:
    """Turn-of-month flow sleeve: long an inverse-vol equity-index basket only in the TOM window.

    Documented month-end/turn flow effect (pension/fund rebalancing): equities drift up around the
    last trading day of the month through the first few of the next. The window is the standard
    [last day .. +``tom_first``] -- deterministic from the calendar, so no look-ahead and no date
    feed needed. Orthogonal to trend/momentum/carry; net of turnover cost.
    """
    # Compute everything on the instruments' OWN trading days (drop all-NaN rows). A combined
    # calendar that includes other assets' weekends (e.g. crypto) would (a) mis-place "first/last of
    # month" and (b) poison the rolling vol with NaNs, manufacturing a spurious small-sample edge.
    clean = index_close.dropna(how="all")
    ret = clean.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    m = pd.Series(clean.index.year * 12 + clean.index.month, index=clean.index)
    within = m.groupby(m).cumcount()
    size = m.groupby(m).transform("size")
    in_window = (within < tom_first) | (within == size - 1)
    out = np.zeros(len(clean), dtype="float64")
    prev = 0.0
    for t in range(1, len(clean)):
        on = 1.0 if bool(in_window.iloc[t]) else 0.0
        r_eq = 0.0
        if on > 0:
            iv, r = inv_vol.iloc[t], ret.iloc[t]
            valid = clean.iloc[t].notna() & r.notna() & iv.notna()
            names = clean.columns[valid]
            if len(names) >= min_names and iv.reindex(names).sum() > 0:
                w = iv.reindex(names) / iv.reindex(names).sum()
                r_eq = float((w * r.reindex(names)).sum())
            else:
                on = 0.0
        out[t] = on * r_eq - abs(on - prev) * cost
        prev = on
    mapped = pd.Series(out, index=clean.index).reindex(index_close.index).fillna(0.0)
    return np.asarray(mapped.to_numpy(), dtype="float64")


def swap_carry_returns(
    close: pd.DataFrame,
    carry_long: pd.DataFrame,
    carry_short: pd.DataFrame,
    cost: dict[str, float],
    *,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 5,
) -> np.ndarray:
    """Cross-sectional carry from broker SWAP rates (MT5-native, forward-validated).

    Ranks instruments by the (lagged) fractional daily carry of a long position; goes long the
    top quantile and short the bottom, inverse-vol within each leg. Daily P&L = price move + carry
    actually earned (longs receive ``carry_long``, shorts receive ``carry_short``) - turnover cost.
    Backtest needs a swap-rate history (see scripts/log_swaps.py); until that accumulates this runs
    forward only.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = carry_long.shift(1)
    cl, cs = carry_long.shift(1), carry_short.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values(ascending=False)              # highest long-carry first
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        carry_pnl = float((w[w > 0] * cl.iloc[t].reindex(w[w > 0].index).fillna(0.0)).sum()
                          + (-w[w < 0] * cs.iloc[t].reindex(w[w < 0].index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret + carry_pnl - turn_cost
        prev = w
    return out


def cot_timeseries_returns(
    close: pd.DataFrame,
    cot_z: pd.DataFrame,
    cost: dict[str, float],
    *,
    band: float,
    vol_window: int = 30,
    z_entry: float = 1.0,
) -> np.ndarray:
    """Per-instrument TIME-SERIES COT fade (complements the cross-sectional version).

    Each instrument is faded against its OWN positioning extreme: short when specs are crowded long
    (lagged z > ``z_entry``), long when crowded short (z < -``z_entry``), inverse-vol sized and
    gross-normalized across whatever instruments are currently at an extreme. This captures the
    documented positioning-reversal premium per market rather than only in the cross-section.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = cot_z.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        z = sig.iloc[t]
        ext = z[z.abs() > z_entry].dropna()
        valid = close.iloc[t].reindex(ext.index).notna() & ret.iloc[t].reindex(ext.index).notna()
        ext = ext.reindex(ext.index[valid]).dropna()
        w = pd.Series(0.0, index=close.columns)
        if len(ext):
            iv = inv_vol.iloc[t].reindex(ext.index).fillna(0.0)
            raw = -np.sign(ext) * iv                  # fade the extreme
            gross = float(raw.abs().sum())
            if gross > 0:
                w[ext.index] = raw / gross
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.0e-3) for s in w.index))
        out[t] = price_ret - turn_cost
        prev = w
    return out


def crisis_hedge_returns(
    asset_close: pd.Series,
    risk_close: pd.Series,
    *,
    ma_window: int = 200,
    vol_window: int = 30,
    cost: float = 2.0e-4,
) -> np.ndarray:
    """Safe-haven (e.g. gold) long ONLY in a risk-off regime -- a convexity/tail-hedge sleeve.

    Goes long ``asset_close`` (vol-scaled to ~unit gross) while the risk proxy ``risk_close`` (an
    equity index) is below its ``ma_window`` moving average (lagged risk-off regime), else flat. Its
    value to the portfolio is tail diversification (it tends to pay in the drawdowns that drive the
    fragility gate), not standalone Sharpe. Decisions use only lagged information.
    """
    a, r = asset_close.align(risk_close, join="outer")
    ret = a.pct_change(fill_method=None)
    risk_off = (r < r.rolling(ma_window).mean()).shift(1)
    out = np.zeros(len(a), dtype="float64")
    prev = 0.0
    for t in range(1, len(a)):
        ra = ret.iloc[t]
        w = 1.0 if bool(risk_off.iloc[t]) else 0.0
        if not np.isfinite(ra):
            out[t] = 0.0
            continue
        out[t] = w * ra - abs(w - prev) * cost
        prev = w
    return out


def cot_positioning_returns(
    close: pd.DataFrame,
    cot_z: pd.DataFrame,
    cost: dict[str, float],
    *,
    band: float,
    vol_window: int = 30,
    min_names: int = 3,
    long_high: bool = False,
) -> np.ndarray:
    """Daily net return of a cross-sectional book driven by a COT positioning z-score.

    ``cot_z`` is the (weekly, ffilled to daily) speculator-positioning z-score per instrument,
    aligned to ``close``. ``long_high=False`` fades crowded positioning (short the most-net-long,
    long the most-net-short) -- the documented COT reversal/risk-premium. Inverse-vol within each
    leg, turnover band, per-symbol cost. Decisions use the lagged z-score (no look-ahead).
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig_l = cot_z.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig_l.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, len(s) // 3)
        ranked = s.sort_values(ascending=not long_high)
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret - turn_cost
        prev = w
    return out
