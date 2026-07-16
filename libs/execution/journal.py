"""Trade journal — an immutable, hash-chained record of every execution event.

Backed by the audit log (append-only, tamper-evident), so submissions, fills, cancels,
timeouts, and reconciliations are all permanently traceable.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

ACTOR = "execution"


class TradeJournal:
    """Writes execution events to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record(
        self,
        event: str,
        inputs: Mapping[str, Any],
        *,
        outcome: str | None = None,
        rationale: str | None = None,
    ) -> AuditEntry:
        return self._audit.append(
            event, actor=ACTOR, inputs=inputs, outcome=outcome, rationale=rationale
        )
