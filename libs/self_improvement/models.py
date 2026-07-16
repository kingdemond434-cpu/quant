"""Stage 13 models — recommendations and assessments.

Stage 13 is the supervisory intelligence layer. It REUSES the Architecture v1.0 foundation
models (``AlphaCard``, ``AlphaHealth``, ``DecayResult``, ``AlphaState``, ``LiveMetrics`` from
``libs.alpha``; allocations from ``libs.portfolio``) and never redefines them. The models here
describe *recommendations* — Stage 13 may recommend and schedule, but every production weight
change requires Portfolio Engine approval (``requires_portfolio_approval``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow


class HealthLevel(StrEnum):
    ELITE = "elite"          # 90+
    STRONG = "strong"        # 80-89
    STABLE = "stable"        # 70-79
    WEAK = "weak"            # 60-69
    CRITICAL = "critical"    # <60

    @classmethod
    def classify(cls, score: float) -> HealthLevel:
        if score >= 90:
            return cls.ELITE
        if score >= 80:
            return cls.STRONG
        if score >= 70:
            return cls.STABLE
        if score >= 60:
            return cls.WEAK
        return cls.CRITICAL


class DecayLevel(StrEnum):
    HEALTHY = "healthy"
    WATCH = "watch"
    WEAK = "weak"
    DECAYING = "decaying"
    DEAD = "dead"


class AlphaCategory(StrEnum):
    TREND_FOLLOWING = "trend_following"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    BREAKOUT = "breakout"
    CARRY = "carry"
    RELATIVE_VALUE = "relative_value"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    CROSS_ASSET = "cross_asset"
    MACRO = "macro"
    MICROSTRUCTURE = "microstructure"
    OPTIONS = "options"
    MARKET_MAKING = "market_making"
    EVENT_DRIVEN = "event_driven"
    ALTERNATIVE_DATA = "alternative_data"
    OTHER = "other"

    @classmethod
    def from_text(cls, text: str) -> AlphaCategory:
        try:
            return cls(text.strip().lower().replace(" ", "_"))
        except ValueError:
            return cls.OTHER


class ImprovementActionType(StrEnum):
    WEIGHT_CHANGE = "weight_change"
    CAPITAL_REALLOCATION = "capital_reallocation"
    PAUSE = "pause"
    RETIRE = "retire"
    REACTIVATE = "reactivate"
    RESEARCH_PRIORITY = "research_priority"
    ENSEMBLE_UPDATE = "ensemble_update"
    META_INSIGHT = "meta_insight"


class ImprovementAction(BaseModel):
    """One recommended action. Weight/capital actions always require Portfolio Engine approval."""

    model_config = ConfigDict(frozen=True)

    type: ImprovementActionType
    target_id: str | None
    rationale: str
    detail: dict[str, Any] = Field(default_factory=dict)
    requires_portfolio_approval: bool = False


class WeightProposal(BaseModel):
    """A *proposed* set of target weights. Stage 13 may not apply these directly."""

    model_config = ConfigDict(frozen=True)

    weights: dict[str, float]
    rationale: str
    requires_portfolio_approval: bool = True  # always — Stage 13 cannot set production weights


class ResearchPriority(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    priority_score: float
    reason: str


class MetaInsight(BaseModel):
    """A learned relationship. NOT deployable until it passes the validation gauntlet."""

    model_config = ConfigDict(frozen=True)

    description: str
    relationship: dict[str, Any]
    evidence: dict[str, Any] = Field(default_factory=dict)
    deployable: bool = False


class HealthAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    health_score: float  # 0-100
    level: HealthLevel
    components: dict[str, float]


class DecayAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    decay_level: DecayLevel
    decay_score: float  # 0-1 (from libs.alpha.detect_decay)
    recommended_action: str
    weight_multiplier: float
    allow_increase: bool


class ImprovementPlan(BaseModel):
    """The controller's output: recommendations only."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    actions: list[ImprovementAction] = Field(default_factory=list)
    weight_proposal: WeightProposal | None = None
    research_priorities: list[ResearchPriority] = Field(default_factory=list)
