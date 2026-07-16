"""Geometric growth and capital-growth simulation.

``GeometricGrowthEngine`` scores a return stream by its compounded (geometric) growth, reusing the
discovery layer's expected-log-growth. ``CapitalGrowthSimulator`` Monte-Carlos terminal wealth and
ruin via block-resampling (reusing the survival engine for ruin), so allocation maximizes expected
long-term log wealth rather than single-period return.
"""

from __future__ import annotations

import numpy as np

from libs.discovery.monte_carlo_survival import monte_carlo_survival
from libs.discovery.objective import expected_log_growth
from libs.stage14.models import GeometricGrowthResult, GrowthSimResult
from libs.validation.bootstrap import stationary_block_indices


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class GeometricGrowthEngine:
    """Scores a return stream by expected compounded growth (the quantity to maximize)."""

    def evaluate(
        self, returns: np.ndarray, *, periods_per_year: float = 252.0, horizon_years: float = 1.0
    ) -> GeometricGrowthResult:
        arr = np.asarray(returns, dtype="float64")
        if len(arr) == 0:
            return GeometricGrowthResult(
                expected_cagr=0.0, expected_geometric_return=0.0, expected_terminal_wealth=1.0,
                growth_efficiency=0.0, geometric_growth_score=0.0,
            )
        glog = expected_log_growth(arr, periods_per_year=periods_per_year)  # annualized log-growth
        cagr = float(np.expm1(glog))
        geo_per_period = float(np.expm1(np.log1p(arr).mean()))
        terminal = float(np.exp(glog * horizon_years))
        arith = float(arr.mean()) * periods_per_year
        # Efficiency: how much of the arithmetic return survives as geometric (variance drag).
        growth_efficiency = _clip01(glog / arith) if arith > 0 else 0.0
        score = 100.0 * _clip01(0.5 * _clip01(cagr / 0.5) + 0.5 * growth_efficiency)
        return GeometricGrowthResult(
            expected_cagr=cagr,
            expected_geometric_return=geo_per_period,
            expected_terminal_wealth=terminal,
            growth_efficiency=growth_efficiency,
            geometric_growth_score=score,
        )


class CapitalGrowthSimulator:
    """Monte-Carlo CAGR / terminal-wealth / ruin distribution for long-horizon optimization."""

    def __init__(self, *, n_sims: int = 2000, block: float = 10.0, seed: int = 0) -> None:
        self.n_sims = n_sims
        self.block = block
        self.seed = seed

    def simulate(
        self, returns: np.ndarray, *, horizon: int | None = None, periods_per_year: float = 252.0
    ) -> GrowthSimResult:
        base = np.asarray(returns, dtype="float64")
        n = len(base)
        if n < 2:
            return GrowthSimResult(
                cagr_median=0.0, cagr_p5=0.0, cagr_p95=0.0, terminal_wealth_median=1.0,
                probability_of_ruin=1.0, expected_log_growth=0.0, survival_probability=0.0,
            )
        steps = horizon or n
        rng = np.random.default_rng(self.seed)
        terminals = np.empty(self.n_sims, dtype="float64")
        cagrs = np.empty(self.n_sims, dtype="float64")
        for s in range(self.n_sims):
            idx = stationary_block_indices(n, self.block, rng)[:steps]
            path = base[idx]
            terminal = float(np.prod(1.0 + path))
            terminals[s] = terminal
            years = steps / periods_per_year
            cagrs[s] = terminal ** (1.0 / years) - 1.0 if terminal > 0 and years > 0 else -1.0
        survival = monte_carlo_survival(base, n_sims=self.n_sims, block=self.block, seed=self.seed)
        return GrowthSimResult(
            cagr_median=float(np.median(cagrs)),
            cagr_p5=float(np.percentile(cagrs, 5)),
            cagr_p95=float(np.percentile(cagrs, 95)),
            terminal_wealth_median=float(np.median(terminals)),
            probability_of_ruin=survival.probability_of_ruin,
            expected_log_growth=expected_log_growth(base, periods_per_year=periods_per_year),
            survival_probability=survival.survival_probability,
        )
