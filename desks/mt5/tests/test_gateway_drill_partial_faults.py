"""The drill's judges for the 2026-10-06 faults, graded both ways on synthetic observations.

Pure: no gateway import, no child process. The end-to-end run is `test_tier_s_gateway_drill`.
"""
from __future__ import annotations

from libs.tiers import gateway_drill as gd


def test_reconcile_before_exposure_is_judged_both_ways() -> None:
    for fault in gd.REFUSE_NEW_RISK:
        assert gd.judge(fault, {"new_risk": "NO_GATE"})[0].startswith("RECONCILE_BEFORE")
        assert gd.judge(fault, {"new_risk": True})[0].startswith("RECONCILE_BEFORE")
        assert gd.judge(fault, {"new_risk": False}) == []
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
