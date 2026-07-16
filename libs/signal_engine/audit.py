"""Signal audit — every BUY/SELL/FLAT decision to the immutable, hash-chained audit log.

Reuses ``libs.store.AuditLog`` (append-only, tamper-evident). No parallel storage; single source
of truth. Each decision records its inputs, scores, regime, and final outcome so it is fully
reproducible and explainable.
"""

from __future__ import annotations

from libs.signal_engine.models import SelectionResult, SignalPackage
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage13_5_signal_engine"


class SignalAudit:
    """Writes signal decisions to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record_package(self, package: SignalPackage) -> AuditEntry:
        return self._audit.append(
            "signal_decision",
            actor=_ACTOR,
            inputs={
                "symbol": package.symbol,
                "quality_score": package.quality_score,
                "confidence": package.confidence,
                "edge_score": package.edge_score,
                "expected_value": package.expected_value,
                "regime": package.regime.value,
                "predicted_regime": package.predicted_regime.value,
                "alpha_breakdown": package.alpha_breakdown,
                "institutional_score": package.institutional_score,
            },
            rationale="approved by signal engine",
            outcome=package.direction.value,
        )

    def record_flat(self, symbol: str, reason: str) -> AuditEntry:
        return self._audit.append(
            "signal_decision",
            actor=_ACTOR,
            inputs={"symbol": symbol},
            rationale=reason,
            outcome="flat",
        )

    def record_selection(self, result: SelectionResult) -> list[AuditEntry]:
        entries = [self.record_package(p) for p in result.approved]
        for symbol in sorted(result.rejected):
            entries.append(self.record_flat(symbol, result.rejected[symbol]))
        return entries
