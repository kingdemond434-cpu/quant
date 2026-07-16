"""Retirement/reactivation apply-side and the improvement audit writer."""

from __future__ import annotations

from tests.self_improvement.conftest import register

from libs.alpha.manager import AlphaLifecycleManager
from libs.alpha.state import AlphaState
from libs.self_improvement.audit import ImprovementAudit
from libs.self_improvement.lifecycle_actions import apply_reactivation, apply_retirement
from libs.self_improvement.models import ImprovementAction, ImprovementActionType
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_apply_retirement_archives_via_manager(manager: AlphaLifecycleManager) -> None:
    card = register(manager)
    retired = apply_retirement(manager, card.id, reason="decay confirmed")
    assert retired.status is AlphaState.RETIRED
    assert retired.retirement_date is not None
    # archived, not deleted: still present in the registry
    assert manager.get_alpha(card.id) is not None


def test_apply_reactivation_reenters_as_candidate(manager: AlphaLifecycleManager) -> None:
    card = register(manager)
    retired = apply_retirement(manager, card.id)
    fresh = apply_reactivation(manager, retired, reason="market structure changed")
    # no validation bypass: re-enters the funnel as a fresh CANDIDATE linked to its predecessor
    assert fresh.status is AlphaState.CANDIDATE
    assert fresh.predecessor_id == retired.id
    assert fresh.id != retired.id
    assert fresh.name.endswith("_reactivated")


def test_improvement_audit_records_action(db: Database) -> None:
    audit = ImprovementAudit(db)
    action = ImprovementAction(
        type=ImprovementActionType.WEIGHT_CHANGE,
        target_id="alpha_1",
        rationale="decay watch -> trim weight",
        detail={"weight_multiplier": 0.9},
        requires_portfolio_approval=True,
    )
    entry = audit.record(action)
    assert entry.decision_type == "improvement_weight_change"
    assert entry.actor == "stage13_self_improvement"
    assert entry.outcome == "recommended"
    assert entry.inputs["target_id"] == "alpha_1"
    assert entry.inputs["requires_portfolio_approval"] is True
    assert verify_audit_chain(db).ok
