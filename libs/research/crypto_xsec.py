"""Cross-sectional crypto funding strategy core (the program's single best candidate).

Long the lowest-funding perps, short the highest, dollar-neutral, risk-parity (inverse-vol) within
each leg, with a turnover band and ADV-tiered realistic costs. Pure function of (close, funding,
adv) -- the SAME code runs the backtest and the forward shadow, so the out-of-sample comparison is
provably apples-to-apples. No parameter mining: the deployable variant is frozen by the caller.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def adv_tier_cost(adv_usd: float) -> float:
    """Per-side realistic cost by average dollar volume (taker + tiered slippage)."""
    if adv_usd > 5e8:
        return 5e-4
    if adv_usd > 1e8:
        return 8e-4
    return 1.5e-3


def xsec_funding_returns(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    adv: dict[str, float],
    *,
    lookback: int,
    q: float,
    band: float,
    vol_window: int = 30,
    min_names: int = 12,
) -> np.ndarray:
    """Daily net-of-cost return series of the cross-sectional funding strategy.

    Decisions use only lagged information (no look-ahead). Returns are NOT vol-scaled here so the
    series is directly comparable across runs; Sharpe is scale-invariant anyway.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    signal = funding.rolling(lookback).mean().shift(1)
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
    out = np.zeros(len(close), dtype="float64")
    prev = pd.Series(0.0, index=close.columns)
    for t in range(1, len(close)):
        sig = signal.iloc[t].dropna()
        valid = close.iloc[t].reindex(sig.index).notna() & ret.iloc[t].reindex(sig.index).notna()
        sig = sig.reindex(sig.index[valid]).dropna()
        if len(sig) < min_names:
            out[t] = float((prev * ret.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(sig) * q))
        ranked = sig.sort_values()
        longs, shorts = ranked.index[:k], ranked.index[-k:]
        iv = inv_vol.iloc[t]
        w = pd.Series(0.0, index=close.columns)
        lw, sw = iv.reindex(longs).fillna(0.0), iv.reindex(shorts).fillna(0.0)
        if lw.sum() > 0:
            w[longs] = 0.5 * lw / lw.sum()
        if sw.sum() > 0:
            w[shorts] = -0.5 * sw / sw.sum()
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)            # turnover band: hold unless target moved
        price_ret = float((w * ret.iloc[t].reindex(w.index).fillna(0.0)).sum())
        funding_pnl = float(-(w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn_cost = float(sum(abs(w[s] - prev[s]) * cost.get(s, 1.5e-3) for s in w.index))
        out[t] = price_ret + funding_pnl - turn_cost
        prev = w
    return out
