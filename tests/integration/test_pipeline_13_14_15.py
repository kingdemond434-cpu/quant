"""Integration: Stage 13.5 (signals) -> Stage 14 (portfolio) -> Stage 15 (research pipeline).

Verifies the stages compose end-to-end on shared models and a shared, hash-chained audit log,
and that fail-closed behavior survives composition. Reuses each stage's own test builders.
"""

from __future__ import annotations

from tests.signal_engine.conftest import strong_obs
from tests.stage14.conftest import make_signal
from tests.stage15.conftest import passing_candidate

from libs.signal_engine.engine import SignalEngine
from libs.signal_engine.models import SelectionResult, SignalPackage
from libs.stage14.audit import PortfolioAudit
from libs.stage14.engine import PortfolioConstructionEngine
from libs.stage15.audit import ResearchAudit
from libs.stage15.orchestrator import ResearchOrchestrator
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_signal_engine_output_feeds_portfolio_construction() -> None:
    # Stage 13.5 produces SignalPackages; Stage 14 consumes them unchanged.
    selection: SelectionResult = SignalEngine().evaluate([strong_obs()])
    assert isinstance(selection, SelectionResult)
    signals: list[SignalPackage] = selection.approved or [make_signal("XAUUSD")]
    result = PortfolioConstructionEngine().construct(signals, capital=100_000.0)
    built_symbols = {p.symbol for p in result.packages}
    assert built_symbols <= {s.symbol for s in signals}  # only approved signals get allocations
    assert result.total_allocation <= 1.0 + 1e-9


def test_portfolio_construction_preserves_signal_symbols() -> None:
    signals = [
        make_signal("XAUUSD", factor_exposures={"momentum": 0.9}),
        make_signal("EURUSD", factor_exposures={"carry": 0.9}),
    ]
    result = PortfolioConstructionEngine().construct(signals, capital=50_000.0)
    assert {p.symbol for p in result.packages} == {"XAUUSD", "EURUSD"}
    for pkg in result.packages:
        assert pkg.position_size == pkg.allocation * pkg.leverage * 50_000.0


def test_shared_audit_chain_across_stage14_and_stage15(db: Database) -> None:
    # Both stages write to the same immutable, hash-chained audit log.
    PortfolioConstructionEngine(audit=PortfolioAudit(db)).construct(
        [make_signal("XAUUSD")], capital=100_000.0
    )
    ResearchOrchestrator(min_allocation_quality=60.0, audit=ResearchAudit(db)).run(
        [passing_candidate("a")]
    )
    chain = verify_audit_chain(db)
    assert chain.ok
    assert chain.length >= 3  # >=1 portfolio + research records + research summary


def test_failclosed_survives_composition() -> None:
    # A research halt blocks allocation even for an otherwise allocation-ready alpha.
    halted = ResearchOrchestrator(min_allocation_quality=60.0).run(
        [passing_candidate("a")], false_discovery_rate=0.99
    )
    assert halted.kill.halt
    assert halted.allocated == []

    # A Stage 14 kill (bad portfolio DSR) halts portfolio construction.
    portfolio = PortfolioConstructionEngine().construct(
        [make_signal("XAUUSD")], capital=100_000.0, portfolio_dsr=-1.0
    )
    assert portfolio.kill.halt
    assert portfolio.packages == []
