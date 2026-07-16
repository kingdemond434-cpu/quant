"""Governance gate, opportunity ranking, and fail-closed final selection."""

from __future__ import annotations

import pytest
from tests.signal_engine.conftest import full_governance, strong_obs

from libs.signal_engine.engine import SignalEngine
from libs.signal_engine.errors import SignalGovernanceError
from libs.signal_engine.governance import (
    GovernanceVerdict,
    require_governance,
    signal_governance_gate,
)
from libs.signal_engine.models import Direction, TradeCandidate
from libs.signal_engine.ranking import SignalRanker, rank_trade_candidates
from libs.signal_engine.selection import select_final_signals, to_package


def _candidate() -> TradeCandidate:
    built = SignalEngine()._build_candidate(strong_obs())
    assert isinstance(built, TradeCandidate)
    return built


def test_governance_gate_requires_all_eight() -> None:
    assert signal_governance_gate(full_governance())
    assert not signal_governance_gate(GovernanceVerdict())  # all default False
    partial = full_governance().model_copy(update={"shadow_period_complete": False})
    assert not signal_governance_gate(partial)


def test_require_governance_raises_on_failure() -> None:
    require_governance(full_governance())  # does not raise
    with pytest.raises(SignalGovernanceError):
        require_governance(GovernanceVerdict())


def test_ranking_orders_by_institutional_score() -> None:
    base = _candidate()
    hi = base.model_copy(
        update={"symbol": "HI", "institutional": base.institutional.model_copy(
            update={"score": 90.0})}
    )
    lo = base.model_copy(
        update={"symbol": "LO", "institutional": base.institutional.model_copy(
            update={"score": 10.0})}
    )
    ranked = rank_trade_candidates([lo, hi])
    assert [c.symbol for c in ranked] == ["HI", "LO"]
    assert SignalRanker().rank([lo, hi])[0].symbol == "HI"


def test_selection_approves_strong_candidate() -> None:
    cand = _candidate()
    result = select_final_signals([cand])
    assert len(result.approved) == 1
    pkg = result.approved[0]
    assert pkg.direction in (Direction.BUY, Direction.SELL)
    assert pkg.symbol == cand.symbol
    assert to_package(cand).institutional_score == cand.institutional.score


def test_to_package_drawdown_proxy_handles_zero_calmar() -> None:
    cand = _candidate()
    flat_calmar = cand.model_copy(
        update={"edge": cand.edge.model_copy(update={"expected_calmar": 0.0})}
    )
    assert to_package(flat_calmar).expected_drawdown == 0.0


def test_selection_rejects_low_quality() -> None:
    cand = _candidate()
    broken = cand.model_copy(
        update={"quality": cand.quality.model_copy(
            update={"quality_score": 50.0, "passed": False})}
    )
    result = select_final_signals([broken])
    assert result.approved == []
    assert result.rejected[broken.symbol] == "quality below threshold"


def test_selection_rejects_nonpositive_ev() -> None:
    cand = _candidate()
    broken = cand.model_copy(
        update={"expected_value": cand.expected_value.model_copy(update={"positive": False})}
    )
    assert select_final_signals([broken]).rejected[broken.symbol] == "expected value not positive"


def test_selection_rejects_unstable_runs_all_checks() -> None:
    # Failing the last rule means every earlier rule passed first.
    cand = _candidate()
    broken = cand.model_copy(
        update={"stability": cand.stability.model_copy(update={"passed": False})}
    )
    assert select_final_signals([broken]).rejected[broken.symbol] == "signal unstable"
