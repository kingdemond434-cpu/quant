"""The break-even floor: it must be COSTED, one-way, and reach both accounts.

WHAT THESE PIN, AND WHY EACH ONE IS A DEFECT SOMEONE WOULD OTHERWISE SHIP.

The principal's order of 2026-09-24 is that the gold sleeves -- the breakout ones and the
limit-placing ones -- "must carry a break-even stop at the least and must never give back
floating profit turning into losses", on the live MT5 account AND on E8.

Four ways to get that wrong, all pinned below:

  1. PARKING THE STOP ON THE ENTRY PRICE. On Fusion, commission is 2.00 per lot per side
     (`fusion_cost.COMMISSION_PER_LOT_PER_SIDE`, measured p10 = p50 = p90 over 433 deals on
     495044). A stop at `price_open` therefore books a small LOSS on every scratch, on every
     trade, scaling linearly with size -- the mechanism inverted while looking correct.
  2. CHARGING THE SPREAD TWICE. MetaTrader compares a long's stop to the BID and a short's to
     the ASK. A long filled at the ask has already paid the spread; adding it to the level again
     asks the market to travel the same distance twice.
  3. CHARGING THE SPREAD ZERO TIMES ON THE SHORT LEG. The bar feed is bid bars, so a short's
     favourable extreme is one spread better than any price it could have bought back at. Arming
     off the raw bid arms shorts early -- the same "scratch becomes a loss" defect, relocated
     from the level to the trigger.
  4. LETTING THE FLOOR WIDEN A STOP. The whole module is built on an invariant that protection
     never decreases; a floor that can lower a stop that has already trailed past it would be a
     way to lose more than the position was sized to lose.

THE FLOOR IS ALSO MEASURED, NOT ASSERTED. `BREAKEVEN_TRIGGER_R = 0.85` came from replaying 82
reconstructed XAUUSD trades bar by bar on M1: +107.94 net on a +227.90 base, E[log W] +0.10256,
26 losers scratched against 11 winners given up. The last test pins the trigger inside the band
the sweep found positive under both intrabar orderings (0.30R..1.10R), so a later edit that
moves it outside the measured evidence fails here rather than silently on the account.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mt5desk.position_manager import (
    BREAKEVEN_TRIGGER_R,
    breakeven_armed,
    breakeven_level,
    net_open_excursion,
    ratchet,
)

# One 0.01-lot XAUUSD position: contract 100 oz, so 2.00/lot/side round trip is 4.00 per lot,
# and one lot is worth 100 account units per 1.00 of price -> 0.04 of price.
COST = 0.04
SPREAD = 0.04


# ----------------------------------------------------------------- the level is costed
def test_the_long_break_even_level_clears_the_round_trip_rather_than_sitting_on_the_entry() -> None:
    entry = 4300.00
    lvl = breakeven_level(entry=entry, side=1, cost_per_unit=COST)
    assert lvl == pytest.approx(4300.04)
    assert lvl > entry, "a stop at the entry price still pays commission twice"


def test_the_short_break_even_level_sits_below_the_entry_by_the_same_round_trip() -> None:
    entry = 4300.00
    lvl = breakeven_level(entry=entry, side=-1, cost_per_unit=COST)
    assert lvl == pytest.approx(4299.96)
    assert lvl < entry


def test_the_costed_level_actually_nets_zero_for_both_sides() -> None:
    """The arithmetic the whole mechanism rests on, stated as money rather than as a price."""
    entry, mult = 4300.00, 1.0     # 0.01 lot x 100 oz = 1.00 account unit per 1.00 of price
    round_trip_money = 2.00 * 2 * 0.01   # 2.00/lot/side, both sides, 0.01 lot

    long_exit = breakeven_level(entry=entry, side=1, cost_per_unit=COST)
    assert (long_exit - entry) * mult - round_trip_money == pytest.approx(0.0, abs=1e-9)

    short_exit = breakeven_level(entry=entry, side=-1, cost_per_unit=COST)
    assert (entry - short_exit) * mult - round_trip_money == pytest.approx(0.0, abs=1e-9)


def test_a_zero_cost_account_breaks_even_at_the_entry_and_that_is_not_the_same_claim() -> None:
    """E8 is commission-free, so its floor collapses to the entry. Fusion's does not."""
    assert breakeven_level(entry=4300.0, side=1, cost_per_unit=0.0) == 4300.0
    assert breakeven_level(entry=4300.0, side=1, cost_per_unit=COST) > 4300.0


