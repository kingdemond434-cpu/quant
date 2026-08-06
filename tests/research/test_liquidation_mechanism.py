"""IS THE REVERSION FORCED FLOW, OR IS IT SUPPLY? -- 93 statements, and I wrote it without a test.

This module answers the question the failed-breakout pre-registration's kill criterion K7 turns on:
when price sweeps a level and fails, is the reversion happening because forced-liquidation flow
EXHAUSTS, or because discretionary sellers arrive and then stop? Those two produce the same candle
and completely different expectations, and only one is a mechanism you can size against.

WHY AN UNTESTED VERSION IS WORSE THAN NONE. If mechanism evidence is absent, an edge found by the
pattern search is an UNEXPLAINED EMPIRICAL REGULARITY -- it may still be real, but it is not this
hypothesis, and promoting it on this hypothesis's ticket would be claiming to know why something
works when the measurement said otherwise. K7 exists to force that distinction. A K7 that mis-fires
either promotes a story or kills a mechanism, and both are silent.

THE THREE DISTINCTIONS THIS FILE PINS, each of which reads as a plausible number if it breaks:

  UNMEASURABLE IS NOT ABSENT. A channel with no data must never report an effect of zero. One says
  "the mechanism is not there", the other says "nobody looked", and K7 fires only on the first.

  CONTRADICTED IS NOT ABSENT EITHER. OI RISING across swept levels is the discretionary-supply
  signature -- the OPPOSITE of the hypothesis, not a weak version of it. Collapsing the two would
  let the desk record "no mechanism" when what it measured was the mechanism running backwards.

  EVERY MEASUREMENT IS CAUSAL. The OI statistic compares a window ENDING at the sweep against one
  before it; funding is standardised against bars STRICTLY PRIOR. A full-sample z-score here is the
  leak that made `book_pressure_vs_funding` lie until it was found on 2026-08-03.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.liquidation_mechanism import (
    K7_EFFECT_FLOOR,
    MechanismEvidence,
    cohens_d,
    funding_extremity,
    liquidation_burst,
    mechanism_evidence,
    oi_collapse,
)


def _idx(*positions: int) -> np.ndarray:
    return np.asarray(positions, dtype="int64")


# ============================================================ the effect size

def test_EFFECT_SIZE_rather_than_a_p_value() -> None:
    """With enough bars ANY difference is 'significant'. K7 asks whether the difference is LARGE,
    because a mechanism that moves OI by a tenth of a standard deviation is not what drives a
    reversion."""
    rng = np.random.default_rng(0)
    a = rng.normal(0.0, 1.0, 100_000)
    b = rng.normal(0.001, 1.0, 100_000)      # a real but tiny shift, hugely significant at this n
    assert abs(cohens_d(a, b)) < K7_EFFECT_FLOOR


def test_a_large_separation_scores_large() -> None:
    rng = np.random.default_rng(1)
    a = rng.normal(0.0, 1.0, 500)
    b = rng.normal(2.0, 1.0, 500)
    assert cohens_d(a, b) == pytest.approx(-2.0, abs=0.2)


def test_the_SIGN_follows_the_first_argument() -> None:
    """`oi_collapse_d < 0` is what PRESENT means -- OI falling on swept levels relative to unswept.
    An inverted sign turns the exhaustion signature into the supply signature."""
    rng = np.random.default_rng(2)
    lo, hi = rng.normal(0.0, 1.0, 200), rng.normal(3.0, 1.0, 200)
    assert cohens_d(lo, hi) < 0
    assert cohens_d(hi, lo) > 0


@pytest.mark.parametrize(("a_n", "b_n"), [(4, 50), (50, 4), (0, 50), (4, 4)])
def test_TOO_FEW_OBSERVATIONS_yields_NaN_rather_than_a_confident_number(a_n, b_n) -> None:
    """NaN propagates to UNMEASURABLE. A d computed from four points is a number that would be
    quoted and would be noise."""
    assert np.isnan(cohens_d(np.zeros(a_n), np.ones(b_n)))


def test_NON_FINITE_values_are_dropped_before_the_count() -> None:
    """A NaN in either arm poisons the mean and the sd, and NaN comparisons are False everywhere --
    so K7 would silently take the 'not absent' branch."""
    rng = np.random.default_rng(4)
    clean = rng.normal(0.0, 1.0, 200)
    dirty = np.concatenate([clean, [np.nan, np.inf, -np.inf]])
    b = rng.normal(2.0, 1.0, 200)
    assert np.isfinite(cohens_d(dirty, b))
    assert cohens_d(dirty, b) == pytest.approx(cohens_d(clean, b))


def test_a_ZERO_VARIANCE_pair_is_NaN_not_infinite() -> None:
    """Two constant arrays have no pooled sd. Dividing by it gives inf, which clears any floor and
    would report the strongest possible mechanism from data that never moved."""
    assert np.isnan(cohens_d(np.ones(50), np.ones(50)))
    assert np.isnan(cohens_d(np.ones(50), np.full(50, 2.0)))


# =========================================================== OI collapse: the primary discriminator

def test_OI_FALLING_across_an_event_reads_NEGATIVE() -> None:
    """Forced liquidation CLOSES positions, so OI falls. Discretionary supply OPENS them, so it
    holds or rises. Same candle, opposite sign here -- and this is the whole discriminator."""
    oi = pd.Series([100.0] * 20 + [50.0] * 20)
    got = oi_collapse(oi, _idx(19), pre=12, post=3)
    assert got[0] < 0


def test_OI_RISING_across_an_event_reads_POSITIVE() -> None:
    oi = pd.Series([100.0] * 20 + [200.0] * 20)
    assert oi_collapse(oi, _idx(19), pre=12, post=3)[0] > 0


def test_the_change_is_a_FRACTION_of_the_pre_level_not_an_absolute() -> None:
    """A 10-unit drop on BTC's open interest and on a small alt's are not the same event. Absolute
    changes make the statistic a proxy for symbol size."""
    small = pd.Series([100.0] * 20 + [90.0] * 20)
    large = pd.Series([10_000.0] * 20 + [9_000.0] * 20)
    assert oi_collapse(small, _idx(19))[0] == pytest.approx(oi_collapse(large, _idx(19))[0])


def test_events_TOO_CLOSE_TO_EITHER_END_are_NaN_rather_than_truncated() -> None:
    """Truncating the window would compare a 12-bar change against a 3-bar one and call them the
    same measurement -- and the shortest windows are the noisiest, so the bias is toward finding
    an effect."""
    oi = pd.Series(np.linspace(100.0, 50.0, 40))
    got = oi_collapse(oi, _idx(2, 20, 39), pre=12, post=3)
    assert np.isnan(got[0]), "no room for the pre-window"
    assert np.isfinite(got[1])
    assert np.isnan(got[2]), "no room for the post-window"


def test_the_POST_window_is_STRICTLY_AFTER_the_event_bar() -> None:
    """The event bar belongs to the BEFORE side. Including it in both windows would let a single
    bar's value cancel itself and shrink every measured effect toward zero."""
    oi = pd.Series([100.0] * 13 + [1_000.0] + [100.0] * 10)
    at_spike = oi_collapse(oi, _idx(13), pre=12, post=3)[0]
    assert at_spike < 0, "the spike is in the BEFORE mean, so the after-window reads as a collapse"


