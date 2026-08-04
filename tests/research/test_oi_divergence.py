"""OI x PRICE QUADRANTS -- the controls, and the sign convention that would otherwise invent one.

The mechanism is arithmetic: a perp exists only while both sides hold it, so OI falls only when
positions CLOSE. Price up on falling OI is shorts covering -- the move is paid for by people
leaving -- and that has different continuation odds than price up on rising OI.

Two ways to get a fake result here, both silent:

  SIGN POOLING   new_longs and new_shorts are both continuation but point opposite ways. Pooling
                 their RAW forward returns cancels to ~0, so any exhaustion group differs from it
                 by construction and every dataset shows "separation".
  THE JOIN       classifying with a window that includes the forward bar makes every quadrant
                 predictive. Truncation catches it; nothing else does.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from libs.research.oi_divergence import (
    CONTINUATION,
    EXHAUSTION,
    FLAT,
    LONG_LIQUIDATION,
    NEW_LONGS,
    NEW_SHORTS,
    SEPARATION_FLOOR,
    SHORT_COVERING,
    classify,
    quadrant_evidence,
)


def test_the_four_quadrants_are_the_arithmetic_they_claim_to_be() -> None:
    price = pd.Series([100.0] * 13 + [110.0, 90.0, 110.0, 90.0])
    oi = pd.Series([1000.0] * 13 + [1100.0, 1100.0, 900.0, 900.0])
    q = classify(price, oi, window=12)
    assert q.iloc[13] == NEW_LONGS          # price up, OI up
    assert q.iloc[14] == NEW_SHORTS         # price down, OI up
    assert q.iloc[15] == SHORT_COVERING     # price up, OI down
    assert q.iloc[16] == LONG_LIQUIDATION   # price down, OI down


def test_an_unfilled_window_is_FLAT_not_a_guess() -> None:
    q = classify(pd.Series(np.arange(20.0) + 100), pd.Series(np.arange(20.0) + 1000), window=12)
    assert (q.iloc[:12] == FLAT).all(), "classified bars before the window could be computed"


def test_the_dead_band_stops_rounding_noise_deciding_the_quadrant() -> None:
    """Without it the sign of a one-tick change picks the quadrant, so most bars are classified by
    float noise and the four groups become four samples of one distribution -- which reads as 'no
    effect' and would retire the hypothesis for a reason about rounding, not about markets."""
    rng = np.random.default_rng(0)
    price = pd.Series(100 + np.cumsum(rng.normal(0, 1e-6, 400)))
    oi = pd.Series(1000 + np.cumsum(rng.normal(0, 1e-6, 400)))
    loose = classify(price, oi, window=12)
    banded = classify(price, oi, window=12, price_eps=1e-3, oi_eps=1e-3)
    assert (banded == FLAT).sum() > (loose == FLAT).sum()


def test_classification_never_reads_the_forward_bar() -> None:
    """TRUNCATION. A window that includes the bar being predicted makes every quadrant look
    predictive, and nothing but this test catches it."""
    rng = np.random.default_rng(4)
    price = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 500))))
    oi = pd.Series(1000 + np.cumsum(rng.normal(0, 5, 500)))
    full = classify(price, oi, window=12)
    cut = 300
    part = classify(price.iloc[:cut], oi.iloc[:cut], window=12)
    assert list(full.iloc[:cut]) == list(part), "a later bar changed an earlier classification"


def test_misaligned_inputs_raise_rather_than_silently_truncating() -> None:
    with pytest.raises(ValueError, match="align"):
        classify(pd.Series([1.0, 2.0, 3.0]), pd.Series([1.0, 2.0]))
    with pytest.raises(ValueError, match="align"):
        quadrant_evidence(pd.Series([NEW_LONGS]), pd.Series([0.1, 0.2]))


# ----------------------------------------------------------------------- controls

