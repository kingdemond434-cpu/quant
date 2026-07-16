"""Root Cause Engine invariants: expected variance -> do nothing; act only on evidenced causes."""

from __future__ import annotations

from libs.research.root_cause import classify, implementation_shortfall


def test_small_deviation_is_expected_variance():
    v = classify({"net_pnl": -4.0, "expected_pnl": 2.0, "funding_earned": 10.0})
    assert v["top_cause"] == "expected_variance"
    assert v["action"] == "monitor_only"                 # DO NOTHING is the verdict


def test_hedge_drift_classified_as_infrastructure():
    v = classify({"net_pnl": -180.0, "expected_pnl": 10.0, "funding_earned": 10.0,
                  "orphan_or_drift_events": 3, "restarts": 3})
    assert v["top_cause"] == "infrastructure_bug"
    assert v["action"] == "act_autonomously"             # fixing infra IS allowed


def test_assumption_break_freezes():
    v = classify({"net_pnl": -50.0, "expected_pnl": 10.0, "assumption_breaks": 2})
    assert v["top_cause"] == "model_assumption"
    assert v["action"] == "freeze_and_audit"


def test_confidence_sums_to_one_and_rule_present():
    v = classify({"net_pnl": -10.0, "expected_pnl": 0.0})
    assert abs(sum(v["confidence"].values()) - 1.0) < 0.01
    assert "PnL alone" in v["rule"]                      # the hard rule rides every verdict


def test_decay_needs_forward_deterioration():
    v = classify({"net_pnl": -30.0, "expected_pnl": 10.0, "funding_earned": 2.0,
                  "fwd_sharpe": 0.1, "bt_sharpe": 2.6})
    assert v["confidence"]["alpha_decay"] > 0.1          # flagged, but only governance retires


def test_shortfall_attributes_missing_bps():
    s = implementation_shortfall(11.0, 3.0, 4.0)
    assert s["after_fees_bps"] == 8.0 and s["missing_bps"] == 4.0   # the actionable question
