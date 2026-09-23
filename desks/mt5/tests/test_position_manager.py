"""The ratchet, and specifically the two things it must never do.

A management routine that can widen a stop is a way to lose more than the position was sized
to lose, and one that tightens on every tick chokes the winners that pay for everything else.
Both failure modes are pinned here, on the invariant rather than on example numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.position_manager import (  # noqa: E402
    K_STALLED,
    K_TREND,
    STALL_BARS,
    banked_state,
    chandelier_stop,
    extreme_and_stall,
    is_stalled,
    ratchet,
    stop_protected_r,
)

# A long that has run well: entered 1.1573, stop 20 pips under, now extended to 1.1693.
LONG = {"entry": 1.15730, "current_stop": 1.15530, "stop_distance": 0.00200,
        "extreme": 1.16932, "atr": 0.00180, "side": 1}
#: A short that has actually run far enough for a k=4 trail to beat its opening stop. The
#: distinction matters: at ATR 18 the trending chandelier sits 72 points off the extreme, so a
#: move of less than that leaves the ORIGINAL stop tighter -- see
#: `test_an_early_move_correctly_declines_to_trail_yet`, which pins that case rather than
#: hiding it behind friendlier numbers.
SHORT = {"entry": 4391.49, "current_stop": 4411.49, "stop_distance": 20.0,
         "extreme": 4280.00, "atr": 18.0, "side": -1}


# ------------------------------------------------- the guaranteed outcome

def test_stop_protected_r_is_negative_while_the_stop_is_still_below_entry():
    """A trade that looks green has secured NOTHING until its stop passes entry.

    This is the distinction the whole module rests on: unrealised P&L can be strongly positive
    and still resolve as a loss. Only `guaranteed_r` can be ratcheted, precisely because it
    cannot move on its own.
    """
    g = stop_protected_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1)
    assert g == pytest.approx(-1.0), "stop one full stop-distance below entry is exactly -1R"


def test_stop_protected_r_ignores_current_price_entirely():
    """Unrealised profit is not an input. If it were, the ratchet would chase price."""
    a = stop_protected_r(entry=1.15730, stop=1.15900, stop_distance=0.00200, side=1)
    b = stop_protected_r(entry=1.15730, stop=1.15900, stop_distance=0.00200, side=1)
    assert a == b == pytest.approx(0.85)


def test_banking_raises_the_guaranteed_outcome_without_touching_the_stop():
    """The second lever. Banking secures wealth when tightening would cost more than it saves."""
    unbanked = stop_protected_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1)
    banked = stop_protected_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1,
                          banked_r=1.5, remaining_fraction=0.5)
    assert banked > unbanked
    assert banked == pytest.approx(1.5 + 0.5 * -1.0)


@pytest.mark.parametrize("side,stop,expected", [
    (1, 1.15930, 1.0),      # long, stop one stop-distance ABOVE entry = +1R secured
    (-1, 4371.49, 1.0),     # short, stop one stop-distance BELOW entry = +1R secured
])
def test_stop_protected_r_is_symmetric_in_side(side, stop, expected):
    entry = 1.15730 if side == 1 else 4391.49
    dist = 0.00200 if side == 1 else 20.0
    assert stop_protected_r(entry=entry, stop=stop, stop_distance=dist,
                        side=side) == pytest.approx(expected)


# ------------------------------------------------- banked state comes from the broker

def test_banked_state_is_reconstructed_from_executed_volume_not_intent():
    """Half the position closed for +1.5R worth of quote currency, half still open."""
    banked_r, remaining = banked_state(original_volume=1.00, live_volume=0.50,
                                       realised_quote=300.0, risk_per_lot_quote=200.0)
    assert remaining == pytest.approx(0.5)
    assert banked_r == pytest.approx(1.5)


def test_an_untouched_position_has_banked_nothing_and_is_wholly_remaining():
    banked_r, remaining = banked_state(original_volume=1.45, live_volume=1.45,
                                       realised_quote=0.0, risk_per_lot_quote=200.0)
    assert banked_r == 0.0 and remaining == pytest.approx(1.0)


def test_volume_above_the_original_refuses_rather_than_flattering_the_outcome():
    """A pyramid add or the wrong ticket. Returning a negative banked fraction here would
    OVERSTATE protection, which is the one direction of error that costs money."""
    with pytest.raises(ValueError, match="not a partial close"):
        banked_state(original_volume=1.00, live_volume=1.50,
                     realised_quote=0.0, risk_per_lot_quote=200.0)


def test_a_realised_loss_on_the_closed_leg_lowers_the_protected_outcome():
    """Banking is not automatically good. A partial closed at a loss must show as negative."""
    banked_r, remaining = banked_state(original_volume=1.00, live_volume=0.50,
                                       realised_quote=-100.0, risk_per_lot_quote=200.0)
    assert banked_r == pytest.approx(-0.5) and remaining == pytest.approx(0.5)
    total = stop_protected_r(entry=1.15730, stop=1.15730, stop_distance=0.00200, side=1,
                             banked_r=banked_r, remaining_fraction=remaining)
    assert total == pytest.approx(-0.5), "a losing partial must drag the protected total down"


@pytest.mark.parametrize("kwargs", [
    {"original_volume": 0.0, "live_volume": 0.0,
     "realised_quote": 0.0, "risk_per_lot_quote": 200.0},
    {"original_volume": 1.0, "live_volume": -0.1,
     "realised_quote": 0.0, "risk_per_lot_quote": 200.0},
    {"original_volume": 1.0, "live_volume": 0.5, "realised_quote": 0.0, "risk_per_lot_quote": 0.0},
])
def test_banked_state_rejects_impossible_inputs(kwargs):
    with pytest.raises(ValueError):
        banked_state(**kwargs)


# ------------------------------------------------- locating the extreme

def test_extreme_and_stall_finds_the_high_water_mark_for_a_long():
    highs = [1.1600, 1.1650, 1.1693, 1.1670, 1.1660]
    lows = [1.1580, 1.1620, 1.1660, 1.1640, 1.1630]
    extreme, bars = extreme_and_stall(highs=highs, lows=lows, side=1)
    assert extreme == pytest.approx(1.1693)
    assert bars == 2, "two bars have printed since the high"


def test_extreme_and_stall_uses_lows_for_a_short():
    highs = [4400.0, 4380.0, 4360.0, 4370.0]
    lows = [4390.0, 4370.0, 4340.0, 4355.0]
    extreme, bars = extreme_and_stall(highs=highs, lows=lows, side=-1)
    assert extreme == pytest.approx(4340.0)
    assert bars == 1


def test_a_fresh_extreme_on_the_latest_bar_is_never_stalled():
    highs = [1.1600, 1.1650, 1.1700]
    lows = [1.1580, 1.1620, 1.1660]
    _, bars = extreme_and_stall(highs=highs, lows=lows, side=1)
    assert bars == 0 and not is_stalled(bars)


def test_a_revisited_extreme_re_confirms_rather_than_counting_as_stale():
    """LAST occurrence wins on ties, and this is a deliberate choice.

    A move that pulls back and then returns to its high has RE-CONFIRMED the level. Taking the
    first occurrence would call this three bars stale and tighten the stop on a trend that is
    still working -- exactly the choke the stall switch exists to avoid.
    """
    highs = [1.1693, 1.1670, 1.1660, 1.1693]
    lows = [1.1660, 1.1640, 1.1630, 1.1660]
    extreme, bars = extreme_and_stall(highs=highs, lows=lows, side=1)
    assert extreme == pytest.approx(1.1693)
    assert bars == 0, "a revisited high is a fresh extreme, not a stale one"
    assert not is_stalled(bars)


def test_extreme_and_stall_refuses_empty_or_ragged_input():
    with pytest.raises(ValueError, match="no bars"):
        extreme_and_stall(highs=[], lows=[], side=1)
    with pytest.raises(ValueError, match="length mismatch"):
        extreme_and_stall(highs=[1.0, 2.0], lows=[1.0], side=1)


# ------------------------------------------------- the stall switch

def test_stall_is_measured_in_bars_without_a_new_extreme():
    assert not is_stalled(STALL_BARS - 1)
    assert is_stalled(STALL_BARS)
    assert is_stalled(STALL_BARS + 10)


def test_a_stalled_move_gets_a_tighter_stop_than_a_trending_one():
    """THE MEASURED MECHANISM (+$11.63/oz paired, t=2.48): same k cannot serve both states."""
    trending = ratchet(**LONG, bars_since_extreme=0)
    stalled = ratchet(**LONG, bars_since_extreme=STALL_BARS)
    assert trending.k_used == K_TREND and not trending.stalled
    assert stalled.k_used == K_STALLED and stalled.stalled
    assert stalled.new_stop > trending.new_stop, (
        "a stalled move must protect more, or the two-state design buys nothing")
    assert stalled.protected_r_after > trending.protected_r_after


def test_the_trending_stop_leaves_real_room_rather_than_hugging_price():
    """The anti-choke property. A trend stop that sits just under the extreme is the failure
    mode that looks like discipline and quietly deletes every 5R outcome."""
    d = ratchet(**LONG, bars_since_extreme=0)
    room = LONG["extreme"] - d.new_stop
    assert room == pytest.approx(K_TREND * LONG["atr"])
    assert room > 3 * LONG["atr"], "trending room collapsed; runners will be cut short"


# ------------------------------------------------- the refusals that protect capital

def test_a_stop_is_never_widened_long():
    """THE MONEY-PATH SAFETY PROPERTY. There is no market state that justifies this."""
    # Extreme barely above entry, huge ATR -> chandelier lands far BELOW the current stop.
    d = ratchet(entry=1.15730, current_stop=1.15900, stop_distance=0.00200,
                extreme=1.15950, atr=0.00500, side=1, bars_since_extreme=0)
    assert not d.moves, "widened a long's stop"
    assert d.protected_r_after == d.protected_r_before
    assert "never widened" in d.reason


def test_a_stop_is_never_widened_short():
    d = ratchet(entry=4391.49, current_stop=4371.49, stop_distance=20.0,
                extreme=4365.00, atr=60.0, side=-1, bars_since_extreme=0)
    assert not d.moves, "widened a short's stop"
    assert d.protected_r_after == d.protected_r_before


def test_the_guaranteed_outcome_never_decreases_across_any_sequence():
    """THE INVARIANT, exercised over a whole path rather than asserted once.

    Walks a long up, stalls it, pulls it back, re-extends it -- the shape of a real runner --
    and requires G to be monotone non-decreasing at every single step. This is the property
    that makes a round-trip from +5R to -1R structurally impossible rather than unlikely.
    """
    entry, dist, atr = 1.15730, 0.00200, 0.00180
    stop = 1.15530
    path = [(1.1600, 0), (1.1650, 0), (1.1693, 0), (1.1693, 1), (1.1693, 2),
            (1.1693, 3), (1.1693, 5), (1.1720, 0), (1.1750, 0), (1.1750, 4)]
    prev_g = stop_protected_r(entry=entry, stop=stop, stop_distance=dist, side=1)
    for extreme, bars in path:
        d = ratchet(entry=entry, current_stop=stop, stop_distance=dist,
                    extreme=extreme, atr=atr, side=1, bars_since_extreme=bars)
        assert d.protected_r_after >= prev_g - 1e-12, (
            f"guaranteed outcome fell {prev_g:+.4f}R -> {d.protected_r_after:+.4f}R "
            f"at extreme={extreme} bars={bars}")
        if d.moves:
            assert d.new_stop > stop, "a 'move' that did not improve the long's stop"
            stop = d.new_stop
        prev_g = max(prev_g, d.protected_r_after)
    assert prev_g > 0, "a move this favourable should have secured a positive outcome"


def test_a_runner_that_reverses_hard_keeps_what_it_secured():
    """The €1,490-open-winner case, stated as a property.

    Once the ratchet has lifted the stop above entry, a violent reversal takes the SECURED
    outcome -- not the original -1R. Before this module existed on the live path, nothing moved
    that stop and the full round-trip was available.
    """
    entry, dist, atr = 1.15730, 0.00200, 0.00180
    d = ratchet(entry=entry, current_stop=1.15530, stop_distance=dist,
                extreme=1.16932, atr=atr, side=1, bars_since_extreme=STALL_BARS)
    assert d.moves and d.new_stop > entry
    assert d.protected_r_after > 0, "stalled at +6R of open profit and secured nothing"


# ------------------------------------------------- input validation

@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_a_nonpositive_stop_distance_raises_rather_than_dividing(bad):
    with pytest.raises(ValueError):
        stop_protected_r(entry=1.0, stop=0.9, stop_distance=bad, side=1)


def test_a_nonpositive_atr_raises_rather_than_producing_a_stop_at_the_extreme():
    """ATR of zero would put the stop exactly on the high-water mark -- an instant exit."""
    with pytest.raises(ValueError):
        chandelier_stop(extreme=1.16932, atr=0.0, side=1, k=K_TREND)


def test_an_invalid_side_raises():
    with pytest.raises(ValueError):
        ratchet(entry=1.0, current_stop=0.9, stop_distance=0.1, extreme=1.2,
                atr=0.05, side=0, bars_since_extreme=0)  # type: ignore[arg-type]


def test_remaining_fraction_outside_zero_to_one_raises():
    with pytest.raises(ValueError):
        stop_protected_r(entry=1.0, stop=0.9, stop_distance=0.1, side=1, remaining_fraction=1.5)


# ------------------------------------------------- shorts get the same guarantees

def test_the_short_side_ratchets_downward():
    d = ratchet(**SHORT, bars_since_extreme=0)
    assert d.moves and d.new_stop < SHORT["current_stop"]
    assert d.protected_r_after > d.protected_r_before


def test_the_short_side_tightens_when_stalled():
    trending = ratchet(**SHORT, bars_since_extreme=0)
    stalled = ratchet(**SHORT, bars_since_extreme=STALL_BARS)
    assert stalled.new_stop < trending.new_stop
    assert stalled.protected_r_after > trending.protected_r_after


def test_an_early_move_correctly_declines_to_trail_yet():
    """A trail that has not yet beaten the opening stop must HOLD, not split the difference.

    Found by this suite rather than reasoned about in advance: gold 51 points onside with ATR 18
    puts the k=4 chandelier 72 points off the extreme, which is LOOSER than the 20-point opening
    stop. The correct answer is to leave the original stop alone -- the position is still in its
    initial-risk phase and has not earned a trail. Tightening toward the chandelier anyway would
    be widening the stop, and clamping it to the current stop would be a no-op dressed up as an
    action. Both are wrong; holding is right, and it is reported as a hold.
    """
    d = ratchet(entry=4391.49, current_stop=4411.49, stop_distance=20.0,
                extreme=4340.00, atr=18.0, side=-1, bars_since_extreme=0)
    assert not d.moves
    assert d.protected_r_after == d.protected_r_before == pytest.approx(-1.0)
    assert "never widened" in d.reason
