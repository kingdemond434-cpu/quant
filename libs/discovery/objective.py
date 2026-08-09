"""The factory objective — expected log utility (geometric growth), not backtest CAGR.

Provides the geometric-growth objective and a composite discovery score that prefers higher log
growth, higher diversification, lower correlation, lower failure dependency, longer half-life,
sufficient capacity for the book actually deployed, wider parameter plateaus — and penalizes
fragility, tail risk, and low survival.
"""

from __future__ import annotations

import numpy as np

from libs.research.capacity_policy import capacity_fit, live_book_usd, live_sleeves


def expected_log_growth(returns: np.ndarray, *, periods_per_year: float = 252.0) -> float:
    """Annualized expected log growth: E[ln(1 + r)] * periods_per_year."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) == 0 or (arr <= -1.0).any():
        return 0.0
    return float(np.log1p(arr).mean() * periods_per_year)


def log_utility(returns: np.ndarray) -> float:
    """Per-period expected log utility E[ln(1 + r)] (the quantity to maximize)."""
    arr = np.asarray(returns, dtype="float64")
    if len(arr) == 0 or (arr <= -1.0).any():
        return 0.0
    return float(np.log1p(arr).mean())


def discovery_score(
    *,
    log_growth: float,
    survival_probability: float,
    diversification_contribution: float,
    average_correlation: float,
    failure_dependency_score: float,
    half_life_days: float,
    capacity_usd: float,
    fragility_score: float,
    tail_risk_score: float,
    parameter_plateau_score: float,
    deployed_equity_usd: float | None = None,
    n_sleeves: int | None = None,
    sleeve: str | None = None,
) -> float:
    """Composite rank score that maximizes sustainable geometric growth under robustness."""
    growth = max(0.0, log_growth)
    survival = max(0.0, min(1.0, survival_probability))
    corr_term = max(0.0, 1.0 - max(0.0, average_correlation))
    failure_term = 1.0 - min(1.0, failure_dependency_score / 100.0)
    fragility_term = 1.0 - min(1.0, fragility_score / 100.0)
    tail_term = 1.0 - min(1.0, tail_risk_score / 100.0)
    plateau_term = min(1.0, parameter_plateau_score / 100.0)
    half_life_term = min(1.0, half_life_days / 365.0)
    # §42 PARITY. This was `min(1, capacity_usd / 1e6)`, which handed a $1M-capacity idea a 1.9x
    # rank advantage over a $50k one -- i.e. the composite ranking quietly undid the survival
    # gate's fix and kept steering the desk at fund-shaped edges. Capacity now scores as
    # SUFFICIENCY for the book actually deployed and goes FLAT above it, because capacity you
    # cannot fill is not an advantage you own.
    # None means "read the live book", which is what keeps the ratio self-scaling as equity grows.
    capacity_term = capacity_fit(
        capacity_usd,
        live_book_usd() if deployed_equity_usd is None else deployed_equity_usd,
        live_sleeves() if n_sleeves is None else n_sleeves,
        sleeve=sleeve,
    )
    diversification_term = 1.0 + max(0.0, diversification_contribution)

    return (
        growth
        * survival
        * corr_term
        * failure_term
        * fragility_term
        * tail_term
        * (0.5 + 0.5 * plateau_term)
        * (0.5 + 0.5 * half_life_term)
        * (0.5 + 0.5 * capacity_term)
        * diversification_term
    )
