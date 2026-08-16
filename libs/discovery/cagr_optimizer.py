"""CAGR / log-utility optimization engine.

Maximizes geometric growth (expected log utility) of a set of validated alphas via Bayesian
Kelly + confidence scaling, volatility targeting, and correlation-aware allocation — then scales
exposure *down* until survival > 95% and max drawdown < 20%. Never levers beyond the risk limit.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.discovery.errors import DiscoveryError
from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import expected_log_growth
from libs.portfolio.engine import build_portfolio
from libs.portfolio.models import AlphaInput, StrategyType
from libs.risk.instruments import Factor
from libs.risk.kelly import calculate_bayesian_kelly
from libs.risk.vol_target import realized_volatility, vol_target


class CAGROptimization(BaseModel):
    model_config = ConfigDict(frozen=True)

    #: Per-alpha allocations. **THEY DO NOT SUM TO `leverage`, AND THE COMMENT HERE SAID THEY DID
    #: UNTIL 2026-08-16.** `build_portfolio` returns a RISK BUDGET whose weights sum to less than
    #: one (0.4 on a two-alpha book, being 0.2 apiece), and this module multiplies that budget by
    #: `leverage` -- so the deployed gross is `sum(base_weights) * leverage`, not `leverage`.
    #:
    #: The discrepancy matters in whichever direction a caller trusts. Sizing from `leverage`
    #: deploys 2.5x what the weights specify; sizing from the weights deploys 40% of what
    #: `leverage` advertises. Both readings are defensible from the old comment, which is what
    #: made it worse than no comment. **`sum(weights.values())` IS THE DEPLOYED GROSS**; `leverage`
    #: is the scalar applied to the risk budget, and the two are equal only when the budget
    #: happens to sum to one. Pinned by tests/discovery/test_cagr_optimizer.py.
    weights: dict[str, float]
    leverage: float
    expected_log_growth: float
    survival_probability: float
    worst_case_drawdown: float
    passed: bool

    def __bool__(self) -> bool:
        return self.passed


def optimize_allocation(
    returns_by_alpha: Mapping[str, np.ndarray],
    *,
    periods_per_year: float = 252.0,
    target_vol: float = 0.15,
    dd_limit: float = 0.20,
    survival_min: float = 0.95,
    kelly_cap: float = 0.25,
    leverage_cap: float = 1.0,
    n_sims: int = 800,
    seed: int = 0,
) -> CAGROptimization:
    """Allocate across alphas for maximum survivable geometric growth."""
    ids = list(returns_by_alpha)
    if not ids:
        raise DiscoveryError("at least one alpha is required")
    length = min(len(returns_by_alpha[i]) for i in ids)
    if length < 10:
        raise DiscoveryError("need >= 10 aligned return observations")
    matrix = np.column_stack(
        [np.asarray(returns_by_alpha[i], dtype="float64")[-length:] for i in ids]
    )

    # Correlation-aware base weights (prefers multiple uncorrelated alphas).
    alphas = [
        AlphaInput(
            alpha_id=i,
            volatility=max(1e-6, realized_volatility(matrix[:, k], annualization=periods_per_year)),
            factor=Factor.FX,
            strategy_type=StrategyType.TREND,
            expected_sharpe=float(np.mean(matrix[:, k]) / (np.std(matrix[:, k], ddof=1) + 1e-12)),
        )
        for k, i in enumerate(ids)
    ]
    correlation = np.corrcoef(matrix, rowvar=False) if len(ids) > 1 else None
    target = build_portfolio(alphas, correlation=correlation, method="optimize")
    base_weights = np.array([target.weights[i] for i in ids], dtype="float64")

    portfolio_returns = matrix @ base_weights
    mu_hat = float(portfolio_returns.mean())
    sigma = float(portfolio_returns.std(ddof=1))
    se_mu = sigma / np.sqrt(length) if sigma > 0 else 0.0
    variance = sigma**2 if sigma > 0 else 1e-12

    # Bayesian Kelly leverage, taken as a fraction (Kelly cap) of full Kelly, then vol-targeted.
    bayes = calculate_bayesian_kelly(mu_hat, se_mu, variance, z=1.0)
    kelly_leverage = min(leverage_cap, bayes * (kelly_cap / 0.25) * kelly_cap)
    port_vol_annual = realized_volatility(portfolio_returns, annualization=periods_per_year)
    vol_scalar = vol_target(port_vol_annual, target_vol=target_vol, k_min=0.0, k_max=1.0)
    leverage = float(min(leverage_cap, max(0.0, kelly_leverage) * vol_scalar))

    # Scale down until survival and drawdown constraints hold.
    survival = monte_carlo_survival(
        portfolio_returns * leverage, n_sims=n_sims, dd_limit=dd_limit,
        survival_min=survival_min, seed=seed,
    )
    for _ in range(8):
        if survival.passed and survival.worst_case_drawdown < dd_limit:
            break
        leverage *= 0.7
        survival = monte_carlo_survival(
            portfolio_returns * leverage, n_sims=n_sims, dd_limit=dd_limit,
            survival_min=survival_min, seed=seed,
        )

    weights = {i: float(base_weights[k] * leverage) for k, i in enumerate(ids)}
    return CAGROptimization(
        weights=weights,
        leverage=leverage,
        expected_log_growth=expected_log_growth(
            portfolio_returns * leverage, periods_per_year=periods_per_year
        ),
        survival_probability=survival.survival_probability,
        worst_case_drawdown=survival.worst_case_drawdown,
        passed=survival.passed and survival.worst_case_drawdown < dd_limit,
    )
