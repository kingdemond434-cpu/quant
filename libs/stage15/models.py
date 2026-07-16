"""Stage 15 models — the research-factory vocabulary.

Stage 15 discovers, validates, ranks, monitors, and retires alphas. It is optimized for the
*smallest* number of durable, scalable, economically-grounded, low-correlation alphas that survive
institutional validation — not the largest backtest count. These models describe that pipeline;
the engines compute them. Reuses the validation layer's ``MechanismType``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.validation.economic_prior import MechanismType

__all__ = [  # noqa: RUF022  # grouped by concern
    "MechanismType",
    "ResearchRegime",
    "PipelineStage",
    "AlphaScores",
    "AlphaQualityScore",
    "MechanismResult",
    "RegimeValidationResult",
    "ContributionForecast",
    "ResearchPriority",
    "AlphaGovernanceVerdict",
    "ResearchKillDecision",
    "PipelineRecord",
    "ResearchPipelineResult",
]


class ResearchRegime(StrEnum):
    """Environments every alpha is validated across."""

    BULL = "bull"
    BEAR = "bear"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    TRENDING = "trending"
    RANGE = "range"
    CRISIS = "crisis"


class PipelineStage(StrEnum):
    """The furthest stage an alpha has reached in the live research pipeline."""

    DISCOVERY = "discovery"
    VALIDATION = "validation"
    WALK_FORWARD = "walk_forward"
    SHADOW = "shadow"
    PAPER = "paper"
    ALLOCATION = "allocation"
    MONITORING = "monitoring"
    REVALIDATION = "revalidation"
    RETIREMENT = "retirement"
    REJECTED = "rejected"


class AlphaScores(BaseModel):
    """Per-alpha measurements feeding the quality score. ``fragility``/``decay`` higher = worse."""

    model_config = ConfigDict(frozen=True)

    expected_return: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    calmar: float = 0.0
    capacity_score: float = 0.0        # 0-100
    fragility_score: float = 0.0       # 0-100 (higher = more fragile)
    stability_score: float = 0.0       # 0-100
    decay_score: float = 0.0           # 0-100 (higher = more decayed)
    survival_score: float = 0.0        # 0-100
    diversification_score: float = 0.0  # 0-100
    economic_score: float = 0.0        # 0-100


class AlphaQualityScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float  # 0-100
    components: dict[str, float]


class MechanismResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    mechanism: MechanismType | None
    missing: list[str] = Field(default_factory=list)
    message: str


class RegimeValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    regime_resilience_score: float  # 0-100
    by_regime: dict[str, float]
    productive_fraction: float
    robust: bool


class ContributionForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    cagr_contribution: float
    sharpe_contribution: float
    diversification_benefit: float  # 0..1
    survival_benefit: float         # 0..1
    correlation_impact: float       # 0..1 (higher = more correlated = worse)
    net_beneficial: bool


class ResearchPriority(BaseModel):
    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    research_priority_score: float  # 0-100
    components: dict[str, float]


class AlphaGovernanceVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    gates: dict[str, bool]
    rejected_reasons: list[str] = Field(default_factory=list)


class ResearchKillDecision(BaseModel):
    """The research kill-switch: protects research capital like risk engines protect trading."""

    model_config = ConfigDict(frozen=True)

    halt: bool
    reasons: list[str] = Field(default_factory=list)


class PipelineRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    stage: PipelineStage
    quality_score: float
    accepted: bool
    note: str = ""


class ResearchPipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    records: list[PipelineRecord] = Field(default_factory=list)
    allocated: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    kill: ResearchKillDecision = ResearchKillDecision(halt=False)
