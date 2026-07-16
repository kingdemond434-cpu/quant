"""Cross-asset diversified-portfolio strategy cores (global research, MT5 execution).

Single-name FX directional already returned zero survivors. The construction that rescued crypto
funding (single-name -> dollar-neutral cross-sectional portfolio) is applied here to instruments the
broker can actually trade (FX, metals, energy, indices, crypto CFDs):

  * ``xsec_signal_returns`` -- generic dollar-neutral cross-sectional book driven by ANY global
    signal (price momentum, Binance funding, a macro factor...). Long the top/bottom signal
    quantile, inverse-vol within each leg, turnover band, per-symbol turnover cost, and an optional
    per-symbol DAILY HOLDING COST (CFD overnight financing / swap). Returns are PRICE-ONLY: holding
    an MT5 CFD does not pay perpetual funding, so a funding-derived edge must survive on the price
    move alone, net of the financing you actually pay. This is the honest MT5-execution accounting.
  * ``xsec_momentum_returns`` -- convenience wrapper: signal = trailing return (momentum/reversal).
  * ``trend_basket_returns``  -- time-series momentum (managed-futures): each asset long/short by
    the sign of its own trend, inverse-vol sized, gross-normalized, net of turnover + holding cost.

Pure functions of (close, signal, cost) so the same code drives a backtest and a forward shadow.
No parameter mining inside -- the caller freezes the deployable variant. Decisions use only lagged
information (``.shift(1)``); no look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _inv_vol(ret: pd.DataFrame, vol_window: int) -> pd.DataFrame:
    return 1.0 / ret.rolling(vol_window).std().shift(1)


def _hold(prev: pd.Series, hold_cost: dict[str, float] | None) -> float:
    if not hold_cost:
        return 0.0
    return float(sum(abs(prev[s]) * hold_cost.get(s, 0.0) for s in prev.index))


def xsec_signal_returns(
    close: pd.DataFrame,
    signal: pd.DataFrame,
    cost: dict[str, float],
    *,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Daily PRICE-ONLY net return of a dollar-neutral cross-sectional book on ``signal``.

    ``signal`` is the point-in-time factor (lagged one bar internally). ``long_high`` buys the top
    quantile and shorts the bottom; flip it to long the lowest-signal names. ``hold_cost`` is the
    per-symbol daily financing charged on the position held (CFD swap) -- the cost that makes a
    funding edge expensive to express via CFDs rather than perps.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    sig_l = signal.shift(1)
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        s = sig_l.iloc[t].dropna()
        valid = close.iloc[t].reindex(s.index).notna() & ret.iloc[t].reindex(s.index).notna()
        s = s.reindex(s.index[valid]).dropna()
        if len(s) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            out[t] -= _hold(prev, hold_cost)
            continue
        k = max(1, int(len(s) * q))
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
        w = w.where(delta > band, prev)                     # turnover band
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.0e-3) for s2 in w.index))
        out[t] = price_ret - turn_cost - _hold(w, hold_cost)
        prev = w
    return out


def xsec_momentum_returns(
    close: pd.DataFrame,
    cost: dict[str, float],
    *,
    lookback: int,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Cross-sectional momentum (``long_high``) or short-term reversal (``long_high=False``)."""
    signal = close / close.shift(lookback) - 1.0
    return xsec_signal_returns(close, signal, cost, q=q, band=band, vol_window=vol_window,
                               min_names=min_names, long_high=long_high, hold_cost=hold_cost)


def vol_target(
    returns: np.ndarray,
    *,
    target_ann_vol: float = 0.10,
    lookback: int = 30,
    max_leverage: float = 3.0,
    ppy: float = 252.0,
) -> np.ndarray:
    """Scale a return stream to a constant target volatility using trailing realized vol (lagged).

    Standard managed-futures overlay: lever up in calm regimes, cut exposure when realized vol
    spikes (i.e. before/into crises). Leverage is lagged one bar (no look-ahead) and capped. Risk
    engineering, not parameter mining -- it targets tail risk/fragility; Sharpe is invariant to
    *constant* leverage, so any Sharpe change comes only from time-variation in exposure.
    """
    r = np.asarray(returns, dtype="float64")
    s = pd.Series(r)
    realized = s.rolling(lookback).std().shift(1) * np.sqrt(ppy)
    lev = (target_ann_vol / realized).clip(upper=max_leverage)
    lev = lev.fillna(0.0).to_numpy()
    return np.asarray(lev * r, dtype="float64")


