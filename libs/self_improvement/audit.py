"""Improvement audit — every Stage 13 action to the existing immutable audit log.

Reuses ``libs.store.AuditLog`` (append-only, hash-chained). No parallel storage is created.
"""

from __future__ import annotations

from libs.self_improvement.models import ImprovementAction, ImprovementPlan
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage13_self_improvement"


class ImprovementAudit:
    """Writes Stage 13 recommendations to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record(self, action: ImprovementAction) -> AuditEntry:
        return self._audit.append(
            f"improvement_{action.type.value}",
            actor=_ACTOR,
            inputs={
                "target_id": action.target_id,
                "requires_portfolio_approval": action.requires_portfolio_approval,
                **action.detail,
            },
            rationale=action.rationale,
            outcome="recommended",
        )

    def record_plan(self, plan: ImprovementPlan) -> list[AuditEntry]:
        return [self.record(action) for action in plan.actions]
