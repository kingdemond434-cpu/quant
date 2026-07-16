"""Tests for the Information Coefficient toolkit."""

from __future__ import annotations

import numpy as np

from libs.research.ic import cross_sectional_ic, evaluate_signal, ic_stats


def test_perfect_predictor_has_high_ic() -> None:
    rng = np.random.RandomState(0)
    fwd = rng.randn(200, 10)
    signal = fwd.copy()                       # signal == forward return -> IC = 1
    ic = cross_sectional_ic(signal, fwd)
    assert np.nanmean(ic) > 0.99


def test_noise_signal_has_zero_ic() -> None:
    rng = np.random.RandomState(1)
    fwd = rng.randn(300, 12)
    noise = rng.randn(300, 12)
    st = evaluate_signal(noise, fwd)
    assert abs(st["mean_ic"]) < 0.1
    assert st["t_stat"] < 3.0                  # not significant


def test_ic_stats_shape_and_hit_rate() -> None:
    rng = np.random.RandomState(2)
    fwd = rng.randn(250, 8)
    signal = fwd + 0.5 * rng.randn(250, 8)     # noisy-but-real predictor
    st = ic_stats(cross_sectional_ic(signal, fwd))
    assert st["mean_ic"] > 0.2
    assert 0.0 <= st["hit_rate"] <= 1.0
    assert st["ic_ir"] > 0


def test_short_series_returns_safe_zeros() -> None:
    st = ic_stats(np.array([0.1, 0.2]))
    assert st["n"] == 2 and st["mean_ic"] == 0.0
