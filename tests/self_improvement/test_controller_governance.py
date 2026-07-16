"""Controller plan generation and the Stage 13 governance invariants."""

from __future__ import annotations

import pytest
from tests.self_improvement.conftest import make_live, make_live_poor, register

from libs.alpha.manager import AlphaLifecycleManager
from libs.portfolio.engine import PortfolioEngine
from libs.portfolio.models import AlphaInput, StrategyType
from libs.risk.instruments import Factor
from libs.self_improvement.audit import ImprovementAudit
from libs.self_improvement.controller import ImprovementController
from libs.self_improvement.errors import GovernanceError
from libs.self_improvement.models import ImprovementActionType, WeightProposal
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_evaluate_recommends_retire_for_dead_alpha(manager: AlphaLifecycleManager) -> None:
    dead = register(manager, name="dead_alpha")
    healthy = register(manager, name="healthy_alpha")
    controller = ImprovementController()
    plan = controller.evaluate(
        [(dead, make_live_poor()), (healthy, make_live())],
        current_weights={dead.id: 0.5, healthy.id: 0.5},
        total_capital=100_000.0,
    )
    retire = [a for a in plan.actions if a.type is ImprovementActionType.RETIRE]
    assert [a.target_id for a in retire] == [dead.id]
    assert plan.weight_proposal is not None
    assert plan.weight_proposal.requires_portfolio_approval is True
    # capital reallocation actions appear because current_weights was supplied
    assert any(a.type is ImprovementActionType.CAPITAL_REALLOCATION for a in plan.actions)
    assert all(a.requires_portfolio_approval for a in plan.actions)


def test_evaluate_maps_decay_levels_to_actions(manager: AlphaLifecycleManager) -> None:
    decaying = register(manager, name="decaying_alpha")
    watch = register(manager, name="watch_alpha")
    controller = ImprovementController()
    plan = controller.evaluate(
        [
            (decaying, make_live(profit_factor=0.9, sharpe=0.5)),  # -> DECAYING
            (watch, make_live(profit_factor=1.3, sharpe=1.0)),     # -> WATCH
        ]
    )
    by_target = {a.target_id: a for a in plan.actions}
    assert by_target[decaying.id].type is ImprovementActionType.PAUSE
    assert by_target[decaying.id].detail["allow_increase"] is False
    assert by_target[watch.id].type is ImprovementActionType.WEIGHT_CHANGE
    assert all(a.requires_portfolio_approval for a in plan.actions)


def test_evaluate_writes_to_immutable_audit_log(
    db: Database, manager: AlphaLifecycleManager
) -> None:
    dead = register(manager)
    audit = ImprovementAudit(db)
    controller = ImprovementController(audit=audit)
    plan = controller.evaluate([(dead, make_live_poor())])
    chain = verify_audit_chain(db)
    assert chain.ok
    # every action in the plan was journaled
    assert chain.length == len(plan.actions)
    assert len(plan.actions) >= 1


def _alpha(alpha_id: str, factor: Factor) -> AlphaInput:
    return AlphaInput(
        alpha_id=alpha_id, volatility=0.15, factor=factor, strategy_type=StrategyType.TREND
    )


def test_apply_weight_proposal_routes_through_portfolio_engine() -> None:
    controller = ImprovementController()
    proposal = WeightProposal(weights={"a": 0.5, "b": 0.5}, rationale="advisory")
    alphas = [_alpha("a", Factor.PRECIOUS_METALS), _alpha("b", Factor.FX)]
    target = controller.apply_weight_proposal(proposal, PortfolioEngine(), alphas)
    # the Portfolio Engine (the approver) re-derives the constrained target
    assert set(target.weights) == {"a", "b"}
    assert target.method == "optimize"
    assert all(0.0 <= w <= 0.25 + 1e-9 for w in target.weights.values())
    assert "max_weight" in target.binding_constraints


def test_apply_weight_proposal_rejects_unapproved_proposal() -> None:
    controller = ImprovementController()
    rogue = WeightProposal(
        weights={"a": 1.0}, rationale="bypass", requires_portfolio_approval=False
    )
    with pytest.raises(GovernanceError):
        controller.apply_weight_proposal(
            rogue, PortfolioEngine(), [_alpha("a", Factor.FX)]
        )


def test_controller_has_no_direct_weight_writer() -> None:
    # Governance is structural: the only realization path requires a PortfolioEngine argument.
    controller = ImprovementController()
    writers = [
        name
        for name in dir(controller)
        if not name.startswith("_") and ("set_weight" in name or "write_weight" in name)
    ]
    assert writers == []
