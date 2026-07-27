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

    # ------------------------------------------------------------------ deep assessment
    # `run` ranks and allocates. These are the engines that answer "is this idea WORTH the
    # research budget" -- novelty against what the desk already killed, crowding, whether the
    # concept can hold the desk's size, and whether it duplicates something already deployed.
    # They were instantiated in __init__ and called by nothing, so the factory imported fifteen
    # engines and exercised two: reachable on paper, idle in fact.

    def assess(
        self,
        *,
        candidate: IdeaCandidate,
        adv_usd: float,
        research_confidence: float = 0.5,
    ) -> dict[str, object]:
        """Full per-candidate assessment: research score, crowding, capacity.

        `crowding` on the candidate is a single number; CrowdingIntelligence wants it split
        three ways. Absent a finer measurement the same value is used for all three -- honest
        about the resolution we actually have rather than inventing a decomposition.
        """
        crowd = self.crowding_intelligence.assess(
            strategy_crowding=candidate.crowding,
            factor_crowding=candidate.crowding,
            style_crowding=candidate.crowding,
        )
        cap = self.capacity_intelligence.assess(adv_usd=adv_usd)
        score = self.research_score.score(
            novelty=candidate.novelty,
            expected_robustness=candidate.expected_robustness,
            expected_capacity=candidate.expected_capacity,
            portfolio_need=candidate.portfolio_need,
            research_confidence=research_confidence,
            crowding_risk=crowd.crowding_score,
        )
        return {
            "idea_id": candidate.idea_id,
            "research_score": score.research_score,
            "components": score.components,
            "crowding_score": crowd.crowding_score,
            "priority_multiplier": crowd.priority_multiplier,
            "capacity_usd": cap.market_capacity_usd,
            "scalability_score": cap.scalability_score,
            "expected_slippage": cap.expected_slippage,
        }

    def duplicates_of(
        self, dna: Mapping[str, object], deployed: Mapping[str, object], *,
        threshold: float = 0.95,
    ) -> list[list[str]]:
        """Concepts whose DNA clusters with something already deployed.

        Re-testing a variant of the sleeve already running is the cheapest way to spend research
        budget on nothing, and it is invisible without an explicit similarity check because the
        statement wording differs every time.
        """
        pool = {**deployed, **dna}
        return self.embedding.cluster(pool, threshold=threshold)  # type: ignore[arg-type]

    def record_lineage(self, alpha_id: str, *, parent_id: str | None = None,
                       mutation_type: str = "root", performance: float = 0.0) -> None:
        """Register a concept in the family tree AND the provenance graph.

        Both, deliberately: the tree answers "what did this descend from", the graph answers
        "what else touches this feature/data source". Losing either is how a desk re-derives an
        idea it already has.
        """
        self.family_tree.add(alpha_id, parent_id=parent_id, mutation_type=mutation_type,
                             performance=performance)
        self.research_graph.add_node(alpha_id, "alpha", performance=performance)
        if parent_id:
            self.research_graph.add_node(parent_id, "alpha")
            self.research_graph.add_edge(parent_id, alpha_id)

    def propose(self, categories: Sequence[AlphaCategory]) -> list[object]:
        """New hypotheses from the discovery + hypothesis engines, expanded by concept evolution.

        Deduplicated on statement: the two generators overlap by design (one is memory-driven,
        one is category-driven) and emitting the same statement twice would inflate every
        downstream count that reads this list.
        """
        seen: set[str] = set()
        out: list[object] = []
        for h in [*self.discovery.generate(categories),
                  *self.hypothesis_engine.generate(categories, memory=self.memory)]:
            if h.statement in seen:
                continue
            seen.add(h.statement)
            out.append(h)
            for variant in self.concept_evolution.evolve(h):
                if variant.statement not in seen:
                    seen.add(variant.statement)
                    out.append(variant)
        return out

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
