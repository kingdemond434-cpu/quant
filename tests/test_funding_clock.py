"""Tests for the funding settlement clock (L1.46).

These fail if the clock's DISCRETE semantics are quietly replaced by an accrual -- which is the
exact regression this module exists to prevent, and the one that hid for the desk's whole history
because it is unbiased in expectation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from libs.research import funding_clock as fc


def _t(h: float, day: int = 1) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC) + timedelta(hours=h)


class TestStamps:
    def test_stamps_anchor_to_utc_day(self) -> None:
        # 00/08/16 UTC exactly -- anchored to the day, never to an epoch offset.
        assert fc.last_settlement(_t(9.5)) == _t(8)
        assert fc.next_settlement(_t(9.5)) == _t(16)
        assert fc.last_settlement(_t(0)) == _t(0)

    def test_next_is_strictly_after(self) -> None:
        # ON a stamp the payment has already been made: the next one is a full interval away.
        assert fc.next_settlement(_t(8)) == _t(16)

    def test_crosses_midnight(self) -> None:
        assert fc.next_settlement(_t(23)) == _t(0, day=2)

    def test_naive_datetime_treated_as_utc(self) -> None:
        assert fc.last_settlement(datetime(2026, 8, 1, 9, 30)) == _t(8)

    def test_four_hour_symbol(self) -> None:
        # The high-funding alts Binance settles 4-hourly -- the case every `/ 8.0` gets wrong.
        assert fc.next_settlement(_t(9.5), interval_h=4.0) == _t(12)


class TestPhase:
    def test_phase_and_time_to_settlement_are_complementary(self) -> None:
        t = _t(7.25)
        assert fc.phase_hours(t) == pytest.approx(7.25)
        assert fc.hours_to_settlement(t) == pytest.approx(0.75)
        assert fc.phase_hours(t) + fc.hours_to_settlement(t) == pytest.approx(8.0)

    def test_phase_is_zero_on_a_stamp_and_time_to_next_is_full(self) -> None:
        assert fc.phase_hours(_t(16)) == pytest.approx(0.0)
        assert fc.hours_to_settlement(_t(16)) == pytest.approx(8.0)


class TestSettlementsIn:
    def test_long_hold_across_no_stamp_earns_nothing(self) -> None:
        # 7.9h of basis risk, zero payment. The case `held / 8.0` books as 0.99 settlements.
        assert fc.settlements_in(_t(0.05), _t(7.95)) == 0

    def test_short_hold_across_a_stamp_earns_a_full_settlement(self) -> None:
        # 0.2h of risk, a FULL payment. `held / 8.0` books this as 0.025.
        assert fc.settlements_in(_t(7.9), _t(8.1)) == 1

    def test_window_is_half_open_excluding_start(self) -> None:
        # Opening exactly ON a stamp does not collect that stamp -- it has already been paid.
        assert fc.settlements_in(_t(8), _t(15)) == 0
        assert fc.settlements_in(_t(8), _t(16)) == 1

    def test_counts_multiple_and_matches_a_full_day(self) -> None:
        assert fc.settlements_in(_t(0), _t(24)) == 3
        assert fc.settlements_in(_t(0), _t(48)) == 6

    def test_reversed_or_empty_window_is_zero(self) -> None:
        assert fc.settlements_in(_t(10), _t(10)) == 0
        assert fc.settlements_in(_t(10), _t(2)) == 0

    def test_four_hour_symbol_earns_double(self) -> None:
        assert fc.settlements_in(_t(0), _t(24), interval_h=4.0) == 6


class TestDiscreteVsContinuousDelta:
    """The whole point: the two models differ per-trade while agreeing on average."""

    def test_continuous_model_disagrees_on_the_pathological_cases(self) -> None:
        # Long hold, no stamp: continuous says ~1 settlement, truth says 0.
        assert fc.continuous_settlements(_t(0.05), _t(7.95)) == pytest.approx(0.9875)
        assert fc.settlements_in(_t(0.05), _t(7.95)) == 0
        # Short hold across a stamp: continuous says 0.025, truth says 1.
        assert fc.continuous_settlements(_t(7.9), _t(8.1)) == pytest.approx(0.025)
        assert fc.settlements_in(_t(7.9), _t(8.1)) == 1

    def test_integer_multiple_holds_are_the_ONLY_exact_case(self) -> None:
        # A hold of exactly N intervals captures exactly N settlements from EVERY phase, so the
        # two models agree perfectly. `_MIN_HOLD_H = 24.0` is exactly 3x8h, which is why the
        # accrual looks defensible -- it is exact at the floor and wrong everywhere above it.
        for phase in range(80):
            t0 = _t(phase / 10)
            assert fc.settlements_in(t0, t0 + timedelta(hours=24)) == 3
            assert fc.continuous_settlements(t0, t0 + timedelta(hours=24)) == pytest.approx(3.0)

    def test_models_agree_in_expectation_but_never_per_trade(self) -> None:
        # This is WHY the defect survived every review. At a 20h hold (fractional part 4h) the
        # continuous model books a flat 2.5 settlements from every phase, while the truth is
        # 2 or 3 depending on phase. The mean delta is ~0 -- and no single trade is right.
        deltas = [fc.settlements_in(_t(p / 10), _t(p / 10 + 20))
                  - fc.continuous_settlements(_t(p / 10), _t(p / 10 + 20))
                  for p in range(80)]
        assert sum(deltas) / len(deltas) == pytest.approx(0.0, abs=1e-9)
        assert max(deltas) - min(deltas) == pytest.approx(1.0)  # ...and it is off by a FULL unit
        assert all(d != 0 for d in deltas)                      # ...on EVERY trade


class TestRefusalPath:
    """Unmeasured must never read as fine (L1.28a) -- the clock refuses, it does not guess."""

    def test_unknown_symbol_interval_refuses_rather_than_defaulting_to_8h(self) -> None:
        assert fc.interval_hours("NEWCOINUSDT") is None
        assert fc.interval_hours("NEWCOINUSDT", {}) is None
        assert fc.interval_hours("NEWCOINUSDT", {"BTCUSDT": 8.0}) is None

    def test_known_symbol_returns_the_venue_value(self) -> None:
        assert fc.interval_hours("HIGHFUNDUSDT", {"HIGHFUNDUSDT": 4.0}) == 4.0

    def test_zero_or_negative_interval_raises_not_silently_divides(self) -> None:
        for bad in (0.0, -8.0):
            with pytest.raises(ValueError):
                fc.settlements_in(_t(0), _t(24), interval_h=bad)
            with pytest.raises(ValueError):
                fc.periods_per_year(bad)
            with pytest.raises(ValueError):
                fc.last_settlement(_t(0), interval_h=bad)


class TestPeriodsPerYear:
    def test_default_matches_the_constant_it_replaces(self) -> None:
        # The `3 * 365` restated at 8 sites across the repo.
        assert fc.PERIODS_PER_YEAR == 3 * 365
        assert fc.periods_per_year() == 3 * 365

    def test_four_hour_symbol_has_double_the_prints(self) -> None:
        assert fc.periods_per_year(4.0) == 6 * 365
