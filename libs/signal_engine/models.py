"""Stage 13.5 models — the vocabulary of the signal intelligence engine.

These describe alpha inputs, market state, the per-engine assessments, and the final
``SignalPackage`` that is the *only* object permitted to flow to the Portfolio Engine. Decay
levels reuse ``libs.self_improvement.DecayLevel`` (single source of truth); nothing here
redefines the alpha/portfolio/audit foundation models.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.self_improvement.models import DecayLevel

__all__ = [  # noqa: RUF022  # grouped by concern
    "Direction",
    "Regime",
    "AlphaSignal",
    "MarketState",
    "EdgeEstimate",
    "ExpectedValueResult",
    "ConfidenceResult",
    "QualityResult",
    "PersistenceResult",
    "StabilityResult",
    "SignalDecayResult",
    "FactorExposureResult",
    "ExecutionFeasibility",
    "CrowdingResult",
    "CapacityForecast",
    "PortfolioContextResult",
    "UncertaintyResult",
    "InstitutionalScore",
    "TradeCandidate",
    "SignalPackage",
    "SelectionResult",
    "MonitoringSnapshot",
    "DecayLevel",
]


class Direction(StrEnum):
    """The only decisions the engine may emit."""

    BUY = "buy"
    SELL = "sell"
    FLAT = "flat"

    @property
    def sign(self) -> int:
        return {Direction.BUY: 1, Direction.SELL: -1, Direction.FLAT: 0}[self]


class Regime(StrEnum):
    TREND = "trend"
    RANGE = "range"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CRISIS = "crisis"
    NEUTRAL = "neutral"


class AlphaSignal(BaseModel):
    """One validated alpha's vote on a symbol (the engine's raw input)."""

    model_config = ConfigDict(frozen=True)

    alpha_id: str
    symbol: str
    direction: Direction
    strength: float = Field(ge=0.0, le=1.0)  # conviction 0..1
    expected_return: float = 0.0  # per-trade fractional
    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_win: float = Field(default=0.0, ge=0.0)
    avg_loss: float = Field(default=0.0, ge=0.0)  # positive magnitude
    profit_factor: float | None = None
    sharpe: float = 0.0
    health_score: float = Field(default=100.0, ge=0.0, le=100.0)
    decay_multiplier: float = Field(default=1.0, ge=0.0, le=1.0)
    regime_affinity: dict[str, float] = Field(default_factory=dict)  # regime -> 0..1
    governance_passed: bool = False  # validated through the gauntlet?


class MarketState(BaseModel):
    """The microstructure / regime context a signal is evaluated in."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    regime: Regime = Regime.NEUTRAL
    predicted_regime: Regime = Regime.NEUTRAL
    transition_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    volatility_state: float = Field(default=0.5, ge=0.0, le=1.0)  # 1 = high vol
    spread_bps: float = Field(default=1.0, ge=0.0)
    liquidity_score: float = Field(default=1.0, ge=0.0, le=1.0)
    cross_asset_score: float = Field(default=1.0, ge=0.0, le=1.0)  # confirmation 0..1
    microstructure_score: float = Field(default=1.0, ge=0.0, le=1.0)
    adv_usd: float = Field(default=1e9, ge=0.0)


class EdgeEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_return: float
    expected_pf: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    edge_score: float  # 0-100


class ExpectedValueResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_value: float
    gross_ev: float
    total_cost: float
    positive: bool


class ConfidenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    confidence: float  # 0..1
    components: dict[str, float]


class QualityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    quality_score: float  # 0-100
    components: dict[str, float]
    passed: bool


class PersistenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    persistence_score: float  # 0-100
    components: dict[str, float]


class StabilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stability_score: float  # 0-100
    components: dict[str, float]
    passed: bool


class SignalDecayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decay_level: DecayLevel
    weight_multiplier: float
    confidence_multiplier: float
    recommended_action: str


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    exposures: dict[str, float]
    concentration: float  # 0..1 (max single-factor share)
    acceptable: bool


class ExecutionFeasibility(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_score: float  # 0-100
    fill_probability: float
    expected_slippage_bps: float
    market_impact_bps: float
    spread_cost_bps: float
    passed: bool


class CrowdingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    crowding_score: float  # 0-100 (higher = more crowded = worse)
    acceptable: bool


class CapacityForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    future_capacity_score: float  # 0-100
    future_slippage_estimate: float
    future_market_impact_estimate: float
    maximum_efficient_capital: float
    capacity_confidence: float  # 0..1


class PortfolioContextResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_contribution_score: float  # 0-100
    portfolio_diversification_score: float  # 0-100
    marginal_sharpe_improvement: float
    marginal_sortino_improvement: float
    marginal_calmar_improvement: float
    accept: bool


class UncertaintyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    epistemic_uncertainty: float  # 0..1
    aleatoric_uncertainty: float  # 0..1
    uncertainty_score: float  # 0..1 (higher = worse)


class InstitutionalScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class TradeCandidate(BaseModel):
    """A fully-assessed opportunity, before final BUY/SELL/FLAT selection."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: Direction
    aggregated_strength: float
    alpha_agreement: float  # 0..1
    alpha_breakdown: dict[str, float]
    regime: Regime
    predicted_regime: Regime
    edge: EdgeEstimate
    expected_value: ExpectedValueResult
    confidence: ConfidenceResult
    quality: QualityResult
    persistence: PersistenceResult
    stability: StabilityResult
    decay: SignalDecayResult
    factor_exposures: FactorExposureResult
    execution: ExecutionFeasibility
    crowding: CrowdingResult
    capacity: CapacityForecast
    portfolio_context: PortfolioContextResult
    uncertainty: UncertaintyResult
    tail_risk_score: float
    institutional: InstitutionalScore


class SignalPackage(BaseModel):
    """The exclusive hand-off to the Portfolio Engine. Immutable."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    direction: Direction
    quality_score: float
    confidence: float
    edge_score: float
    expected_return: float
    expected_drawdown: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    expected_pf: float
    expected_value: float
    regime: Regime
    predicted_regime: Regime
    alpha_breakdown: dict[str, float]
    factor_exposures: dict[str, float]
    execution_score: float
    capacity_score: float
    crowding_score: float
    portfolio_contribution: float
    institutional_score: float
    timestamp: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class SelectionResult(BaseModel):
    """The output of one engine run: approved packages + audited rejections."""

    model_config = ConfigDict(frozen=True)

    approved: list[SignalPackage] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)  # symbol -> reason (FLAT)


class MonitoringSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    metrics: dict[str, Any] = Field(default_factory=dict)
