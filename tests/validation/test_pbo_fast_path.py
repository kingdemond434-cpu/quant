"""The fast CSCV path must BE the naive definition, not merely resemble it.

A 100x speedup on a validation gate is worthless if it moves the gate. These tests exist because
the optimisation replaced two things that are easy to get subtly wrong: a two-pass variance with
one assembled from block sums (which can cancel), and `scipy.stats.rankdata` with a closed-form
tie-averaged rank (which can disagree on ties). Both are checked against the thing they replaced,
on inputs chosen to break them.
"""
from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import rankdata

from libs.validation.errors import ValidationError
from libs.validation.pbo import (
    _average_rank_of,
    _pbo_reference,
    probability_backtest_overfitting,
)


def _identical(a, b) -> bool:
    return (a.pbo == b.pbo
            and a.n_combinations == b.n_combinations
            and a.n_strategies == b.n_strategies
            and a.median_logit == pytest.approx(b.median_logit, abs=1e-12))


# ------------------------------------------------------------------ the fast path IS the reference

@pytest.mark.parametrize("seed", range(6))
def test_vectorised_matches_the_naive_reference_on_random_matrices(seed: int) -> None:
    rng = np.random.default_rng(seed)
    m = rng.normal(0.0, 0.01, (320, 12))
    assert _identical(probability_backtest_overfitting(m, n_splits=8),
                      _pbo_reference(m, n_splits=8))


def test_a_mean_far_larger_than_the_deviation_does_not_cancel() -> None:
    """THE NUMERICAL STRESSOR. Assembling variance as S2 - S1^2/n subtracts two nearly equal
    numbers when mean >> sd. Here mean/sd is 10,000, which is where a naive block-sum
    implementation loses its digits -- the column-mean shift is what keeps this exact."""
    rng = np.random.default_rng(11)
    m = rng.normal(1.0, 1e-4, (320, 10))
    assert _identical(probability_backtest_overfitting(m, n_splits=8),
                      _pbo_reference(m, n_splits=8))


def test_a_constant_column_scores_zero_rather_than_nan() -> None:
    """A column that never moves has no Sharpe, not an infinite one. If it came back nan it would
    poison argmax and the 'best' strategy would be whichever index numpy happened to return."""
    rng = np.random.default_rng(5)
    m = np.hstack([rng.normal(0.0, 0.01, (320, 9)), np.zeros((320, 1))])
    assert _identical(probability_backtest_overfitting(m, n_splits=8),
                      _pbo_reference(m, n_splits=8))


def test_identical_columns_still_agree() -> None:
    """Every column tied is where a rank shortcut is most likely to diverge from rankdata."""
    rng = np.random.default_rng(2)
    m = np.tile(rng.normal(0.0, 0.01, (320, 1)), (1, 6))
    assert _identical(probability_backtest_overfitting(m, n_splits=8),
                      _pbo_reference(m, n_splits=8))


def test_fat_tails_agree() -> None:
    rng = np.random.default_rng(9)
    m = rng.standard_t(3, (320, 12)) * 0.01
    assert _identical(probability_backtest_overfitting(m, n_splits=8),
                      _pbo_reference(m, n_splits=8))


# --------------------------------------------------------------------------- the rank shortcut

@pytest.mark.parametrize("seed", range(8))
def test_average_rank_matches_scipy_under_heavy_ties(seed: int) -> None:
    rng = np.random.default_rng(seed)
    v = rng.choice([0.0, 1.0, 1.0, 2.5, -3.0], size=int(rng.integers(2, 30)))
    expected = rankdata(v)
    assert [_average_rank_of(v, i) for i in range(len(v))] == pytest.approx(list(expected))


# ------------------------------------------------------------------------- behaviour preserved

def test_pbo_low_for_a_persistent_edge() -> None:
    """The property the gate exists for: a real, persistent edge is not flagged as overfit."""
    rng = np.random.default_rng(1)
    noise = rng.normal(0.0, 0.01, (480, 8))
    edge = noise + np.linspace(0.0, 0.004, 8)      # column 7 genuinely best, in and out of sample
    assert probability_backtest_overfitting(edge, n_splits=8).pbo < 0.5


def test_input_validation_is_unchanged() -> None:
    with pytest.raises(ValidationError):
        probability_backtest_overfitting(np.zeros((100, 1)))
    with pytest.raises(ValidationError):
        probability_backtest_overfitting(np.zeros((100, 3)), n_splits=7)
    with pytest.raises(ValidationError):
        probability_backtest_overfitting(np.zeros((4, 3)), n_splits=8)
