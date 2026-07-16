"""Cross-sectional funding strategy core (shared by backtest + shadow)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.crypto_xsec import adv_tier_cost, xsec_funding_returns


def test_cost_tiers() -> None:
    assert adv_tier_cost(1e9) == 5e-4        # very liquid
    assert adv_tier_cost(2e8) == 8e-4        # mid
    assert adv_tier_cost(1e6) == 1.5e-3      # illiquid


def _panel(n_days: int = 400, n_names: int = 20) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2022-01-01", periods=n_days, freq="D", tz="UTC")
    cols = [f"C{i}" for i in range(n_names)]
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.02, (n_days, n_names)), 0),
                         index=idx, columns=cols)
    # persistent per-name funding dispersion (some always high, some always low)
    base = rng.uniform(-0.0005, 0.0005, n_names)
    funding = pd.DataFrame(base + rng.normal(0, 0.0001, (n_days, n_names)), index=idx, columns=cols)
    adv = dict.fromkeys(cols, 1e9)
    return close, funding, adv


def test_returns_shape_and_no_lookahead() -> None:
    close, funding, adv = _panel()
    r = xsec_funding_returns(close, funding, adv, lookback=3, q=0.2, band=0.02)
    assert len(r) == len(close)
    assert r[0] == 0.0                         # first bar has no prior signal -> flat
    assert np.isfinite(r).all()


def test_harvests_persistent_funding_spread() -> None:
    close, funding, adv = _panel()
    r = xsec_funding_returns(close, funding, adv, lookback=5, q=0.2, band=0.0)
    # with persistent dispersion and zero price drift, the funding spread should net positive
    assert float(np.mean(r[r != 0.0])) > 0.0
