"""``libs.alpha_factory`` — the Alpha Factory & Research Operating System.

Sits *above* the research pipeline: it generates, ranks, evolves, allocates, and learns from
research, compounding knowledge so the platform discovers more (and better) alphas over time.
It does NOT trade. Governance is structural: the factory may generate/rank/allocate-research/
archive/recommend, but may not promote or retire alphas, change risk/validation thresholds, or
allocate production capital.

Reuses Architecture v1.0: ``libs.discovery`` (research ROI, capacity), ``libs.self_improvement``
(categories, PSI drift), and the SQLite system of record (``research_memory`` table, migration
0003). No duplicate abstractions; single source of truth.
"""

from __future__ import annotations

from libs.alpha_factory.alpha_discovery_engine import AlphaDiscoveryEngine
from libs.alpha_factory.alpha_dna import build_alpha_dna, dna_distance
from libs.alpha_factory.alpha_embedding_engine import AlphaEmbeddingEngine
from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
from libs.alpha_factory.alpha_family_tree import AlphaFamilyTree
from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
from libs.alpha_factory.concept_evolution_engine import ConceptEvolutionEngine
from libs.alpha_factory.crowding_intelligence import CrowdingIntelligence
from libs.alpha_factory.errors import AlphaFactoryError, AlphaFactoryGovernanceError
from libs.alpha_factory.feature_drift_engine import FeatureDriftEngine
from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import (
    AllocationResult,
    AlphaCategory,
    AlphaDNA,
    AlphaFactoryReport,
    CapacityIntelligenceResult,
    CrowdingEstimate,
    DriftResult,
    FailureCause,
    FamilyNode,
    Hypothesis,
    IdeaCandidate,
    IdeaRecord,
    IdeaScore,
    ResearchResult,
    ResearchScoreResult,
    SimilarityResult,
)
from libs.alpha_factory.research_allocator import ResearchAllocator
from libs.alpha_factory.research_dashboard_exports import build_research_dashboard
from libs.alpha_factory.research_graph import ResearchGraph
from libs.alpha_factory.research_memory import ResearchMemory
from libs.alpha_factory.research_roi_engine import ResearchROIEngine
from libs.alpha_factory.research_score_engine import ResearchScoreEngine
from libs.alpha_factory.strategy_similarity_engine import StrategySimilarityEngine

__all__ = [  # noqa: RUF022  # grouped by concern
    # models / enums
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
    # engines
    "AlphaDiscoveryEngine",
    "AlphaEmbeddingEngine",
    "AlphaFamilyTree",
    "build_alpha_dna",
    "dna_distance",
    "CapacityIntelligence",
    "ConceptEvolutionEngine",
    "CrowdingIntelligence",
    "FeatureDriftEngine",
    "HypothesisEngine",
    "IdeaRankingEngine",
    "ResearchAllocator",
    "ResearchGraph",
    "ResearchMemory",
    "ResearchROIEngine",
    "ResearchScoreEngine",
    "StrategySimilarityEngine",
    "build_research_dashboard",
    # controller
    "AlphaFactoryController",
    # errors
    "AlphaFactoryError",
    "AlphaFactoryGovernanceError",
]
