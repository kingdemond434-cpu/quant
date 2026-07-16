"""Crypto-native alpha sleeves (Binance perps) -- economically distinct mechanisms.

Built on the same dollar-neutral, inverse-vol, turnover-banded, net-of-cost construction as the
proven funding carry core, but driven by different economic signals so the portfolio gets genuinely
orthogonal return streams (the goal is portfolio Sharpe, not another funding clone). Each sleeve
earns/pays funding on the positions it holds (the real perp cashflow). Decisions use only lagged
information; no look-ahead.

Funding family here:
  * funding_carry      -> see crypto_xsec.xsec_funding_returns (long lowest / short highest funding)
  * funding_momentum   -> trade WITH the change in funding (positioning building)
  * funding_reversal   -> fade funding EXTREMES (crowded longs pay; short them, collect funding)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crypto_xsec import adv_tier_cost


def _book(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    adv: dict[str, float],
    signal: pd.DataFrame,
    *,
    q: float,
    band: float,
    vol_window: int,
    min_names: int,
    long_low: bool,
) -> np.ndarray:
    """Generic dollar-neutral cross-sectional perp book on ``signal``, earning funding cashflow.

    ``long_low`` longs the bottom-quantile signal and shorts the top; flip for the opposite. Returns
    daily net = price P&L + funding earned/paid - turnover cost (ADV-tiered).
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = 1.0 / ret.rolling(vol_window).std().shift(1)
    sig = signal.shift(1)
    cost = {s: adv_tier_cost(a) for s, a in adv.items()}
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
        ranked = s.sort_values(ascending=long_low)        # long_low -> smallest first = longs
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
        funding_pnl = float(-(w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float(sum(abs(w[s2] - prev[s2]) * cost.get(s2, 1.5e-3) for s2 in w.index))
        out[t] = price_ret + funding_pnl - turn
        prev = w
    return out


def funding_momentum_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Cross-sectional funding-rate momentum (positioning shifts -> short-term continuation)."""
    signal = funding.rolling(lookback).mean() - funding.rolling(lookback * 3).mean()
    # long where funding is FALLING (signal low) -> shorts being squeezed / longs unwinding cheaply
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def funding_reversal_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Fade short-term PRICE momentum, collecting funding -- reversal of crowded perp moves."""
    signal = close / close.shift(lookback) - 1.0
    # long recent losers / short recent winners (price reversal); funding cashflow is incidental
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def latest_weights(
    close: pd.DataFrame, signal: pd.DataFrame, *,
    q: float, vol_window: int = 30, min_names: int = 12, long_low: bool = True,
) -> dict[str, float]:
    """Today's dollar-neutral cross-sectional target weights for a signal (the brain's decision).

    Mirrors the backtest book's construction (lagged signal, inverse-vol, +0.5/-0.5 legs) but only
    for the latest bar -- what the executor should hold now. ``long_low`` longs the lowest-signal q.
    """
    ret = close.pct_change(fill_method=None)
    inv_vol = (1.0 / ret.rolling(vol_window).std()).iloc[-1]
    s = signal.shift(1).iloc[-1].dropna()
    s = s[close.iloc[-1].reindex(s.index).notna()].dropna()
    if len(s) < min_names:
        return {}
    k = max(1, int(len(s) * q))
    ranked = s.sort_values(ascending=long_low)
    longs, shorts = ranked.index[:k], ranked.index[-k:]
    lw, sw = inv_vol.reindex(longs).fillna(0.0), inv_vol.reindex(shorts).fillna(0.0)
    out: dict[str, float] = {}
    if lw.sum() > 0:
        out.update({x: 0.5 * float(lw[x]) / float(lw.sum()) for x in longs})
    if sw.sum() > 0:
        out.update({x: -0.5 * float(sw[x]) / float(sw.sum()) for x in shorts})
    return out


def xsec_lowvol_returns(
    close: pd.DataFrame, funding: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Cross-sectional LOW-VOLATILITY factor: long the lowest-realised-vol perps, short the highest.

    The low-vol anomaly / volatility risk premium is one of the most robust factors in finance:
    low-vol assets earn higher risk-adjusted returns than high-vol lottery names. Economically
    distinct from funding/momentum/flow -- a vol-based source -- so it is a breadth candidate. Earns
    funding cashflow on the book; decisions use lagged realised vol only.
    """
    signal = close.pct_change(fill_method=None).rolling(lookback).std()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def basis_carry_returns(
    close: pd.DataFrame, funding: pd.DataFrame, basis: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Perp-spot BASIS carry: long backwardated perps (basis low/negative) / short rich premium.

    Distinct from funding (basis captures spot-perp arbitrage pressure, not just leverage demand);
    a rich premium signals crowded longs that mean-revert. Earns funding cashflow on the book.
    """
    signal = basis.rolling(lookback).mean()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=True)


def taker_flow_returns(
    close: pd.DataFrame, funding: pd.DataFrame, taker: pd.DataFrame, adv: dict[str, float],
    *, lookback: int, q: float, band: float, vol_window: int = 30, min_names: int = 12,
) -> np.ndarray:
    """Taker order-flow momentum: long perps with the strongest recent net taker BUYING.

    ``taker`` is the taker-buy fraction (>0.5 = aggressive buyers lifting offers). Persistent buy
    pressure tends to continue short-term -- an order-flow edge orthogonal to funding/price.
    """
    signal = taker.rolling(lookback).mean()
    return _book(close, funding, adv, signal, q=q, band=band, vol_window=vol_window,
                 min_names=min_names, long_low=False)
