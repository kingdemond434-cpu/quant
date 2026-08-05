"""The Type-II cost instrument must tell 'could not have seen it' apart from 'it is not there'.

THE HAND-COMPUTED CASE THIS FILE PINS (restated from libs/validation/type2_cost.py's docstring so
a reader of either file can check the other without running anything):

    T = 2018 daily bars, PPY = 365      -> years   = 2018 / 365      = 5.5287671...
    N = 196 candidates, alpha = 0.05    -> z_crit  = Phi^-1(1 - 0.05/196)
                                                   = Phi^-1(0.9997448979...) = 3.4753414...
    min detectable ann. Sharpe (50% power) = 3.4753414 / sqrt(5.5287671)
                                           = 3.4753414 / 2.3513331 = 1.4780300
    power at a TRUE ann. Sharpe of 1.0     = Phi(1.0 * 2.3513331 - 3.4753414)
                                           = Phi(-1.1240083) = 0.1305048
    P(reject | true SR = 1.0)              = 1 - 0.1305048 = 0.8694952

Every one of those five numbers is asserted below to 1e-6, and the 1.478 is independently
corroborated: reports/reality_check_audit.json, computed by a different author in a different
script, records exactly {196: 1.478, 50: 1.314, 20: 1.194, 5: 0.989, 1: 0.700}. A closed form that
reproduces an artifact it did not write is a closed form describing the desk's gate rather than a
model of it, which is the whole reason to prefer arithmetic over a fresh Monte Carlo here.
"""

from __future__ import annotations

import json
import math
from itertools import pairwise

import numpy as np
import pytest

from libs.validation.type2_cost import (
    DEFAULT_ALPHA,
    INDETERMINATE,
    POWERED,
    PPY,
    UNDERPOWERED,
    autocorr_deflator,
    correlation_n_eff,
    correlation_negative,
    correlation_power,
    critical_z,
    effective_years,
    headline,
    indeterminate,
    min_detectable_correlation,
    min_detectable_sharpe,
    pooling_multiplier,
    sharpe_negative,
    sharpe_power,
)

_T = 2018.0
_YEARS = _T / PPY


# ------------------------------------------------------------------------ the hand-computed case


def test_hand_computed_case() -> None:
    """Every number in this module's docstring, to 1e-6."""
    assert pytest.approx(5.5287671232, abs=1e-9) == _YEARS
    assert math.sqrt(_YEARS) == pytest.approx(2.3513330524, abs=1e-9)

    z = critical_z(0.05, 196)
    assert z == pytest.approx(3.4753414, abs=1e-6)

    mde = min_detectable_sharpe(years=_YEARS, n_tests=196)
    assert mde == pytest.approx(1.4780300, abs=1e-6)

    power = sharpe_power(1.0, years=_YEARS, n_tests=196)
    assert power == pytest.approx(0.1305048, abs=1e-6)

    cost = sharpe_negative("hand-computed", n_bars=_T, n_tests=196)
    assert cost.min_detectable_effect == pytest.approx(1.4780300, abs=1e-6)
    assert cost.power_at_reference == pytest.approx(0.1305048, abs=1e-6)
    assert dict(cost.p_reject_given_true)[1.0] == pytest.approx(0.8694952, abs=1e-6)


def test_reproduces_the_desks_recorded_closed_form_table() -> None:
    """reports/reality_check_audit.json, written by another script, must be reproduced exactly."""
    recorded = {196: 1.478, 50: 1.314, 20: 1.194, 5: 0.989, 1: 0.700}
    for n, expected in recorded.items():
        assert round(min_detectable_sharpe(years=_YEARS, n_tests=n), 3) == expected


def test_reproduces_the_recorded_pooled_floor() -> None:
    """m=10 symbols at rho=0.348, N=20 mechanisms -> 0.767, the artifact's pooled floor."""
    assert pooling_multiplier(10, 0.348) == pytest.approx(2.4201355, abs=1e-6)
    years = effective_years(_T, n_units=10, cross_corr=0.348)
    assert round(min_detectable_sharpe(years=years, n_tests=20), 3) == 0.767


def test_reproduces_axis_screens_min_detectable_ic() -> None:
    """axis_screen uses 1.96/sqrt(n_eff); the two instruments must never disagree about power."""
    assert min_detectable_correlation(n_eff=4294.0) == pytest.approx(1.96 / math.sqrt(4294.0),
                                                                     rel=1e-3)
    # The recorded value from reports/axis_screens/liquidation_reversion_BTCUSDT.json.
    assert round(min_detectable_correlation(n_eff=4294.0), 4) == 0.0299
    # ...and its n_eff, including the bound at the rows actually observed (horizon < 1 period).
    assert correlation_n_eff(4294.0, horizon_periods=0.003472222222222222) == 4294.0


# --------------------------------------------------------- the two labels the module exists for