def test_a_ZERO_or_NEGATIVE_pre_level_yields_NaN(  ) -> None:
    """Dividing by a zero baseline gives inf, and a venue publishing 0 open interest for a dead
    contract is routine. Inf would clear every floor."""
    oi = pd.Series([0.0] * 20 + [50.0] * 20)
    assert np.isnan(oi_collapse(oi, _idx(19))[0])


def test_NON_NUMERIC_open_interest_is_coerced_and_gaps_survive() -> None:
    """Venues return these as strings, and a gap is a real state. Raising would take down the whole
    mechanism pass for one bad row."""
    oi = pd.Series(["100"] * 13 + [None] + ["100"] * 6 + ["50"] * 20)
    got = oi_collapse(oi, _idx(21), pre=12, post=3)
    assert np.isfinite(got[0])


def test_an_EMPTY_event_list_returns_an_empty_array() -> None:
    assert oi_collapse(pd.Series([1.0] * 50), _idx()).shape == (0,)


# ============================================================ funding: the precondition

def test_funding_is_standardised_against_STRICTLY_PRIOR_bars() -> None:
    """THE LEAK THAT MADE `book_pressure_vs_funding` LIE until 2026-08-03. A full-sample z-score
    lets the event's own regime set its baseline, so an extreme reading standardises to nothing."""
    calm = [0.0001] * 200
    spike = [0.05]
    f = pd.Series(calm + spike)
    got = funding_extremity(f, _idx(200), lookback=200)
    assert got[0] > 5.0, "an enormous funding print against a calm history must score enormous"