# ----------------------------------------------------------------- the trigger is costed too
def test_the_short_leg_is_charged_its_spread_and_the_long_leg_is_not() -> None:
    """Bid bars: a long realises at the bid it printed, a short must buy back one spread above."""
    entry = 4300.00
    long_net = net_open_excursion(entry=entry, extreme=4310.00, side=1,
                                  cost_per_unit=COST, spread=SPREAD)
    assert long_net == pytest.approx(10.00 - COST)

    short_net = net_open_excursion(entry=entry, extreme=4290.00, side=-1,
                                   cost_per_unit=COST, spread=SPREAD)
    assert short_net == pytest.approx(10.00 - COST - SPREAD)
    assert short_net < long_net, "the short leg must be the more expensive of the two"


def test_arming_needs_the_trigger_in_net_profit_not_gross() -> None:
    """The round trip is charged BEFORE the trigger is compared, not after.

    The epsilon is a real statement, not a fudge. At the exact boundary the comparison is a
    float equality on a number that is not representable (4308.54 - 4300.0 - 0.04 lands at
    8.499999999999964), so the boundary case is genuinely ambiguous and the code arms one pass
    later. That is the harmless direction -- protection a tick late, never a tick early -- and
    tightening it with a tolerance would be inventing precision the prices do not have.
    """
    entry, dist = 4300.00, 10.0
    eps = 1e-6
    # Exactly 0.85R gross, which is NOT 0.85R net once the round trip is charged.
    gross_only = entry + BREAKEVEN_TRIGGER_R * dist
    assert not breakeven_armed(entry=entry, extreme=gross_only, stop_distance=dist, side=1,
                               cost_per_unit=COST, spread=SPREAD)
    assert breakeven_armed(entry=entry, extreme=gross_only + COST + eps, stop_distance=dist,
                           side=1, cost_per_unit=COST, spread=SPREAD)


def test_arming_is_measured_off_the_high_water_mark_so_it_never_disarms() -> None:
    entry, dist = 4300.00, 10.0
    peak = entry + BREAKEVEN_TRIGGER_R * dist + COST + 1e-6
    assert breakeven_armed(entry=entry, extreme=peak, stop_distance=dist, side=1,
                           cost_per_unit=COST, spread=SPREAD)
    # The extreme only ever grows, so the same call on a later pass cannot answer False.
    assert breakeven_armed(entry=entry, extreme=peak + 5.0, stop_distance=dist, side=1,
                           cost_per_unit=COST, spread=SPREAD)


# ----------------------------------------------------------------- composed into the ratchet
def _ratchet(**kw):  # type: ignore[no-untyped-def]
    base = {"entry": 4300.0, "current_stop": 4290.0, "stop_distance": 10.0,
            "extreme": 4310.0, "atr": 2.0, "side": 1, "bars_since_extreme": 0,
            "cost_per_unit": COST, "spread": SPREAD}
    return ratchet(**(base | kw))


def test_the_floor_lifts_a_stop_the_wide_trail_would_have_left_below_the_entry() -> None:
    """The giveback the principal named: k=4 x ATR off the extreme still sits under water."""
    # Chandelier: 4310 - 4*2.0 = 4302 -- above entry here, so force a wide ATR to reproduce it.
    d = _ratchet(atr=6.0)          # chandelier = 4310 - 24 = 4286, below the current stop
    assert d.moves, "the break-even floor should still act where the trail refuses"
    assert d.breakeven_floor
    assert d.new_stop == pytest.approx(4300.04)
    assert d.new_stop > 4300.0, "a floor that lands under the entry is not break-even"


def test_the_floor_never_choked_a_trail_that_already_protects_more() -> None:
    d = _ratchet(atr=1.0)          # chandelier = 4310 - 4 = 4306, well above break-even
    assert d.moves
    assert not d.breakeven_floor
    assert d.new_stop == pytest.approx(4306.0)


def test_the_floor_never_widens_a_stop_that_has_already_passed_it() -> None:
    """The invariant. A long's stop may only rise; equality is not an improvement."""
    d = _ratchet(atr=6.0, current_stop=4305.0)
    assert not d.moves, d.reason
    assert "never widened" in d.reason


def test_the_floor_never_widens_a_short_stop_either() -> None:
    d = ratchet(entry=4300.0, current_stop=4295.0, stop_distance=10.0, extreme=4290.0,
                atr=6.0, side=-1, bars_since_extreme=0, cost_per_unit=COST, spread=SPREAD)
    assert not d.moves, d.reason


def test_an_armed_short_is_floored_below_its_entry() -> None:
    d = ratchet(entry=4300.0, current_stop=4310.0, stop_distance=10.0, extreme=4289.0,
                atr=6.0, side=-1, bars_since_extreme=0, cost_per_unit=COST, spread=SPREAD)
    assert d.moves and d.breakeven_floor
    assert d.new_stop == pytest.approx(4299.96)
    assert d.new_stop < d.protected_r_after + 1e9   # sanity; real claim is the level itself


