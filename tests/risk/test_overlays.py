"""Tests for the variance-reduction overlays (vol-target + beta-hedge)."""

from __future__ import annotations

import numpy as np

from libs.risk.overlays import beta_neutralize, vol_target_scale


def test_vol_target_stabilises_vol_and_no_lookahead() -> None:
    rng = np.random.RandomState(0)
    # a series with a clear vol regime shift (calm -> stormy); targeting should compress the storm
    calm = rng.normal(0.0, 0.005, 400)
    storm = rng.normal(0.0, 0.04, 400)
    r = np.concatenate([calm, storm])
    scaled, exposure = vol_target_scale(r, target_vol=0.30, lookback=20)
    assert len(scaled) == len(r)
    # in the stormy regime the overlay should cut exposure below 1 (de-lever high vol)
    assert float(np.nanmean(exposure[500:])) < 1.0
    # targeted series has MORE uniform vol: storm/calm vol ratio shrinks vs raw
    raw_ratio = np.std(r[500:800]) / np.std(r[100:400])
    tgt_ratio = np.std(scaled[500:800]) / np.std(scaled[100:400])
    assert tgt_ratio < raw_ratio


def test_beta_neutralize_removes_market_exposure() -> None:
    rng = np.random.RandomState(1)
    market = rng.normal(0.0, 0.02, 600)
    alpha = rng.normal(0.0, 0.005, 600)
    asset = 1.5 * market + alpha                       # strong market beta + small idiosyncratic
    resid, beta = beta_neutralize(asset, market, lookback=60)
    # residual should be far less correlated to the market than the raw asset
    raw_corr = abs(np.corrcoef(asset, market)[0, 1])
    res_corr = abs(np.corrcoef(resid[100:], market[100:])[0, 1])
    assert res_corr < raw_corr
    assert float(np.nanmean(beta[100:])) > 0.5         # recovers a positive beta
