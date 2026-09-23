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

#: WHY THESE LOOPS REUSE ONE BUFFER (2026-08-28).
#:
#: Both bootstraps resample rows of the (T x N) performance matrix `n_boot` times. Written as
#: `f[idx].mean(axis=0)`, each iteration ALLOCATES a fresh T x N array, and the allocation is the
#: expensive part -- not the arithmetic. Fresh pages must be faulted in by the OS before they can
#: be written, so the cost is paid in page faults rather than FLOPs.
#:
#: That stayed invisible while this desk swept 460 cells: the matrix was ~2,000 x 460, about 7MB,
#: and a thousand 7MB allocations are nothing. The docket then grew to 6,270 cells and the same
#: line began allocating a 100MB array a thousand times -- on a box with 8GB shared with the live
#: MT5 terminal. Measured that night: 178 million page faults, 14.9GB committed against 8GB
#: physical, and a sweep using 0.68 of 4 cores because it was waiting on memory rather than
#: computing. The gates did not get harder; they got further from RAM.
#:
#: `np.take(f, idx, axis=0, out=buf, mode="clip")` writes the resampled rows into ONE buffer
#: allocated once, whose pages stay resident across all `n_boot` iterations.
#:
#: `mode="clip"` IS LOAD-BEARING, not decoration. Measured on a 2,000 x 1,500 matrix, 200
#: bootstraps:
#:     f[idx].mean(axis=0)                    13.10s   24.0MB allocated per iteration
#:     np.take(..., out=buf)                   9.41s   24.0MB  <- STILL allocates
#:     np.take(..., out=buf, mode="clip")      6.65s    0.1MB
#: The default mode="raise" performs its bounds check through a temporary copy, so passing `out`
#: alone does NOT remove the allocation -- it only removes the output array. Only the clip path
#: writes straight into the buffer. All three produced a bit-identical checksum.
#:
#: Clipping would silently substitute the last row for an out-of-range index instead of raising,
#: so the bound is asserted explicitly below. That check costs T comparisons against a T x N
#: gather -- under a tenth of a percent -- and keeps the guarantee mode="raise" was providing.
#:
#: THE ARITHMETIC IS UNCHANGED, DELIBERATELY. `np.take(..., axis=0)` gathers exactly the rows
#: `f[idx]` gathers, in the same order, and the subsequent `.mean(axis=0)` reduces them in the
#: same order -- so every intermediate and every result is bit-for-bit identical. A faster
#: formulation exists (weighting rows by their `bincount` and taking one matrix-vector product,
#: skipping the gather entirely) and it is NOT used here: it changes floating-point summation
#: order, which would move p-values in the last bits. On a certification path a candidate sitting
#: exactly at a threshold could flip, and "it is only the last bits" is not a thing worth being
#: wrong about. This optimisation is free; that one is not.


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
    resampled = np.empty_like(f)          # allocated once; see the note at the top of this module
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        if idx.max() >= t_obs or idx.min() < 0:
            raise ValidationError("bootstrap produced an out-of-range row index")
        np.take(f, idx, axis=0, out=resampled, mode="clip")
        f_star = resampled.mean(axis=0)
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
    resampled = np.empty_like(f)          # allocated once; see the note at the top of this module
    for b in range(n_boot):
        idx = stationary_block_indices(t_obs, mean_block, rng)
        if idx.max() >= t_obs or idx.min() < 0:
            raise ValidationError("bootstrap produced an out-of-range row index")
        np.take(f, idx, axis=0, out=resampled, mode="clip")
        f_star = resampled.mean(axis=0)
        z = np.sqrt(t_obs) * (f_star - d_bar * keep) / omega
        boot_max[b] = max(0.0, float(z.max()))
    p_value = float(np.mean(boot_max >= statistic))
    return RealityCheckResult(
        statistic=statistic, p_value=p_value, n_strategies=n, method="hansen_spa"
    )
