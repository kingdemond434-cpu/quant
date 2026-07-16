"""Core models for the Alpha Discovery Factory.

The factory's objective is NOT backtest CAGR. It is sustainable long-term geometric growth
(expected log utility) through a diversified set of statistically-valid, capacity-aware,
regime-robust, low-fragility, independently-failing alphas — subject to survival > 95% and
max drawdown < 20%. These models carry the evidence that justifies (or rejects) each candidate.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.portfolio.models import StrategyType
from libs.validation.economic_prior import MechanismType


class HypothesisCategory(StrEnum):
    SESSION = "session_effects"
    LEAD_LAG = "cross_asset_lead_lag"
    VOL_REGIME = "volatility_regime"
    VOL_EXPANSION = "volatility_expansion"
    VOL_COMPRESSION = "volatility_compression"
    TREND = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    CARRY = "carry"
    SEASONAL = "seasonal"
    MOMENTUM = "momentum"
    RELATIVE_STRENGTH = "relative_strength"
    INTERMARKET = "intermarket"
    RISK_ON_OFF = "risk_on_off"
    REGIME_SWITCHING = "regime_switching"
    MARKET_STRUCTURE = "market_structure"
    CROSS_SECTIONAL = "cross_sectional"
    ENSEMBLE = "ensemble"
    PORTFOLIO_DIVERSIFICATION = "portfolio_diversification"


# Maps each research category to its dominant strategy family and economic mechanism.
CATEGORY_FAMILY: dict[HypothesisCategory, StrategyType] = {
    HypothesisCategory.SESSION: StrategyType.SESSION,
    HypothesisCategory.LEAD_LAG: StrategyType.LEAD_LAG,
    HypothesisCategory.VOL_REGIME: StrategyType.VOLATILITY,
    HypothesisCategory.VOL_EXPANSION: StrategyType.VOLATILITY,
    HypothesisCategory.VOL_COMPRESSION: StrategyType.VOLATILITY,
    HypothesisCategory.TREND: StrategyType.TREND,
    HypothesisCategory.MEAN_REVERSION: StrategyType.MEAN_REVERSION,
    HypothesisCategory.BREAKOUT: StrategyType.TREND,
    HypothesisCategory.CARRY: StrategyType.CARRY,
    HypothesisCategory.SEASONAL: StrategyType.SEASONAL,
    HypothesisCategory.MOMENTUM: StrategyType.MOMENTUM,
    HypothesisCategory.RELATIVE_STRENGTH: StrategyType.MOMENTUM,
    HypothesisCategory.INTERMARKET: StrategyType.LEAD_LAG,
    HypothesisCategory.RISK_ON_OFF: StrategyType.MOMENTUM,
    HypothesisCategory.REGIME_SWITCHING: StrategyType.VOLATILITY,
    HypothesisCategory.MARKET_STRUCTURE: StrategyType.MEAN_REVERSION,
    HypothesisCategory.CROSS_SECTIONAL: StrategyType.MOMENTUM,
    HypothesisCategory.ENSEMBLE: StrategyType.TREND,
    HypothesisCategory.PORTFOLIO_DIVERSIFICATION: StrategyType.MEAN_REVERSION,
}

CATEGORY_MECHANISM: dict[HypothesisCategory, MechanismType] = {
    HypothesisCategory.SESSION: MechanismType.BEHAVIORAL,
    HypothesisCategory.LEAD_LAG: MechanismType.STRUCTURAL,
    HypothesisCategory.VOL_REGIME: MechanismType.RISK_PREMIUM,
    HypothesisCategory.VOL_EXPANSION: MechanismType.STRUCTURAL,
    HypothesisCategory.VOL_COMPRESSION: MechanismType.STRUCTURAL,
    HypothesisCategory.TREND: MechanismType.BEHAVIORAL,
    HypothesisCategory.MEAN_REVERSION: MechanismType.LIQUIDITY,
    HypothesisCategory.BREAKOUT: MechanismType.STRUCTURAL,
    HypothesisCategory.CARRY: MechanismType.RISK_PREMIUM,
    HypothesisCategory.SEASONAL: MechanismType.BEHAVIORAL,
    HypothesisCategory.MOMENTUM: MechanismType.BEHAVIORAL,
    HypothesisCategory.RELATIVE_STRENGTH: MechanismType.BEHAVIORAL,
    HypothesisCategory.INTERMARKET: MechanismType.STRUCTURAL,
    HypothesisCategory.RISK_ON_OFF: MechanismType.RISK_PREMIUM,
    HypothesisCategory.REGIME_SWITCHING: MechanismType.RISK_PREMIUM,
    HypothesisCategory.MARKET_STRUCTURE: MechanismType.LIQUIDITY,
    HypothesisCategory.CROSS_SECTIONAL: MechanismType.BEHAVIORAL,
    HypothesisCategory.ENSEMBLE: MechanismType.BEHAVIORAL,
    HypothesisCategory.PORTFOLIO_DIVERSIFICATION: MechanismType.STRUCTURAL,
}


class AlphaHypothesis(BaseModel):
    """A pre-registered, economically-anchored hypothesis (data only)."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    symbol: str
    category: HypothesisCategory
    family: StrategyType
    mechanism: MechanismType
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class RobustnessScores(BaseModel):
    """Aggregated robustness-engine outputs for one candidate (each 0-100 unless noted)."""

    model_config = ConfigDict(frozen=True)

    fragility: float                 # higher = more fragile (worse)
    parameter_stability: float       # higher = wider plateau (better)
    regime_diversification: float    # higher = more regime-robust (better)
    stress_resilience: float         # higher = survives stress (better)
    tail_risk: float                 # higher = more hidden tail exposure (worse)
    survival_probability: float      # 0-1
    worst_case_drawdown: float       # 0-1 magnitude
    half_life_days: float
    capacity_usd: float


class DiscoveryCandidate(BaseModel):
    """A hypothesis that ran the full pipeline, with its evidence and verdict."""

    model_config = ConfigDict(frozen=True)

    hypothesis: AlphaHypothesis
    expected_cagr: float
    expected_sharpe: float
    dsr: float
    pbo: float
    cost_adjusted_return: float
    log_utility: float
    robustness: RobustnessScores
    accepted: bool
    rejection_reasons: list[str]
    rank: int = 0
    score: float = 0.0


class DiscoveryReport(BaseModel):
    """The factory's output: how many were tried, and the accepted survivors only."""

    model_config = ConfigDict(frozen=True)

    n_generated: int
    n_backtested: int
    n_accepted: int
    accepted: list[DiscoveryCandidate]
    error_budget_note: str
