"""GARCH challenger to the EWMA baseline: parameter recovery, no look-ahead, honest refusals."""

from __future__ import annotations

import numpy as np
import pytest

from libs.research import garch
from libs.research.volatility_signals import ewma_variance


def _simulate(n: int, omega: float, alpha: float, beta: float, gamma: float = 0.0,
              seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    r = np.empty(n)
    h = omega / (1.0 - alpha - beta - 0.5 * gamma)
    for i in range(n):
        r[i] = np.sqrt(h) * z[i]
        h = omega + (alpha + (gamma if r[i] < 0 else 0.0)) * r[i] ** 2 + beta * h
    return r


def test_fit_recovers_garch_parameters() -> None:
    r = _simulate(6000, omega=2e-6, alpha=0.10, beta=0.80)
    m = garch.fit(r)
    assert m is not None and m.converged
    assert m.alpha == pytest.approx(0.10, abs=0.03)
    assert m.beta == pytest.approx(0.80, abs=0.06)
    assert m.long_run_variance == pytest.approx(2e-5, rel=0.25)
    assert m.persistence < 1.0


def test_fit_is_scale_free() -> None:
    r = _simulate(3000, omega=2e-6, alpha=0.10, beta=0.80)
    a, b = garch.fit(r), garch.fit(r * 100.0)
    assert a is not None and b is not None
    assert b.alpha == pytest.approx(a.alpha, abs=1e-3)
    assert b.beta == pytest.approx(a.beta, abs=1e-3)
    assert b.omega == pytest.approx(a.omega * 1e4, rel=1e-2)


def test_gjr_finds_the_asymmetry_and_plain_garch_data_has_none() -> None:
    skewed = garch.fit(_simulate(8000, omega=2e-6, alpha=0.03, beta=0.80, gamma=0.14), gjr=True)
    assert skewed is not None and skewed.gamma > 0.07
    flat = garch.fit(_simulate(8000, omega=2e-6, alpha=0.10, beta=0.80), gjr=True)
    assert flat is not None and flat.gamma < 0.05


def test_filter_is_riskmetrics_at_the_ewma_corner() -> None:
    # omega=0, alpha=1-lam, beta=lam IS the RiskMetrics recursion. Seeded with the same h0 the
    # EWMA uses (the first squared return), the two forecasts agree bar for bar with no shift.
    # `ewma_variance` leaves bar 0 empty (no return precedes it), so the comparison starts at 1.
    r = _simulate(400, omega=2e-6, alpha=0.10, beta=0.80)
    lam = 0.94
    h0 = float(r[0] ** 2)
    e = ewma_variance(r, lam=lam)
    g = garch.filter_variance(r, 0.0, 1.0 - lam, lam, h0=h0)
    np.testing.assert_allclose(g[1:len(r)], e[1:], rtol=1e-9)
    # and the forecast for bar i moves with r[i-1], never with r[i]: no look-ahead
    bumped = r.copy()
    bumped[200] *= 10.0
    e2 = ewma_variance(bumped, lam=lam)
    assert e2[200] == e[200] and e2[201] > e[201]


def test_walk_forward_has_no_lookahead() -> None:
    r = _simulate(1400, omega=2e-6, alpha=0.10, beta=0.80)
    base = garch.walk_forward_variance(r, min_train=500, refit_every=100)
    cut = 950                                    # mid-window, not on a refit boundary
    shocked = r.copy()
    shocked[cut:] *= 25.0                        # the future changes violently
    again = garch.walk_forward_variance(shocked, min_train=500, refit_every=100)
    np.testing.assert_array_equal(base[:cut + 1], again[:cut + 1])
    assert np.isnan(base[:500]).all() and np.isfinite(base[500:]).all()


def test_garch_beats_ewma_out_of_sample_on_mean_reverting_variance() -> None:
    r = _simulate(5000, omega=4e-6, alpha=0.15, beta=0.65, seed=11)
    res = garch.compare_to_ewma(r, min_train=1000, refit_every=250)
    assert res["status"] == "MEASURED"
    q = res["qlike"]
    assert q["garch"] < q["ewma"]
    assert res["dm_t"]["garch"] > 2.0
    assert res["best"] in ("garch", "gjr")
    assert q["ewma"] <= q["ewma_as_shipped"]      # the aligned baseline is the harder one to beat


def test_refuses_instead_of_inventing() -> None:
    assert garch.fit(np.zeros(1000)) is None                     # no measurable variance
    assert garch.fit(_simulate(100, 2e-6, 0.1, 0.8)) is None     # too short
    res = garch.compare_to_ewma(_simulate(600, 2e-6, 0.1, 0.8), min_train=500)
    assert res["status"] == "UNMEASURED" and "need" in res["why"]
    assert np.isnan(garch.qlike(np.full(5, np.nan), np.ones(5)))


def test_missing_bars_do_not_invent_a_shock() -> None:
    r = _simulate(800, omega=2e-6, alpha=0.10, beta=0.80)
    holed = r.copy()
    holed[300:305] = np.nan
    h = garch.filter_variance(holed, 2e-6, 0.10, 0.80)
    assert np.isfinite(h).all() and (h > 0).all()
    assert garch.fit(holed) is not None


def test_a_degenerate_fit_cannot_drive_the_forecast_to_zero() -> None:
    # Calm for a long stretch after training: a near-zero-omega fit would decay toward nothing.
    rng = np.random.default_rng(3)
    r = np.concatenate([_simulate(600, 2e-6, 0.10, 0.80), rng.standard_normal(400) * 1e-7])
    h = garch.walk_forward_variance(r, min_train=600, refit_every=400)
    train_var = float(np.var(r[:600]))
    assert np.nanmin(h[600:]) >= garch.FORECAST_FLOOR_FRAC * train_var
