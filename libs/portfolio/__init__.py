"""``libs.portfolio`` — portfolio construction engine.

Risk parity, HRP, robust optimization, correlation/exposure/factor controls, a diversification
engine, rebalancing, and full analytics. Risk overrides alpha: the engine proposes constrained
target weights; the risk gate disposes.
"""

from __future__ import annotations

from libs.portfolio.analytics import allocate_capital, portfolio_analytics
from libs.portfolio.constraints import apply_constraints
from libs.portfolio.covariance import cov_to_corr, covariance_from_alphas
from libs.portfolio.diversification import (
    apply_correlation_controls,
    concentration,
    diversification_ratio,
    effective_bets,
)
from libs.portfolio.engine import PortfolioEngine, build_portfolio
from libs.portfolio.errors import PortfolioError
from libs.portfolio.exposures import (
    calculate_asset_class_exposures,
    calculate_factor_exposures,
    calculate_risk_contributions,
    calculate_strategy_exposures,
    calculate_symbol_exposures,
)
from libs.portfolio.factor_model import FactorRiskModel, ShrinkageCovariance
from libs.portfolio.hrp import hrp_weights
from libs.portfolio.models import (
    AlphaInput,
    PortfolioAnalytics,
    PortfolioConstraints,
    PortfolioTarget,
    RebalanceResult,
    StrategyType,
)
from libs.portfolio.multiperiod import MultiPeriodOptimizer, MultiPeriodPlan
from libs.portfolio.optimize import optimize_portfolio
from libs.portfolio.rebalance import rebalance
from libs.portfolio.risk_parity import allocate_risk, risk_parity_weights

__all__ = [  # noqa: RUF022  # grouped by concern
    # models
    "AlphaInput",
    "StrategyType",
    "PortfolioConstraints",
    "PortfolioTarget",
    "PortfolioAnalytics",
    "RebalanceResult",
    # covariance
    "covariance_from_alphas",
    "cov_to_corr",
    "ShrinkageCovariance",
    "FactorRiskModel",
    # allocators
    "risk_parity_weights",
    "allocate_risk",
    "hrp_weights",
    "optimize_portfolio",
    "allocate_capital",
    # multi-period
    "MultiPeriodOptimizer",
    "MultiPeriodPlan",
    # controls / constraints
    "apply_constraints",
    "apply_correlation_controls",
    # exposures / risk contributions
    "calculate_factor_exposures",
    "calculate_strategy_exposures",
    "calculate_asset_class_exposures",
    "calculate_symbol_exposures",
    "calculate_risk_contributions",
    # diversification
    "diversification_ratio",
    "concentration",
    "effective_bets",
    # rebalancing / analytics
    "rebalance",
    "portfolio_analytics",
    # engine
    "build_portfolio",
    "PortfolioEngine",
    # errors
    "PortfolioError",
]
