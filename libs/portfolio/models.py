"""Portfolio inputs, constraints, and result models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.risk.instruments import Factor


class StrategyType(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    CARRY = "carry"
    SESSION = "session"
    LEAD_LAG = "lead_lag"
    SEASONAL = "seasonal"


class AlphaInput(BaseModel):
    """One alpha presented to the portfolio engine."""

    model_config = ConfigDict(frozen=True)

    alpha_id: str
    volatility: float = Field(gt=0)  # annualized
    factor: Factor
    strategy_type: StrategyType
    expected_return: float = 0.0
    expected_sharpe: float = 0.0
    expected_drawdown: float = 0.0
    symbol: str | None = None
    asset_class: str | None = None
    decay_score: float = 0.0  # 0 healthy .. 1 decayed
    stability: float = 1.0  # 1 stable .. 0 unstable


class PortfolioConstraints(BaseModel):
    """Hard caps the constructed portfolio must respect."""

    model_config = ConfigDict(frozen=True)

    max_weight: float = 0.25
    min_weight: float = 0.0
    max_factor_weight: float = 0.40
    max_strategy_weight: float = 0.50
    max_asset_class_weight: float = 0.60
    long_only: bool = True
    sum_to_one: bool = True


class PortfolioTarget(BaseModel):
    """The constructed target allocation plus its analytics."""

    model_config = ConfigDict(frozen=True)

    weights: dict[str, float]
    method: str
    factor_exposures: dict[str, float]
    strategy_exposures: dict[str, float]
    risk_contributions: dict[str, float]
    diversification_ratio: float
    effective_bets: float
    binding_constraints: list[str]


class PortfolioAnalytics(BaseModel):
    """Realized/expected portfolio analytics from a returns matrix."""

    model_config = ConfigDict(frozen=True)

    cagr: float
    geometric_growth: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    volatility: float
    risk_contributions: dict[str, float]
    factor_contributions: dict[str, float]


class RebalanceResult(BaseModel):
    """The outcome of a rebalance decision."""

    model_config = ConfigDict(frozen=True)

    rebalanced: bool
    trades: dict[str, float]
    turnover: float
    reason: str
