"""Portfolio analytics and capital allocation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np

from libs.portfolio.exposures import calculate_risk_contributions
from libs.portfolio.models import AlphaInput, PortfolioAnalytics


def allocate_capital(weights: Mapping[str, float], total_capital: float) -> dict[str, float]:
    """Translate weights into capital per alpha."""
    return {alpha_id: float(weight) * total_capital for alpha_id, weight in weights.items()}


def portfolio_analytics(
    weights: Mapping[str, float],
    returns: np.ndarray,
    order: Sequence[str],
    *,
    periods_per_year: float = 252.0,
    alphas: Sequence[AlphaInput] | None = None,
) -> PortfolioAnalytics:
    """Compute portfolio analytics from a (T x N) returns matrix aligned to ``order``."""
    matrix = np.asarray(returns, dtype="float64")
    w = np.array([weights[i] for i in order], dtype="float64")
    port_ret = matrix @ w
    n = len(port_ret)
    ann = math.sqrt(periods_per_year)

    mean = float(port_ret.mean()) if n else 0.0
    std = float(port_ret.std(ddof=1)) if n >= 2 else 0.0
    volatility = std * ann
    sharpe = (mean / std * ann) if std > 0 else 0.0

    downside = port_ret[port_ret < 0]
    dstd = float(downside.std(ddof=1)) if len(downside) >= 2 else 0.0
    sortino = (mean / dstd * ann) if dstd > 0 else 0.0

    equity = np.cumprod(1.0 + port_ret) if n else np.array([1.0])
    cagr = float(equity[-1] ** (periods_per_year / n) - 1.0) if n else 0.0
    geometric_growth = float(np.log1p(port_ret).mean() * periods_per_year) if n else 0.0
    running = np.maximum.accumulate(equity)
    max_drawdown = float((equity / running - 1.0).min()) if n else 0.0
    calmar = (cagr / abs(max_drawdown)) if max_drawdown < 0 else 0.0

    cov = np.atleast_2d(np.cov(matrix, rowvar=False))
    rc = calculate_risk_contributions(weights, cov, order)

    factor_contributions: dict[str, float] = {}
    if alphas is not None:
        factor_of = {a.alpha_id: a.factor.value for a in alphas}
        for alpha_id, contribution in rc.items():
            factor = factor_of.get(alpha_id)
            if factor is not None:
                factor_contributions[factor] = factor_contributions.get(factor, 0.0) + contribution

    return PortfolioAnalytics(
        cagr=cagr, geometric_growth=geometric_growth, sharpe=sharpe, sortino=sortino,
        calmar=calmar, max_drawdown=max_drawdown, volatility=volatility,
        risk_contributions=rc, factor_contributions=factor_contributions,
    )
