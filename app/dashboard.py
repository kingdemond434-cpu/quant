"""Unified dashboard state — aggregates the whole platform into one read-only snapshot.

Seven sections: Research, Alpha Registry, Portfolio, Risk, Execution, Monitoring, System Health.
Pure and deterministic: it reads the SQLite system of record and existing stores; it never mutates.
A renderer (Streamlit/FastAPI) consumes this; the aggregation itself runs anywhere.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from libs.alpha.registry import AlphaCardStore
from libs.alpha_factory.research_dashboard_exports import build_research_dashboard
from libs.alpha_factory.research_memory import ResearchMemory
from libs.autodiscovery.memory import CandidateStore
from libs.core.time import to_iso8601, utcnow
from libs.monitoring.alerting import AlertStore
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database
from libs.store.migrations import current_version
from libs.store.trading import OrderStore


class DashboardState(BaseModel):
    """A single immutable snapshot of platform state for display."""

    model_config = ConfigDict(frozen=True)

    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
    research: dict[str, Any] = Field(default_factory=dict)
    research_lab: dict[str, Any] = Field(default_factory=dict)
    alpha_registry: dict[str, Any] = Field(default_factory=dict)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    monitoring: dict[str, Any] = Field(default_factory=dict)
    system_health: dict[str, Any] = Field(default_factory=dict)


def _count(db: Database, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_dashboard(db: Database) -> DashboardState:
    """Assemble the full dashboard snapshot from the system of record."""
    cards = AlphaCardStore(db).list_all()
    status_counts: dict[str, int] = {}
    for card in cards:
        status_counts[card.status.value] = status_counts.get(card.status.value, 0) + 1

    positions = OrderStore(db).list_positions()
    open_positions = [p for p in positions if p.qty != 0]
    chain = verify_audit_chain(db)

    lab = CandidateStore(db)
    funnel = lab.status_counts()
    return DashboardState(
        research=build_research_dashboard(ResearchMemory(db)),
        research_lab={
            "candidates_tested": lab.total(),
            "validation_funnel": funnel,
            "survivors": len(lab.survivors()),
            "rejections": funnel.get("rejected", 0),
            "shadow_portfolio": funnel.get("shadow", 0),
            "paper_portfolio": funnel.get("paper", 0),
            "by_family": lab.family_counts(),
            "last_campaign": lab.get_checkpoint("last_campaign"),
        },
        alpha_registry={"total": len(cards), "by_status": status_counts},
        portfolio={
            "open_positions": len(open_positions),
            "gross_qty": sum(abs(p.qty) for p in open_positions),
            "symbols": sorted(p.instrument for p in open_positions),
        },
        risk={"approvals_issued": _count(db, "risk_registry")},
        execution={
            "orders": _count(db, "orders"),
            "fills": _count(db, "fills"),
            "positions": len(positions),
        },
        monitoring={
            "open_alerts": len(AlertStore(db).open_alerts()),
            "metric_points": _count(db, "metric_points"),
        },
        system_health={
            "schema_version": current_version(db),
            "audit_chain_ok": chain.ok,
            "audit_entries": chain.length,
        },
    )
