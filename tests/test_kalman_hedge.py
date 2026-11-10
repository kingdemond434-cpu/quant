"""Kalman hedge ratio: tracks a drifting beta, never reads the future, refuses honestly."""

from __future__ import annotations

import numpy as np

from libs.research import kalman_hedge as kh


def _pair(n: int, *, drift: float, seed: int = 5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.standard_normal(n) * 0.01) + 5.0
    beta = 1.0 + np.cumsum(rng.standard_normal(n) * drift)
    y = 0.3 + beta * x + rng.standard_normal(n) * 0.005
    return y, x, beta


def test_tracks_a_drifting_hedge_ratio() -> None:
    y, x, beta = _pair(3000, drift=0.002)
    path = kh.kalman_regression(y, x, delta=1e-3)
    tail = slice(500, None)
    implied = path.alpha[tail] + path.beta[tail] * x[tail]
    truth = 0.3 + beta[tail] * x[tail]
    err = float(np.sqrt(np.mean((implied - truth) ** 2)))
    # The truth moves ~0.002 * x ~ 0.01 per bar, which no one-step-behind filter can remove.
    # A hedge fitted once on the first 500 bars is the "did not track at all" reference.
    b0, a0 = np.polyfit(x[:500], y[:500], 1)
    static = float(np.sqrt(np.mean((a0 + b0 * x[tail] - truth) ** 2)))
    assert err < 0.03 and err < 0.1 * static
    assert np.isnan(path.forecast[:30]).all() and np.isfinite(path.forecast[30:]).all()


def test_forecast_never_reads_the_current_or_future_bar() -> None:
    y, x, _ = _pair(800, drift=0.001)
    base = kh.kalman_regression(y, x, delta=1e-4)
    y2 = y.copy()
    y2[400:] += 3.0                                   # today and the whole future change
    again = kh.kalman_regression(y2, x, delta=1e-4)
    np.testing.assert_array_equal(base.forecast[:401], again.forecast[:401])
    np.testing.assert_array_equal(base.beta[:401], again.beta[:401])
    assert again.forecast[401] != base.forecast[401]  # ...and it does learn from it afterwards
    ols = kh.rolling_ols_forecast(y, x, window=60)
    ols2 = kh.rolling_ols_forecast(y2, x, window=60)
    np.testing.assert_array_equal(ols[:401], ols2[:401])


def test_kalman_beats_rolling_ols_when_the_hedge_drifts() -> None:
    y, x, _ = _pair(4000, drift=0.003, seed=9)
    res = kh.compare_to_rolling_ols(y, x, train=1000)
    assert res["status"] == "MEASURED"
    assert res["best"] == "kalman" and res["mse_ratio"] < 1.0
    assert res["dm_t"] > 2.0
    assert res["delta"] in kh.DELTA_GRID and res["ols_window"] in (30, 60, 120)


def test_levels_are_flagged_as_a_trap_and_returns_are_not() -> None:
    # Two trending log-price series with a fixed hedge in RETURN space.
    rng = np.random.default_rng(21)
    dx = rng.standard_normal(3000) * 0.01
    dy = 0.8 * dx + rng.standard_normal(3000) * 0.004
    x, y = np.cumsum(dx) + 5.0, np.cumsum(dy) + 3.0
    levels = kh.compare_to_rolling_ols(y, x, train=1000)
    assert levels["status"] == "MEASURED" and levels["level_trap"] is True
    rets = kh.compare_to_rolling_ols(dy, dx, train=1000)
    assert rets["status"] == "MEASURED" and rets["level_trap"] is False
    assert rets["mse"]["kalman"] < 0.5 * rets["mse"]["carry_forward"]


def test_a_fixed_hedge_selects_a_slow_filter() -> None:
    y, x, _ = _pair(2500, drift=0.0)
    slow = kh.select_delta(y[:1000], x[:1000])
    y2, x2, _ = _pair(2500, drift=0.004)
    fast = kh.select_delta(y2[:1000], x2[:1000])
    assert slow is not None and fast is not None and slow < fast


def test_is_scale_free() -> None:
    y, x, _ = _pair(1500, drift=0.001)
    a = kh.kalman_regression(y, x, delta=1e-4)
    b = kh.kalman_regression(y * 1000.0, x, delta=1e-4)
    np.testing.assert_allclose(b.forecast[30:], a.forecast[30:] * 1000.0, rtol=1e-6)


def test_refuses_instead_of_inventing() -> None:
    y, x, _ = _pair(600, drift=0.001)
    assert kh.compare_to_rolling_ols(y, x, train=500)["status"] == "UNMEASURED"
    flat = kh.kalman_regression(np.ones(200), np.ones(200))
    assert np.isnan(flat.forecast).all() and np.isnan(flat.loglik)
    assert kh.select_delta(np.ones(200), np.ones(200)) is None


def test_missing_bars_are_skipped_not_imputed() -> None:
    y, x, _ = _pair(900, drift=0.001)
    y[300:305] = np.nan
    path = kh.kalman_regression(y, x, delta=1e-4)
    assert np.isnan(path.forecast[300:305]).all()
    assert np.isfinite(path.forecast[305:]).all()
