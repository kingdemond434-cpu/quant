"""Per-symbol net-of-cost wiring into the discovery lab (committee T1/T2)."""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.generators import net_returns
from libs.autodiscovery.models import MarketSeries
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.timeframe import Timeframe
from libs.store.connection import Database


def _series(n: int = 500) -> MarketSeries:
    rng = np.random.default_rng(0)
    close = 100.0 * np.cumprod(1.0 + rng.normal(0, 0.01, n))
    return MarketSeries(close=close, high=close * 1.001, low=close * 0.999)


def test_net_returns_is_cost_sensitive() -> None:
    s = _series()
    rng = np.random.default_rng(1)
    pos = np.sign(rng.normal(size=len(s)))  # frequent flips -> real turnover to be charged
    cheap = net_returns(s, pos, cost=0.0).sum()
    pricey = net_returns(s, pos, cost=0.01).sum()
    assert pricey < cheap  # higher per-turnover cost strictly reduces net return


def test_lab_uses_cost_provider_when_present(db: Database) -> None:
    lab = AutoDiscoveryLab(
        db, lambda _s: None, bar=Timeframe.D1, cost=0.0003,
        cost_provider=lambda sym: 0.9 if sym == "XAUUSD" else 0.01,
    )
    assert lab._cost_for("XAUUSD") == 0.9      # per-symbol calibrated cost
    assert lab._cost_for("EURUSD") == 0.01


def test_lab_falls_back_to_flat_cost(db: Database) -> None:
    lab = AutoDiscoveryLab(db, lambda _s: None, bar=Timeframe.D1)  # no provider
    assert lab._cost_for("ANYTHING") == 0.0003
