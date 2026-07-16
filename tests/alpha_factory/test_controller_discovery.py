"""Hypothesis engine, discovery coordinator, dashboard, and factory governance."""

from __future__ import annotations

import pytest
from tests.alpha_factory.conftest import make_candidate

from libs.alpha_factory.alpha_discovery_engine import AlphaDiscoveryEngine
from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
from libs.alpha_factory.errors import AlphaFactoryGovernanceError
from libs.alpha_factory.hypothesis_engine import HypothesisEngine
from libs.alpha_factory.models import AlphaCategory, FailureCause, ResearchResult
from libs.alpha_factory.research_dashboard_exports import build_research_dashboard
from libs.alpha_factory.research_memory import ResearchMemory
from libs.store.connection import Database


def test_hypothesis_engine_generates_and_uses_priors(db: Database) -> None:
    mem = ResearchMemory(db)
    eng = HypothesisEngine()
    base = eng.generate([AlphaCategory.MOMENTUM])
    assert base
    assert all(h.category == "momentum" for h in base)
    assert base[0].expected_edge == 0.5  # default prior, no memory

    mem.record(category="momentum", statement="x", result=ResearchResult.SUCCESS)
    informed = eng.generate([AlphaCategory.MOMENTUM], memory=mem)
    assert informed[0].expected_edge == 1.0  # learned from 1/1 success


def test_discovery_engine_pipeline(db: Database) -> None:
    eng = AlphaDiscoveryEngine(ResearchMemory(db))
    hyps = eng.generate([AlphaCategory.MOMENTUM, AlphaCategory.CARRY])
    assert hyps
    ranked = eng.prioritize([make_candidate("a", expected_edge=0.9),
                             make_candidate("b", expected_edge=0.1)])
    assert ranked[0].idea_id == "a"
    eng.archive(category="momentum", statement="tested idea", result=ResearchResult.FAILURE,
                failure_cause=FailureCause.OVERFIT)
    learned = eng.learn()
    assert learned["momentum"] == 0.0  # the one momentum idea failed


def test_dashboard_exports(db: Database) -> None:
    mem = ResearchMemory(db)
    mem.record(category="momentum", statement="a", result=ResearchResult.SUCCESS)
    mem.record(category="carry", statement="b", result=ResearchResult.FAILURE,
               failure_cause=FailureCause.CROWDED_EDGE)
    dash = build_research_dashboard(mem)
    assert dash["n_ideas"] == 2
    assert dash["n_success"] == 1
    assert dash["failure_cause_histogram"] == {"crowded_edge": 1}
    assert "momentum" in dash["success_rate_by_category"]


def test_controller_run_produces_report(db: Database) -> None:
    ctrl = AlphaFactoryController(db)
    report = ctrl.run(
        candidates=[make_candidate("a", expected_edge=0.9),
                    make_candidate("b", expected_edge=0.2)],
        categories=[AlphaCategory.MOMENTUM, AlphaCategory.CARRY],
        regime_gaps={"momentum": 0.8},
        portfolio_gaps={"carry": 0.5},
    )
    assert [s.idea_id for s in report.research_priorities] == ["a", "b"]
    assert report.allocation is not None
    assert abs(sum(report.allocation.allocations.values()) - 1.0) < 1e-9
    assert report.regime_gaps == ["momentum"]
    assert report.portfolio_gaps == ["carry"]


def test_controller_governance_forbidden_actions(db: Database) -> None:
    ctrl = AlphaFactoryController(db)
    for action in (
        ctrl.promote_alpha,
        ctrl.retire_alpha,
        ctrl.allocate_production_capital,
        ctrl.change_risk_limit,
        ctrl.change_validation_threshold,
    ):
        with pytest.raises(AlphaFactoryGovernanceError):
            action("anything")