def test_the_event_bar_is_NEVER_in_its_own_baseline() -> None:
    """Included, the spike inflates the historical mean and sd it is being measured against, and
    the reading shrinks toward zero exactly where the hypothesis needs it to be large."""
    hist = [0.0001] * 200
    with_spike = pd.Series([*hist, 0.05])
    prior_only = funding_extremity(with_spike, _idx(200), lookback=200)[0]
    contaminated = abs((0.05 - np.mean([*hist, 0.05])) / np.std([*hist, 0.05], ddof=1))
    assert prior_only > contaminated


def test_funding_extremity_is_ABSOLUTE_because_crowding_has_two_signs() -> None:
    """Crowded shorts paying longs is the same precondition as crowded longs paying shorts. A
    signed measure would find the mechanism on only half the events."""
    rng = np.random.default_rng(3)
    base = list(rng.normal(0.0, 0.0001, 200))
    up = pd.Series([*base, 0.05])
    dn = pd.Series([*base, -0.05])
    assert funding_extremity(up, _idx(200))[0] > 5
    assert funding_extremity(dn, _idx(200))[0] > 5


def test_TOO_LITTLE_HISTORY_yields_NaN_rather_than_a_z_from_nothing() -> None:
    """Below 30 prior observations a z-score is a statement about three points."""
    f = pd.Series([0.0001] * 10 + [0.05])
    assert np.isnan(funding_extremity(f, _idx(10))[0])


def test_a_FLAT_funding_history_yields_NaN_not_infinity() -> None:
    """Zero sd. Inf would report maximum crowding on a symbol whose funding never moved."""
    f = pd.Series([0.0001] * 100)
    assert np.isnan(funding_extremity(f, _idx(99))[0])


def test_the_LOOKBACK_bounds_how_far_back_the_baseline_reaches() -> None:
    """An unbounded baseline standardises today's funding against a regime three years gone, which
    is a different market."""
    rng = np.random.default_rng(9)
    # Both regimes need VARIANCE -- a flat window has zero sd and correctly yields NaN, so a
    # constant fixture would test the degenerate branch instead of the lookback.
    old_regime = list(rng.normal(0.05, 0.01, 500))
    new_regime = list(rng.normal(0.0001, 0.00002, 100))
    f = pd.Series(old_regime + new_regime + [0.001])
    short = funding_extremity(f, _idx(600), lookback=100)[0]
    long_ = funding_extremity(f, _idx(600), lookback=600)[0]
    assert short > long_, "against the recent calm regime the same print is far more extreme"


# ============================================================ liquidation prints

def test_a_BURST_is_measured_as_a_MULTIPLE_of_the_trailing_median() -> None:
    """A multiple is comparable across symbols; a raw notional is a proxy for symbol size."""
    liq = pd.Series([100.0] * 200 + [10_000.0, 0.0, 0.0])
    got = liquidation_burst(liq, _idx(200), window=3, lookback=200)
    assert got[0] > 10


def test_a_QUIET_window_scores_near_its_own_baseline() -> None:
    """FOUND A REAL OFF-BY-ONE. The burst window spans i..i+window INCLUSIVE (window+1 bars) and
    the denominator counted `window`, so a perfectly quiet window scored 1.333 rather than 1.0 and
    every multiple was inflated by (window+1)/window -- 33% at window=3, uniformly, in the
    flattering direction. Uniform bias is the kind no downstream check can see: the ORDERING of
    events is untouched, so only the absolute multiple is wrong and it is wrong everywhere."""
    liq = pd.Series([100.0] * 250)
    assert liquidation_burst(liq, _idx(200), window=3, lookback=200)[0] == pytest.approx(1.0,
                                                                                         abs=0.1)


