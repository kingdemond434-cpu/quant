"""Half-Kelly is earned: the engine's roi_qualified wiring (committee Kelly policy)."""

from __future__ import annotations

from tests.stage14.conftest import make_signal

from libs.stage14.engine import PortfolioConstructionEngine


def test_strong_signal_qualifies_for_half_kelly() -> None:
    eng = PortfolioConstructionEngine()
    strong = make_signal("XAUUSD")  # defaults clear every ROI threshold
    assert eng._roi_qualified(strong, walk_forward_passed=True) is True
    # walk-forward failure alone disqualifies (no out-of-sample proof -> stay at 1/3 base)
    assert eng._roi_qualified(strong, walk_forward_passed=False) is False


def test_marginal_signals_stay_at_third_kelly() -> None:
    eng = PortfolioConstructionEngine()
    assert eng._roi_qualified(make_signal(edge_score=55.0), walk_forward_passed=True) is False
    assert eng._roi_qualified(make_signal(capacity_score=50.0), walk_forward_passed=True) is False
    assert eng._roi_qualified(make_signal(expected_pf=1.1), walk_forward_passed=True) is False
    assert eng._roi_qualified(make_signal(confidence=0.4), walk_forward_passed=True) is False
    assert eng._roi_qualified(make_signal(expected_value=-0.01), walk_forward_passed=True) is False
