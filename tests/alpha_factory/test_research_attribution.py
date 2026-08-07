"""RESEARCH ATTRIBUTION -- and the multiple-testing surface nobody guards.

The desk deflates ALPHA selection: DSR, PBO, sqrt(2 ln N). Then it runs eight generation methods,
reads off "method C survived at 1.8% vs 0.4% pooled", and reallocates the research budget to C with
no deflation whatsoever -- because choosing among METHODS does not look like a backtest.

It is one. With eight methods and a few hundred trials each, a spread that wide arises from
sampling noise routinely. And a false attribution is worse than a false alpha: an alpha loses one
allocation, while a misdirected search process is inherited by every future batch, invisibly,
with the telemetry agreeing throughout.

Four properties are load-bearing here and each is a test below:
  1. a flattering point estimate on thin trials does NOT steer budget;
  2. the bar tightens as more methods are compared (Sidak), so adding methods cannot buy a winner;
  3. with zero survivors anywhere, NOTHING is better than the pool -- the desk's actual state, and
     the one where a confident ranking would be pure noise;
  4. UNDECIDED methods are not penalised, or they starve into permanent under-power.
"""

from __future__ import annotations

import pytest

from libs.alpha_factory.research_attribution import (
    FAMILY_ALPHA,
    Maturity,
    attribute,
    classify,
    ladder_census,
    sidak_alpha,
    steer_weights,
    wilson_interval,
)

# ------------------------------------------------------------------- the ladder, not a flag

def test_TOUCHED_IS_NOT_TESTED_AND_UNEXPLORED_IS_NOT_TOUCHED() -> None:
    """The collapse of these three is how a desk decides a region is finished. `UNEXPLORED` and
    `TOUCHED` both mean "we know nothing here" -- but only one looks like work was done, and an
    exploration engine treating them alike walks away from a region it merely glanced at."""
    assert classify(0) is Maturity.UNEXPLORED
    assert classify(8, min_n=30) is Maturity.TOUCHED
    assert classify(500, min_n=30) is Maturity.ADEQUATELY_TESTED
    assert Maturity.UNEXPLORED.rank < Maturity.TOUCHED.rank < Maturity.ADEQUATELY_TESTED.rank


def test_A_SURVIVOR_REQUIRES_OUT_OF_SAMPLE_NO_MATTER_HOW_GOOD_THE_IN_SAMPLE_NUMBER() -> None:
    """"Cleared the bar" computed in-sample is precisely the claim the deflation exists to
    disbelieve. The flag is required rather than implied."""
    assert classify(50_000, out_of_sample=False, cleared_deflated_bar=True) \
        is Maturity.ADEQUATELY_TESTED
    assert classify(50_000, out_of_sample=True, cleared_deflated_bar=False) \
        is Maturity.ROBUSTLY_VALIDATED
    assert classify(50_000, out_of_sample=True, cleared_deflated_bar=True) is Maturity.SURVIVOR


def test_RETIRED_OUTRANKS_EVERYTHING() -> None:
    """A retired survivor is not a survivor. Reporting it as one keeps a graveyard entry counting
    toward the live tally, inflating every rate that divides by it."""
    assert classify(50_000, out_of_sample=True, cleared_deflated_bar=True, live=True,
                    retired=True) is Maturity.RETIRED


def test_THE_CENSUS_ALWAYS_SHOWS_THE_EMPTY_RUNGS() -> None:
    """Omitting zero-count rungs is the small reporting choice that hides the finding: `touched:
    412` alone reads as progress; `survivor: 0` beside it reads as the truth."""
    census = ladder_census([Maturity.TOUCHED] * 412)
    assert census["touched"] == 412
    assert census["survivor"] == 0
    assert set(census) == {m.value for m in Maturity}


# ------------------------------------------------------------ the interval, where p is near zero

def test_WILSON_DOES_NOT_CLAIM_CERTAINTY_FROM_ZERO_SUCCESSES() -> None:
    """The normal approximation gives 0% +/- 0% for 0/50 -- perfect certainty derived from no
    information -- which would make an untried method look conclusively dead. Survivor rates live
    at exactly this end of the scale."""
    lo, hi = wilson_interval(0, 50)
    assert lo == 0.0
    assert hi > 0.0, "an interval of zero width from zero successes is a false certainty"
    assert wilson_interval(0, 5)[1] > hi, "a smaller sample must give a WIDER interval"


def test_NO_TRIALS_IS_TOTAL_IGNORANCE() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_THE_INTERVAL_TIGHTENS_WITH_SAMPLE_SIZE() -> None:
    wide = wilson_interval(5, 50)
    narrow = wilson_interval(500, 5000)
    assert (narrow[1] - narrow[0]) < (wide[1] - wide[0])


# ---------------------------------------------------------- comparing methods IS multiple testing

def test_THE_BAR_TIGHTENS_AS_MORE_METHODS_ARE_COMPARED() -> None:
    """Otherwise adding methods buys a winner: with enough candidates one always looks good, and
    the desk would reallocate to whichever noise draw came out highest."""
    assert sidak_alpha(FAMILY_ALPHA, 8) < sidak_alpha(FAMILY_ALPHA, 2) < FAMILY_ALPHA
    assert sidak_alpha(FAMILY_ALPHA, 1) == FAMILY_ALPHA, (
        "one method is not a family -- inflating the bar there makes the desk unable to learn "
        "anything from its first method")


