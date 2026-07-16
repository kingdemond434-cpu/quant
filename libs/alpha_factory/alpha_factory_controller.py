"""Alpha Factory controller — the master research coordinator (recommend-only).

Wires the research engines together and emits research recommendations: priorities, budget
allocation, and portfolio/regime gaps. Governance is structural and explicit: the factory MAY
generate/rank/allocate-research/archive/recommend, but MAY NOT promote or retire alphas, change
risk or validation thresholds, or allocate production capital — those raise.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NoReturn

from libs.alpha_factory.alpha_discovery_engine import AlphaDiscoveryEngine
from libs.alpha_factory.alpha_embedding_engine import AlphaEmbeddingEngine
from libs.alpha_factory.alpha_family_tree import AlphaFamilyTree
from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
from libs.alpha_factory.concept_evolution_engine import ConceptEvolutionEngine
from libs.alpha_factory.crowding_intelligence import CrowdingIntelligence
from libs.alpha_factory.errors import AlphaFactoryGovernanceError
from libs.alpha_factory.feature_drift_engine import FeatureDriftEngine
from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AlphaCategory,
    AlphaFactoryReport,
    IdeaCandidate,
)
from libs.alpha_factory.research_allocator import ResearchAllocator
from libs.alpha_factory.research_graph import ResearchGraph
from libs.alpha_factory.research_memory import ResearchMemory
from libs.alpha_factory.research_roi_engine import ResearchROIEngine
from libs.alpha_factory.research_score_engine import ResearchScoreEngine
from libs.alpha_factory.strategy_similarity_engine import StrategySimilarityEngine
from libs.store.connection import Database


class AlphaFactoryController:
    """Coordinates every research engine and enforces factory governance."""

    def __init__(self, db: Database) -> None:
        self.memory = ResearchMemory(db)
        self.discovery = AlphaDiscoveryEngine(self.memory)
        self.hypothesis_engine = HypothesisEngine()
        self.idea_ranking = IdeaRankingEngine()
        self.research_score = ResearchScoreEngine()
        self.concept_evolution = ConceptEvolutionEngine()
        self.crowding_intelligence = CrowdingIntelligence()
        self.capacity_intelligence = CapacityIntelligence()
        self.research_roi = ResearchROIEngine()
        self.allocator = ResearchAllocator()
        self.family_tree = AlphaFamilyTree()
        self.research_graph = ResearchGraph()
        self.similarity = StrategySimilarityEngine()
        self.embedding = AlphaEmbeddingEngine()
        self.feature_drift = FeatureDriftEngine()

    def run(
        self,
        *,
        candidates: Sequence[IdeaCandidate],
        categories: Sequence[AlphaCategory],
        regime_gaps: Mapping[str, float] | None = None,
        portfolio_gaps: Mapping[str, float] | None = None,
        crowding: Mapping[str, float] | None = None,
    ) -> AlphaFactoryReport:
        """Produce a research recommendation plan (recommend-only)."""
        regime_gaps = regime_gaps or {}
        portfolio_gaps = portfolio_gaps or {}
        priorities = self.idea_ranking.rank(candidates)
        allocation = self.allocator.allocate(
            categories, memory=self.memory, regime_gaps=regime_gaps,
            portfolio_gaps=portfolio_gaps, crowding=crowding,
        )
        return AlphaFactoryReport(
            research_priorities=priorities,
            allocation=allocation,
            portfolio_gaps=sorted(k for k, v in portfolio_gaps.items() if v > 0.0),
            regime_gaps=sorted(k for k, v in regime_gaps.items() if v > 0.0),
            notes="recommend-only; production decisions require the validation gauntlet",
        )

    # --------------------------------------------------------- governance (MAY NOT)

    def promote_alpha(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not promote alphas")

    def retire_alpha(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not retire alphas")

    def allocate_production_capital(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not allocate production capital")

    def change_risk_limit(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not change risk limits")

    def change_validation_threshold(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise AlphaFactoryGovernanceError("Alpha Factory may not change validation thresholds")
