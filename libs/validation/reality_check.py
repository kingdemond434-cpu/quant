"""White's Reality Check and Hansen's SPA test.

Both ask whether the *best* of many strategies beats a benchmark by more than luck, correcting
for the fact that you searched. White's Reality Check uses the max raw outperformance; Hansen's
SPA studentizes and recenters, giving more power. Both use the stationary bootstrap.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.bootstrap import stationary_block_indices
from libs.validation.errors import ValidationError


class RealityCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    statistic: float
    p_value: float
    n_strategies: int
    method: str

    @property
    def significant_at_5pct(self) -> bool:
        return self.p_value < 0.05


def _as_matrix(performance: np.ndarray) -> np.ndarray:
    matrix = np.asarray(performance, dtype="float64")
    if matrix.ndim != 2 or matrix.shape[1] < 1:
        raise ValidationError("performance must be a 2-D (T x N) array")
    return matrix


def whites_reality_check(
    performance: np.ndarray, *, n_boot: int = 1000, mean_block: float = 10, seed: int = 0
) -> RealityCheckResult:
    """White's Reality Check. ``performance[t, k]`` = strategy k's edge over benchmark at t."""
    f = _as_matrix(performance)
    t_obs, n = f.shape
    d_bar = f.mean(axis=0)
    statistic = float(np.sqrt(t_obs) * d_bar.max())
    rng = np.random.default_rng(seed)
    boot_max = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        f_star = f[idx].mean(axis=0)
        boot_max[b] = np.sqrt(t_obs) * (f_star - d_bar).max()
    p_value = float(np.mean(boot_max >= statistic))
    return RealityCheckResult(
        statistic=statistic, p_value=p_value, n_strategies=n, method="white_reality_check"
    )


def hansen_spa(
    performance: np.ndarray, *, n_boot: int = 1000, mean_block: float = 10, seed: int = 0
) -> RealityCheckResult:
    """Hansen's SPA test (consistent variant), studentized and recentered."""
    f = _as_matrix(performance)
    t_obs, n = f.shape
    d_bar = f.mean(axis=0)
    omega = f.std(axis=0, ddof=1)
    omega = np.where(omega <= 0, np.inf, omega)  # zero-variance strategies cannot be significant
    statistic = float(max(0.0, np.max(np.sqrt(t_obs) * d_bar / omega)))

    # Consistent recentring threshold A_n (Hansen 2005).
    loglog = max(np.log(np.log(t_obs)) if t_obs > np.e else 1.0, 1e-6)
    threshold = -np.sqrt((omega**2 / t_obs) * 2.0 * loglog)
    keep = d_bar >= threshold

    rng = np.random.default_rng(seed)
    boot_max = np.empty(n_boot, dtype="float64")
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        f_star = f[idx].mean(axis=0)
        z = np.sqrt(t_obs) * (f_star - d_bar * keep) / omega
        boot_max[b] = max(0.0, float(z.max()))
    p_value = float(np.mean(boot_max >= statistic))
    return RealityCheckResult(
        statistic=statistic, p_value=p_value, n_strategies=n, method="hansen_spa"
    )
