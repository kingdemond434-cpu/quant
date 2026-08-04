"""CONTRIBUTION ESTIMATES -- the allocator's own named bottleneck, made computable.

WHAT IS ACTUALLY UNDER TEST. P4 routes the marginal resource to argmax_i |dE[log W]/dC_i|. Every
allocator run this desk has ever done reported the binding constraint as "CONTRIBUTION ESTIMATES",
because no term in that expression had ever been computed -- so the allocation was a guess wearing
a formula. This module lets a subsystem state a contribution from whatever evidence it has, with
the provenance of that evidence attached.

THE TWO FAILURES IT SITS BETWEEN, and the tests are organised around them. Refusing to estimate
without live data is not neutrality -- it silently assigns a subsystem zero and routes resource
away from it forever (P23 timidity). Asserting a live-quality number from a backtest is the
opposite failure (P8). Provenance-inflated standard errors are what makes both avoidable at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.doctrine.contribution import (
    PROVENANCE,
    Contribution,
    credibility,
    rank,
    summarise,
    unestimated,
    widen_for_disagreement,
)


def _c(sub="x", value=0.01, se=0.002, n=30, prov="LIVE", basis="measured over 30 cycles"):
    return Contribution(sub, f"dE[logW]/d({sub})", value, se, n, prov, basis)


# ------------------------------------------------------------------ provenance is the mechanism


def test_the_provenance_ladder_is_ordered_worst_to_best() -> None:
    """Each step down the ladder removes something specific that makes an estimate trustworthy.
    If the order were not monotone, a weaker evidence class could outrank a stronger one at equal
    measured precision -- which would make the whole ladder decorative."""
    order = ["LIVE", "SHADOW", "BACKTEST", "PRIOR", "NEVER_EXECUTED"]
    factors = [PROVENANCE[k][0] for k in order]
    assert factors == sorted(factors), factors
    assert factors[0] == 1.0, "LIVE is the estimand itself and must not be inflated"


def test_an_unknown_provenance_is_treated_as_the_worst_case() -> None:
    """A typo must never silently promote an estimate to live quality. Defaulting the other way
    means the one class of error nobody can see also happens to be the dangerous one."""
    assert credibility("typo-here") == PROVENANCE["NEVER_EXECUTED"]
    assert credibility("live") == PROVENANCE["LIVE"], "case must not matter"


def test_provenance_widens_the_interval_and_never_shrinks_the_value() -> None:
    """THE DESIGN DECISION THIS MODULE TURNS ON. Multiplying the point estimate toward zero to
    express doubt double-counts: it corrupts the quantity being estimated in order to say
    something about how well it is known, and it makes a confident-but-unproven claim look
    identical to a measured-and-small one."""
    live = _c(value=0.01, se=0.002, prov="LIVE")
    back = _c(value=0.01, se=0.002, prov="BACKTEST")
    assert back.estimate().value == live.estimate().value == 0.01
    assert back.estimate().se > live.estimate().se


def test_a_never_executed_contribution_can_never_become_actionable() -> None:
    """It is ranked so the gap stays visible and costed -- never so it can be mistaken for a
    finding. A subsystem that has never run must not be able to pull resource toward itself on
    the strength of its owner's optimism."""
    c = _c(value=99.0, se=0.0001, n=0, prov="NEVER_EXECUTED", basis="strong belief, no run")
    assert c.actionable() is False


def test_a_fabricated_sample_size_is_refused_rather_than_inflated() -> None:
    """CAUGHT BY THIS SUITE, NOT BY REVIEW. Credibility inflation multiplies a SELF-REPORTED
    standard error, so an author claiming se=0.0001 on a value of 99 sails through every factor
    the ladder can apply and becomes actionable. The incoherence is in the n -- observations of
    WHAT, on a path that has never run? -- and clamping it quietly would leave the same false
    confidence sitting in the artifact for a later reader to trust."""
    with pytest.raises(ValueError, match="cannot have observations"):
        Contribution("x", "d", 99.0, 0.0001, 1000, "NEVER_EXECUTED", "strong belief, no run")


def test_the_refusal_names_the_two_honest_ways_out() -> None:
    """A refusal that does not say what to do instead gets worked around rather than fixed."""
    with pytest.raises(ValueError) as e:
        Contribution("x", "d", 1.0, 0.1, 5, "NEVER_EXECUTED", "b")
    assert "PRIOR, BACKTEST, SHADOW or LIVE" in str(e.value) and "n is 0" in str(e.value)


def test_a_zero_observation_estimate_does_not_claim_infinite_precision() -> None:
    """se=0 with n=0 would read as a perfectly known quantity and win every ranking it entered.
    The floor is what stops absence of measurement masquerading as certainty."""
    c = _c(value=0.05, se=0.0, n=0, prov="PRIOR", basis="reasoned from mechanism")
    assert c.estimate().se > 0.0


# ------------------------------------------------------------------ the estimate must be auditable


