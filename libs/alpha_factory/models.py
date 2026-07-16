"""Alpha Factory models — research vocabulary (recommend-only; the factory never trades).

Reuses the Stage 13 ``AlphaCategory`` (single source of truth for categories) and the discovery
layer's economic models. Everything here is data describing ideas, DNA, lineage, and research
recommendations; nothing here promotes alphas or allocates production capital.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.self_improvement.models import AlphaCategory

__all__ = [  # noqa: RUF022  # grouped by concern
    "AlphaCategory",
    "ResearchResult",
    "FailureCause",
    "AlphaDNA",
    "Hypothesis",
    "IdeaRecord",
    "IdeaCandidate",
    "IdeaScore",
    "ResearchScoreResult",
    "SimilarityResult",
    "CrowdingEstimate",
    "CapacityIntelligenceResult",
    "DriftResult",
    "FamilyNode",
    "AllocationResult",
    "AlphaFactoryReport",
]


class ResearchResult(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"


class FailureCause(StrEnum):
    NONE = "none"
    OVERFIT = "overfit"
    REGIME_DEPENDENT = "regime_dependent"
    CAPACITY_FAILURE = "capacity_failure"
    DATA_LEAKAGE = "data_leakage"
    CROWDED_EDGE = "crowded_edge"
    INSUFFICIENT_ROBUSTNESS = "insufficient_robustness"
    EXECUTION_FAILURE = "execution_failure"
    CORRELATION_FAILURE = "correlation_failure"
    VALIDATION_FAILURE = "validation_failure"


class AlphaDNA(BaseModel):
    """A structural fingerprint of an alpha — what kind of thing it is."""

    model_config = ConfigDict(frozen=True)

    signal_type: str
    market: str
    timeframe: str
    holding_period: str
    factor_exposures: dict[str, float] = Field(default_factory=dict)
    regime_affinity: dict[str, float] = Field(default_factory=dict)
    volatility_sensitivity: float = 0.0
    trend_sensitivity: float = 0.0
    mean_reversion_sensitivity: float = 0.0
    capacity_estimate: float = 0.0
    turnover_profile: float = 0.0
    risk_profile: float = 0.0

    def numeric_vector(self) -> list[float]:
        """A fixed-order numeric embedding of the scalar genes (for similarity/clustering)."""
        return [
            self.volatility_sensitivity,
            self.trend_sensitivity,
            self.mean_reversion_sensitivity,
            self.turnover_profile,
            self.risk_profile,
        ]


class Hypothesis(BaseModel):
    """A research hypothesis to be tested (data only; outcome tracked in research memory)."""

    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    category: str
    features: list[str] = Field(default_factory=list)
    expected_edge: float = 0.0
    rationale: str = ""
    created_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))


class IdeaRecord(BaseModel):
    """A durable research-memory record of one tested idea/hypothesis and its outcome."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    category: str
    statement: str
    result: ResearchResult
    failure_cause: FailureCause = FailureCause.NONE
    failure_reason: str | None = None
    success_reason: str | None = None
    failure_stage: str | None = None
    lessons: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    predecessor_id: str | None = None


class IdeaCandidate(BaseModel):
    """A future research idea awaiting prioritization."""

    model_config = ConfigDict(frozen=True)

    idea_id: str
    category: str
    statement: str = ""
    expected_edge: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_robustness: float = Field(default=0.0, ge=0.0, le=1.0)
    expected_capacity: float = Field(default=0.0, ge=0.0, le=1.0)
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    crowding: float = Field(default=0.0, ge=0.0, le=1.0)
    regime_need: float = Field(default=0.0, ge=0.0, le=1.0)
    portfolio_need: float = Field(default=0.0, ge=0.0, le=1.0)


class IdeaScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    idea_id: str
    category: str
    idea_priority_score: float  # 0-100
    components: dict[str, float]


class ResearchScoreResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    research_score: float  # 0-100
    components: dict[str, float]


class SimilarityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    signal_similarity: float
    return_similarity: float
    factor_similarity: float
    feature_similarity: float
    overall: float  # 0..1
    is_duplicate: bool


class CrowdingEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_crowding: float
    factor_crowding: float
    style_crowding: float
    crowding_score: float  # 0..1 (higher = more crowded)
    priority_multiplier: float  # <1 dampens crowded research


class CapacityIntelligenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    market_capacity_usd: float
    expected_slippage: float
    liquidity_depth: float
    scalability_score: float  # 0-100


class DriftResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    psi: float
    drifted: bool
    recommendation: str


class FamilyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    alpha_id: str
    parent_id: str | None
    mutation_type: str
    created_at: str
    performance: float = 0.0


class AllocationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    allocations: dict[str, float]  # category -> fraction (sums to ~1)
    rationale: dict[str, str]


class AlphaFactoryReport(BaseModel):
    """The factory's recommendation output. Recommend-only; never trades or allocates capital."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    research_priorities: list[IdeaScore] = Field(default_factory=list)
    allocation: AllocationResult | None = None
    portfolio_gaps: list[str] = Field(default_factory=list)
    regime_gaps: list[str] = Field(default_factory=list)
    notes: str = ""
