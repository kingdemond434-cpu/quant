"""THE FAILED-BREAKOUT HARNESS -- and the leakage test that is the reason to believe it.

Almost every published version of this pattern identifies swing highs with a CENTRED window,
`rolling(2k+1, center=True).max()`, which at bar t reads bars up to t+k. It is what charting
libraries do, it looks innocuous, and it leaks precisely the future extremes the pattern claims to
anticipate. A study built on it reports an edge that cannot be traded.

So the load-bearing tests here are not "does it find events" -- they are:

  TRUNCATION      recomputing on data up to t must reproduce the value at t. A feature that
                  changes its own past when future bars arrive is looking forward, and this is
                  the only check that catches it mechanically.
  ORDERING        confirmation strictly after occurrence, sweep strictly after confirmation,
                  failure strictly after sweep, entry strictly after failure.
  THE CONTROL     mechanism evidence must come back ABSENT on data with no mechanism in it, and
                  PRESENT on data with one planted. A harness that always answers the same thing
                  is not measuring.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.failed_breakout import (
    LevelParams,
    atr,
    find_events,
    swing_levels,
)
from libs.research.liquidation_mechanism import (
    K7_EFFECT_FLOOR,
    cohens_d,
    mechanism_evidence,
    oi_collapse,
)


def _bars(n: int = 600, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    spread = np.abs(rng.normal(0, 0.003, n)) * close
    return pd.DataFrame({"high": close + spread, "low": close - spread, "close": close})


# ------------------------------------------------------------------- no look-ahead

def test_atr_never_changes_its_own_past_when_future_bars_arrive() -> None:
    """TRUNCATION IS THE ONLY MECHANICAL LEAKAGE TEST. Everything else is a promise."""
    b = _bars()
    full = atr(b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy(), 14)
    cut = 400
    part = atr(b["high"].to_numpy()[:cut], b["low"].to_numpy()[:cut],
               b["close"].to_numpy()[:cut], 14)
    ok = np.isfinite(full[:cut]) & np.isfinite(part)
    assert ok.sum() > 100
    assert np.allclose(full[:cut][ok], part[ok]), "ATR rewrote its history -- it reads forward"


def test_a_swing_high_is_not_KNOWN_until_k_bars_after_it_happens() -> None:
    """The distinction the centred-window formulation destroys. The extreme is AT bar i; it
    becomes knowable at i+k; it is usable from i+k+1. Marking and using are different acts."""
    h = np.array([1, 2, 3, 9, 3, 2, 1, 1, 1], dtype="float64")
    low = np.array([1, 1, 1, 1, 1, 1, 1, 1, 1], dtype="float64")
    is_hi, _ = swing_levels(h, low, k=2)
    assert is_hi[3], "the peak at index 3 is a swing high"
    # ...and truncating BEFORE its right-hand confirmation must not report it.
    is_hi_early, _ = swing_levels(h[:5], low[:5], k=2)
    assert not is_hi_early[3], (
        "a swing high was reported before its confirming bars existed -- that is the centred-"
        "window time machine, and it is the single most common way this pattern is mis-tested")


def test_events_are_ordered_occurrence_confirmation_sweep_failure_entry() -> None:
    """Each step must read strictly later than the one before, or the chain leaks somewhere."""
    b = _bars(900, seed=7)
    evs = find_events(b, LevelParams(k=10, n_touch=0, n_fail=3))
    assert evs, "the fixture produced no events -- the test would prove nothing"
    for e in evs:
        assert e.confirmed_idx == e.level_idx + 10
        assert e.sweep_idx > e.confirmed_idx, "swept a level before it was confirmed"
        if e.failed:
            assert e.failure_idx is not None and e.failure_idx > e.sweep_idx
            if e.entry_idx is not None:
                assert e.entry_idx == e.failure_idx + 1, (
                    "entry must be the bar AFTER the failure close -- the failure close is not "
                    "obtainable at the moment the signal is known")


def test_the_event_set_is_stable_under_truncation() -> None:
    """The whole-pipeline version of the truncation test: events found on a prefix must be a
    prefix of the events found on the whole series. If a later bar CREATES an earlier event, the
    pipeline reads forward somewhere between level detection and failure resolution."""
    b = _bars(900, seed=11)
    p = LevelParams(k=10, n_touch=0, n_fail=3)
    full = find_events(b, p)
    cut = 600
    part = find_events(b.iloc[:cut].reset_index(drop=True), p)
    # Compare only events whose ENTIRE window closed before the cut.
    horizon = cut - p.n_fail - 2
    a = [e.as_dict() for e in full if e.sweep_idx < horizon]
    c = [e.as_dict() for e in part if e.sweep_idx < horizon]
    assert a == c, "truncating the series changed earlier events -- something reads forward"


def test_n_touch_is_a_hyperparameter_that_actually_binds() -> None:
    """It counts against the trial budget, so it had better change the answer -- a knob that does
    nothing still deflates the Sharpe and buys no information."""
    b = _bars(900, seed=5)
    loose = find_events(b, LevelParams(k=10, n_touch=0))
    strict = find_events(b, LevelParams(k=10, n_touch=3))
    assert len(strict) < len(loose), "n_touch does not bind; it is deflating for nothing"


# -------------------------------------------------------------- mechanism controls

def test_cohens_d_refuses_to_speak_on_a_tiny_sample() -> None:
    assert np.isnan(cohens_d(np.array([1.0, 2.0]), np.arange(50.0)))
    assert np.isnan(cohens_d(np.zeros(50), np.zeros(50))), "zero dispersion has no effect size"


def test_oi_collapse_is_negative_when_positions_are_CLOSED() -> None:
    """The sign is the hypothesis. Forced liquidation closes positions, so OI falls across the
    sweep; discretionary supply opens them, so it rises. Same candle, opposite sign here."""
    oi = pd.Series(np.r_[np.full(50, 1000.0), np.full(50, 700.0)])
    d = oi_collapse(oi, np.array([49]), pre=12, post=3)
    assert d[0] < -0.1, "a 30% OI drop across the event did not register as a collapse"


def test_oi_collapse_is_NaN_rather_than_truncated_at_the_series_edge() -> None:
    """Truncating the window would compare a 12-bar change against a 3-bar one and call the
    difference an effect."""
    oi = pd.Series(np.arange(20.0))
    assert np.isnan(oi_collapse(oi, np.array([2]), pre=12, post=3)[0])
    assert np.isnan(oi_collapse(oi, np.array([19]), pre=12, post=3)[0])


def test_funding_is_standardised_against_STRICTLY_PRIOR_bars() -> None:
    """A full-sample z-score lets the event's own regime set its baseline. That exact leak lived
    in book_pressure_vs_funding until it was found on 2026-08-03, and it survived review because
    the synthetic tape had no funding for the causality test to compare."""
    import inspect

    from libs.research import liquidation_mechanism as M
    src = inspect.getsource(M.funding_extremity)
    assert "v[lo:i]" in src, "the window must END BEFORE the event, not include it"
    assert "strictly prior" in src


def test_the_mechanism_verdict_is_ABSENT_on_data_with_no_mechanism() -> None:
    """THE NEGATIVE CONTROL. Swept and unswept levels drawn from the same distribution must not
    produce mechanism evidence -- if they do, the statistic is measuring the split, not the flow."""
    rng = np.random.default_rng(1)
    oi = pd.Series(1000 + rng.normal(0, 5, 2000))
    swept = rng.choice(np.arange(200, 1800), 120, replace=False)
    control = rng.choice(np.setdiff1d(np.arange(200, 1800), swept), 120, replace=False)
    ev = mechanism_evidence(swept, control, oi=oi)
    assert ev.verdict == "ABSENT", f"invented a mechanism from noise: {ev.as_dict()}"
    assert abs(ev.oi_collapse_d) < K7_EFFECT_FLOOR


def test_the_mechanism_verdict_is_PRESENT_when_one_is_planted() -> None:
    """THE POSITIVE CONTROL, AND THE MORE IMPORTANT ONE. A harness that never finds a mechanism is
    indistinguishable from a broken harness, and 'no mechanism' from it would mean nothing."""
    rng = np.random.default_rng(2)
    n = 2000
    oi_v = 1000 + rng.normal(0, 5, n)
    swept = rng.choice(np.arange(200, 1800), 120, replace=False)
    for i in swept:                       # positions closed across each swept level
        oi_v[i + 1:i + 4] -= 150.0
    control = rng.choice(np.setdiff1d(np.arange(200, 1800), swept), 120, replace=False)
    ev = mechanism_evidence(swept, control, oi=pd.Series(oi_v))
    assert ev.verdict == "PRESENT", ev.as_dict()
    assert ev.oi_collapse_d < -K7_EFFECT_FLOOR


def test_rising_OI_across_the_sweep_CONTRADICTS_rather_than_confirms() -> None:
    """Discretionary supply is the competing hypothesis, not a weaker version of this one. If
    participants are OPENING into the sweep, the pre-registered mechanism is refuted -- and a
    verdict that folded this into 'present' would confirm the hypothesis on its own opposite."""
    rng = np.random.default_rng(4)
    n = 2000
    oi_v = 1000 + rng.normal(0, 5, n)
    swept = rng.choice(np.arange(200, 1800), 120, replace=False)
    for i in swept:
        oi_v[i + 1:i + 4] += 150.0
    control = rng.choice(np.setdiff1d(np.arange(200, 1800), swept), 120, replace=False)
    ev = mechanism_evidence(swept, control, oi=pd.Series(oi_v))
    assert ev.verdict == "CONTRADICTED", ev.as_dict()


def test_missing_open_interest_is_UNMEASURABLE_not_absent() -> None:
    """The distinction K7 turns on. 'We measured and found nothing' kills the hypothesis;
    'nobody measured' does not, and reporting the second as the first would retire a live
    hypothesis on the strength of a missing file."""
    swept, control = np.arange(100, 220), np.arange(300, 420)
    ev = mechanism_evidence(swept, control, oi=None)
    assert ev.verdict == "UNMEASURABLE"
    assert "oi_collapse" in ev.unmeasurable
    assert "UNEXPLAINED" in ev.why

    ev2 = mechanism_evidence(swept, control, oi=pd.Series([np.nan] * 500))
    assert ev2.verdict == "UNMEASURABLE", "an all-NaN series is not a measurement of zero"


def test_the_K7_floor_matches_the_pre_registration() -> None:
    """A threshold that lives in two places drifts, and the one that governs becomes whichever was
    edited last. The document is the authority; this asserts the code still agrees with it."""
    from pathlib import Path
    doc = Path("docs/research/FAILED_BREAKOUT_PREREGISTRATION.md").read_text("utf-8")
    assert f"< {K7_EFFECT_FLOOR}" in doc or f"{K7_EFFECT_FLOOR}" in doc, (
        "the K7 effect floor in liquidation_mechanism.py is not the one the pre-registration "
        "states -- a pre-registration the code does not honour is not a pre-registration")


@pytest.mark.parametrize("bad", ["high", "low", "close"])
def test_missing_a_required_column_raises_rather_than_guessing(bad: str) -> None:
    b = _bars(200).drop(columns=[bad])
    with pytest.raises(ValueError, match="missing"):
        find_events(b, LevelParams())
