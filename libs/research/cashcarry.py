"""Delta-neutral cash-and-carry return (long spot + short perp).

Harvests funding + basis convergence with ~zero directional exposure (the spot leg hedges the perp's
price risk). Shared by the backtest and the forward shadow so the out-of-sample comparison is
apples-to-apples. Decisions use lagged funding only; no look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cashcarry_returns(funding: pd.DataFrame, basis: pd.DataFrame, *, lookback: int = 3,
                      q: float = 0.2, band: float = 0.02, cost: float = 8e-4) -> np.ndarray:
    """Daily delta-neutral carry: + funding collected, + basis convergence, - turnover cost.

    Cross-sectional: long-spot/short-perp on the top-q funding names (collect positive funding),
    long-perp/short-spot on the bottom-q (collect negative funding). Weights are equal within each
    leg, gross-normalised, turnover-banded."""
    sig = funding.rolling(lookback).mean().shift(1)
    dbasis = basis.diff()
    out = np.zeros(len(funding))
    prev = pd.Series(0.0, index=funding.columns)
    for t in range(1, len(funding)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            out[t] = float((prev * funding.iloc[t].reindex(prev.index).fillna(0.0)).sum())
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=funding.columns)
        w[ranked.index[-k:]] = 0.5 / k                 # high funding -> short perp/long spot (+)
        w[ranked.index[:k]] = -0.5 / k                 # low/neg funding -> long perp/short spot (-)
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        fund_pnl = float((w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        basis_pnl = float(-(w * dbasis.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float((w - prev).abs().sum()) * cost
        out[t] = fund_pnl + basis_pnl - turn
        prev = w
    return out


def spot_basis_carry_returns(funding: pd.DataFrame, basis: pd.DataFrame, *, lookback: int = 3,
                             q: float = 0.2, band: float = 0.02, cost: float = 8e-4) -> np.ndarray:
    """Second spot sleeve: delta-neutral carry weighted by the perp-premium BASIS, not funding.

    When a perp trades rich to spot (high positive basis / contango), short-perp/long-spot harvests
    BOTH the convergence as basis decays to zero AND the funding the longs pay. Distinct signal from
    cashcarry_returns (basis level vs funding rate) -> adds spot breadth. Lagged basis only."""
    sig = basis.rolling(lookback).mean().shift(1)
    dbasis = basis.diff()
    out = np.zeros(len(basis))
    prev = pd.Series(0.0, index=basis.columns)
    for t in range(1, len(basis)):
        s = sig.iloc[t].dropna()
        if len(s) < 12:
            continue
        k = max(1, int(len(s) * q))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=basis.columns)
        w[ranked.index[-k:]] = 0.5 / k                 # rich perp -> short perp/long spot (+)
        w[ranked.index[:k]] = -0.5 / k                 # cheap perp -> long perp/short spot (-)
        delta = (w - prev).abs()
        w = w.where(delta > band, prev)
        fund_pnl = float((w * funding.iloc[t].reindex(w.index).fillna(0.0)).sum())
        conv_pnl = float(-(w * dbasis.iloc[t].reindex(w.index).fillna(0.0)).sum())
        turn = float((w - prev).abs().sum()) * cost
        out[t] = fund_pnl + conv_pnl - turn
        prev = w
    return out