def test_nothing_arms_before_the_trigger_is_reached() -> None:
    d = _ratchet(atr=6.0, extreme=4302.0)   # only 0.2R gross
    assert not d.moves
    assert not d.breakeven_floor


def test_omitting_the_cost_leaves_the_trail_exactly_as_it_was() -> None:
    """Back-compatibility: callers that pass no cost get the pre-2026-09-24 behaviour."""
    with_cost = _ratchet(atr=6.0)
    without = ratchet(entry=4300.0, current_stop=4290.0, stop_distance=10.0, extreme=4310.0,
                      atr=6.0, side=1, bars_since_extreme=0)
    assert with_cost.moves and not without.moves
    assert not without.breakeven_floor


def test_the_protected_outcome_can_only_rise_across_the_floor() -> None:
    d = _ratchet(atr=6.0)
    assert d.protected_r_after > d.protected_r_before
    assert d.improvement_r > 0


# ------------------------------------------------- floor without trail (fixed brackets)
def test_a_fixed_bracket_gets_the_floor_but_never_the_trail() -> None:
    """The 2026-09-16 finding and the 2026-09-24 order are both satisfied, not traded off.

    Trailing a certificate earned on a fixed bracket is a lookalike strategy under a certified
    name (measured: five forex closes at a manage-tightened stop, -4.25 EUR). But a plain `skip`
    there also refused the break-even stop -- and three of the thirteen LIVE sleeves are
    `family_market` XAUUSD session-range BREAKOUTS, the exact sleeves the principal named. So the
    trail is suppressed and the floor still acts.
    """
    # A tight ATR: the chandelier at 4310 - 4*0.5 = 4308 would be a big tightening. Floor-only
    # must ignore it entirely and propose the break-even level instead.
    d = _ratchet(atr=0.5, floor_only=True)
    assert d.moves and d.breakeven_floor
    assert d.new_stop == pytest.approx(4300.04), "floor-only must not trail to 4308"
    assert "no trail" in d.reason


def test_a_fixed_bracket_below_the_trigger_is_left_completely_alone() -> None:
    d = _ratchet(atr=0.5, extreme=4302.0, floor_only=True)
    assert not d.moves
    assert not d.breakeven_floor


def test_floor_only_never_widens_either() -> None:
    d = _ratchet(atr=0.5, current_stop=4305.0, floor_only=True)
    assert not d.moves, d.reason


def test_the_trail_still_runs_when_floor_only_is_off() -> None:
    """The default path is unchanged: a sleeve whose certificate carried a trail still trails."""
    d = _ratchet(atr=0.5)
    assert d.moves and not d.breakeven_floor
    assert d.new_stop == pytest.approx(4308.0)


# ----------------------------------------------------------------- the measured band
def test_the_trigger_stays_inside_the_band_the_sweep_measured_positive() -> None:
    """0.30R..1.10R was positive under BOTH intrabar orderings on 82 XAUUSD trades.

    Outside it the sign flips: -46.71 at 0.25R (scratching winners inside ordinary noise) and
    -97.32 at 2.00R (arming too late to catch the losers). A future edit that moves the constant
    out of the measured band is making a claim the desk has not cashed, and Growth Governance
    rule 1 says that claim has to be re-measured first.
    """
    assert 0.30 <= BREAKEVEN_TRIGGER_R <= 1.10


def test_the_cost_constant_this_was_measured_against_has_not_moved() -> None:
    from libs.portfolio.fusion_cost import COMMISSION_PER_LOT_PER_SIDE

    assert COMMISSION_PER_LOT_PER_SIDE == 2.00


# ----------------------------------------------------------------- inputs that must refuse
@pytest.mark.parametrize("kw", [
    {"cost_per_unit": -0.01},
    {"side": 0},
])
def test_degenerate_level_inputs_refuse_rather_than_guess(kw: dict) -> None:
    with pytest.raises(ValueError):
        breakeven_level(**({"entry": 4300.0, "side": 1, "cost_per_unit": COST} | kw))


def test_a_zero_r_position_refuses_rather_than_dividing_by_it() -> None:
    with pytest.raises(ValueError):
        breakeven_armed(entry=4300.0, extreme=4310.0, stop_distance=0.0, side=1,
                        cost_per_unit=COST)


def test_a_negative_spread_refuses() -> None:
    with pytest.raises(ValueError):
        net_open_excursion(entry=4300.0, extreme=4310.0, side=1,
                           cost_per_unit=COST, spread=-0.01)
