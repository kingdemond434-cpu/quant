"""End-to-end portfolio construction, attribution, and audit."""

from __future__ import annotations

import numpy as np
import pytest
from tests.stage14.conftest import make_signal

from libs.stage14.attribution import PortfolioAttributionEngine
from libs.stage14.audit import PortfolioAudit
from libs.stage14.engine import PortfolioConstructionEngine
from libs.stage14.models import PortfolioState
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_construct_allocates_approved_signals() -> None:
    signals = [
        make_signal("XAUUSD", factor_exposures={"momentum": 0.9}),
        make_signal("EURUSD", factor_exposures={"carry": 0.9}),
        make_signal("US500", factor_exposures={"volatility": 0.9}),
    ]
    result = PortfolioConstructionEngine().construct(signals, capital=100_000.0)
    assert len(result.packages) == 3
    assert result.state is PortfolioState.NORMAL
    assert result.total_allocation <= 1.0 + 1e-9
    for pkg in result.packages:
        assert pkg.allocation > 0
        assert pkg.position_size == pytest.approx(pkg.allocation * pkg.leverage * 100_000.0)
        assert 0.0 <= pkg.institutional_score <= 100.0


def test_construct_rejects_non_positive_ev() -> None:
    signals = [
        make_signal("XAUUSD"),
        make_signal("EURUSD", expected_value=-0.01),
    ]
    result = PortfolioConstructionEngine().construct(signals, capital=100_000.0)
    assert "EURUSD" in result.rejected
    assert "expected value" in result.rejected["EURUSD"]
    assert [p.symbol for p in result.packages] == ["XAUUSD"]


def test_construct_halts_on_kill_criteria() -> None:
    result = PortfolioConstructionEngine().construct(
        [make_signal("XAUUSD")], capital=100_000.0, portfolio_dsr=-1.0
    )
    assert result.kill.halt
    assert result.packages == []
    assert result.state is PortfolioState.CRISIS


def test_crisis_drawdown_zeroes_allocations() -> None:
    result = PortfolioConstructionEngine().construct(
        [make_signal("XAUUSD")], capital=100_000.0, current_drawdown=0.25
    )
    assert result.state is PortfolioState.CRISIS
    assert result.total_allocation == pytest.approx(0.0)
    assert result.kill.defensive_mode  # drawdown beyond max -> defensive


def test_walk_forward_failure_blocks_allocation() -> None:
    result = PortfolioConstructionEngine().construct(
        [make_signal("XAUUSD")], capital=100_000.0, walk_forward_passed=False
    )
    assert result.packages == []
    assert result.kill.no_new_capital


def test_construct_writes_audit(db: Database) -> None:
    engine = PortfolioConstructionEngine(audit=PortfolioAudit(db))
    result = engine.construct([make_signal("XAUUSD")], capital=100_000.0)
    assert result.packages
    chain = verify_audit_chain(db)
    assert chain.ok
    assert chain.length >= len(result.packages) + 1  # per-package + construction summary


def test_construct_with_returns_and_correlation() -> None:
    rng = np.random.default_rng(0)
    returns = 0.004 + rng.normal(0.0, 0.008, size=400)  # survivable positive drift
    correlation = np.array([[1.0, 0.1], [0.1, 1.0]])
    signals = [
        make_signal("XAUUSD", factor_exposures={"momentum": 0.9}),
        make_signal("EURUSD", factor_exposures={}),  # no factors -> OTHER sleeve
    ]
    result = PortfolioConstructionEngine().construct(
        signals, capital=100_000.0, portfolio_returns=returns, correlation=correlation
    )
    assert result.packages
    # survival/diversification now derive from the supplied data, not the neutral defaults
    assert all(0.0 <= p.survival_score <= 100.0 for p in result.packages)
    assert all(p.diversification_score > 0 for p in result.packages)


def test_construct_normalizes_to_max_gross() -> None:
    signals = [
        make_signal("XAUUSD", factor_exposures={"momentum": 0.9}),
        make_signal("EURUSD", factor_exposures={"carry": 0.9}),
    ]
    result = PortfolioConstructionEngine(max_gross=0.5).construct(signals, capital=100_000.0)
    assert result.total_allocation <= 0.5 + 1e-9


def test_construct_all_rejected_with_audit(db: Database) -> None:
    engine = PortfolioConstructionEngine(audit=PortfolioAudit(db))
    result = engine.construct(
        [make_signal("XAUUSD", expected_value=-0.01)], capital=100_000.0
    )
    assert result.packages == []
    assert "XAUUSD" in result.rejected
    assert verify_audit_chain(db).ok  # summary still journaled


def test_construct_halt_with_audit(db: Database) -> None:
    engine = PortfolioConstructionEngine(audit=PortfolioAudit(db))
    result = engine.construct([make_signal("XAUUSD")], capital=100_000.0, portfolio_dsr=-1.0)
    assert result.kill.halt
    assert verify_audit_chain(db).ok


def test_portfolio_attribution() -> None:
    attr = PortfolioAttributionEngine().attribute(
        gross_return=0.04, cost=0.01,
        sleeve_weights={"trend": 0.6, "carry": 0.4}, regime="trend",
    )
    assert attr.net_return == pytest.approx(0.03)
    assert attr.by_sleeve["trend"] == pytest.approx(0.024)
    assert attr.by_regime["trend"] == pytest.approx(0.03)
