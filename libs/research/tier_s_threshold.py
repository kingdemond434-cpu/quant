"""THE TIER S t, DERIVED FROM THE CANONICAL DEFLATED SHARPE -- never a literal, never a copy.

The Tier S bar (owner's T8 ruling, 2026-10-13) is `libs.validation.dsr.deflated_sharpe_ratio`
at n_trials = `trial_count_guard.bar_n()` (= 5) with the per-cell null variance 1/(T-1), passing
at DSR >= 0.95. Under normal returns the per-cell t it demands is about 4.56 at T=5, 3.06 at
T=24, 2.89 at T=100, tending to about 2.84 -- and the SAME at any trial count, because the N is
fixed. Organs that want "the Tier S t" import it from here (re-exported by
`libs.research.trial_count_guard`); `scripts/check_trial_inflation.py` fails any bare 2.84-ish
constant used as a bar anywhere else, because a written-down t is a copy of this arithmetic that
stops tracking T, skew and kurtosis the day it is typed.

t is reported as the per-period Sharpe times sqrt(T): the t-statistic of the mean.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from libs.research.trial_count_guard import bar_n
from libs.validation.dsr import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    psr_from_moments,
)

#: The DSR the Tier S bar demands (the canonical function's default threshold).
TIER_S_DSR_THRESHOLD = 0.95


def tier_s_variance(n_obs: int) -> float:
    """The per-cell null variance of the Tier S bar: 1/(T-1)."""
    return 1.0 / (int(n_obs) - 1)


def tier_s_sr0(n_obs: int) -> float:
    """The per-period Sharpe benchmark the canonical DSR uses at the Tier S bar."""
    return expected_max_sharpe(bar_n(), tier_s_variance(n_obs))


def tier_s_t_required(n_obs: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """The t (per-period Sharpe x sqrt(T)) at which the canonical DSR reaches 0.95 at the Tier S
    bar, for a series of `n_obs` periods with the given skew and NON-excess kurtosis.

    Inverted numerically from `psr_from_moments`, the very arithmetic `deflated_sharpe_ratio`
    runs on a sample. Returns inf when no Sharpe can pass (T < 3, or a skew/kurtosis that makes
    the PSR variance non-positive over the whole bracket)."""
    n = int(n_obs)
    if n < 3:
        return math.inf
    sr0 = tier_s_sr0(n)

    def psr(sr: float) -> float:
        return psr_from_moments(sr, n, float(skew), float(kurtosis), sr_benchmark=sr0)

    lo, hi = sr0, max(sr0, 1e-6) * 2.0 + 1.0
    while psr(hi) < TIER_S_DSR_THRESHOLD:
        hi *= 2.0
        if hi > 1e6:
            return math.inf
    for _ in range(200):                       # bisection: psr is monotone on [sr0, hi] here
        mid = 0.5 * (lo + hi)
        if psr(mid) >= TIER_S_DSR_THRESHOLD:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-12:
            break
    return float(hi * math.sqrt(n))


def tier_s_passes(returns: Sequence[float] | np.ndarray) -> tuple[bool, float]:
    """(passed, dsr) from the canonical `deflated_sharpe_ratio` on `returns` at the Tier S bar.
    A series too short to carry a null variance (T < 2) is (False, 0.0): never a pass."""
    r = np.asarray(returns, dtype="float64")
    if r.size < 2:
        return False, 0.0
    res = deflated_sharpe_ratio(r, n_trials=bar_n(), variance_of_sharpes=tier_s_variance(r.size),
                                threshold=TIER_S_DSR_THRESHOLD)
    return bool(res.passed), float(res.dsr)
