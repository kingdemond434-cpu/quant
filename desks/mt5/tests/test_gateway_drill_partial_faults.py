"""The drill's judges for the 2026-10-06 faults, graded both ways on synthetic observations.

Pure: no gateway import, no child process. The end-to-end run is `test_tier_s_gateway_drill`.
"""
from __future__ import annotations

from libs.tiers import gateway_drill as gd


def test_reconcile_before_exposure_is_judged_both_ways() -> None:
    for fault in gd.REFUSE_NEW_RISK:
        assert gd.judge(fault, {"new_risk": "NO_GATE"})[0].startswith("RECONCILE_BEFORE")
        assert gd.judge(fault, {"new_risk": True})[0].startswith("RECONCILE_BEFORE")
        # REFUSED_FOR_THE_RIGHT_REASON: a refusal must name its own cause.
        why = " / ".join(gd.EXPECTED_WHY.get(fault, ()))
        assert gd.judge(fault, {"new_risk": False, "new_risk_why": why}) == []
        if gd.EXPECTED_WHY.get(fault):
            wrong = gd.judge(fault, {"new_risk": False, "new_risk_why": "release identity"})
            assert wrong[0].startswith("REFUSED_FOR_THE_RIGHT_REASON")
    # a gate that refuses everything is a finding too: a healthy pass must still trade
    assert gd.judge("healthy", {"new_risk": False})[0].startswith("RECONCILE_BEFORE")
    assert gd.judge("healthy", {"new_risk": True}) == []
    assert set(gd.REFUSE_NEW_RISK) <= set(gd.FAULTS)
    assert "stale_positions" in gd.REFUSE_NEW_RISK


def test_partial_fill_is_judged_on_the_basket_and_the_send_count() -> None:
    good = {"scalp_sends": 1, "scalp_basket": {"entries": [[100.0, 0.02]], "residual": 0.02}}
    assert gd.judge("partial_fill", good) == []
    assert gd.judge("partial_fill", {"scalp_sends": 1, "scalp_basket": None})
    asked = {"scalp_sends": 1, "scalp_basket": {"entries": [[100.0, 0.04]]}}
    assert any("holds 0.04" in b for b in gd.judge("partial_fill", asked))
    resent = {**good, "scalp_sends": 2}
    assert gd.judge("partial_fill", resent)[0].startswith("PARTIAL_FILL_RECORDED")


def test_close_partial_is_judged_on_the_residual_and_no_resend() -> None:
    assert gd.judge("close_partial", {"close_sends": 1, "close_residual": {"777": 0.02}}) == []
    assert gd.judge("close_partial", {"close_sends": 1, "close_residual": None})
    assert gd.judge("close_partial", {"close_sends": 2, "close_residual": {"777": 0.02}})


def test_the_2026_10_07_faults_are_judged_both_ways() -> None:
    """Family/bracket partials, a healthy partial close, netting armed and unarmed, and a
    close-only session: each judge passes the right observation and names the wrong one."""
    fam = {"fam_sends": 1, "fam_residual": {"lots": 0.02, "expires": "2026-10-07T11:00"},
           "fam_book": {"target": 0.02, "filled": 0.02}, "fam_ttl": "x", "fam_retired": 1,
           "fam_residual_after": None}
    assert gd.judge("family_partial", fam) == []
    assert gd.judge("family_partial", {**fam, "fam_sends": 2})
    assert gd.judge("family_partial", {**fam, "fam_book": {"target": 0.04, "filled": 0.02}})
    assert gd.judge("family_partial", {**fam, "fam_residual_after": {"lots": 0.02}})
    assert gd.judge("bracket_partial", {"bp_book": {"target": 0.02, "filled": 0.02}}) == []
    assert gd.judge("bracket_partial", {"bp_book": {"target": 0.04, "filled": 0.02}})
    assert gd.judge("healthy_partial_close", {"new_risk": True}) == []
    assert gd.judge("healthy_partial_close", {"new_risk": False})[0].startswith(
        "PARTIAL_CLOSE_IS_HEALTHY")
    filled = {"net_long": 0.04, "net_short": -0.01}
    armed = {"net_sent": [{"side": "buy", "volume": 0.03}], "net_filled": filled,
             "net_account": 0.03, "net_long_basket": 0.03}
    assert gd.judge("netting_armed", armed) == []
    two = [{"side": "buy", "volume": 0.04}, {"side": "sell", "volume": 0.01}]
    assert any(b.startswith("NETTING_ROUTED") for b in gd.judge(
        "netting_armed", {**armed, "net_sent": two}))
    assert gd.judge("netting_unarmed", {**armed, "net_sent": two, "net_long_basket": 0.04}) == []
    assert gd.judge("netting_unarmed", armed)
    assert gd.judge("netting_armed", {**armed, "net_filled": {"net_long": 0.03}})
    closed = {"sends": 0, "bracket_stage": "session_closed", "scalp_sends": 0,
              "session_refusal": "session: EURUSD trade_mode CLOSEONLY", "session_gate": False,
              "session_gate_why": "session: EURUSD trade_mode CLOSEONLY"}
    assert gd.judge("session_closed", closed) == []
    assert gd.judge("session_closed", {**closed, "scalp_sends": 1})
    assert gd.judge("session_closed", {**closed, "sends": 2, "bracket_stage": None})
