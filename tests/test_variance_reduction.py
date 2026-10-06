"""Variance reduction is proven on planted truth before anything trusts it."""
from __future__ import annotations

import numpy as np

from libs.research import variance_reduction as vr


def test_control_variate_is_unbiased_and_tighter_on_a_planted_mean():
    def est(rng, cv):
        c = rng.normal(0.0, 1.0, 200)
        y = 1.0 + 2.0 * c + rng.normal(0.0, 0.5, 200)
        return vr.control_variate(y, c, 0.0).mean if cv else float(y.mean())

    plain = vr.planted_truth(lambda r: est(r, False), 1.0)
    cv = vr.planted_truth(lambda r: est(r, True), 1.0)
    assert abs(cv["bias"]) < 0.01 and cv["rmse"] < plain["rmse"] / 3


def test_adjusted_pool_keeps_the_pool_mean_and_cuts_variance():
    rng = np.random.default_rng(1)
    c = rng.uniform(0, 1, 400)
    y = 3 * c + rng.normal(0, 0.2, 400)
    adj, ratio = vr.adjusted_pool(y, c)
    assert abs(adj.mean() - y.mean()) < 1e-12 and ratio < 0.2


def test_a_constant_control_changes_nothing():
    y = np.arange(10.0)
    adj, ratio = vr.adjusted_pool(y, np.ones(10))
    assert np.array_equal(adj, y) and ratio == 1.0


def test_antithetic_halves_the_error_of_a_monotone_function():
    rng = np.random.default_rng(2)
    m, se = vr.antithetic_mean(np.exp, 5000, rng)
    plain = np.exp(np.random.default_rng(3).standard_normal(10000))
    assert abs(m - np.exp(0.5)) < 4 * se and se < plain.std() / 100 ** 1 * 1.0


def test_inverse_transform_stays_inside_the_sample():
    rng = np.random.default_rng(4)
    s = rng.normal(0, 1, 50)
    d = vr.inverse_transform(s, 1000, rng)
    assert d.min() >= s.min() and d.max() <= s.max()