def test_an_estimate_with_no_basis_is_refused_at_construction() -> None:
    """An estimate whose author cannot say what was measured is a number. The allocator must
    never rank on those, and catching it at construction means it cannot reach the ranking at
    all rather than being filtered later by something that might forget."""
    with pytest.raises(ValueError, match="basis is required"):
        Contribution("x", "d", 0.1, 0.01, 10, "LIVE", "   ")


def test_a_negative_standard_error_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        Contribution("x", "d", 0.1, -0.01, 10, "LIVE", "measured")


# ------------------------------------------------------------------ ranking


def test_stronger_evidence_outranks_a_larger_but_weaker_estimate() -> None:
    """The whole point of the ladder. A backtest claiming three times the contribution of a live
    measurement should NOT take the resource, because the ranking is penalised by width and the
    backtest's width is inflated."""
    live = _c("measured", value=0.004, se=0.0005, n=60, prov="LIVE")
    guess = _c("hoped", value=0.012, se=0.0005, n=0, prov="NEVER_EXECUTED")
    rows = rank([guess, live])
    assert rows[0]["subsystem"] == "measured", [r["subsystem"] for r in rows]


def test_cheapness_cannot_buy_a_wide_estimate_up_the_ranking() -> None:
    """Penalised BEFORE dividing by cost, deliberately. Cheapness is a reason to TRY something;
    it is never a reason to believe it, and dividing an unpenalised estimate by a small cost
    would convert low confidence into high priority."""
    wide_cheap = _c("cheap", value=0.01, se=0.02, n=30, prov="LIVE")
    tight_dear = _c("dear", value=0.01, se=0.0005, n=30, prov="LIVE")
    rows = rank([wide_cheap, tight_dear], costs={"cheap": 0.1, "dear": 1.0})
    assert rows[0]["subsystem"] == "dear", [(r["subsystem"], r["density"]) for r in rows]


def test_everything_is_ranked_including_what_cannot_be_acted_on() -> None:
    """A subsystem excluded from the ranking is a subsystem assigned ZERO, and zero is a far
    stronger claim than 'unmeasured'. Exclusion is how three subsystems stayed invisible for
    twenty-five cycles."""
    cs = [_c("a", prov="LIVE"), _c("b", n=0, prov="NEVER_EXECUTED")]
    rows = rank(cs)
    assert {r["subsystem"] for r in rows} == {"a", "b"}
    assert [r["rank"] for r in rows] == [1, 2]


def test_the_ranking_explains_why_each_interval_was_widened() -> None:
    """Auditability: six weeks later somebody must be able to see why a subsystem lost, without
    re-deriving the ladder from the source."""
    rows = rank([_c(prov="BACKTEST")])
    assert "historical replay" in rows[0]["why_inflated"]
    assert rows[0]["se_effective"] > rows[0]["se_raw"]


# ------------------------------------------------------------------ the residual gap


def test_a_subsystem_nobody_has_spoken_about_is_distinguished_from_an_unproven_one() -> None:
    """THE DISTINCTION THAT JUSTIFIES HAVING BOTH. NEVER_EXECUTED is an owner stating a belief and
    labelling it unproven -- that subsystem is instrumented. Silence is the actual gap, and
    collapsing the two would let the desk report a full table while nobody had spoken."""
    cs = [_c("spoken", n=0, prov="NEVER_EXECUTED")]
    assert unestimated({"spoken", "silent"}, cs) == ["silent"]
    s = summarise(cs, {"spoken", "silent"})
    assert s["argmax_computable"] is False
    assert "silently assigns the rest zero" in s["note"]


def test_argmax_is_computable_only_when_every_subsystem_has_spoken() -> None:
    cs = [_c("a"), _c("b")]
    s = summarise(cs, {"a", "b"})
    assert s["argmax_computable"] is True
    assert s["estimated_pct"] == 100.0


# ------------------------------------------------------------------ disagreement


def test_disagreeing_methods_widen_the_interval_rather_than_average_away() -> None:
    """Two methods that AGREE tell you more than one; two that DISAGREE tell you the standard
    error was understated. Averaging the disagreement away reports precision the desk does not
    have -- the specific dishonesty P8 exists to prevent."""
    base = _c(value=0.010, se=0.001, prov="LIVE")
    widened = widen_for_disagreement(base, [0.030, 0.002])
    assert widened.se > base.se
    assert "disagreement-widened" in widened.tags
    assert "spread" in widened.basis


def test_agreement_between_methods_does_not_inflate() -> None:
    """The mechanism must be driven by DISAGREEMENT specifically, or it degenerates into a
    penalty for looking twice -- which would discourage exactly the second opinion that makes an
    estimate trustworthy."""
    base = _c(value=0.010, se=0.001, prov="LIVE")
    same = widen_for_disagreement(base, [0.010, 0.010])
    assert same.se == pytest.approx(base.se, rel=1e-9)


def test_no_competing_estimates_leaves_the_contribution_untouched() -> None:
    base = _c()
    assert widen_for_disagreement(base, []) is base
