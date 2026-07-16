"""Stage 14.5 models — hedging, crisis alpha, and exposure management.

Institutional hedging, not retail offset: protect long-term geometric growth via alpha/factor/
regime diversification and crisis alpha, never by cosmetically reducing volatility. Survival
dominates return; geometric growth dominates smoothness. These models describe exposures, scores,
hedge proposals, governance and lifecycle; the engines compute them.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class HedgeType(StrEnum):
    ALPHA = "alpha"        # rebalance toward under-represented alpha families
    FACTOR = "factor"      # reduce a concentrated factor exposure
    REGIME = "regime"      # add exposure to under-covered regimes
    CRISIS = "crisis"      # add crisis-alpha exposure


class AlphaFamily(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    CARRY = "carry"
    MACRO = "macro"
    STRUCTURAL = "structural"


class FactorExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    net_usd: float
    net_directional: float
    beta: float
    volatility_exposure: float
    factor_exposure_score: float  # 0-100 (higher = more concentrated = worse)
    acceptable: bool


class TailRiskResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    tail_loss_probability: float
    expected_tail_loss: float
    extreme_drawdown_risk: float
    correlation_collapse_risk: float
    tail_risk_score: float  # 0-100 (higher = worse)
    acceptable: bool


class CorrelationShockResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    base_avg_correlation: float
    shocked_avg_correlation: float
    diversification_loss: float       # 0..1 fraction of effective bets lost under shock
    correlation_fragility_score: float  # 0-100 (higher = more fragile)
    fragile: bool


class ConcentrationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol_concentration: float
    alpha_concentration: float
    family_concentration: float
    factor_concentration: float
    regime_concentration: float
    concentration_score: float  # 0-100 (higher = more concentrated = worse)
    acceptable: bool


class RegimeExposureResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_regime: dict[str, float]
    regime_balance_score: float  # 0-100 (higher = better balanced)
    uncovered_regimes: list[str]
    balanced: bool


class CrisisAlphaResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    crisis_alpha_score: float  # 0-100 (higher = stronger crisis alpha)
    by_scenario: dict[str, float]
    is_crisis_alpha: bool


class HedgeProposal(BaseModel):
    """A proposed institutional hedge (diversifying tilt / crisis-alpha add), recommend-only."""

    model_config = ConfigDict(frozen=True)

    hedge_type: HedgeType
    target: str                 # family / factor / regime / crisis-alpha id
    rationale: str
    expected_cagr_delta: float  # may be slightly negative if survival/tail justify it
    expected_survival_delta: float
    expected_tail_reduction: float


class HedgeEffectiveness(BaseModel):
    model_config = ConfigDict(frozen=True)

    hedge_effectiveness_score: float  # 0-100
    cagr_contribution: float
    survival_contribution: float
    diversification_contribution: float
    tail_risk_contribution: float
    capacity_impact: float


class HedgeGovernanceVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    reason: str


class Hedge(BaseModel):
    """An active hedge tracked by the lifecycle engine."""

    model_config = ConfigDict(frozen=True)

    hedge_id: str
    hedge_type: HedgeType
    target: str
    purpose: str
    opened_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class HedgeLifecycleDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    close: bool
    reasons: list[str] = Field(default_factory=list)
