"""What the ulcer index sees that max drawdown cannot, and the sign convention that matters.

The test that carries the module is test_ulcer_separates_a_long_shallow_trough_from_a_brief_deep_one
-- if that ever stops holding, the ulcer index has collapsed into an expensive way to recompute
max drawdown and the whole reason for the module is gone.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.drawdown_metrics import (
    MARTIN_TARGET_RETURN_OVER_DD,
    drawdown_series,
    martin_ratio,
    report,
    return_over_max_drawdown,
    ulcer_index,
)


def _from_equity(path: list[float]) -> np.ndarray:
    """Log returns that reproduce a given equity path exactly."""
    e = np.array(path, dtype="float64")
    return np.diff(np.log(e))


# --------------------------------------------------------------------------- drawdown series

def test_drawdown_is_measured_from_the_running_peak():
    r = _from_equity([100, 120, 90, 150])
    dd = drawdown_series(r)
    assert dd[0] == pytest.approx(0.0)            # new high
    assert dd[1] == pytest.approx(1 - 90 / 120)   # 25% off the 120 peak, not off 100
    assert dd[2] == pytest.approx(0.0)            # new high again


def test_a_monotonically_rising_equity_never_draws_down():
    assert np.allclose(drawdown_series(_from_equity([100, 110, 120, 130])), 0.0)


def test_drawdown_is_bounded_in_zero_one():
    rng = np.random.default_rng(1)
    dd = drawdown_series(rng.normal(0, 0.03, 3000))
    assert dd.min() >= -1e-12 and dd.max() < 1.0


def test_log_returns_compose_so_deep_drawdowns_are_not_understated():
    """Summing SIMPLE returns overstates compounding and would make a 50% drawdown look shallower
    than it is. The equity path is reconstructed by exponentiating the cumulative LOG sum, so the
    reported drawdown is the one the account actually experienced."""
    r = _from_equity([100, 50])
    assert drawdown_series(r)[0] == pytest.approx(0.5)


# ------------------------------------------------------- what ulcer sees that max drawdown cannot

def test_ulcer_separates_a_long_shallow_trough_from_a_brief_deep_one():
    """THE POINT OF THE MODULE. Both paths recover to the same place. The brief-deep one has the
    larger MAX drawdown; the long-shallow one spends far longer underwater. Max drawdown ranks
    them one way and the ulcer index ranks them the other, and the trader who has to sit through
    them agrees with the ulcer index."""
    brief_deep = _from_equity([100, 60, 100] + [100] * 40)
    long_shallow = _from_equity([100] + [92] * 40 + [100])

    assert max(drawdown_series(brief_deep)) > max(drawdown_series(long_shallow)), (
        "the fixture must actually have a deeper max drawdown on the brief path")
    assert ulcer_index(long_shallow) > ulcer_index(brief_deep), (
        "the ulcer index has stopped pricing duration and is just tracking max drawdown")


def test_ulcer_is_zero_when_there_is_no_drawdown():
    assert ulcer_index(_from_equity([100, 110, 120])) == pytest.approx(0.0)


def test_ulcer_is_the_rms_of_the_drawdown_series():
    r = _from_equity([100, 90, 95, 100])
    assert ulcer_index(r) == pytest.approx(float(np.sqrt(np.mean(drawdown_series(r) ** 2))))


# --------------------------------------------------------------------------------- martin ratio

def test_a_losing_series_gets_a_NEGATIVE_martin_ratio():
    """THE SIGN CONVENTION, and a deliberate departure from the source. neurotrader's version
    negates the ratio for losing series so a pattern search can pick the best SHORT from the
    minimum. That is right for a search and wrong for a statistic: it makes a bad strategy and a
    good short-side strategy report the same number. Here a loser reads as a loser."""
    assert martin_ratio(_from_equity([100, 90, 80, 70])) < 0


def test_a_winning_series_gets_a_positive_martin_ratio():
    assert martin_ratio(_from_equity([100, 90, 120, 115, 140])) > 0


def test_a_drawdown_free_series_is_undefined_rather_than_infinite():
    """Zero ulcer means the window was too short to contain a loss, not that the strategy cannot
    lose. Reporting infinite risk-adjusted return would be the most flattering possible reading of
    the least informative possible sample."""
    assert np.isnan(martin_ratio(_from_equity([100, 110, 120, 130])))
    assert np.isnan(return_over_max_drawdown(_from_equity([100, 110, 120])))


def test_too_short_a_series_is_undefined():
    assert np.isnan(martin_ratio(np.array([0.01])))


def test_martin_ranks_the_smoother_path_higher_at_equal_total_return():
    """Both paths end in exactly the same place, so their total log return is identical. The one
    that got there with the shallower trough must rank higher, or the statistic is not
    risk-adjusting anything.

    The smooth path carries a SMALL dip on purpose. A path with no drawdown at all has an ulcer
    index of zero and a correctly UNDEFINED Martin ratio, which is the module behaving as
    documented -- it just cannot be compared against anything, so it makes a useless fixture."""
    smooth = _from_equity([100, 105, 103, 115, 120])
    rough = _from_equity([100, 70, 85, 95, 120])
    assert np.sum(smooth) == pytest.approx(np.sum(rough))
    assert np.isfinite(martin_ratio(smooth)), "the smooth fixture must still have a drawdown"
    assert martin_ratio(smooth) > martin_ratio(rough)


# ------------------------------------------------------------------------------- the report

def test_the_report_names_the_statistic_the_target_belongs_to():
    """Davey's 2.0 was set against return-over-MAX-drawdown. Comparing it to the Martin ratio
    instead would silently change what the threshold means, so the report evaluates it against
    the statistic it was written for."""
    rep = report(_from_equity([100, 80, 130, 120, 160]))
    assert rep["clears_davey_target"] == (
        rep["return_over_max_drawdown"] >= MARTIN_TARGET_RETURN_OVER_DD)


def test_the_report_counts_the_time_spent_underwater():
    """The quantity a trader actually experiences and the one max drawdown is silent about."""
    rep = report(_from_equity([100] + [90] * 12 + [130]))
    assert rep["longest_underwater_bars"] >= 12


def test_an_empty_series_does_not_raise():
    rep = report(np.array([]))
    assert rep["n_bars"] == 0 and rep["clears_davey_target"] is None
