"""portfolio_geometry_engine — optimize portfolio-level compounding, not standalone CAGR.

Favors faster recovery, lower drawdowns, higher diversification, and better compounding
efficiency (convexity). The portfolio's *geometry* is what compounds, so it is optimized over
individual alpha performance.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict


class PortfolioGeometryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_geometry_score: float  # 0-100
    geometric_growth: float
    max_drawdown: float
    recovery_periods: float
    diversification_ratio: float
    convexity: float


def portfolio_geometry(
    portfolio_returns: np.ndarray,
    *,
    diversification_ratio: float = 1.0,
    periods_per_year: float = 252.0,
) -> PortfolioGeometryResult:
    """Score portfolio compounding geometry."""
    arr = np.asarray(portfolio_returns, dtype="float64")
    if len(arr) < 2:
        return PortfolioGeometryResult(
            portfolio_geometry_score=0.0, geometric_growth=0.0, max_drawdown=0.0,
            recovery_periods=float("inf"), diversification_ratio=diversification_ratio,
            convexity=1.0,
        )
    geometric_growth = float(np.log1p(arr).mean() * periods_per_year)
    equity = np.cumprod(1.0 + arr)
    running = np.maximum.accumulate(equity)
    max_drawdown = float((1.0 - equity / running).max())
    mean_ret = float(arr.mean())
    recovery_periods = max_drawdown / mean_ret if mean_ret > 0 else float("inf")

    upside = arr[arr > 0]
    downside = arr[arr < 0]
    up = float(upside.mean()) if len(upside) else 0.0
    down = float(-downside.mean()) if len(downside) else 1e-9
    convexity = up / down if down > 0 else 1.0

    growth_term = min(1.0, max(0.0, geometric_growth / 0.20))
    dd_term = 1.0 - min(1.0, max_drawdown / 0.20)
    recovery_term = 1.0 / (1.0 + (recovery_periods / periods_per_year))
    div_term = min(1.0, (diversification_ratio - 1.0))
    convex_term = min(1.0, convexity / 2.0)
    score = 100.0 * (
        0.30 * growth_term + 0.25 * dd_term + 0.15 * recovery_term
        + 0.15 * div_term + 0.15 * convex_term
    )
    return PortfolioGeometryResult(
        portfolio_geometry_score=score,
        geometric_growth=geometric_growth,
        max_drawdown=max_drawdown,
        recovery_periods=recovery_periods,
        diversification_ratio=diversification_ratio,
        convexity=convexity,
    )
