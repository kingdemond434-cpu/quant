"""Portfolio state machine, institutional score, governance gate, and kill criteria."""

from __future__ import annotations

from libs.stage14.governance import PortfolioKillCriteria, portfolio_governance_gate
from libs.stage14.models import PortfolioState
from libs.stage14.score import institutional_portfolio_score
from libs.stage14.state_machine import PortfolioStateMachine


def test_state_machine_classifies_and_scales() -> None:
    sm = PortfolioStateMachine()
    assert sm.classify(drawdown=0.0) is PortfolioState.NORMAL
    assert sm.classify(drawdown=0.07) is PortfolioState.CAUTION
    assert sm.classify(drawdown=0.13) is PortfolioState.DEFENSIVE
    assert sm.classify(drawdown=0.25) is PortfolioState.CRISIS
    assert sm.classify(drawdown=0.30, survival_score=40.0) is PortfolioState.CRISIS
    assert sm.classify(drawdown=0.02, recovering=True) is PortfolioState.RECOVERY
    assert sm.risk_multiplier(PortfolioState.CRISIS) == 0.0
    assert sm.risk_multiplier(PortfolioState.NORMAL) == 1.0


def test_institutional_score_survival_dominates() -> None:
    strong = institutional_portfolio_score(
        survival_score=95.0, geometric_growth_score=80.0, expected_sharpe=2.0,
        expected_calmar=2.0, capacity_score=90.0, diversification_score=80.0,
    )
    weak_survival = institutional_portfolio_score(
        survival_score=20.0, geometric_growth_score=80.0, expected_sharpe=2.0,
        expected_calmar=2.0, capacity_score=90.0, diversification_score=80.0,
    )
    assert strong.score > weak_survival.score
    assert 0.0 <= weak_survival.score <= 100.0


def test_governance_gate_fail_closed() -> None:
    kwargs = {
        "signal_approved": True, "expected_value": 0.01, "portfolio_contribution": 0.1,
        "capacity_available": True, "survival_score": 80.0, "fragility": 0.1,
        "correlation_acceptable": True, "walk_forward_passed": True,
    }
    allowed, _ = portfolio_governance_gate(**kwargs)  # type: ignore[arg-type]
    assert allowed

    for override in (
        {"expected_value": -0.01},
        {"portfolio_contribution": 0.0},
        {"capacity_available": False},
        {"survival_score": 10.0},
        {"fragility": 0.9},
        {"correlation_acceptable": False},
        {"walk_forward_passed": False},
        {"signal_approved": False},
    ):
        blocked, reason = portfolio_governance_gate(**{**kwargs, **override})  # type: ignore[arg-type]
        assert not blocked
        assert reason


def test_kill_criteria() -> None:
    kc = PortfolioKillCriteria(min_dsr=0.0, min_survival_score=50.0, max_drawdown=0.20)
    clean = kc.evaluate(portfolio_dsr=1.0, survival_score=80.0, drawdown=0.05,
                        walk_forward_passed=True)
    assert not clean.halt and not clean.defensive_mode and not clean.no_new_capital

    halt = kc.evaluate(portfolio_dsr=-1.0, survival_score=80.0, drawdown=0.05,
                       walk_forward_passed=True)
    assert halt.halt

    defensive = kc.evaluate(portfolio_dsr=1.0, survival_score=80.0, drawdown=0.25,
                            walk_forward_passed=True)
    assert defensive.defensive_mode

    no_capital = kc.evaluate(portfolio_dsr=1.0, survival_score=80.0, drawdown=0.05,
                             walk_forward_passed=False)
    assert no_capital.no_new_capital

    low_survival = kc.evaluate(portfolio_dsr=1.0, survival_score=30.0, drawdown=0.05,
                               walk_forward_passed=True)
    assert low_survival.halt  # survival below floor halts the book
