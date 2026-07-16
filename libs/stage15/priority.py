"""Research prioritization — rank research opportunities by expected value of research.

Prioritizes hypotheses with high expected edge, low correlation to existing alphas, large capacity,
strong economic rationale, and high regime-diversification potential. Highest scores get resources
first. Distinct from the Stage 13 ResearchPriorityEngine (category budgeting) — this ranks ideas.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from libs.stage15.models import ResearchPriority

_WEIGHTS: dict[str, float] = {
    "expected_edge": 0.30,
    "uncorrelated": 0.25,
    "capacity": 0.15,
    "economic_strength": 0.20,
    "regime_diversification": 0.10,
}


class ResearchCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    hypothesis_id: str
    expected_edge: float = Field(default=0.0, ge=0.0, le=1.0)
    correlation_to_existing: float = Field(default=0.0, ge=0.0, le=1.0)
    capacity: float = Field(default=0.0, ge=0.0, le=1.0)
    economic_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    regime_diversification_potential: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchPriorityEngine:
    """Ranks research candidates by expected value of research (recommend-only)."""

    def score(self, candidate: ResearchCandidate) -> ResearchPriority:
        components = {
            "expected_edge": candidate.expected_edge,
            "uncorrelated": 1.0 - candidate.correlation_to_existing,
            "capacity": candidate.capacity,
            "economic_strength": candidate.economic_strength,
            "regime_diversification": candidate.regime_diversification_potential,
        }
        score = 100.0 * sum(_WEIGHTS[k] * v for k, v in components.items())
        return ResearchPriority(
            hypothesis_id=candidate.hypothesis_id, research_priority_score=score,
            components=components,
        )

    def rank(self, candidates: Sequence[ResearchCandidate]) -> list[ResearchPriority]:
        return sorted(
            (self.score(c) for c in candidates),
            key=lambda p: p.research_priority_score,
            reverse=True,
        )
