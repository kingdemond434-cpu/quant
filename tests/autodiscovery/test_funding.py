"""Funding-stress reversal generator (Level-3 crypto signal)."""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.generators import _funding_stress_reversal
from libs.autodiscovery.models import MarketSeries


def _series(funding: np.ndarray | None) -> MarketSeries:
    n = len(funding) if funding is not None else 200
    close = np.full(n, 100.0)
    return MarketSeries(close=close, high=close * 1.001, low=close * 0.999, funding=funding)


def test_fades_extreme_positive_and_negative_funding() -> None:
    base = np.full(200, 0.0001)
    pos = base.copy()
    pos[-1] = 0.02                               # extreme positive funding -> short
    neg = base.copy()
    neg[-1] = -0.02                              # extreme negative funding -> long
    assert _funding_stress_reversal(_series(pos), {"window": 30, "z_entry": 1.5})[-1] == -1.0
    assert _funding_stress_reversal(_series(neg), {"window": 30, "z_entry": 1.5})[-1] == 1.0


def test_flat_when_funding_calm() -> None:
    calm = np.full(200, 0.0001)
    out = _funding_stress_reversal(_series(calm), {"window": 30, "z_entry": 1.5})
    assert np.all(out == 0.0)


def test_degrades_to_flat_without_funding() -> None:
    out = _funding_stress_reversal(_series(None), {"window": 30, "z_entry": 1.5})
    assert np.all(out == 0.0)
