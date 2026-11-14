"""The shared Kalman and Hawkes modules recover planted truth and never read the future."""
from __future__ import annotations

import math

import numpy as np

from libs.research import point_process as pp
from libs.research import state_space as ss


def _simulate(mu, alpha, beta, span, seed=0):
    rng = np.random.default_rng(seed)
    mu, alpha = np.asarray(mu, float), np.asarray(alpha, float)
    t, s, out = 0.0, np.zeros(mu.size), []
    while True:
        bound = float((mu + alpha @ s).sum())
        w = rng.exponential(1 / bound)
        t += w
        s *= math.exp(-beta * w)
        if t > span:
            break
        lam = mu + alpha @ s
        if rng.uniform() * bound <= lam.sum():
            i = int(rng.choice(mu.size, p=lam / lam.sum()))
            out.append((t, i))
            s[i] += beta
    a = np.array(out)
    return a[:, 0], a[:, 1].astype(int)


def test_hawkes_recovers_a_planted_branching_matrix():
    t, k = _simulate([0.02, 0.01], [[0.3, 0.0], [0.5, 0.2]], 0.23, 30000)
    f = pp.fit(t, k, span=30000)
    assert f is not None and f.beta == 0.23 and f.stationary
    assert abs(f.alpha[1, 0] - 0.5) < 0.15 and f.alpha[0, 1] < 0.12
    table = pp.excitation_table(f, ["a", "b"])
    assert table["branching"]["b"]["a"] == round(float(f.alpha[1, 0]), 4)


def test_poisson_has_no_branching():
    rng = np.random.default_rng(3)
    t = np.sort(rng.uniform(0, 20000, 400))
    f = pp.fit(t, span=20000)
    assert f is not None and f.alpha[0, 0] < 0.15


def test_intensity_counts_only_events_at_or_before_the_grid_time():
    t, k = _simulate([0.02], [[0.5]], 0.087, 5000, seed=4)
    f = pp.fit(t, k, span=5000)
    grid = np.arange(0, 5000, 7.0)
    full = pp.intensity_at(grid, t, k, f)
    cut = 2500.0
    part = pp.intensity_at(grid[grid <= cut], t[t <= cut], k[t <= cut], f)
    assert np.allclose(part, full[: part.shape[0]])


def test_dynamic_regression_tracks_a_planted_beta():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 3000).cumsum()
    y = 2.0 * x + rng.normal(0, 1, 3000)
    assert abs(ss.dynamic_regression(y, x, delta=1e-5, r=1.0).filt[-1, -1] - 2.0) < 0.1


def test_filters_are_causal():
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, 800).cumsum()
    x = y + rng.normal(0, 1, 800)
    for fn in (lambda a, b: ss.dynamic_regression(a, b).innov,
               lambda a, b: ss.local_linear_trend(a, 1.0, 1e-3, 0.1).filt[:, 1],
               lambda a, b: ss.log_variance_level(np.diff(a, prepend=0.0)).innov,
               lambda a, b: ss.dynamic_correlation(np.diff(a, prepend=0.0),
                                                   np.diff(b, prepend=0.0))):
        full, part = fn(y, x), fn(y[:500], x[:500])
        assert np.allclose(full[:500], part, equal_nan=True)


def test_log_variance_level_is_unbiased_for_gaussian_returns():
    rng = np.random.default_rng(5)
    lv = ss.log_variance_level(rng.normal(0, 0.01, 20000), q=0.001)
    assert abs(lv.filt[1000:, 0].mean() - math.log(1e-4)) < 0.05
