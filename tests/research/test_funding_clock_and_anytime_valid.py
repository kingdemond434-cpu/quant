"""THE FUNDING CLOCK AND THE ANYTIME-VALID GATE -- 75 statements, zero tests until now.

Two small modules that each replace a shortcut the desk was measurably paying for.

FUNDING_CLOCK replaces `held / 8.0`. That incumbent books the EXPECTATION of the settlement count
rather than the count: unbiased over many trades (measured mean delta -0.012 settlements over 254
closes) and therefore invisible to review, but wrong per-trade with sd 0.491, with 43.3% of closes
mis-marked by half a settlement or more. An error that averages out is the hardest kind to notice
and it still mis-prices every individual trade, so the discrete count and the continuous accrual
both live here and are asserted to DIFFER in exactly that way -- a test that only checked they
agree would have no idea which one was being used.

ANYTIME_VALID replaces the fixed clock. Its whole value is that it can be peeked at every day on a
growing series without inflating the false-positive rate, which is the one property a p-value does
not have. The tests therefore check the property, not the arithmetic: repeated looks at pure noise
must not graduate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from libs.research import anytime_valid as AV
from libs.research import funding_clock as FC

# =========================================================================== funding_clock


def _t(h: float, *, day: int = 15) -> datetime:
    return datetime(2026, 8, day, tzinfo=UTC) + timedelta(hours=h)


def test_settlements_are_anchored_to_the_UTC_DAY_not_to_an_epoch_offset() -> None:
    """Binance defines them from 00:00 UTC. An epoch anchor lands on 04/12/20 instead and every
    phase coordinate is wrong by four hours -- silently, and identically, everywhere."""
    for h in (0, 3, 7.99):
        assert FC.last_settlement(_t(h)).hour == 0
    for h in (8, 11, 15.99):
        assert FC.last_settlement(_t(h)).hour == 8
    for h in (16, 23.99):
        assert FC.last_settlement(_t(h)).hour == 16


def test_a_stamp_is_its_own_last_settlement() -> None:
    assert FC.last_settlement(_t(8)) == _t(8)


def test_the_next_settlement_is_STRICTLY_after() -> None:
    """A position closed exactly ON a stamp has already been paid, so the next payment it could
    earn is one full interval away. Inclusive here would pay the same settlement twice."""
    assert FC.next_settlement(_t(8)) == _t(16)
    assert FC.next_settlement(_t(7.9)) == _t(8)


def test_phase_and_time_to_settlement_are_complementary() -> None:
    for h in (0.0, 1.5, 7.99, 8.0, 13.25):
        t = _t(h)
        assert FC.phase_hours(t) + FC.hours_to_settlement(t) == pytest.approx(8.0)


def test_phase_is_in_0_to_interval_and_forfeit_is_in_0_exclusive_to_interval() -> None:
    """The two coordinates are half-open at OPPOSITE ends, and that is not cosmetic: a close
    exactly on a stamp has phase 0 (just paid) and forfeit 8 (a full interval to the next), never
    phase 8 or forfeit 0."""
    on_stamp = _t(8)
    assert FC.phase_hours(on_stamp) == 0.0
    assert FC.hours_to_settlement(on_stamp) == 8.0
    for h in (0.1, 3.0, 7.9):
        assert 0.0 <= FC.phase_hours(_t(h)) < 8.0
        assert 0.0 < FC.hours_to_settlement(_t(h)) <= 8.0


def test_a_naive_datetime_is_read_as_UTC_rather_than_local_time() -> None:
    """A naive stamp interpreted in the box's local zone is the KST/UTC class of bug that produced
    an IC of 0.72 on this desk."""
    naive = datetime(2026, 8, 15, 9, 0)
    assert FC.last_settlement(naive) == _t(8)


def test_a_non_utc_timezone_is_converted_not_stripped() -> None:
    tokyo = datetime(2026, 8, 15, 18, 0, tzinfo=UTC).astimezone(
        __import__("datetime").timezone(timedelta(hours=9)))
    assert FC.last_settlement(tokyo) == _t(16)


def test_the_settlement_count_is_the_half_open_window_a_position_is_actually_paid_for() -> None:
    """(t0, t1]: the settlement at the open is NOT earned, the settlement at the close IS."""
    assert FC.settlements_in(_t(8), _t(16)) == 1
    assert FC.settlements_in(_t(8.01), _t(16)) == 1
    assert FC.settlements_in(_t(8), _t(15.99)) == 0
    assert FC.settlements_in(_t(0), _t(16)) == 2


def test_a_closed_or_reversed_window_pays_nothing() -> None:
    assert FC.settlements_in(_t(8), _t(8)) == 0
    assert FC.settlements_in(_t(16), _t(8)) == 0


def test_the_discrete_count_and_the_continuous_accrual_DISAGREE_per_trade() -> None:
    """THE POINT OF THE MODULE. `held/8` is unbiased across many trades and wrong on each one. A
    test that asserted they agree would be satisfied by the desk still using the incumbent."""
    open_t = _t(7.9)
    close_t = _t(8.1)
    assert FC.settlements_in(open_t, close_t) == 1, "it crossed a stamp -- one payment is owed"
    assert FC.continuous_settlements(open_t, close_t) == pytest.approx(0.2 / 8.0)


def test_the_two_models_converge_over_long_holds() -> None:
    """Which is exactly why the error was invisible to review: it averages out."""
    t0 = _t(0, day=1)
    t1 = _t(0, day=1) + timedelta(days=200)
    disc = FC.settlements_in(t0, t1)
    cont = FC.continuous_settlements(t0, t1)
    assert abs(disc - cont) / cont < 0.01


def test_continuous_accrual_is_never_negative() -> None:
    assert FC.continuous_settlements(_t(16), _t(8)) == 0.0


def test_periods_per_year_single_sources_the_restated_literal() -> None:
    assert FC.PERIODS_PER_YEAR == 1095.0
    assert FC.periods_per_year() == FC.PERIODS_PER_YEAR
    assert FC.periods_per_year(4.0) == 2190.0, "a 4h symbol pays twice as often"


@pytest.mark.parametrize("fn", [FC.periods_per_year, FC.last_settlement, FC.settlements_in])
def test_a_non_positive_interval_raises_rather_than_dividing_by_zero(fn) -> None:
    args = {FC.periods_per_year: (0.0,), FC.last_settlement: (_t(1), 0.0),
            FC.settlements_in: (_t(1), _t(2), 0.0)}[fn]
    with pytest.raises(ValueError, match="must be positive"):
        fn(*args)


def test_a_four_hour_symbol_settles_six_times_a_day() -> None:
    assert [FC.last_settlement(_t(h), 4.0).hour for h in (0, 5, 9, 13, 17, 21)] == \
        [0, 4, 8, 12, 16, 20]
    assert FC.settlements_in(_t(0), _t(24), 4.0) == 6


def test_the_interval_REFUSES_rather_than_defaulting_for_an_unknown_symbol() -> None:
    """Binance publishes fundingIntervalHours per symbol and it is 4h for many high-funding alts.
    Assuming 8h for an unknown symbol is the exact 2x UNDER-COUNT this module exists to surface,
    so a caller that wants the default must ask for it and own that choice."""
    assert FC.interval_hours("WHOKNOWSUSDT") is None
    assert FC.interval_hours("WHOKNOWSUSDT", {}) is None
    assert FC.interval_hours("BTCUSDT", {"BTCUSDT": 8.0}) == 8.0
    assert FC.interval_hours("HIGHFUNDUSDT", {"HIGHFUNDUSDT": 4.0}) == 4.0


def test_a_zero_interval_from_the_venue_is_treated_as_unknown() -> None:
    """0.0 is not an interval. Passing it through would divide by zero downstream in a module
    whose entire purpose is to be the one place that cannot."""
    assert FC.interval_hours("X", {"X": 0.0}) is None


# =========================================================================== anytime_valid

def _rets(n: int, mean: float, sd: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, sd, n)


def test_a_real_edge_graduates() -> None:
    """The positive control. A gate that never graduates anything is indistinguishable from a
    broken gate, and 'nothing survived' from it would mean nothing."""
    out = AV.graduates(_rets(400, 0.004, 0.01, 1))
    assert out["graduates"] is True
    assert out["e_value"] >= out["threshold"]


def test_pure_noise_does_NOT_graduate() -> None:
    assert AV.graduates(_rets(400, 0.0, 0.01, 2))["graduates"] is False


def test_a_LOSING_series_does_not_graduate() -> None:
    assert AV.graduates(_rets(400, -0.003, 0.01, 3))["graduates"] is False


def test_PEEKING_EVERY_DAY_AT_NOISE_does_not_manufacture_a_graduation() -> None:
    """THE WHOLE REASON THIS MODULE EXISTS. A p-value tested daily on a growing series crosses 0.05
    eventually with probability 1. An e-process may be peeked at without inflating the error rate,
    and that property -- not the arithmetic -- is what is asserted here."""
    false_positives = 0
    trials = 12
    for seed in range(trials):
        r = _rets(300, 0.0, 0.01, 100 + seed)
        if any(AV.e_value(r[:t]) >= 1.0 / 0.01 for t in range(AV._MIN_OBS, len(r) + 1, 5)):
            false_positives += 1
    assert false_positives <= 1, (
        f"{false_positives}/{trials} noise series graduated under daily peeking -- the "
        "anytime-validity guarantee is not holding")


def test_too_few_observations_returns_ZERO_evidence_rather_than_a_lucky_number() -> None:
    """Below _MIN_OBS the scale estimate is untrustworthy, and an e-value computed from an
    untrustworthy scale is a number that looks like evidence."""
    assert AV.e_value(_rets(AV._MIN_OBS - 1, 0.01, 0.01, 4)) == 0.0
    assert AV.graduates(_rets(5, 0.05, 0.01, 5))["graduates"] is False


def test_a_CONSTANT_series_yields_no_evidence_rather_than_INFINITE_evidence() -> None:
    """FOUND BY THIS TEST, and it was a promotion path for a dead feed.

    `np.full(200, 0.01).std(ddof=1)` is 1.74e-18, not 0.0 -- the variance is a difference of
    squares and does not cancel exactly -- so an `s <= 0.0` guard passed it straight through. z
    reached 5.75e15 and the e-value came back INFINITE: a series that never moved, certified as
    overwhelming evidence of an edge. A constant return series is exactly what a stuck recorder
    echoing its last value produces, which `data_registry` already scores as a live failure mode.
    """
    assert AV.e_value(np.full(200, 0.01)) == 0.0
    assert AV.graduates(np.full(200, 0.01))["graduates"] is False
    assert AV.e_value(np.zeros(200)) == 0.0


def test_an_overwhelming_edge_returns_a_FINITE_value_rather_than_overflowing() -> None:
    """ALSO FOUND HERE. At 600 observations of a real edge the log-capital exceeds 709 and
    `np.exp` overflows to inf with a RuntimeWarning -- and this repo runs `filterwarnings = error`,
    so the gate RAISED on precisely the candidates it should have passed most confidently."""
    monster = _rets(800, 0.02, 0.005, 12)
    e = AV.e_value(monster)
    assert np.isfinite(e) and e > 1.0 / 0.01
    assert AV.graduates(monster)["graduates"] is True


def test_non_finite_observations_are_dropped_rather_than_poisoning_the_product() -> None:
    """One NaN in a running product makes every subsequent value NaN, and NaN >= threshold is
    False -- so the failure would be silent and permanent."""
    r = _rets(400, 0.004, 0.01, 6)
    r[7] = np.nan
    r[19] = np.inf
    assert AV.e_value(r) > 0.0


def test_the_threshold_is_stricter_than_a_conventional_p_value() -> None:
    """alpha=0.01 rather than 0.05 because this gate can be peeked at daily and the desk's whole
    failure mode is promoting noise."""
    out = AV.graduates(_rets(100, 0.0, 0.01, 7))
    assert out["alpha"] == 0.01 and out["threshold"] == 100.0


def test_evidence_accumulates_monotonically_in_expectation_on_a_real_edge() -> None:
    r = _rets(600, 0.004, 0.01, 8)
    assert AV.e_value(r[:500]) > AV.e_value(r[:100])


def test_days_to_graduation_reports_the_calendar_a_fixed_clock_would_have_wasted() -> None:
    r = _rets(600, 0.005, 0.01, 9)
    t = AV.days_to_graduation(r)
    assert t is not None and AV._MIN_OBS <= t <= len(r)
    assert AV.e_value(r[:t]) >= 100.0
    assert AV.e_value(r[:t - 1]) < 100.0, "it must be the FIRST crossing, not any later one"


def test_days_to_graduation_is_None_when_it_never_crosses() -> None:
    assert AV.days_to_graduation(_rets(300, 0.0, 0.01, 10)) is None


def test_the_verdict_carries_its_own_sample_size() -> None:
    """An e-value with no n attached cannot be argued with -- 4.0 on 25 observations and 4.0 on
    2,500 are different statements about the world."""
    out = AV.graduates(_rets(123, 0.001, 0.01, 11))
    assert out["n"] == 123
