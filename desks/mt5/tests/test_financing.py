"""OVERNIGHT FINANCING -- that the count is half-open, that Wednesday is triple, and that an
absent broker table produces UNMEASURED rather than zero.

The third property is the one with history behind it. `engine.Costs` documents how this desk
already shipped a gold book running "very nearly spread-free" because a cost was present but
wrong. A cost that is ABSENT is the same defect with no stress test able to reach it, and the
only defence is that the absence has to be loud.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.financing import (  # noqa: E402
    ROLLOVER_HOUR_UTC, TRIPLE_SWAP_NIGHTS, TRIPLE_SWAP_WEEKDAY, assess, breakeven_swap_per_lot,
    drag_r, profile, rollover_nights, stamp_provenance)

UTC = timezone.utc


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """2026-08-<day> in UTC. 2026-08-17 is a Monday, so day 19 is the Wednesday stamp."""
    return datetime(2026, 8, day, hour, minute, tzinfo=UTC)


# ------------------------------------------------------------------ the count

class TestTheStampIsHalfOpen:
    def test_a_trade_opened_on_the_stamp_is_not_yet_financed(self) -> None:
        # Opening at 22:00:00 and closing at 23:00 has not been held overnight. Charging it
        # double-counts every trade that both opens and closes on a stamp, and on hourly bars
        # that alignment is the common one rather than a corner case.
        assert rollover_nights(at(17, ROLLOVER_HOUR_UTC), at(17, 23)) == 0

    def test_a_trade_closed_on_the_stamp_IS_financed(self) -> None:
        assert rollover_nights(at(17, 20), at(17, ROLLOVER_HOUR_UTC)) == 1

    def test_a_trade_entirely_inside_one_session_crosses_nothing(self) -> None:
        assert rollover_nights(at(17, 8), at(17, 16)) == 0

    def test_a_reversed_or_instant_interval_charges_nothing_rather_than_raising(self) -> None:
        # A bad timestamp is the caller's data defect to find. Inventing a charge hides it.
        assert rollover_nights(at(18, 10), at(17, 10)) == 0
        assert rollover_nights(at(17, 10), at(17, 10)) == 0

    def test_the_count_grows_one_per_day_held(self) -> None:
        entry = at(17, 8)                       # Monday morning
        # Mon stamp 1; +Tue stamp 2; +Wed stamp is TRIPLE so 5, not 3; +Thu stamp 6.
        assert rollover_nights(entry, at(18, 8)) == 1
        assert rollover_nights(entry, at(18, 23)) == 2
        assert rollover_nights(entry, at(19, 23)) == 5
        assert rollover_nights(entry, at(20, 23)) == 6


class TestWednesdayIsTriple:
    def test_the_wednesday_stamp_charges_three_nights(self) -> None:
        assert at(19, 0).weekday() == TRIPLE_SWAP_WEEKDAY
        assert rollover_nights(at(19, 20), at(19, 23)) == TRIPLE_SWAP_NIGHTS

    def test_every_other_weekday_stamp_charges_one(self) -> None:
        for day in (17, 18, 20, 21):
            assert rollover_nights(at(day, 20), at(day, 23)) == 1

    def test_ignoring_the_triple_understates_a_continuous_hold_by_two_sevenths(self) -> None:
        """The size of the error, so it cannot be dismissed as a detail: 29% of the annual
        financing on anything held continuously, which is larger than most cost differences
        this desk argues about."""
        entry, exit_ = at(17, 0), at(17, 0) + timedelta(days=70)
        with_triple = rollover_nights(entry, exit_)
        without = rollover_nights(entry, exit_, triple_weekday=None)
        assert with_triple / without == pytest.approx(9 / 7, rel=0.02)

    def test_the_rule_can_be_disabled_for_instruments_that_do_not_settle_T2(self) -> None:
        # Index and energy CFDs are financed daily and take no weekend stamp.
        assert rollover_nights(at(19, 20), at(19, 23), triple_weekday=None) == 1


class TestTheStampHourIsAnAssumptionAndSaysSo:
    def test_the_provenance_string_refuses_to_imply_it_was_read(self) -> None:
        p = stamp_provenance()
        assert "NOT read" in p and "22:00" in p

    def test_a_different_broker_clock_can_be_passed(self) -> None:
        assert rollover_nights(at(17, 20), at(17, 22), hour=21) == 1
        assert rollover_nights(at(17, 20), at(17, 22), hour=23) == 0


# ------------------------------------------------------------------ the profile

class TestTheProfileKeepsTheTailSeparateFromTheMedian:
    def test_a_rare_but_long_hold_shows_up_in_p90_not_in_the_mean(self) -> None:
        spiky = profile([0] * 80 + [10] * 20)      # crosses rarely, holds a week when it does
        steady = profile([2] * 100)                # charged two nights, every single trade
        assert spiky.mean_nights == steady.mean_nights == pytest.approx(2.0)
        assert (spiky.p90_nights, steady.p90_nights) == (10, 2), (
            "sizing sees the mean and survival sees the tail; a profile reporting only the mean "
            "would make these two sleeves identical")
        assert spiky.crossing_rate == pytest.approx(0.20)
        assert steady.crossing_rate == pytest.approx(1.0)

    def test_p90_is_nearest_rank_because_a_broker_cannot_charge_1_point_4_nights(self) -> None:
        assert profile([1, 1, 2]).p90_nights == 2
        assert profile([0, 0, 0, 0, 0, 0, 0, 0, 0, 5]).p90_nights == 0

    def test_an_empty_sleeve_profiles_to_zero_rather_than_dividing_by_it(self) -> None:
        p = profile([])
        assert (p.trades, p.crossings, p.mean_nights, p.crossing_rate) == (0, 0, 0.0, 0.0)

    def test_crossings_count_trades_and_total_nights_count_charges(self) -> None:
        p = profile([0, 1, 3, 3])
        assert p.crossings == 3 and p.total_nights == 7


# ------------------------------------------------------------------ the money

class TestDragIsExpressedInR:
    def test_one_night_costing_the_whole_stop_is_exactly_one_R(self) -> None:
        assert drag_r(1.0, 25.0, 25.0) == pytest.approx(1.0)

    def test_the_sign_convention_is_positive_equals_cost(self) -> None:
        assert drag_r(2.0, 12.0, 40.0) > 0
        assert drag_r(2.0, -12.0, 40.0) < 0, "the financed side that is PAID gets a credit"

    def test_a_zero_stop_stops_rather_than_reporting_inf_beside_a_plausible_expectancy(
            self) -> None:
        for bad in (0.0, -1.0):
            with pytest.raises(ValueError, match="stop"):
                drag_r(1.0, 10.0, bad)

    def test_the_most_exposed_sleeve_still_carries_an_order_of_magnitude_of_headroom(self) -> None:
        """THE NULL THIS MODULE EXISTS TO PUBLISH, pinned so it cannot quietly decay.

        gold_afternoon is the worst case in the reproducible book: 83.2% of its 1,559 trades cross
        a stamp, at 1.481 charged nights each. It is also nowhere near threatened, because one R
        at full lot is 2,725.50 and a raw-spread broker charges XAUUSD in the tens per night.
        """
        nights, exp_r, one_r = 1.481, 0.0957, 2725.50
        be = breakeven_swap_per_lot(exp_r, nights, one_r)
        assert be is not None and be == pytest.approx(176.05, abs=0.5)

        at_20 = drag_r(nights, 20.0, one_r)
        assert at_20 == pytest.approx(0.0109, abs=0.0005)
        assert at_20 / exp_r == pytest.approx(0.114, abs=0.01), (
            "about 11% of the expectancy -- real, worth modelling, and not a kill. If this ever "
            "approaches 1.0 the sleeve's stop has tightened or its edge has thinned, and the "
            "unmodelled swap has become the thing that decides it")

    def test_two_costs_of_similar_size_say_nothing_about_whether_either_matters(self) -> None:
        """The comparison that made this look dangerous, kept so it is not made again.

        Gold's modelled ROUND TRIP is 39.00/lot, so above ~26/lot/night the unmodelled swap does
        exceed the entire modelled cost. True, and irrelevant: both are small against a 2,725 stop.
        """
        crossover = 39.00 / 1.481
        assert crossover == pytest.approx(26.3, abs=0.2)
        assert drag_r(1.481, crossover, 2725.50) < 0.02, (
            "the swap that doubles the modelled cost still moves the sleeve by under 0.02R")


class TestTheBreakevenIsTheAnswerThatNeedsNoBrokerTable:
    def test_it_inverts_the_drag_exactly(self) -> None:
        be = breakeven_swap_per_lot(0.30, 1.5, 40.0)
        assert be is not None
        assert drag_r(1.5, be, 40.0) == pytest.approx(0.30)

    def test_a_sleeve_that_never_crosses_returns_None_meaning_NOT_APPLICABLE(self) -> None:
        # None must never be rendered as "safe" -- it is "swap is not what decides this".
        assert breakeven_swap_per_lot(0.30, 0.0, 40.0) is None

    def test_an_already_dead_sleeve_returns_None_because_swap_is_not_its_problem(self) -> None:
        assert breakeven_swap_per_lot(-0.01, 1.5, 40.0) is None
        assert breakeven_swap_per_lot(0.0, 1.5, 40.0) is None

    def test_a_thinner_edge_or_a_longer_hold_is_killed_by_a_smaller_charge(self) -> None:
        thick = breakeven_swap_per_lot(0.53, 1.0, 40.0)
        thin = breakeven_swap_per_lot(0.03, 1.0, 40.0)
        held = breakeven_swap_per_lot(0.53, 4.0, 40.0)
        assert thick is not None and thin is not None and held is not None
        assert thin < thick and held < thick


# ------------------------------------------------------------------ the verdict

class TestAnAbsentRateIsLOUDRatherThanZero:
    def test_no_rate_gives_UNMEASURED_and_never_a_post_swap_number(self) -> None:
        v = assess("XAUUSD.afternoon", expectancy_r=0.0957, mean_nights=1.481,
                   stop_value_per_lot=40.0)
        assert v.state == "UNMEASURED"
        assert v.drag_r is None and v.expectancy_after_r is None, (
            "an UNMEASURED verdict that still published a post-swap expectancy would be zero "
            "wearing a warning label -- the exact laundering L1.28a forbids")
        assert v.breakeven_per_lot == pytest.approx(0.0957 * 40.0 / 1.481)
        assert "UNMEASURED" in v.why and "NOT read" in v.why

    def test_a_supplied_rate_gives_MEASURED_with_both_halves_of_the_arithmetic(self) -> None:
        v = assess("XAUUSD.afternoon", expectancy_r=0.0957, mean_nights=1.481,
                   stop_value_per_lot=40.0, swap_per_lot=8.0)
        assert v.state == "MEASURED"
        assert v.drag_r is not None and v.expectancy_after_r is not None
        assert v.expectancy_after_r == pytest.approx(0.0957 - v.drag_r)
        assert "KILLED BY" in v.why, "0.296R of drag against a 0.096R edge is a kill"

    def test_a_sleeve_can_survive_its_financing_and_the_verdict_says_so(self) -> None:
        v = assess("AUDCAD.asia.TREND_DAY", expectancy_r=0.5295, mean_nights=0.584,
                   stop_value_per_lot=40.0, swap_per_lot=2.0)
        assert v.expectancy_after_r is not None and v.expectancy_after_r > 0
        assert "SURVIVES" in v.why

    def test_a_non_crossing_sleeve_is_not_reported_as_endangered(self) -> None:
        v = assess("intraday", expectancy_r=0.20, mean_nights=0.0, stop_value_per_lot=40.0)
        assert v.breakeven_per_lot is None
        assert "cannot be what" in v.why

    def test_the_verdict_is_frozen(self) -> None:
        v = assess("x", expectancy_r=0.2, mean_nights=1.0, stop_value_per_lot=40.0)
        with pytest.raises(Exception, match=r"frozen|cannot assign"):
            v.state = "MEASURED"       # type: ignore[misc]
