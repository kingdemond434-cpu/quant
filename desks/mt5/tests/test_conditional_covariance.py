"""Crisis severity must be measured from the book, and may only ever ratchet upward.

`crisis_common_share` IS the pairwise correlation the crisis worlds impose -- a one-factor
overlay in which each sleeve is sqrt(s)*common + sqrt(1-s)*idio has pairwise correlation exactly
s. It was the constant 0.55, with nothing behind it, governing how bad the desk believes a crisis
gets. These pin that the measurement recovers a known correlation, and that a quiet sample can
never talk the desk into a gentler crisis than it was already assuming.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio.conditional_covariance import (  # noqa: E402
    MIN_POOL_DAYS,
    by_regime,
    calibrate,
)
from libs.portfolio.robust_elog import WorldConfig  # noqa: E402

STANDING = WorldConfig()


def _one_factor(n_days: int, n_sleeves: int, share: float, scale: float = 1.0,
                seed: int = 0) -> np.ndarray:
    """A matrix whose true pairwise correlation is exactly `share`."""
    rng = np.random.default_rng(seed)
    common = rng.standard_normal(n_days)[:, None]
    idio = rng.standard_normal((n_days, n_sleeves))
    return scale * (np.sqrt(share) * common + np.sqrt(1.0 - share) * idio)


def test_the_measurement_recovers_a_known_pairwise_correlation():
    hist = _one_factor(4000, 8, share=0.70)
    cov = by_regime(hist, ["calm"] * 4000)["calm"]
    assert cov.mean_corr == pytest.approx(0.70, abs=0.05)


def test_a_stressed_regime_is_found_by_volatility_not_by_its_name():
    """Labels come from a classifier whose vocabulary changes; volatility is the real quantity."""
    calm = _one_factor(1200, 6, share=0.10, scale=1.0, seed=1)
    hot = _one_factor(600, 6, share=0.75, scale=3.0, seed=2)
    hist = np.vstack([calm, hot])
    labels = ["placid_sounding_name"] * 1200 + ["also_innocuous"] * 600
    cal = calibrate(hist, labels, standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert cal.stress_regime == "also_innocuous"
    assert cal.by_regime["also_innocuous"].mean_corr > 0.6
    assert cal.by_regime["placid_sounding_name"].mean_corr < 0.3


def test_a_measured_crisis_worse_than_the_constant_raises_it():
    calm = _one_factor(1000, 6, share=0.10, scale=1.0, seed=3)
    hot = _one_factor(800, 6, share=0.85, scale=4.0, seed=4)
    cal = calibrate(np.vstack([calm, hot]), ["calm"] * 1000 + ["hot"] * 800,
                    standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert cal.crisis_common_share > STANDING.crisis_common_share
    assert cal.crisis_vol_mult > STANDING.crisis_vol_mult


def test_a_quiet_sample_can_never_soften_the_crisis():
    """The ratchet. This is the property that keeps a calm decade from relaxing the risk model."""
    quiet = _one_factor(3000, 6, share=0.02, scale=0.5, seed=5)
    cal = calibrate(quiet, ["boring"] * 3000,
                    standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert cal.crisis_common_share == pytest.approx(STANDING.crisis_common_share)
    assert cal.crisis_vol_mult == pytest.approx(STANDING.crisis_vol_mult)


def test_a_thin_pool_is_not_measured_at_all():
    hist = _one_factor(4000, 6, share=0.9, seed=6)
    labels = ["big"] * (4000 - 5) + ["tiny"] * 5
    per = by_regime(hist, labels)
    assert "tiny" not in per
    assert per["big"].n_days == 4000 - 5


def test_thin_evidence_shrinks_toward_the_standing_constant():
    """A short stress pool moves the assumption a little, a long one moves it a lot."""
    calm = _one_factor(2000, 6, share=0.05, scale=1.0, seed=7)
    short_hot = _one_factor(25, 6, share=0.95, scale=5.0, seed=8)
    long_hot = _one_factor(900, 6, share=0.95, scale=5.0, seed=9)
    short = calibrate(np.vstack([calm, short_hot]), ["c"] * 2000 + ["h"] * 25,
                      standing_share=STANDING.crisis_common_share,
                      standing_vol_mult=STANDING.crisis_vol_mult)
    long = calibrate(np.vstack([calm, long_hot]), ["c"] * 2000 + ["h"] * 900,
                     standing_share=STANDING.crisis_common_share,
                     standing_vol_mult=STANDING.crisis_vol_mult)
    assert STANDING.crisis_common_share <= short.crisis_common_share < long.crisis_common_share


def test_no_labels_keeps_the_constants_and_says_so():
    cal = calibrate(_one_factor(500, 5, share=0.5), None,
                    standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert cal.crisis_common_share == STANDING.crisis_common_share
    assert "standing constants kept" in cal.note


def test_a_matrix_too_small_to_measure_refuses():
    cal = calibrate(np.zeros((MIN_POOL_DAYS - 1, 4)), None,
                    standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    assert "too small" in cal.note


def test_dead_sleeves_do_not_poison_the_correlation():
    hist = _one_factor(1000, 5, share=0.4, seed=10)
    hist = np.column_stack([hist, np.zeros(1000)])          # a sleeve that never traded
    cov = by_regime(hist, ["x"] * 1000)["x"]
    assert np.isfinite(cov.mean_corr)
    assert cov.mean_corr == pytest.approx(0.4, abs=0.1)


def test_the_diversification_ratio_spans_independence_to_lockstep():
    indep = by_regime(_one_factor(3000, 10, share=0.0, seed=11), ["a"] * 3000)["a"]
    locked = by_regime(_one_factor(3000, 10, share=0.95, seed=12), ["a"] * 3000)["a"]
    assert indep.diversification_ratio == pytest.approx(1.0, abs=0.2)
    assert locked.diversification_ratio > 5.0


def test_the_overrides_are_exactly_the_worldconfig_fields():
    cal = calibrate(_one_factor(500, 5, share=0.5), None,
                    standing_share=STANDING.crisis_common_share,
                    standing_vol_mult=STANDING.crisis_vol_mult)
    over = cal.as_overrides()
    for key in over:
        assert hasattr(STANDING, key), f"calibration emits {key}, which WorldConfig has no field for"
    WorldConfig(**over)


def test_the_allocator_passes_the_calibration_into_the_world_config():
    import inspect

    from research import pf_allocator

    src = inspect.getsource(pf_allocator.run)
    assert "_calibrate_cov" in src
    assert "**(cov_cal.as_overrides() if cov_cal else {})" in src
