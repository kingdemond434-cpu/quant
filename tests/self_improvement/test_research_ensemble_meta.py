"""Research prioritization, ensemble optimization, and governed meta-learning."""

from __future__ import annotations

import numpy as np

from libs.discovery.research_roi import CategoryStat
from libs.portfolio.models import AlphaInput, StrategyType
from libs.risk.instruments import Factor
from libs.self_improvement.ensemble_optimizer import EnsembleOptimizer
from libs.self_improvement.meta_learning import (
    MetaLearningEngine,
    meta_learning_governance_gate,
)
from libs.self_improvement.research_priority import ResearchPriorityEngine


def test_research_priority_ranks_by_need_and_yield() -> None:
    engine = ResearchPriorityEngine()
    priorities = engine.prioritize(
        decaying_by_category={"trend_following": 0.8, "carry": 0.0},
        roi_stats={
            "trend_following": CategoryStat(tested=10, validated=4, contribution=0.5),
            "carry": CategoryStat(tested=10, validated=0, contribution=0.0),
        },
    )
    assert priorities[0].category == "trend_following"
    assert priorities[0].priority_score > priorities[-1].priority_score
    assert priorities[0].priority_score > 0


def test_research_priority_no_pressure_reason() -> None:
    priorities = ResearchPriorityEngine().prioritize(decaying_by_category={"carry": 0.0})
    assert priorities[0].reason == "no current research pressure"


def _alpha(alpha_id: str, factor: Factor) -> AlphaInput:
    return AlphaInput(
        alpha_id=alpha_id,
        volatility=0.15,
        factor=factor,
        strategy_type=StrategyType.TREND,
        expected_return=0.10,
        expected_sharpe=1.2,
    )


def test_ensemble_optimizer_proposes_via_portfolio_engine() -> None:
    alphas = [
        _alpha("a", Factor.PRECIOUS_METALS),
        _alpha("b", Factor.FX),
        _alpha("c", Factor.EQUITY_INDEX),
    ]
    proposal = EnsembleOptimizer().optimize(alphas)
    assert set(proposal.weights) == {"a", "b", "c"}
    assert sum(proposal.weights.values()) > 0
    assert proposal.requires_portfolio_approval is True


def test_meta_learning_insight_not_deployable_until_governed() -> None:
    engine = MetaLearningEngine()
    labels = ["trend", "range", "trend", "crisis"]
    returns = {"a": np.array([0.02, -0.01, 0.03, -0.05])}
    insight = engine.learn_regime_affinity(labels, returns)
    assert insight.deployable is False
    assert set(insight.relationship["a"]) == {"trend", "range", "crisis"}
    assert insight.evidence["n_observations"] == 4

    passed = engine.govern(
        insight, cpcv_pass=True, dsr_pass=True, pbo_pass=True, walk_forward_pass=True
    )
    assert passed.deployable is True
    failed = engine.govern(
        insight, cpcv_pass=True, dsr_pass=False, pbo_pass=True, walk_forward_pass=True
    )
    assert failed.deployable is False


def test_meta_learning_gate_requires_all() -> None:
    assert meta_learning_governance_gate(
        cpcv_pass=True, dsr_pass=True, pbo_pass=True, walk_forward_pass=True
    )
    assert not meta_learning_governance_gate(
        cpcv_pass=True, dsr_pass=True, pbo_pass=True, walk_forward_pass=False
    )
