"""Tests for DSR, PBO, reality check / SPA, bootstrap, and FDR control."""

from __future__ import annotations

import numpy as np
import pytest
from tests.validation.conftest import edge_matrix, noise_matrix, strong_returns

from libs.validation.bootstrap import (
    block_bootstrap,
    confidence_interval,
    moving_block_indices,
    stationary_bootstrap,
)
from libs.validation.dsr import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_ratio,
)
from libs.validation.errors import ValidationError
from libs.validation.fdr import benjamini_hochberg, benjamini_yekutieli
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.reality_check import hansen_spa, whites_reality_check

# --- DSR -------------------------------------------------------------------


def test_sharpe_ratio_basic() -> None:
    assert sharpe_ratio(np.array([1.0, 1.0, 1.0])) == 0.0  # zero variance
    assert sharpe_ratio(strong_returns()) > 0


def test_psr_in_unit_interval_and_high_for_strong() -> None:
    psr = probabilistic_sharpe_ratio(strong_returns(n=500))
    assert 0.0 <= psr <= 1.0
    assert psr > 0.9


def test_expected_max_sharpe_increases_with_trials() -> None:
    assert expected_max_sharpe(1000, 0.25) > expected_max_sharpe(10, 0.25) > 0


def test_dsr_passes_few_trials_fails_many() -> None:
    returns = strong_returns(n=500)
    few = deflated_sharpe_ratio(returns, n_trials=5, variance_of_sharpes=0.25)
    many = deflated_sharpe_ratio(returns, n_trials=1_000_000, variance_of_sharpes=0.25)
    assert few.passed
    assert many.sr0_threshold > few.sr0_threshold
    assert not many.passed


def test_dsr_requires_variance_or_estimates() -> None:
    with pytest.raises(ValidationError):
        deflated_sharpe_ratio(strong_returns(), n_trials=10)


def test_min_track_record_length() -> None:
    assert np.isfinite(min_track_record_length(strong_returns(n=500)))
    # Sharpe <= benchmark -> infinite required length
    assert min_track_record_length(np.array([-1.0, -1.0, 1.0, -1.0])) == float("inf")


# --- PBO -------------------------------------------------------------------


def test_pbo_low_for_persistent_edge() -> None:
    result = probability_backtest_overfitting(edge_matrix(t=240, n=8), n_splits=8)
    assert result.pbo < 0.5


def test_pbo_validates_inputs() -> None:
    with pytest.raises(ValidationError):
        probability_backtest_overfitting(np.zeros((100, 1)))
    with pytest.raises(ValidationError):
        probability_backtest_overfitting(np.zeros((100, 3)), n_splits=7)


# --- reality check / SPA ---------------------------------------------------


def test_reality_check_pvalues_in_unit_interval_and_deterministic() -> None:
    matrix = edge_matrix()
    p1 = whites_reality_check(matrix, n_boot=300, seed=42).p_value
    p2 = whites_reality_check(matrix, n_boot=300, seed=42).p_value
    assert p1 == p2
    assert 0.0 <= p1 <= 1.0


def test_spa_more_significant_for_edge_than_noise() -> None:
    edge_p = hansen_spa(edge_matrix(seed=0), n_boot=300, seed=1).p_value
    noise_p = hansen_spa(noise_matrix(seed=5), n_boot=300, seed=1).p_value
    assert edge_p <= noise_p
    assert edge_p < 0.05


# --- bootstrap -------------------------------------------------------------


def test_moving_block_indices_valid() -> None:
    rng = np.random.default_rng(0)
    idx = moving_block_indices(50, 7, rng)
    assert len(idx) == 50
    assert idx.min() >= 0 and idx.max() < 50


def test_block_bootstrap_ci_brackets_mean() -> None:
    x = strong_returns(n=500)
    samples = block_bootstrap(x, lambda a: float(a.mean()), block=10, n_boot=500, seed=0)
    lo, hi = confidence_interval(samples)
    assert lo <= x.mean() <= hi


def test_stationary_bootstrap_deterministic() -> None:
    x = strong_returns(n=200)
    a = stationary_bootstrap(x, lambda v: float(v.mean()), mean_block=8, n_boot=200, seed=7)
    b = stationary_bootstrap(x, lambda v: float(v.mean()), mean_block=8, n_boot=200, seed=7)
    assert np.array_equal(a, b)


# --- FDR -------------------------------------------------------------------


def test_benjamini_hochberg_rejects_small_pvalues() -> None:
    result = benjamini_hochberg(np.array([0.001, 0.008, 0.02, 0.5, 0.9]), alpha=0.05)
    assert result.rejected[0] is True
    assert result.rejected[-1] is False
    assert result.n_rejected >= 1


def test_bh_rejects_none_when_all_large() -> None:
    result = benjamini_hochberg(np.array([0.4, 0.6, 0.8]), alpha=0.05)
    assert result.n_rejected == 0


def test_by_is_more_conservative_than_bh() -> None:
    p = np.array([0.001, 0.01, 0.02, 0.03, 0.2])
    bh = benjamini_hochberg(p, alpha=0.05)
    by = benjamini_yekutieli(p, alpha=0.05)
    assert by.n_rejected <= bh.n_rejected
