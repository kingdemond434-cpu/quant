"""Deployment readiness checks — verify the demo stack is wired and fail-closed.

Runs entirely offline (no MT5 / no web server). It confirms the schema, audit integrity, that
every stage constructs, and that fail-closed behavior holds at the risk, governance, and portfolio
layers. External dependencies (MetaTrader5, Streamlit) are reported as warnings, not blockers — the
demo decision path does not need them; only live data/serving does.
"""

from __future__ import annotations

import importlib.util

from pydantic import BaseModel, ConfigDict, Field

from libs.execution.paper_broker import PaperBroker
from libs.risk.gate import AccountState, OrderIntent, risk_gate
from libs.signal_engine.engine import SignalEngine
from libs.signal_engine.shadow import ShadowDeployment
from libs.stage14.engine import PortfolioConstructionEngine
from libs.stage15.governance import alpha_governance_gate
from libs.stage15.orchestrator import ResearchOrchestrator
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database
from libs.store.migrations import current_version
from libs.validation.revalidation import WalkForwardEngine

_LATEST_SCHEMA = 4


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    critical: bool
    detail: str


class ReadinessReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    ready: bool
    checks: list[CheckResult] = Field(default_factory=list)

    @property
    def failures(self) -> list[str]:
        return [c.name for c in self.checks if c.critical and not c.passed]

    @property
    def warnings(self) -> list[str]:
        return [c.name for c in self.checks if not c.critical and not c.passed]


def _dep_present(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def readiness_check(db: Database) -> ReadinessReport:
    checks: list[CheckResult] = []

    def add(name: str, passed: bool, *, critical: bool = True, detail: str = "") -> None:
        checks.append(CheckResult(name=name, passed=passed, critical=critical, detail=detail))

    # --- schema + audit integrity ---
    version = current_version(db)
    add("schema_current", version >= _LATEST_SCHEMA, detail=f"version={version}")
    add("audit_chain_intact", verify_audit_chain(db).ok)

    # --- every stage constructs ---
    try:
        SignalEngine()
        PortfolioConstructionEngine()
        ResearchOrchestrator()
        WalkForwardEngine()
        ShadowDeployment("readiness")
        PaperBroker()
        add("engines_constructable", True)
    except Exception as exc:
        add("engines_constructable", False, detail=str(exc))

    # --- fail-closed probes ---
    bad_intent = OrderIntent(
        instrument="EURUSD", side="buy", kelly_fraction=0.1, risk_budget=0.01, risk_per_unit=1.0
    )
    bad_account = AccountState(equity=0.0, peak_equity=0.0, forecast_vol=0.1)
    risk_decision = risk_gate(bad_intent, bad_account)
    add("risk_gate_fail_closed", not risk_decision.approved, detail="rejects invalid equity")

    verdict = alpha_governance_gate(
        cpcv_passed=True, pbo_acceptable=True, dsr_passed=False, reality_check_passed=True,
        economic_mechanism_present=True, capacity_acceptable=True, fragility_acceptable=True,
        walk_forward_passed=True,
    )
    add("alpha_governance_fail_closed", not verdict.accepted, detail="rejects failed DSR")

    portfolio = PortfolioConstructionEngine().construct([], capital=1.0, portfolio_dsr=-1.0)
    add("portfolio_kill_fail_closed", portfolio.kill.halt, detail="halts on bad portfolio DSR")

    halted = ResearchOrchestrator().run([], false_discovery_rate=0.99)
    add("research_kill_fail_closed", halted.kill.halt, detail="halts on FDR breach")

    # --- shadow + walk-forward operational ---
    add("shadow_operational", ShadowDeployment("x").result(min_decisions=1).n_decisions == 0)

    # --- external dependencies (warnings only) ---
    add("mt5_available", _dep_present("MetaTrader5"), critical=False,
        detail="needed for live MT5 data/account")
    add("dashboard_server_available", _dep_present("streamlit"), critical=False,
        detail="needed to serve the web dashboard")

    ready = all(c.passed for c in checks if c.critical)
    return ReadinessReport(ready=ready, checks=checks)
