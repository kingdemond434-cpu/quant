"""The shared Kalman module: filter vs a closed form, missing observations, PIT (no future data
in the filtered path), smoother improvement, and MLE recovery of noise variances."""
from __future__ import annotations

import numpy as np
import pytest

from libs.quant_models import kalman as k


def _ll_data(n: int = 500, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    mu = np.cumsum(rng.normal(0, 0.5, n))
    return mu, mu + rng.normal(0, 1.0, n)


def test_scalar_and_general_paths_agree() -> None:
    _, y = _ll_data(200)
    m1 = k.local_level(y, 1.0, 0.25)
    r1 = k.kalman_filter(y, m1)
    # the same model as a 2-observation system with one component always missing
    y2 = np.column_stack([y, np.full(y.size, np.nan)])
    m2 = k.StateSpace(Z=np.array([[1.0], [1.0]]), H=np.eye(2), T=np.eye(1),
                      Q=np.array([[0.25]]), a0=m1.a0, P0=m1.P0, n_diffuse=1)
    r2 = k.kalman_filter(y2, m2)
    np.testing.assert_allclose(r1.a_filt, r2.a_filt, rtol=1e-9)
    assert r1.loglik == pytest.approx(r2.loglik, rel=1e-9)


def test_steady_state_gain_matches_closed_form() -> None:
    _, y = _ll_data(400)
    q, h = 0.25, 1.0
    r = k.kalman_filter(y, k.local_level(y, h, q))
    p = (q + np.sqrt(q * q + 4 * q * h)) / 2        # steady-state predicted variance
    assert r.P_pred[-1, 0, 0] == pytest.approx(p, rel=1e-6)


def test_missing_observations_are_pure_prediction() -> None:
    _, y = _ll_data(100)
    y[40:50] = np.nan
    r = k.kalman_filter(y, k.local_level(y, 1.0, 0.25))
    assert np.all(np.isnan(r.v[40:50]))
    np.testing.assert_allclose(r.a_filt[40:50, 0], r.a_filt[39, 0])
    assert np.all(np.diff(r.P_pred[40:51, 0, 0]) > 0)


def test_filter_is_point_in_time() -> None:
    _, y = _ll_data(300)
    m = k.local_level(y, 1.0, 0.25, a0=0.0, P0=10.0)
    full = k.kalman_filter(y, m)
    cut = k.kalman_filter(y[:150], m)
    np.testing.assert_allclose(full.a_filt[:150], cut.a_filt)
    np.testing.assert_allclose(full.y_hat[:150], cut.y_hat)


def test_smoother_beats_filter_and_innovations_are_standard() -> None:
    mu, y = _ll_data(600)
    fit = k.fit_local_level(y)
    r = k.kalman_filter(y, fit.model)
    a_s, _ = k.rts_smoother(r, fit.model)
    assert np.mean((a_s[:, 0] - mu) ** 2) < np.mean((r.a_filt[:, 0] - mu) ** 2)
    z = r.innovation_z()[5:, 0]
    assert np.nanstd(z) == pytest.approx(1.0, abs=0.1)


def test_local_level_mle_recovers_variances() -> None:
    _, y = _ll_data(800, seed=4)
    fit = k.fit_local_level(y)
    assert fit.params[0] == pytest.approx(1.0, rel=0.3)
    assert fit.params[1] == pytest.approx(0.25, rel=0.4)


def test_tvp_regression_recovers_drifting_beta() -> None:
    rng = np.random.default_rng(1)
    n = 500
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    beta = np.column_stack([np.zeros(n), 1 + np.cumsum(rng.normal(0, 0.05, n))])
    y = (X * beta).sum(1) + rng.normal(0, 0.2, n)
    fit = k.fit_tvp_regression(y, X)
    assert fit.params[0] == pytest.approx(0.04, rel=0.35)
    assert 0.001 < fit.params[2] < 0.0065           # true 0.0025: one path, n=500
    assert fit.params[1] < 0.2 * fit.params[2]      # the static intercept is found static
    r = k.kalman_filter(k.tvp_y(y, X), fit.model)
    err = r.a_filt[50:, 1] - beta[50:, 1]
    assert np.sqrt(np.mean(err ** 2)) < 0.15


def test_fallback_optimizer_runs() -> None:
    _, y = _ll_data(200, seed=2)
    a = k.fit_local_level(y)
    b = k.fit_local_level(y, use_scipy=False)
    assert b.method == "nelder_mead_fallback"
    assert b.loglik == pytest.approx(a.loglik, abs=0.5)
