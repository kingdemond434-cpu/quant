"""Alpha discovery engine — coordinate the idea lifecycle (recommend-only).

Pipeline: generate -> score -> prioritize -> (research/validate happen in the discovery+validation
layers) -> archive -> learn. This engine handles the non-trading coordination: prioritizing ideas
and archiving outcomes to research memory so the factory compounds knowledge. It never validates,
promotes, or allocates capital itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AlphaCategory,
    FailureCause,
    Hypothesis,
    IdeaCandidate,
    IdeaRecord,
    IdeaScore,
    ResearchResult,
)
from libs.alpha_factory.research_memory import ResearchMemory


class AlphaDiscoveryEngine:
    """Coordinates idea generation, prioritization, archival, and learning."""

    def __init__(
        self,
        memory: ResearchMemory,
        *,
        hypothesis_engine: HypothesisEngine | None = None,
        ranking_engine: IdeaRankingEngine | None = None,
    ) -> None:
        self.memory = memory
        self.hypothesis_engine = hypothesis_engine or HypothesisEngine()
        self.ranking_engine = ranking_engine or IdeaRankingEngine()

    def generate(self, categories: Sequence[AlphaCategory]) -> list[Hypothesis]:
        return self.hypothesis_engine.generate(categories, memory=self.memory)

    def prioritize(self, candidates: Sequence[IdeaCandidate]) -> list[IdeaScore]:
        return self.ranking_engine.rank(candidates)

    def archive(
        self,
        *,
        category: str,
        statement: str,
        result: ResearchResult,
        failure_cause: FailureCause = FailureCause.NONE,
        failure_reason: str | None = None,
        success_reason: str | None = None,
        failure_stage: str | None = None,
        lessons: str | None = None,
        metrics: Mapping[str, Any] | None = None,
        predecessor_id: str | None = None,
    ) -> IdeaRecord:
        return self.memory.record(
            category=category, statement=statement, result=result,
            failure_cause=failure_cause, failure_reason=failure_reason,
            success_reason=success_reason, failure_stage=failure_stage, lessons=lessons,
            metrics=metrics, predecessor_id=predecessor_id,
        )

    def learn(self) -> dict[str, float]:
        """Per-category success rates compounded from all archived research."""
        return self.hypothesis_engine.learn(self.memory)
