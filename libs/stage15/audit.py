"""Research audit — every Stage 15 pipeline decision to the immutable audit log.

Reuses ``libs.store.AuditLog`` (append-only, hash-chained). Records each alpha's pipeline routing
and the research kill-switch verdict, so discovery decisions are as auditable as risk decisions.
No parallel storage.
"""

from __future__ import annotations

from libs.stage15.models import ResearchPipelineResult
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage15_research"


class ResearchAudit:
    """Writes Stage 15 research-pipeline decisions to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record_pipeline(self, result: ResearchPipelineResult) -> list[AuditEntry]:
        entries = [
            self._audit.append(
                f"research_pipeline_{record.stage.value}",
                actor=_ACTOR,
                inputs={
                    "alpha_id": record.alpha_id,
                    "quality_score": record.quality_score,
                    "accepted": record.accepted,
                },
                rationale=record.note,
                outcome=record.stage.value,
            )
            for record in result.records
        ]
        self._audit.append(
            "research_pipeline",
            actor=_ACTOR,
            inputs={
                "n_allocated": len(result.allocated),
                "n_rejected": len(result.rejected),
                "research_halt": result.kill.halt,
                "halt_reasons": result.kill.reasons,
            },
            rationale="stage15 research pipeline run",
            outcome="halted" if result.kill.halt else "completed",
        )
        return entries