def test_A_FLATTERING_RATE_ON_THIN_TRIALS_CANNOT_MOVE_BUDGET() -> None:
    """3/12 is 25%, six times the pooled rate, and means nothing. This is the single most likely
    way for the attribution layer to misdirect the whole search programme."""
    att = attribute({"thin": (3, 12), "fat": (40, 1000), "other": (35, 1000)})
    thin = next(m for m in att.methods if m.method == "thin")
    assert thin.rate > att.pooled_rate * 2
    assert thin.verdict == "UNDERPOWERED"
    assert thin.steerable is False


def test_A_GENUINELY_BETTER_METHOD_IS_DETECTED() -> None:
    """The other half of the bar: a guard that never says BETTER cannot steer anything, and the
    attribution layer would be decoration."""
    att = attribute({"good": (120, 1000), "a": (10, 1000), "b": (10, 1000), "c": (10, 1000)})
    good = next(m for m in att.methods if m.method == "good")
    assert good.verdict == "BETTER" and good.steerable
    assert good.ci[0] > att.pooled_rate


def test_A_GENUINELY_WORSE_METHOD_IS_DETECTED() -> None:
    att = attribute({"bad": (0, 2000), "a": (120, 1000), "b": (120, 1000)})
    bad = next(m for m in att.methods if m.method == "bad")
    assert bad.verdict == "WORSE"


def test_MARGINAL_SEPARATION_IS_UNDECIDED_NOT_A_WINNER() -> None:
    """Two methods a hair apart on similar samples are not distinguishable, and 'pick the higher
    one' is exactly the noise-chasing this module exists to stop."""
    att = attribute({"a": (52, 1000), "b": (48, 1000)})
    assert {m.verdict for m in att.methods} == {"UNDECIDED"}
    assert att.steerable == ()


def test_WITH_ZERO_SURVIVORS_NOTHING_IS_BETTER_THAN_THE_POOL() -> None:
    """THE DESK'S ACTUAL STATE: 434 candidates, 0 survivors. An attribution layer that produced a
    ranking here would be ranking sampling noise with no signal present at all."""
    att = attribute({"a": (0, 5000), "b": (0, 5000), "c": (0, 5000)})
    assert att.pooled_rate == 0.0
    assert att.steerable == ()
    assert all(m.verdict == "UNDECIDED" for m in att.methods)
    assert any("ZERO SURVIVORS" in n for n in att.notes)
    assert any("NOT MEASURED" in n for n in att.notes)


def test_NO_TRIALS_AT_ALL_IS_UNDEFINED_NOT_EMPTY() -> None:
    att = attribute({"a": (0, 0)})
    assert att.total_trials == 0
    assert any("NO TRIALS RUN" in n for n in att.notes)


def test_IMPOSSIBLE_COUNTS_RAISE() -> None:
    """More survivors than trials is a data-pipeline bug. Silently computing a rate above 1.0 would
    let it propagate into the allocator as an extremely attractive method."""
    with pytest.raises(ValueError, match="invalid counts"):
        attribute({"a": (10, 5)})
    with pytest.raises(ValueError, match="invalid counts"):
        attribute({"a": (-1, 5)})


def test_METHOD_ORDER_IS_DETERMINISTIC() -> None:
    att = attribute({"z": (5, 500), "a": (5, 500), "m": (5, 500)})
    assert [m.method for m in att.methods] == ["a", "m", "z"]


# ----------------------------------------------------------------------- steering, without a rut

def test_ONLY_A_DEMONSTRATED_WINNER_GAINS_WEIGHT() -> None:
    att = attribute({"good": (120, 1000), "a": (10, 1000), "b": (10, 1000), "c": (10, 1000)})
    base = {"good": 0.25, "a": 0.25, "b": 0.25, "c": 0.25}
    w = steer_weights(att, base)
    assert w["good"] > base["good"]
    assert sum(w.values()) == pytest.approx(1.0)


def test_AN_UNDERPOWERED_METHOD_IS_NOT_PENALISED() -> None:
    """SELF-SEALING OTHERWISE: shrink its budget for being unproven, so it gets fewer trials, so it
    stays underpowered, so it keeps getting fewer. That is the rut arriving through the attribution
    layer instead of the allocator -- and invisible, because the weights would look responsive."""
    att = attribute({"new": (0, 5), "old": (50, 1000), "other": (50, 1000)})
    base = {"new": 1 / 3, "old": 1 / 3, "other": 1 / 3}
    w = steer_weights(att, base)
    assert w["new"] == pytest.approx(base["new"]), "an unproven method was starved"


def test_STEERING_ON_A_ZERO_SURVIVOR_BOARD_CHANGES_NOTHING() -> None:
    """No signal, no reallocation. A layer that reshuffled weights here would be laundering noise
    into a research plan."""
    att = attribute({"a": (0, 5000), "b": (0, 5000)})
    base = {"a": 0.5, "b": 0.5}
    assert steer_weights(att, base) == pytest.approx(base)


def test_METHODS_ABSENT_FROM_THE_BASE_ARE_IGNORED() -> None:
    """Attribution history outlives any one batch's method set. A method no longer generated must
    not reappear in the weights as a side effect of being in the record."""
    att = attribute({"retired_method": (120, 1000), "a": (10, 1000), "b": (10, 1000)})
    w = steer_weights(att, {"a": 0.5, "b": 0.5})
    assert set(w) == {"a", "b"}
    assert sum(w.values()) == pytest.approx(1.0)
