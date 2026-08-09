"""monte_carlo_survival_engine — probability of ruin, survival, worst-case drawdown.

Runs bootstrap, trade-reshuffling, cost-stress, and parameter-perturbation simulations to
estimate survival probability. Rejects anything with survival < 95%.

READ THIS BEFORE WIRING IT. As of 2026-08-01 this function has NO production caller: its only
importers, libs/stage14/growth.py and libs/stage14/analytics.py, are themselves imported only by
their own tests. It is inert, and the defaults below have therefore never been calibrated against
anything real. They do not survive contact with crypto.

MEASURED (tests/stage14/test_survival_calibration.py, daily bars at ~57% annualised vol):

    true Sharpe   median max DD    survival at dd_limit=0.20
    0.5           0.79             0.000
    1.0           0.66             0.000
    2.0           0.49             0.000

Zero at every level, including the whole of REAL_EDGE_OOS_SHARPE_BAND (0.5-1.5), the band
libs/validation/robustness_filters.py records as where genuine verified edge is OBSERVED to live.
The default is not strict, it is unreachable -- ``survival_min=0.95`` asks for the 95th-percentile
drawdown to sit under the limit, and on crypto volatility that is a far larger number than the
median. An external 350,000-backtest sweep on Bitcoin found the same shape from the other side:
zero walk-forward survivors under a 40% drawdown cap, four under 60%, and its best survivor ran an
OOS Sharpe of 1.08 with a 42% drawdown.

So: wiring this as-is would reject every candidate the desk could ever plausibly find, and the
2026-08-01 gate audit is unambiguous that over-rejection is this desk's failure mode rather than
its safeguard. Do not fix that by quietly widening ``dd_limit`` to whatever lets something
through -- that is editing the guard to fit the violation. Set it from the drawdown the BOOK can
actually survive, then accept that it is a capital-allocation limit and not evidence of quality.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.bootstrap import stationary_block_indices


class MonteCarloSurvivalResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    survival_probability: float
    probability_of_ruin: float
    worst_case_drawdown: float
    median_drawdown: float
    passed: bool

    def __bool__(self) -> bool:
        return self.passed


def _max_drawdown(returns: np.ndarray) -> float:
    equity = np.cumprod(1.0 + returns)
    running = np.maximum.accumulate(equity)
    return float((1.0 - equity / running).max())


def monte_carlo_survival(
    returns: np.ndarray,
    *,
    n_sims: int = 2000,
    block: float = 10.0,
    dd_limit: float = 0.20,
    ruin_drawdown: float = 0.50,
    cost_per_period: float = 0.0,
    survival_min: float = 0.95,
    seed: int = 0,
) -> MonteCarloSurvivalResult:
    """Estimate survival via mixed-method resampling of the return stream."""
    base = np.asarray(returns, dtype="float64") - cost_per_period  # cost stress
    n = len(base)
    if n < 2:
        return MonteCarloSurvivalResult(
            survival_probability=0.0, probability_of_ruin=1.0, worst_case_drawdown=1.0,
            median_drawdown=1.0, passed=False,
        )
    rng = np.random.default_rng(seed)
    drawdowns = np.empty(n_sims, dtype="float64")
    for s in range(n_sims):
        method = s % 3
        if method == 0:  # block bootstrap (preserves autocorrelation)
            sample = base[stationary_block_indices(n, block, rng)]
        elif method == 1:  # trade reshuffling
            sample = base[rng.permutation(n)]
        else:  # parameter perturbation (multiplicative noise on the edge)
            sample = base * (1.0 + rng.normal(0.0, 0.1, size=n))
        drawdowns[s] = _max_drawdown(sample)

    survival = float(np.mean(drawdowns < dd_limit))
    ruin = float(np.mean(drawdowns >= ruin_drawdown))
    return MonteCarloSurvivalResult(
        survival_probability=survival,
        probability_of_ruin=ruin,
        worst_case_drawdown=float(drawdowns.max()),
        median_drawdown=float(np.median(drawdowns)),
        passed=survival >= survival_min,
    )
