"""Growth-optimal (Kelly) leverage analysis."""

from __future__ import annotations

import numpy as np

from libs.risk.growth_leverage import (
    analyze,
    ann_geom_growth,
    cagr,
    kelly_optimal,
    max_drawdown,
    risk_of_ruin,
)


def _edge(n: int = 4000, mu: float = 0.0004, sigma: float = 0.01, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sigma, n)


def test_growth_peaks_then_falls_with_leverage() -> None:
    r = _edge()
    g_low = ann_geom_growth(r, 1.0)
    g_kelly = ann_geom_growth(r, kelly_optimal(r))
    g_over = ann_geom_growth(r, 9.0)
    assert g_kelly >= g_low                    # Kelly is the growth peak
    assert g_kelly >= g_over                   # over-leverage drags growth back down


def test_kelly_in_reasonable_range_of_mu_over_sigma2() -> None:
    mu, sigma = 0.0004, 0.01
    r = _edge(mu=mu, sigma=sigma)
    analytic = mu / sigma**2                    # ~4.0; exact log-optimum sits a bit below this
    k = kelly_optimal(r)
    assert 0.4 * analytic <= k <= analytic + 0.5   # same order, below small-return approximation


def test_drawdown_and_ruin_increase_with_leverage() -> None:
    r = _edge()
    assert max_drawdown(r, 5.0) <= max_drawdown(r, 1.0)        # deeper DD when levered
    assert risk_of_ruin(r, 8.0) >= risk_of_ruin(r, 1.0)       # more ruin risk when levered


def test_cagr_negative_returns_ruin_on_overleverage() -> None:
    # a return stream with a -30% day is wiped out at >3.33x leverage
    r = np.concatenate([_edge(n=500), np.array([-0.30])])
    assert cagr(r, 10.0) == -1.0               # 1 + 10*(-0.30) < 0 -> ruin


def test_analyze_orders_leverage_points() -> None:
    rep = analyze(_edge(), kelly_fraction=0.5, governance_cap=3.0)
    assert rep["recommended_leverage"] <= rep["growth_optimal_leverage"]
    assert rep["points"]["aggressive"]["max_dd"] <= rep["points"]["recommended"]["max_dd"]
