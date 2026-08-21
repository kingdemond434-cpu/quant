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
    K_STALLED, K_TREND, STALL_BARS, chandelier_stop, guaranteed_r, is_stalled, ratchet)

# A long that has run well: entered 1.1573, stop 20 pips under, now extended to 1.1693.
LONG = dict(entry=1.15730, current_stop=1.15530, stop_distance=0.00200,
            extreme=1.16932, atr=0.00180, side=1)
#: A short that has actually run far enough for a k=4 trail to beat its opening stop. The
#: distinction matters: at ATR 18 the trending chandelier sits 72 points off the extreme, so a
#: move of less than that leaves the ORIGINAL stop tighter -- see
#: `test_an_early_move_correctly_declines_to_trail_yet`, which pins that case rather than
#: hiding it behind friendlier numbers.
SHORT = dict(entry=4391.49, current_stop=4411.49, stop_distance=20.0,
             extreme=4280.00, atr=18.0, side=-1)


# ------------------------------------------------- the guaranteed outcome

def test_guaranteed_r_is_negative_while_the_stop_is_still_below_entry():
    """A trade that looks green has secured NOTHING until its stop passes entry.

    This is the distinction the whole module rests on: unrealised P&L can be strongly positive
    and still resolve as a loss. Only `guaranteed_r` can be ratcheted, precisely because it
    cannot move on its own.
    """
    g = guaranteed_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1)
    assert g == pytest.approx(-1.0), "stop one full stop-distance below entry is exactly -1R"


def test_guaranteed_r_ignores_current_price_entirely():
    """Unrealised profit is not an input. If it were, the ratchet would chase price."""
    a = guaranteed_r(entry=1.15730, stop=1.15900, stop_distance=0.00200, side=1)
    b = guaranteed_r(entry=1.15730, stop=1.15900, stop_distance=0.00200, side=1)
    assert a == b == pytest.approx(0.85)


def test_banking_raises_the_guaranteed_outcome_without_touching_the_stop():
    """The second lever. Banking secures wealth when tightening would cost more than it saves."""
    unbanked = guaranteed_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1)
    banked = guaranteed_r(entry=1.15730, stop=1.15530, stop_distance=0.00200, side=1,
                          banked_r=1.5, remaining_fraction=0.5)
    assert banked > unbanked
    assert banked == pytest.approx(1.5 + 0.5 * -1.0)


@pytest.mark.parametrize("side,stop,expected", [
    (1, 1.15930, 1.0),      # long, stop one stop-distance ABOVE entry = +1R secured
    (-1, 4371.49, 1.0),     # short, stop one stop-distance BELOW entry = +1R secured
])
def test_guaranteed_r_is_symmetric_in_side(side, stop, expected):
    entry = 1.15730 if side == 1 else 4391.49
    dist = 0.00200 if side == 1 else 20.0
    assert guaranteed_r(entry=entry, stop=stop, stop_distance=dist,
                        side=side) == pytest.approx(expected)


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
    assert stalled.guaranteed_r_after > trending.guaranteed_r_after


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
    assert d.guaranteed_r_after == d.guaranteed_r_before
    assert "never widened" in d.reason


def test_a_stop_is_never_widened_short():
    d = ratchet(entry=4391.49, current_stop=4371.49, stop_distance=20.0,
                extreme=4365.00, atr=60.0, side=-1, bars_since_extreme=0)
    assert not d.moves, "widened a short's stop"
    assert d.guaranteed_r_after == d.guaranteed_r_before


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
    prev_g = guaranteed_r(entry=entry, stop=stop, stop_distance=dist, side=1)
    for extreme, bars in path:
        d = ratchet(entry=entry, current_stop=stop, stop_distance=dist,
                    extreme=extreme, atr=atr, side=1, bars_since_extreme=bars)
        assert d.guaranteed_r_after >= prev_g - 1e-12, (
            f"guaranteed outcome fell {prev_g:+.4f}R -> {d.guaranteed_r_after:+.4f}R "
            f"at extreme={extreme} bars={bars}")
        if d.moves:
            assert d.new_stop > stop, "a 'move' that did not improve the long's stop"
            stop = d.new_stop
        prev_g = max(prev_g, d.guaranteed_r_after)
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
    assert d.guaranteed_r_after > 0, "stalled at +6R of open profit and secured nothing"


# ------------------------------------------------- input validation

@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_a_nonpositive_stop_distance_raises_rather_than_dividing(bad):
    with pytest.raises(ValueError):
        guaranteed_r(entry=1.0, stop=0.9, stop_distance=bad, side=1)


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
        guaranteed_r(entry=1.0, stop=0.9, stop_distance=0.1, side=1, remaining_fraction=1.5)


# ------------------------------------------------- shorts get the same guarantees

def test_the_short_side_ratchets_downward():
    d = ratchet(**SHORT, bars_since_extreme=0)
    assert d.moves and d.new_stop < SHORT["current_stop"]
    assert d.guaranteed_r_after > d.guaranteed_r_before


def test_the_short_side_tightens_when_stalled():
    trending = ratchet(**SHORT, bars_since_extreme=0)
    stalled = ratchet(**SHORT, bars_since_extreme=STALL_BARS)
    assert stalled.new_stop < trending.new_stop
    assert stalled.guaranteed_r_after > trending.guaranteed_r_after


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
    assert d.guaranteed_r_after == d.guaranteed_r_before == pytest.approx(-1.0)
    assert "never widened" in d.reason