def test_NO_PUBLISHED_LIQUIDATIONS_is_NaN_and_NEVER_ZERO() -> None:
    """A NaN means the venue published nothing. Zero would mean 'measured, and there were no
    liquidations' -- which is a finding about the market rather than about the feed."""
    liq = pd.Series([np.nan] * 250)
    assert np.isnan(liquidation_burst(liq, _idx(200))[0])


def test_a_ZERO_MEDIAN_history_yields_NaN_rather_than_infinity() -> None:
    """A symbol with no liquidations in its lookback has a median of 0. Dividing by it makes the
    first liquidation ever look infinitely extreme."""
    liq = pd.Series([0.0] * 200 + [500.0])
    assert np.isnan(liquidation_burst(liq, _idx(200), lookback=200)[0])


def test_too_little_history_yields_NaN() -> None:
    liq = pd.Series([100.0] * 10 + [10_000.0])
    assert np.isnan(liquidation_burst(liq, _idx(10))[0])


def test_the_burst_window_INCLUDES_the_event_bar() -> None:
    """The liquidations that matter start ON the sweep. A window opening at t+1 would miss the
    print the hypothesis is about."""
    liq = pd.Series([100.0] * 200 + [50_000.0] + [100.0] * 5)
    assert liquidation_burst(liq, _idx(200), window=3, lookback=200)[0] > 10


# ============================================================ the verdict

def _swept_unswept(n: int = 400) -> tuple[np.ndarray, np.ndarray]:
    return np.arange(50, 150, dtype="int64"), np.arange(200, 300, dtype="int64")


def test_OI_FALLING_on_swept_levels_reads_PRESENT() -> None:
    """The signature of positions being closed involuntarily rather than new supply arriving."""
    swept, unswept = _swept_unswept()
    rng = np.random.default_rng(5)
    oi = pd.Series(1_000.0 + rng.normal(0, 1, 400))
    for i in swept:                       # a real collapse across every swept level
        oi.iloc[i + 1:i + 4] -= 300.0
    ev = mechanism_evidence(swept, unswept, oi=oi)
    assert ev.verdict == "PRESENT"
    assert ev.oi_collapse_d < 0
    assert "involuntarily" in ev.why


def test_OI_RISING_on_swept_levels_reads_CONTRADICTED_and_NOT_absent() -> None:
    """THE DISTINCTION THAT WOULD OTHERWISE BE LOST. Rising OI is the DISCRETIONARY-SUPPLY
    signature -- the opposite of the hypothesis, not a weak version of it. Recording it as ABSENT
    would let the desk file 'no mechanism' when what it measured was the mechanism backwards."""
    swept, unswept = _swept_unswept()
    rng = np.random.default_rng(6)
    oi = pd.Series(1_000.0 + rng.normal(0, 1, 400))
    for i in swept:
        oi.iloc[i + 1:i + 4] += 300.0
    ev = mechanism_evidence(swept, unswept, oi=oi)
    assert ev.verdict == "CONTRADICTED"
    assert ev.oi_collapse_d > 0
    assert "OPPOSITE of the hypothesis" in ev.why


def test_NO_SEPARATION_reads_ABSENT_and_says_K7_FIRES() -> None:
    """Positions are not being closed across the sweep in any size that could drive a reversion.
    Whatever the pattern search finds, it is not this mechanism."""
    swept, unswept = _swept_unswept()
    rng = np.random.default_rng(7)
    oi = pd.Series(1_000.0 + rng.normal(0, 5, 400))
    ev = mechanism_evidence(swept, unswept, oi=oi)
    assert ev.verdict == "ABSENT"
    assert abs(ev.oi_collapse_d) < K7_EFFECT_FLOOR
    assert "K7 FIRES" in ev.why


def test_NO_OPEN_INTEREST_reads_UNMEASURABLE_and_NEVER_ABSENT() -> None:
    """One says the mechanism is not there; the other says nobody looked. K7 fires only on the
    first, and conflating them would kill a hypothesis for a data gap."""
    swept, unswept = _swept_unswept()
    ev = mechanism_evidence(swept, unswept, oi=None)
    assert ev.verdict == "UNMEASURABLE"
    assert "oi_collapse" in ev.unmeasurable
    assert np.isnan(ev.oi_collapse_d)
    assert "K7 cannot be evaluated" in ev.why


@pytest.mark.parametrize("oi", [None, pd.Series(dtype="float64"),
                                pd.Series([np.nan] * 400)])
