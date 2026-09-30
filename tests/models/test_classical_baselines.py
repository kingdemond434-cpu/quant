from __future__ import annotations

import math

import numpy as np

from libs.models.classical_baselines import BetaBinary, HawkesIntensity, nelder_mead


def test_nelder_mead_finds_simple_minimum() -> None:
    x, value = nelder_mead(lambda z: float((z[0] - 2.0) ** 2), np.array([0.0]))
    assert abs(float(x[0]) - 2.0) < 1e-3
    assert value < 1e-6


def test_beta_binary_is_fitted_and_scores() -> None:
    model = BetaBinary().fit([1, 1, 0, 1])
    assert model.state["fitted"] is True
    assert 0.5 < model.state["p"] < 1.0
    assert math.isfinite(model.score([1, 0]))


def test_hawkes_baseline_returns_measured_finite_state() -> None:
    model = HawkesIntensity().fit([0.0, 1.0, 1.5, 3.0, 3.2, 6.0])
    assert model.state["verdict"] == "MEASURED"
    assert 0.0 <= model.state["branching_ratio"] < 1.0
    assert model.state["decay_halflife"] > 0.0
