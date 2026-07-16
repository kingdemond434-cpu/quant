"""Tests for the delta-neutral cash-and-carry return."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research.cashcarry import cashcarry_returns, spot_basis_carry_returns


def _panel(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.RandomState(seed)
    cols = [f"S{i}" for i in range(20)]
    # clear persistent funding SPREAD (top rich, bottom cheap) + tiny noise -> the carry collects
    # the spread on both legs; low noise so the harvest is reliably positive.
    base = np.tile(np.linspace(-0.001, 0.001, 20), (300, 1))
    funding = pd.DataFrame(base + rng.normal(0.0, 5e-5, (300, 20)), columns=cols)
    basis = pd.DataFrame(np.zeros((300, 20)), columns=cols)
    return funding, basis


def test_cashcarry_runs_and_is_low_variance() -> None:
    funding, basis = _panel()
    r = cashcarry_returns(funding, basis)
    assert len(r) == len(funding)
    active = r[r != 0.0]
    # delta-neutral carry should be LOW variance (no price-return term)
    assert float(np.std(active)) < 0.01


def test_cashcarry_harvests_positive_funding() -> None:
    funding, basis = _panel(1)
    r = cashcarry_returns(funding, basis)
    # with persistent positive funding the book should net positive
    assert float(np.sum(r)) > 0.0


def test_spot_basis_carry_runs_and_low_variance() -> None:
    rng = np.random.RandomState(2)
    cols = [f"S{i}" for i in range(20)]
    funding = pd.DataFrame(rng.normal(0.0, 1e-4, (300, 20)), columns=cols)
    # persistent basis SPREAD (top rich/contango, bottom cheap) -> convergence carry harvests it
    base = np.tile(np.linspace(-0.01, 0.01, 20), (300, 1))
    basis = pd.DataFrame(base + rng.normal(0.0, 5e-4, (300, 20)), columns=cols)
    r = spot_basis_carry_returns(funding, basis)
    assert len(r) == len(basis)
    # delta-neutral (no price-return term) -> low variance
    assert float(np.std(r[r != 0.0])) < 0.02