def _panel(n: int, effect: float, seed: int = 1) -> tuple[pd.Series, pd.Series]:
    """Quadrants and forward returns with a KNOWN exhaustion effect of `effect`."""
    rng = np.random.default_rng(seed)
    quads = rng.choice([NEW_LONGS, NEW_SHORTS, SHORT_COVERING, LONG_LIQUIDATION], n)
    r = rng.normal(0, 0.01, n)
    # exhaustion pays on the direction it implies: reverse of the move that produced it
    for i, q in enumerate(quads):
        if q == SHORT_COVERING:
            r[i] -= effect            # implied direction is DOWN, so a down move pays
        elif q == LONG_LIQUIDATION:
            r[i] += effect            # implied direction is UP
    return pd.Series(quads), pd.Series(r)


def test_no_separation_is_reported_when_there_is_none() -> None:
    """THE NEGATIVE CONTROL. Quadrants assigned at random against returns that ignore them must
    not produce separation -- if they do, the statistic is measuring the split."""
    q, r = _panel(4000, effect=0.0)
    ev = quadrant_evidence(q, r)
    assert ev.verdict == "NO-SEPARATION", ev.as_dict()
    assert abs(ev.exhaustion_vs_continuation_d) < SEPARATION_FLOOR


def test_a_planted_exhaustion_effect_IS_found() -> None:
    """THE POSITIVE CONTROL, AND THE MORE IMPORTANT ONE. A harness that never separates anything
    is indistinguishable from a broken one, and 'no separation' from it would mean nothing."""
    q, r = _panel(4000, effect=0.006)
    ev = quadrant_evidence(q, r)
    assert ev.verdict == "SEPARATED", ev.as_dict()
    assert ev.exhaustion_vs_continuation_d > SEPARATION_FLOOR


def test_pooling_RAW_returns_would_have_invented_an_effect() -> None:
    """THE SIGN-CONVENTION TRAP, DEMONSTRATED. new_longs and new_shorts point opposite ways, so
    pooling their raw forward returns cancels to ~0. Any exhaustion group then differs from that
    zero by construction. This asserts the module signs by implied direction instead."""
    rng = np.random.default_rng(9)
    n = 4000
    quads = rng.choice([NEW_LONGS, NEW_SHORTS, SHORT_COVERING, LONG_LIQUIDATION], n)
    # returns that PERFECTLY follow the move's direction: pure continuation, zero exhaustion edge
    r = np.where(np.isin(quads, [NEW_LONGS, SHORT_COVERING]), 0.01, -0.01)
    r = r + rng.normal(0, 0.001, n)
    q, fr = pd.Series(quads), pd.Series(r)

    raw_ex = fr[q.isin(EXHAUSTION)].to_numpy()
    raw_co = fr[q.isin(CONTINUATION)].to_numpy()
    assert abs(raw_co.mean()) < 0.002, "the fixture must make raw continuation cancel"

    ev = quadrant_evidence(q, fr)
    # Signed correctly, continuation is the side that pays here, so exhaustion must be NEGATIVE.
    assert ev.exhaustion_vs_continuation_d < 0, (
        f"the sign convention is wrong: raw pooling gave co={raw_co.mean():+.5f} vs "
        f"ex={raw_ex.mean():+.5f}, and the signed comparison must not follow that artefact")


def test_an_underpowered_panel_says_so_rather_than_reporting_zero() -> None:
    """'Too few observations to tell' and 'the quadrants are identical' are different findings,
    and only the second retires a hypothesis."""
    q, r = _panel(30, effect=0.0)
    assert quadrant_evidence(q, r).verdict == "UNDERPOWERED"


def test_the_separation_floor_matches_the_preregistration() -> None:
    """A threshold in two places drifts, and the one that governs becomes whichever was edited
    last -- here that would mean scoring against a number chosen after seeing the result."""
    from pathlib import Path
    doc = Path("docs/research/THREE_MECHANISM_PREREGISTRATION.md").read_text("utf-8")
    assert str(SEPARATION_FLOOR) in doc, (
        "the OI separation floor in the code is not the one the pre-registration states")


def test_SEPARATED_is_explicitly_not_a_tradeable_claim() -> None:
    """The verdict is a precondition. Reading it as an edge is how a stage-A reading becomes a
    position, and the wording is the only thing standing between those two."""
    q, r = _panel(4000, effect=0.006)
    why = quadrant_evidence(q, r).why
    assert "NOT a tradeable edge" in why
    assert "costs" in why and "capacity" in why
