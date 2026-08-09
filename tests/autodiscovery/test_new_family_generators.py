"""The seven 2026-08-04 families: causal by test, not by claim.

Truncation invariance is the load-bearing check: a generator's position at bar t computed on the
first t+1 bars must equal its position at bar t computed on the full series. Any read of the
future -- a centered window, an unshifted extreme, a forward fill -- breaks it immediately.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.autodiscovery.generators import NEW_FAMILY_GENERATORS
from libs.autodiscovery.models import MarketSeries


def _series(t: int = 600, seed: int = 0) -> MarketSeries:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + rng.normal(0, 0.02, t))
    spread = np.abs(rng.normal(0, 0.01, t)) + 1e-3
    return MarketSeries(close=close, high=close * (1 + spread), low=close * (1 - spread),
                        volume=np.abs(rng.normal(1e6, 2e5, t)) + 1.0, hour=np.zeros(t))


def _truncate(s: MarketSeries, t: int) -> MarketSeries:
    return MarketSeries(close=s.close[:t], high=s.high[:t], low=s.low[:t],
                        volume=s.volume[:t], hour=s.hour[:t])


@pytest.mark.parametrize("spec", NEW_FAMILY_GENERATORS, ids=lambda g: g.subtype)
def test_truncation_invariance(spec) -> None:
    s = _series()
    cut = 400
    p = dict(spec.param_variants[0])
    full = np.asarray(spec.fn(s, p), dtype="float64")[:cut]
    trunc = np.asarray(spec.fn(_truncate(s, cut), p), dtype="float64")
    np.testing.assert_allclose(full, trunc, atol=1e-12,
                               err_msg=f"{spec.subtype} reads the future")


@pytest.mark.parametrize("spec", NEW_FAMILY_GENERATORS, ids=lambda g: g.subtype)
def test_positions_are_bounded_and_finite(spec) -> None:
    s = _series(seed=3)
    for p in spec.param_variants:
        pos = np.asarray(spec.fn(s, dict(p)), dtype="float64")
        assert len(pos) == len(s.close)
        assert np.all(np.isfinite(pos))
        assert np.all(np.abs(pos) <= 1.0 + 1e-12)


@pytest.mark.parametrize("spec", NEW_FAMILY_GENERATORS, ids=lambda g: g.subtype)
def test_every_family_actually_fires_on_realistic_data(spec) -> None:
    """A generator that never takes a position is dead code wearing a registration -- the exact
    defect class the orphan sweeps exist for, caught at birth instead."""
    fired = 0.0
    for seed in range(3):
        s = _series(t=1500, seed=seed)
        for p in spec.param_variants:
            fired += float(np.mean(np.asarray(spec.fn(s, dict(p))) != 0.0))
    assert fired > 0.0, f"{spec.subtype} never fired across 3 seeds x all variants"


def test_declared_failure_modes_everywhere() -> None:
    for g in NEW_FAMILY_GENERATORS:
        assert g.failure_modes, f"{g.subtype} has no declared failure modes"
