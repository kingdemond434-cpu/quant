"""Covariance helpers for the portfolio engine."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np

from libs.portfolio.errors import PortfolioError
from libs.portfolio.models import AlphaInput


def covariance_from_alphas(
    alphas: Sequence[AlphaInput], correlation: np.ndarray | None = None
) -> np.ndarray:
    """Build a covariance matrix from per-alpha volatilities and an optional correlation matrix."""
    vols = np.array([a.volatility for a in alphas], dtype="float64")
    n = len(vols)
    if n == 0:
        raise PortfolioError("at least one alpha is required")
    if correlation is None:
        return cast("np.ndarray", np.diag(vols**2))
    corr = np.asarray(correlation, dtype="float64")
    if corr.shape != (n, n):
        raise PortfolioError(f"correlation shape {corr.shape} != ({n}, {n})")
    return cast("np.ndarray", np.outer(vols, vols) * corr)


def cov_to_corr(cov: np.ndarray) -> np.ndarray:
    """Convert a covariance matrix to a correlation matrix."""
    std = np.sqrt(np.diag(cov))
    std_safe = np.where(std > 0, std, 1.0)
    corr = cov / np.outer(std_safe, std_safe)
    np.fill_diagonal(corr, 1.0)
    return cast("np.ndarray", corr)


# --------------------------------------------------------------------------- dynamic forecasting
# Static full-sample correlation is dangerous in crypto: in a crash everything correlates and a
# static risk-parity book is suddenly over-concentrated. These forecast next-period covariance
# (EWMA) and allocate by equal risk contribution (ERC) -- correlation-aware, so the book de-risks
# automatically when sleeves start co-moving. All estimates use only past data (no look-ahead).

def ewma_cov(returns: np.ndarray, lam: float = 0.94) -> np.ndarray:
    """EWMA covariance forecast (latest) from a T x N matrix. lam~0.94 ~= 33-day half-life."""
    r = np.asarray(returns, dtype="float64")
    r = r[~np.isnan(r).any(axis=1)]
    n = r.shape[1] if r.ndim == 2 else 0
    if len(r) < n + 2:
        return cast("np.ndarray", np.cov(r, rowvar=False)) if len(r) > 1 else np.eye(max(n, 1))
    mean = r.mean(axis=0)
    cov = np.cov(r, rowvar=False)
    for t in range(len(r)):
        x = (r[t] - mean).reshape(-1, 1)
        cov = lam * cov + (1.0 - lam) * (x @ x.T)
    return cast("np.ndarray", cov)


def erc_weights(cov: np.ndarray, *, iters: int = 250, max_weight: float = 0.40) -> np.ndarray:
    """Long-only equal-risk-contribution weights (correlation-aware), capped per name.

    Equalizes each name's risk *contribution* rc_i = w_i (cov w)_i via a damped multiplicative
    fixed point. For uncorrelated assets this reduces to inverse-vol (the ERC solution there).
    """
    n = cov.shape[0]
    d = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    w = (1.0 / d)
    w = w / w.sum()
    for _ in range(iters):
        rc = np.clip(w * (cov @ w), 1e-15, None)         # risk contribution per name
        w = w * np.sqrt(rc.mean() / rc)                  # damped step toward equal rc
        w = np.clip(w, 0.0, None)
        s = w.sum()
        if s <= 0:
            return np.asarray(np.ones(n) / n, dtype="float64")
        w = w / s
    for _ in range(8):
        over = w > max_weight
        if not over.any():
            break
        excess = float((w[over] - max_weight).sum())
        w[over] = max_weight
        room = ~over & (w > 0)
        if not room.any():
            break
        w[room] += excess * (w[room] / w[room].sum())
    return np.asarray(w / w.sum(), dtype="float64")


def cov_forecast_portfolio(
    returns: np.ndarray, *, lam: float = 0.94, lookback: int = 252,
    min_obs: int = 90, max_weight: float = 0.40, band: float = 0.03, rebal_cost: float = 5e-4,
) -> np.ndarray:
    """Daily portfolio returns using forecast-covariance ERC weights from the trailing window.

    Transaction-cost-aware: weights only move when the target shifts beyond ``band`` (a no-trade
    band that kills churn), and each rebalance pays ``rebal_cost`` per unit of weight turnover, so
    the reported return is net of the cost of acting on the forecast -- not a frictionless ideal.
    """
    r = np.asarray(returns, dtype="float64")
    t_total, n = r.shape
    out = np.zeros(t_total, dtype="float64")
    w = np.ones(n) / n
    for t in range(t_total):
        if t > min_obs:
            window = r[max(0, t - lookback):t]
            window = window[~np.isnan(window).any(axis=1)]
            if len(window) > min_obs:
                # EV gate: only fund sleeves with positive trailing mean (ERC alone would risk-
                # weight the losers too). Correlation-aware sizing across the survivors.
                live = np.flatnonzero(window.mean(axis=0) > 0.0)
                target = np.zeros(n)
                if len(live) >= 1:
                    cov = ewma_cov(window[:, live], lam)
                    target[live] = erc_weights(cov, max_weight=max_weight)
                if np.abs(target - w).sum() > band:      # no-trade band kills churn
                    out[t] -= float(np.abs(target - w).sum()) * rebal_cost
                    w = target
        out[t] += float(w @ np.nan_to_num(r[t]))
    return out
