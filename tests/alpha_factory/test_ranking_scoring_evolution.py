"""Idea ranking, research score, concept evolution, crowding, capacity, ROI, allocator."""

from __future__ import annotations

from tests.alpha_factory.conftest import make_candidate

from libs.alpha_factory.capacity_intelligence import CapacityIntelligence
from libs.alpha_factory.concept_evolution_engine import ConceptEvolutionEngine
from libs.alpha_factory.crowding_intelligence import CrowdingIntelligence
from libs.alpha_factory.idea_ranking_engine import IdeaRankingEngine
from libs.alpha_factory.models import AlphaCategory, Hypothesis, ResearchResult
from libs.alpha_factory.research_allocator import ResearchAllocator
from libs.alpha_factory.research_memory import ResearchMemory
from libs.alpha_factory.research_roi_engine import ResearchROIEngine
from libs.alpha_factory.research_score_engine import ResearchScoreEngine
from libs.discovery.research_roi import CategoryStat
from libs.store.connection import Database


def test_idea_ranking_orders_by_priority() -> None:
    eng = IdeaRankingEngine()
    strong = make_candidate("strong", expected_edge=0.9, crowding=0.0)
    weak = make_candidate("weak", expected_edge=0.1, crowding=0.9)
    ranked = eng.rank([weak, strong])
    assert [s.idea_id for s in ranked] == ["strong", "weak"]
    assert 0.0 <= ranked[-1].idea_priority_score <= ranked[0].idea_priority_score <= 100.0


def test_research_score_penalizes_crowding() -> None:
    eng = ResearchScoreEngine()
    base = {
        "novelty": 0.8, "expected_robustness": 0.8, "expected_capacity": 0.7,
        "portfolio_need": 0.6, "research_confidence": 0.8,
    }
    clean = eng.score(**base, crowding_risk=0.0)
    crowded = eng.score(**base, crowding_risk=1.0)
    assert clean.research_score > crowded.research_score


def test_concept_evolution_adds_unique_mutations() -> None:
    base = Hypothesis(id="h1", statement="momentum works", category="momentum",
                      features=["momentum"], expected_edge=0.6)
    variants = ConceptEvolutionEngine().evolve(base)
    assert len(variants) == 4
    assert all(v.category == "momentum" for v in variants)
    assert all(len(v.features) == 2 for v in variants)
    # already-present mutation is not duplicated
    has_regime = base.model_copy(update={"features": ["momentum", "regime_filter"]})
    assert len(ConceptEvolutionEngine().evolve(has_regime)) == 3


def test_crowding_intelligence_multiplier() -> None:
    eng = CrowdingIntelligence()
    uncrowded = eng.assess(strategy_crowding=0.0, factor_crowding=0.0, style_crowding=0.0)
    crowded = eng.assess(strategy_crowding=1.0, factor_crowding=1.0, style_crowding=1.0)
    assert uncrowded.priority_multiplier == 1.0
    assert crowded.priority_multiplier == 0.0
    assert crowded.crowding_score == 1.0


def test_capacity_intelligence_scalability() -> None:
    eng = CapacityIntelligence()
    deep = eng.assess(adv_usd=1e10)
    thin = eng.assess(adv_usd=1e6)
    assert deep.scalability_score >= thin.scalability_score
    assert 0.0 <= deep.scalability_score <= 100.0
    assert deep.market_capacity_usd > 0.0


def test_research_roi_scores_and_ranks() -> None:
    eng = ResearchROIEngine()
    result = eng.score(ideas_generated=20, ideas_tested=10, ideas_validated=3,
                       time_hours=40.0, production_contribution=0.5)
    assert 0.0 <= result.research_roi_score <= 100.0
    ranked = eng.rank({
        "momentum": CategoryStat(tested=10, validated=4, contribution=0.5),
        "carry": CategoryStat(tested=10, validated=0, contribution=0.0),
    })
    assert ranked[0][0] == "momentum"


def test_allocator_normalizes_and_uses_signals() -> None:
    alloc = ResearchAllocator().allocate(
        [AlphaCategory.MOMENTUM, AlphaCategory.CARRY],
        regime_gaps={"momentum": 1.0},
        crowding={"carry": 1.0},
    )
    assert abs(sum(alloc.allocations.values()) - 1.0) < 1e-9
    assert alloc.allocations["momentum"] > alloc.allocations["carry"]
    assert "success=" in alloc.rationale["momentum"]


def test_allocator_equal_split_when_no_signal(db: Database) -> None:
    # All categories have a zero success record and full crowding -> every raw weight is 0,
    # so the allocator falls back to an equal split rather than dividing by zero.
    mem = ResearchMemory(db)
    for cat in ("momentum", "carry"):
        mem.record(category=cat, statement="x", result=ResearchResult.FAILURE)
    alloc = ResearchAllocator().allocate(
        [AlphaCategory.MOMENTUM, AlphaCategory.CARRY],
        memory=mem,
        crowding={"momentum": 1.0, "carry": 1.0},
    )
    assert alloc.allocations == {"momentum": 0.5, "carry": 0.5}
