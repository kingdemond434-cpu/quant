"""Stage 14 models — sleeves, portfolio state, budgets, scores, and the output package.

Stage 14 transforms approved Stage 13.5 :class:`SignalPackage` objects into capital allocations
optimized for long-term compounded wealth. These models describe the allocation vocabulary; the
engines compute them. Reuses Stage 13.5 ``Regime`` and the platform's existing risk primitives.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class AlphaSleeve(StrEnum):
    """Capital is budgeted at the sleeve level before the position level."""

    TREND = "trend"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CARRY = "carry"
    MACRO = "macro"
    OTHER = "other"

    @classmethod
    def from_text(cls, text: str) -> AlphaSleeve:
        try:
            return cls(text.strip().lower().replace(" ", "_"))
        except ValueError:
            return cls.OTHER


class PortfolioState(StrEnum):
    """The portfolio risk regime; modulates budgets, Kelly fractions, and leverage."""

    NORMAL = "normal"
    CAUTION = "caution"
    DEFENSIVE = "defensive"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class RiskBudget(BaseModel):
    """Risk (not capital) budgets that drive allocation."""

    model_config = ConfigDict(frozen=True)

    vol_budget: float = 0.15            # annualized portfolio volatility target
    drawdown_budget: float = 0.20       # max tolerated drawdown
    tail_budget: float = 0.10           # tail-risk allowance
    correlation_budget: float = 0.60    # max acceptable average pairwise correlation
    capacity_budget: float = 0.80       # max capacity utilization


class GeometricGrowthResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_cagr: float
    expected_geometric_return: float
    expected_terminal_wealth: float
    growth_efficiency: float
    geometric_growth_score: float  # 0-100


class GrowthSimResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    cagr_median: float
    cagr_p5: float
    cagr_p95: float
    terminal_wealth_median: float
    probability_of_ruin: float
    expected_log_growth: float
    survival_probability: float


class SurvivalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    survival_probability: float
    probability_of_ruin: float
    stress_survival: float
    survival_score: float  # 0-100


class PortfolioCapacityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_utilization: float  # 0..1
    capacity_score: float        # 0-100
    forecast_slippage: float
    impact_cost: float


class CapacityGovernorAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str          # "ok" | "scale" | "block" | "zero"
    scale_factor: float  # multiplier to apply to size (1.0 = unchanged, 0.0 = blocked)
    reason: str


class StressResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stress_score: float  # 0-100 (higher = more resilient)
    worst_drawdown: float
    by_scenario: dict[str, float]


class ResilienceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    resilience_score: float  # 0-100
    components: dict[str, float]


class CorrelationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    avg_pairwise: float
    max_pairwise: float
    concentration: float  # 0..1
    acceptable: bool


class ConvexityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    skew: float
    convexity: float
    crisis_alpha: float
    convexity_score: float  # 0-100


class EfficiencyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capital_efficiency_score: float  # 0-100
    return_per_risk: float
    return_per_capacity: float


class LeverageDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    leverage: float
    rationale: str


class ReinvestmentDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    reinvestment_rate: float  # 0..1
    rationale: str


class MarginalContribution(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_signal: dict[str, float]
    total: float


class InstitutionalPortfolioScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class KillDecision(BaseModel):
    """Portfolio-level kill criteria (distinct from per-strategy kills)."""

    model_config = ConfigDict(frozen=True)

    halt: bool = False
    defensive_mode: bool = False
    no_new_capital: bool = False
    reasons: list[str] = Field(default_factory=list)


class PortfolioPackage(BaseModel):
    """One symbol's final allocation — Stage 14's output to the Risk Engine."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    sleeve: AlphaSleeve
    allocation: float       # fraction of portfolio capital
    position_size: float    # allocation x leverage x capital (account currency)
    kelly_fraction: float
    leverage: float
    expected_return: float
    expected_sharpe: float
    expected_sortino: float
    expected_calmar: float
    expected_drawdown: float
    geometric_growth_score: float
    survival_score: float
    capacity_score: float
    diversification_score: float
    fragility_score: float
    portfolio_contribution: float
    institutional_score: float
    timestamp: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class PortfolioConstructionResult(BaseModel):
    """The full Stage 14 output: allocations, rejections, state, and kill status."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    packages: list[PortfolioPackage] = Field(default_factory=list)
    rejected: dict[str, str] = Field(default_factory=dict)  # symbol -> reason (allocation 0)
    state: PortfolioState = PortfolioState.NORMAL
    kill: KillDecision = KillDecision()
    total_allocation: float = 0.0