def test_underpowered_sample_is_not_a_merit_rejection() -> None:
    """Sixty daily bars cannot resolve a Sharpe-1.0 edge, so its null must not read as knowledge."""
    cost = sharpe_negative("sixty-bar screen", n_bars=60.0)
    assert cost.label == UNDERPOWERED
    assert cost.label != POWERED
    assert not cost.powered
    assert cost.min_detectable_effect > cost.reference_effect
    assert cost.power_at_reference < cost.power_target
    # The Type-II cost is the point: a real Sharpe-1.0 edge is thrown away almost every time.
    # 60 daily bars is 0.164 years, a detection floor of 4.06 annualised Sharpe, and a ~89%
    # chance of discarding a genuine Sharpe-1.0 edge.
    assert cost.min_detectable_effect == pytest.approx(4.0569, abs=1e-3)
    assert dict(cost.p_reject_given_true)[1.0] > 0.85


def test_well_powered_null_is_a_powered_negative() -> None:
    """Thirty years of daily bars at N=1 CAN resolve the reference effect, so its null informs."""
    cost = sharpe_negative("thirty-year screen", n_bars=30 * PPY)
    assert cost.label == POWERED
    assert cost.powered
    assert cost.min_detectable_effect < cost.reference_effect
    assert cost.power_at_reference > 0.99


def test_label_and_minimum_detectable_effect_never_disagree() -> None:
    """POWERED iff the reference effect is at or above the floor -- one fact, two views."""
    for bars in (30.0, 200.0, 800.0, 2018.0, 6000.0, 20000.0):
        for n_tests in (1, 20, 196, 920):
            cost = sharpe_negative("x", n_bars=bars, n_tests=n_tests)
            assert (cost.label == POWERED) == (
                cost.min_detectable_effect <= cost.reference_effect + 1e-12
            )


def test_indeterminate_is_never_powered_and_never_merit() -> None:
    cost = indeterminate("a graveyard row", "no sample size recorded")
    assert cost.label == INDETERMINATE
    assert not cost.powered
    assert math.isnan(cost.min_detectable_effect)
    assert cost.power_curve == ()


def test_a_rejection_with_no_recorded_sample_falls_to_indeterminate() -> None:
    """An artifact recording zero bars must not silently produce an infinite detection floor."""
    assert sharpe_negative("no bars", n_bars=0.0).label == INDETERMINATE
    assert correlation_negative("two points", n_obs=2.0).label == INDETERMINATE


# ---------------------------------------------------------------------------------- monotonicity


@pytest.mark.parametrize("n_tests", [1, 20, 920])
def test_power_is_monotone_increasing_in_sample_length(n_tests: int) -> None:
    powers = [sharpe_power(1.0, years=y, n_tests=n_tests) for y in (0.5, 1, 2, 4, 8, 16, 32)]
    assert all(b >= a for a, b in pairwise(powers))
    assert powers[-1] > powers[0]


@pytest.mark.parametrize("years", [0.5, 5.5287671232, 30.0])
def test_power_is_monotone_increasing_in_effect_size(years: float) -> None:
    powers = [sharpe_power(sr, years=years) for sr in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0)]
    assert all(b >= a for a, b in pairwise(powers))
    assert powers[-1] > powers[0]


def test_correlation_power_is_monotone_in_n_and_in_effect() -> None:
    by_n = [correlation_power(0.05, n_eff=n) for n in (10, 50, 200, 1000, 5000, 20000)]
    assert all(b >= a for a, b in pairwise(by_n))
    by_e = [correlation_power(e, n_eff=2000) for e in (0.0, 0.01, 0.03, 0.05, 0.1, 0.3)]
    assert all(b >= a for a, b in pairwise(by_e))


def test_minimum_detectable_effect_is_monotone_decreasing_in_sample() -> None:
    mdes = [min_detectable_sharpe(years=y) for y in (0.5, 1, 4, 16, 64)]
    assert all(b <= a for a, b in pairwise(mdes))


def test_power_at_zero_effect_is_the_size_of_the_test() -> None:
    """The sanity check that this is a power function: at SR=0 it returns alpha/N, not something."""
    assert sharpe_power(0.0, years=_YEARS, n_tests=1) == pytest.approx(0.05, abs=1e-9)
    assert sharpe_power(0.0, years=_YEARS, n_tests=20) == pytest.approx(0.05 / 20, abs=1e-9)


def test_multiplicity_can_only_cost_power_never_buy_it() -> None:
    powers = [sharpe_power(1.5, years=_YEARS, n_tests=n) for n in (1, 5, 20, 196, 920)]
    assert all(b <= a for a, b in pairwise(powers))


# -------------------------------------------------------------------------- effective sample size