def test_an_EMPTY_or_ALL_NaN_channel_is_UNMEASURABLE(oi) -> None:
    swept, unswept = _swept_unswept()
    ev = mechanism_evidence(swept, unswept, oi=oi)
    assert ev.verdict == "UNMEASURABLE"


def test_a_PURE_TREND_with_TIME_MATCHED_arms_reads_ABSENT() -> None:
    """THE COMPARISON THAT IS EASY TO GET WRONG. OI drifts and funding trends, so a before/after
    split confirms the hypothesis on ANY series with a trend in it. Holding "there was a level
    here" fixed and varying only the sweep is what makes the difference attributable -- and with
    the arms INTERLEAVED, a pure monotone trend correctly produces nothing."""
    idx = np.arange(50, 350, dtype="int64")
    swept, unswept = idx[0::2], idx[1::2]
    trending = pd.Series(np.linspace(1_000.0, 500.0, 400))     # OI falls all day, no sweeps
    ev = mechanism_evidence(swept, unswept, oi=trending)
    assert ev.verdict == "ABSENT", (
        "a pure downtrend must NOT read as forced liquidation when the arms share the same epoch")


def test_DISJOINT_TIME_BLOCKS_manufacture_a_verdict_from_a_TREND_ALONE() -> None:
    """THE CALLER'S OBLIGATION, MEASURED RATHER THAN ASSUMED -- and the reason the module docstring
    now names it.

    `oi_collapse` reports a FRACTIONAL change, so on a falling series the same absolute move is a
    LARGER fraction wherever the level is lower. Put every swept event early and every control
    late and a straight line from 1000 to 500 -- with no sweeps in it at all -- produces a
    CONTRADICTED verdict. That is the before/after failure returning through the SAMPLING rather
    than through the windows, and this function cannot see it: both arms are validly "levels".

    Recorded as a test so the obligation cannot be lost the next time somebody writes a caller.
    """
    swept = np.arange(50, 150, dtype="int64")
    unswept = np.arange(200, 300, dtype="int64")
    trending = pd.Series(np.linspace(1_000.0, 500.0, 400))
    ev = mechanism_evidence(swept, unswept, oi=trending)
    assert ev.verdict == "CONTRADICTED"
    assert abs(ev.oi_collapse_d) > K7_EFFECT_FLOOR, (
        "if this ever stops firing the demonstration is dead and the docstring's warning is stale")


def test_every_measured_and_unmeasured_channel_is_NAMED() -> None:
    """A verdict that does not say which channels it could see cannot be re-read later: 'the
    mechanism was absent' means something different when two of three channels were dark."""
    swept, unswept = _swept_unswept()
    rng = np.random.default_rng(8)
    oi = pd.Series(1_000.0 + rng.normal(0, 5, 400))
    ev = mechanism_evidence(swept, unswept, oi=oi, funding=None, liq=None)
    assert "oi_collapse" in ev.measurable
    assert set(ev.unmeasurable) >= {"funding_extremity", "liquidation_burst"}


def test_the_evidence_reports_BOTH_sample_sizes() -> None:
    """A d from 100 swept against 3 unswept is not the same claim as 100 against 100, and the
    verdict alone cannot say which it was."""
    swept, unswept = _swept_unswept()
    ev = mechanism_evidence(swept, unswept, oi=pd.Series([1.0] * 400))
    assert ev.n_swept == len(swept) and ev.n_control == len(unswept)


def test_the_evidence_is_FROZEN_and_serialisable() -> None:
    """A verdict that can be edited after the fact is not a measurement."""
    import json
    ev = MechanismEvidence(n_swept=1, n_control=1)
    json.dumps(ev.as_dict())
    with pytest.raises(AttributeError):
        ev.verdict = "PRESENT"          # type: ignore[misc]


def test_the_floor_is_the_pre_registrations_number() -> None:
    """Not a tuning knob: it is written into FAILED_BREAKOUT_PREREGISTRATION.md, and changing it
    here without changing that document is how a pre-registration stops binding."""
    doc = __import__("pathlib").Path("docs/research/FAILED_BREAKOUT_PREREGISTRATION.md")
    assert K7_EFFECT_FLOOR == 0.2
    if doc.exists():
        assert "0.2" in doc.read_text("utf-8")