def trend_basket_weights(
    close: pd.DataFrame,
    *,
    lookback: int,
    vol_window: int = 30,
    min_names: int = 4,
) -> dict[str, float]:
    """Latest target weights of the trend basket (the brain's decision to hand to execution).

    Gross-normalized to 1 (sum of absolute weights), band-free -- turnover is the executor's job
    (the rebalancer applies the drift threshold). Returns {} if too few names are available.
    """
    if len(close) <= lookback + 1:
        return {}
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    trend = np.sign(close.iloc[-1] / close.iloc[-1 - lookback] - 1.0)
    trend = trend[close.iloc[-1].notna()].dropna()
    if len(trend) < min_names:
        return {}
    raw = trend * inv_vol.reindex(trend.index).fillna(0.0)
    gross = float(raw.abs().sum())
    if gross <= 0:
        return {}
    return {k: float(v) for k, v in (raw / gross).items() if v != 0.0}


def xsec_momentum_weights(
    close: pd.DataFrame,
    *,
    lookback: int,
    q: float,
    vol_window: int = 30,
    min_names: int = 6,
    long_high: bool = True,
) -> dict[str, float]:
    """Latest dollar-neutral cross-sectional momentum target weights (+0.5 long / -0.5 short)."""
    if len(close) <= lookback + 1:
        return {}
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    sig = (close.iloc[-1] / close.iloc[-1 - lookback] - 1.0)
    sig = sig[close.iloc[-1].notna()].dropna()
    if len(sig) < min_names:
        return {}
    k = max(1, int(len(sig) * q))
    ranked = sig.sort_values(ascending=not long_high)
    longs, shorts = ranked.index[:k], ranked.index[-k:]
    lw = inv_vol.reindex(longs).fillna(0.0)
    sw = inv_vol.reindex(shorts).fillna(0.0)
    out: dict[str, float] = {}
    if lw.sum() > 0:
        out.update({s: 0.5 * float(lw[s]) / float(lw.sum()) for s in longs})
    if sw.sum() > 0:
        out.update({s: -0.5 * float(sw[s]) / float(sw.sum()) for s in shorts})
    return out


def combine_weights(*books: dict[str, float], renorm: bool = True) -> dict[str, float]:
    """Equal-risk combine target-weight books, then gross-normalize to 1 (max-robustness book)."""
    n = len(books)
    if n == 0:
        return {}
    keys = sorted({k for b in books for k in b})
    merged = {k: sum(b.get(k, 0.0) for b in books) / n for k in keys}
    if not renorm:
        return merged
    gross = sum(abs(v) for v in merged.values())
    if gross <= 0:
        return {}
    return {k: v / gross for k, v in merged.items() if v != 0.0}


def trend_basket_returns(
    close: pd.DataFrame,
    cost: dict[str, float],
    *,
    lookback: int,
    band: float,
    vol_window: int = 30,
    min_names: int = 4,
    hold_cost: dict[str, float] | None = None,
) -> np.ndarray:
    """Daily net return of a time-series-momentum (managed-futures) basket.

    Each asset is held long or short by the sign of its own lagged ``lookback``-day return, sized
    inverse-vol, with the book gross-normalized to 1 so it is comparable across runs.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = _inv_vol(ret, vol_window)
    trend = np.sign((close / close.shift(lookback) - 1.0).shift(1))
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        tr = trend.iloc[t].dropna()
        valid = close.iloc[t].reindex(tr.index).notna() & ret.iloc[t].reindex(tr.index).notna()
        tr = tr.reindex(tr.index[valid]).dropna()
        if len(tr) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            out[t] -= _hold(prev, hold_cost)
            continue
        iv = inv_vol.iloc[t].reindex(tr.index).fillna(0.0)
        raw = tr * iv
        gross = raw.abs().sum()
        w = pd.Series(0.0, index=close.columns)
        if gross > 0:
            w[tr.index] = raw / gross
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.0e-3) for s in w.index))
        out[t] = price_ret - turn_cost - _hold(w, hold_cost)
        prev = w
    return out