def test_bar_count_is_not_evidence() -> None:
    """The same 61 elapsed days at 5m, 15m and 1h must carry the SAME power. This is the whole rule.

    docs/research/REALITY_CHECK_POWER.md: t = SR_ann * sqrt(YEARS), so resampling multiplies both
    T and PPY and changes nothing. A power instrument that let a caller buy power by switching to
    finer bars would certify the desk's intraday NO-GOs as informative when they are 61 days long.
    """
    five_min = effective_years(17568.0, ppy=PPY * 24 * 12)
    fifteen_min = effective_years(5856.0, ppy=PPY * 24 * 4)
    hourly = effective_years(1464.0, ppy=PPY * 24)
    assert five_min == pytest.approx(fifteen_min, rel=1e-12)
    assert five_min == pytest.approx(hourly, rel=1e-12)
    assert five_min == pytest.approx(61.0 / 365.0, rel=1e-9)
    assert (
        sharpe_power(1.0, years=five_min) == sharpe_power(1.0, years=hourly)
    )


def test_pooling_multiplier_is_clamped_to_the_units_that_exist() -> None:
    """Never more evidence than units collected, never less than one (via effective_bets)."""
    assert pooling_multiplier(1, 0.0) == 1.0
    assert pooling_multiplier(21, 1.0) == pytest.approx(1.0)
    assert pooling_multiplier(21, -0.9) <= 21.0
    assert 1.0 <= pooling_multiplier(21, 0.348) <= 21.0


def test_effective_years_never_exceeds_observation_time_collected() -> None:
    for units in (1, 5, 21, 139):
        for rho in (-0.5, 0.0, 0.05, 0.348, 0.9):
            y = effective_years(2018.0, n_units=units, cross_corr=rho)
            assert y <= (2018.0 / PPY) * units + 1e-9


def test_autocorrelation_can_only_shrink_the_effective_sample() -> None:
    rng = np.random.default_rng(0)
    white = rng.normal(size=1000)
    # An AR(1) with positive rho: each step keeps 80% of the last, so the effective sample shrinks.
    ar = np.zeros(1000)
    for i in range(1, 1000):
        ar[i] = 0.8 * ar[i - 1] + rng.normal()
    assert autocorr_deflator(white) >= 1.0
    assert autocorr_deflator(ar) > autocorr_deflator(white)
    assert effective_years(1000.0, deflator=autocorr_deflator(ar)) < effective_years(1000.0)


def test_correlation_n_eff_never_exceeds_rows_observed() -> None:
    """The axis_screen defect: at horizon < 1 the overlap deflator inverts into a multiplier."""
    assert correlation_n_eff(4314.0, horizon_periods=6.9e-4) == 4314.0
    assert correlation_n_eff(1000.0, horizon_periods=20.0) == pytest.approx(50.0)
    assert correlation_n_eff(1000.0, panel_width=139) == pytest.approx(1000.0 / 139.0)


# ------------------------------------------------------------------------------ the desk headline


def test_headline_counts_indeterminate_in_the_denominator() -> None:
    """Dropping unlabellable rejections would answer a strictly more flattering question."""
    rows = [
        sharpe_negative("powered", n_bars=30 * PPY),
        sharpe_negative("blind", n_bars=60.0),
        indeterminate("no sample", "the row records no sample size"),
    ]
    h = headline(rows)
    assert (h.n_negatives, h.n_powered, h.n_underpowered, h.n_indeterminate) == (3, 1, 1, 1)
    assert h.fraction_powered == pytest.approx(1 / 3)
    assert "MOST RECORDED NEGATIVES CARRY NO INFORMATION" in h.verdict


def test_headline_of_nothing_is_not_a_finding() -> None:
    h = headline([])
    assert h.n_negatives == 0
    assert math.isnan(h.fraction_powered)
    assert "NO RECORDED NEGATIVES" in h.verdict


# ---------------------------------------------------------------------------------- publishability


def test_alpha_is_five_percent_and_this_module_does_not_move_it() -> None:
    assert DEFAULT_ALPHA == 0.05
    assert sharpe_negative("x", n_bars=_T).alpha == 0.05
    assert correlation_negative("x", n_obs=1000.0).alpha == 0.05


def test_as_dict_is_strict_json_even_for_indeterminate_rows() -> None:
    """inf/nan must become null: json.dump writes bare NaN, which strict readers reject."""
    for cost in (
        sharpe_negative("a", n_bars=_T, n_tests=196),
        correlation_negative("b", n_obs=1000.0),
        indeterminate("c", "no sample size recorded"),
    ):
        text = json.dumps(cost.as_dict(), allow_nan=False)
        assert "NaN" not in text and "Infinity" not in text
        assert json.loads(text)["label"] in {POWERED, UNDERPOWERED, INDETERMINATE}


def test_summary_states_which_of_the_two_things_a_rejection_is() -> None:
    blind = sharpe_negative("blind", n_bars=60.0).summary()
    seen = sharpe_negative("seen", n_bars=30 * PPY).summary()
    assert UNDERPOWERED in blind and "ABOVE" in blind
    assert POWERED in seen and "INSIDE" in seen
