"""BEHAVIORAL tests for the external performance benchmark.

The two failures this subsystem exists to prevent, and they are opposite:

    a TARGET quietly becoming an achieved return, so we chase a number nobody hit
    a lead computed from an incomparable pair, so we believe we are winning when we are not

Both are tested from both sides -- our own side is held to the same standard as the other one.
"""

from __future__ import annotations

import pytest

from libs.research.external_benchmark import (
    EVIDENCE_CLASSES,
    MIN_COMPARABLE_DAYS,
    BenchmarkClaim,
    OwnPerformance,
    comparable,
    log_growth_from_claim,
    performance_lead,
    promote,
    summarise,
    win_conditions,
)


def _claim(**kw) -> BenchmarkClaim:
    base: dict[str, object] = {
        "claimant": "public operator", "source": "video 2026-03-02",
        "observed_at": "2026-03-02T00:00:00Z", "evidence_class": "SELF_REPORTED",
        "start_value": 1_000.0, "end_value": 20_000.0, "elapsed_days": 120.0}
    base.update(kw)
    return BenchmarkClaim(**base)  # type: ignore[arg-type]


def _own(**kw) -> OwnPerformance:
    base: dict[str, object] = {
        "realized_log_growth": 0.35, "elapsed_days": 180.0, "deployed_capital": 4_000.0,
        "total_capital": 10_000.0, "max_drawdown": 0.12, "real_fills": 430,
        "realised_pnl": 1_400.0}
    base.update(kw)
    return OwnPerformance(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------ targets are not results

def test_a_target_has_no_growth_to_compute() -> None:
    g, why = log_growth_from_claim(_claim(evidence_class="TARGET"))
    assert g is None
    assert "TARGET, not a result" in why
    assert "by the passage of time" in why


def test_a_target_cannot_be_promoted_without_a_new_source() -> None:
    """THE NAMED FAILURE. A '10x' announced in month one becomes a 10x result in month six, and
    the record that would have said otherwise was overwritten."""
    t = _claim(evidence_class="TARGET")
    with pytest.raises(ValueError, match=r"requires a\s+NEW source"):
        promote(t, to_class="VERIFIED", new_source="   ")


def test_promotion_requires_strictly_stronger_evidence() -> None:
    c = _claim(evidence_class="VERIFIED")
    with pytest.raises(ValueError, match="refusing to move"):
        promote(c, to_class="SELF_REPORTED", new_source="a blog post")
    with pytest.raises(ValueError, match="refusing to move"):
        promote(c, to_class="VERIFIED", new_source="the same thing again")


def test_a_legitimate_promotion_keeps_the_history_legible() -> None:
    c = _claim(evidence_class="PUBLIC_DASHBOARD")
    up = promote(c, to_class="PARTIALLY_VERIFIABLE", new_source="on-chain settlement records")
    assert up.evidence_class == "PARTIALLY_VERIFIABLE"
    assert "on-chain settlement records" in up.verification_notes
    assert up.start_value == c.start_value


def test_the_evidence_ladder_is_ordered_weakest_first() -> None:
    assert EVIDENCE_CLASSES[0] == "TARGET"
    assert EVIDENCE_CLASSES[-1] == "AUDITED"


# --------------------------------------------------------------- comparability gating

@pytest.mark.parametrize("kw,expect", [
    ({"evidence_class": "SELF_REPORTED"}, "below"),
    ({"evidence_class": "VERIFIED", "net_of_costs": False}, "gross and ours is net"),
    ({"evidence_class": "VERIFIED", "net_of_costs": True, "realised": False}, "unrealised mark"),
    ({"evidence_class": "VERIFIED", "net_of_costs": True, "realised": True,
      "flows_disclosed": False}, "undisclosed"),
    ({"evidence_class": "VERIFIED", "net_of_costs": True, "realised": True,
      "flows_disclosed": True, "elapsed_days": 10.0}, "shortest horizon"),
])
def test_an_incomparable_pair_yields_no_lead_and_says_why(kw, expect) -> None:
    ok, why = comparable(_claim(**kw), _own())
    assert ok is False
    assert expect in why
    lead, lwhy = performance_lead(_claim(**kw), _own())
    assert lead is None
    assert "LEAD NOT REPORTABLE" in lwhy


def test_a_genuinely_comparable_pair_produces_a_signed_lead() -> None:
    c = _claim(evidence_class="VERIFIED", net_of_costs=True, realised=True,
               flows_disclosed=True, estimated_beta_share=0.6,
               start_value=1_000.0, end_value=1_400.0, elapsed_days=180.0)
    lead, why = performance_lead(c, _own())
    assert lead is not None
    # ours: 0.35 over 180d; theirs: log(1.4) = 0.3365 over 180d -> we lead slightly
    assert lead == pytest.approx(0.35 * (365 / 180) - 0.33647 * (365 / 180), abs=0.01)
    assert "PERFORMANCE_LEAD" in why
    assert "annualising a short window inflates BOTH sides" in why


def test_caveats_are_attached_to_every_weak_external_figure() -> None:
    _, why = log_growth_from_claim(_claim(evidence_class="SELF_REPORTED"))
    for c in ("GROSS of costs", "unrealised marks", "flows undisclosed", "beta share unmeasured"):
        assert c in why


# ------------------------------------------------------- our own side is not exempt

def test_surviving_by_not_deploying_is_not_a_win() -> None:
    wc = win_conditions(_own(deployed_capital=0.0, total_capital=10_000.0))
    assert wc["REAL_CAPITAL"][0] is False
    assert "abstention" in wc["REAL_CAPITAL"][1]


def test_a_simulation_result_cannot_enter_the_comparison() -> None:
    wc = win_conditions(_own(real_fills=0))
    assert wc["REAL_FILLS"][0] is False
    assert "simulation result" in wc["REAL_FILLS"][1]


def test_unrealised_gains_are_refused_from_our_side_too() -> None:
    wc = win_conditions(_own(realised_pnl=0.0))
    assert wc["RETAINED_PROFIT"][0] is False
    assert "exact thing this benchmark refuses to accept from the other side" \
        in wc["RETAINED_PROFIT"][1]


def test_a_short_live_horizon_fails_our_own_win_condition() -> None:
    wc = win_conditions(_own(elapsed_days=20.0))
    assert wc["SUFFICIENT_TIME"][0] is False


def test_all_win_conditions_can_be_met() -> None:
    wc = win_conditions(_own())
    assert all(ok for ok, _ in wc.values()), {k: v for k, (ok, v) in wc.items() if not ok}


# ------------------------------------------------------------------------------ report

def test_the_report_counts_targets_separately_and_never_as_results() -> None:
    rep = summarise([_claim(evidence_class="TARGET"),
                     _claim(evidence_class="SELF_REPORTED"),
                     _claim(evidence_class="VERIFIED", net_of_costs=True, realised=True,
                            flows_disclosed=True)], _own())
    assert rep["targets_recorded"] == 1
    assert rep["usable_for_comparison"] == 1
    assert "TARGETS and never will be without a new observation" in str(rep["headline"])


def test_an_unreportable_lead_is_stated_as_a_fact_about_the_evidence() -> None:
    rep = summarise([_claim(evidence_class="TARGET")], _own())
    assert "fact about the evidence rather than about the performance" in str(rep["headline"])


def test_the_horizon_floor_is_not_silently_tiny() -> None:
    assert MIN_COMPARABLE_DAYS >= 90
