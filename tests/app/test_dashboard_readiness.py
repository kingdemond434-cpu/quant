"""Dashboard aggregation and deployment readiness checks."""

from __future__ import annotations

from app.dashboard import build_dashboard
from app.readiness import readiness_check
from libs.store.connection import Database


def test_dashboard_has_all_sections(db: Database) -> None:
    state = build_dashboard(db)
    # all seven required sections present and the system-health view is sane on a fresh db
    assert set(state.research) >= {"n_ideas"}
    assert state.alpha_registry["total"] == 0
    assert state.portfolio["open_positions"] == 0
    assert state.risk["approvals_issued"] == 0
    assert state.execution["orders"] == 0
    assert state.monitoring["open_alerts"] == 0
    assert state.system_health["schema_version"] == 6
    assert state.system_health["audit_chain_ok"] is True


def test_readiness_is_ready_on_migrated_db(db: Database) -> None:
    report = readiness_check(db)
    assert report.ready is True
    assert report.failures == []
    names = {c.name for c in report.checks}
    assert {"risk_gate_fail_closed", "portfolio_kill_fail_closed", "research_kill_fail_closed",
            "alpha_governance_fail_closed", "engines_constructable"} <= names


def test_readiness_external_deps_are_non_critical(db: Database) -> None:
    report = readiness_check(db)
    # MT5 / streamlit are non-critical: whether present or absent, they never block demo readiness.
    names = {c.name: c for c in report.checks}
    assert names["mt5_available"].critical is False
    assert names["dashboard_server_available"].critical is False
    assert report.ready is True
