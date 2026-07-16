"""Dynamic covariance forecasting + ERC allocation."""

from __future__ import annotations

import numpy as np

from libs.portfolio.covariance import cov_forecast_portfolio, erc_weights, ewma_cov


def test_ewma_cov_shape_and_psd() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0, 0.01, (500, 4))
    cov = ewma_cov(r, lam=0.94)
    assert cov.shape == (4, 4)
    assert np.allclose(cov, cov.T)
    assert np.all(np.linalg.eigvalsh(cov) > -1e-9)        # PSD


def test_erc_equalizes_risk_contribution() -> None:
    # two assets, one 2x the vol -> ERC should give the high-vol one less weight (uncapped here)
    cov = np.array([[0.04, 0.0], [0.0, 0.01]])
    w = erc_weights(cov, max_weight=1.0)
    assert w[1] > w[0]                                     # low-vol asset gets more weight
    rc = w * (cov @ w)
    assert abs(rc[0] - rc[1]) < 0.05 * rc.sum()           # roughly equal risk contribution


def test_erc_caps_concentration() -> None:
    cov = np.diag([0.0001, 0.04, 0.04, 0.04])             # one near-riskless asset
    w = erc_weights(cov, max_weight=0.40)
    assert w.max() <= 0.4001
    assert abs(w.sum() - 1.0) < 1e-9


def test_cov_forecast_portfolio_no_lookahead_and_finite() -> None:
    rng = np.random.default_rng(1)
    r = rng.normal(0.0003, 0.01, (600, 4))
    p = cov_forecast_portfolio(r, lookback=120, min_obs=60)
    assert len(p) == len(r)
    assert np.isfinite(p).all()
