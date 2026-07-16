"""Portfolio audit — every Stage 14 allocation to the immutable audit log.

Reuses ``libs.store.AuditLog`` (append-only, hash-chained). No parallel storage.
"""

from __future__ import annotations

from libs.stage14.models import PortfolioConstructionResult, PortfolioPackage
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.store.models import AuditEntry

_ACTOR = "stage14_portfolio"


class PortfolioAudit:
    """Writes Stage 14 allocations to the immutable audit log."""

    def __init__(self, db: Database) -> None:
        self._audit = AuditLog(db)

    def record_package(self, package: PortfolioPackage) -> AuditEntry:
        return self._audit.append(
            "portfolio_allocation",
            actor=_ACTOR,
            inputs={
                "symbol": package.symbol,
                "sleeve": package.sleeve.value,
                "allocation": package.allocation,
                "position_size": package.position_size,
                "leverage": package.leverage,
                "kelly_fraction": package.kelly_fraction,
                "survival_score": package.survival_score,
                "institutional_score": package.institutional_score,
            },
            rationale="stage14 capital allocation",
            outcome="allocated",
        )

    def record_result(self, result: PortfolioConstructionResult) -> list[AuditEntry]:
        entries = [self.record_package(p) for p in result.packages]
        self._audit.append(
            "portfolio_construction",
            actor=_ACTOR,
            inputs={
                "state": result.state.value,
                "n_allocations": len(result.packages),
                "n_rejected": len(result.rejected),
                "total_allocation": result.total_allocation,
                "halt": result.kill.halt,
            },
            rationale="stage14 portfolio constructed",
            outcome="halted" if result.kill.halt else "constructed",
        )
        return entries
