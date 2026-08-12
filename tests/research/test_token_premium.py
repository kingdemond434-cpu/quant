"""GRADUATES L0077 -- one tokenized-commodity chart cannot name the cause of its own move.

THE PAID LESSON. 2026-08-05 21:45Z: the conviction seat read PAXGUSDT +4.002%/24h as a breakout in
gold. That reading is only correct if the METAL moved. If instead the Paxos wrapper had gone to a
premium, the same chart looks identical and the correct trade is the OPPOSITE one -- short the
premium and wait for convergence. The discriminator cost one extra quote: Tether Gold
(XAUTUSDT, a different issuer on the same metal) printed +3.957% over the same window, 4.5bp
apart, PAXG/XAUT ratio 1.0027. The metal moved; the momentum reading survived.

What is pinned here is the DISCRIMINATOR, not that day's answer:
  * agreement between independent issuers => the underlying moved
  * disagreement => a wrapper premium, and the trade inverts
  * no second quote => UNVERIFIABLE, which is the pre-lesson state and must never read as
    confirmation, because "I could not check" is exactly the evidence that produced the error
"""
from __future__ import annotations

from libs.research.token_premium import (
    AGREE_BPS,
    CROSS_ISSUER,
    MIN_MOVE_PCT,
    classify,
    peer_for,
)


# ------------------------------------------------------------------ the day it was learned
def test_the_2026_08_05_gold_move_is_confirmed_by_the_other_issuer() -> None:
    """The measured case, to the basis point. PAXG +4.002 vs XAUT +3.957 is 4.5bp of daylight."""
    v = classify("PAXGUSDT", 4.002, 3.957)
    assert v.state == "CONFIRMED" and v.confirmed
    assert abs(v.gap_bps) < 5.0, v
    assert "XAUTUSDT" in v.why and "independent" in v.why


def test_a_flat_twin_inverts_the_trade_rather_than_merely_weakening_it() -> None:
    """THE LOAD-BEARING COUNTERFACTUAL. Had XAUT been flat that night, the correct action was not
    'a smaller long' -- it was SHORT the premium. A check that only downgraded confidence would
    still have taken the wrong side, just less of it."""
    v = classify("PAXGUSDT", 4.002, 0.05)
    assert v.state == "DISLOCATION" and not v.confirmed
    assert "CONVERGENCE" in v.trade and "wrong side" in v.trade
    assert "PAXGUSDT" in v.trade, "the report must name WHICH token carries the premium"


def test_the_dislocation_names_the_token_that_is_rich_not_just_that_a_gap_exists() -> None:
    """A gap alone does not say which leg to short. When the TWIN is the one that ran, the
    premium is on the twin and the desk's own instrument is the fair leg.

    THIS TEST CAUGHT A REAL BUG IN THE FIRST DRAFT of the module it graduates. The noise floor
    was applied to the desk's own leg alone, so a flat PAXG against a XAUT that ran 4% came back
    NOISE -- "nothing happened" -- when it is the single most actionable state on the board: the
    metal moved and the wrapper did not follow, so PAXG is CHEAP to the underlying. The floor is
    now a property of the PAIR, and this asymmetric case is why.
    """
    v = classify("PAXGUSDT", 0.10, 4.002)
    assert v.state == "DISLOCATION"
    assert "XAUTUSDT" in v.trade and "PAXGUSDT" not in v.trade.split("premium on ")[1][:12]


# ------------------------------------------------------------------ unknown is never a pass
def test_a_missing_twin_quote_is_unverifiable_never_confirmed() -> None:
    """The whole lesson is that one chart is not enough. Failing to fetch the second one leaves
    precisely the evidence that caused the loss, so it must not resolve in the trade's favour."""
    v = classify("PAXGUSDT", 4.002, None)
    assert v.state == "UNVERIFIABLE" and not v.confirmed
    assert v.gap_bps is None, "an unmeasured gap must be None, never 0.0"
    assert "unconfirmed" in v.trade


def test_a_symbol_with_no_independent_twin_says_so_rather_than_passing() -> None:
    v = classify("BTCUSDT", 9.0, None)
    assert v.state == "UNVERIFIABLE" and not v.confirmed
    assert "no independently-issued twin" in v.why


def test_confirmed_is_the_only_state_that_reads_as_a_pass() -> None:
    """Four states, one pass. A caller writing `if not v.state == "DISLOCATION"` would wave
    UNVERIFIABLE through, so the boolean is provided and it is strict."""
    passes = [s for s in ("CONFIRMED", "DISLOCATION", "NOISE", "UNVERIFIABLE")
              if classify("PAXGUSDT", 4.002, 3.957 if s == "CONFIRMED" else
                          (0.05 if s == "DISLOCATION" else None)).state == s
              and classify("PAXGUSDT", 4.002, 3.957 if s == "CONFIRMED" else
                           (0.05 if s == "DISLOCATION" else None)).confirmed]
    assert passes == ["CONFIRMED"]


# ------------------------------------------------------------------ the floor and the band
def test_a_move_inside_the_measured_noise_floor_is_not_classified_at_all() -> None:
    """Attributing a cause to a move smaller than the instrument's own noise is measuring the
    noise. The desk's measured PAXG 24h floor is 0.64%."""
    v = classify("PAXGUSDT", 0.30, 0.02)
    assert v.state == "NOISE" and not v.confirmed
    assert str(MIN_MOVE_PCT) in v.why


def test_the_agreement_band_is_wide_enough_to_survive_ordinary_microstructure() -> None:
    """A band tight enough to fire on venue noise gets switched off within a week and then
    protects nothing. The failure being guarded is a premium BLOWOUT -- whole percents -- so the
    band is set an order of magnitude above the 4.5bp actually observed on agreement."""
    assert AGREE_BPS >= 20.0
    assert classify("PAXGUSDT", 4.00, 3.80).state == "CONFIRMED", "20bp must still agree"
    assert classify("PAXGUSDT", 4.00, 3.00).state == "DISLOCATION", "100bp must not"


def test_the_twin_is_from_a_different_issuer_which_is_the_whole_mechanism() -> None:
    """Two tokens from ONE issuer share the redemption plumbing that dislocates. They would agree
    while both were wrong, and the check would confirm the error instead of catching it."""
    assert peer_for("PAXGUSDT") == "XAUTUSDT"
    assert peer_for("XAUTUSDT") == "PAXGUSDT"
    for underlying, peers in CROSS_ISSUER.items():
        assert len(set(peers)) >= 2, f"{underlying} has no cross-check at all"
