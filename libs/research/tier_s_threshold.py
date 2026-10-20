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

import itertools
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


def _real_roots(a: float, b: float, c: float) -> list[float]:
    """Real roots of a*x^2 + b*x + c (linear or constant when a, b vanish)."""
    if abs(a) < 1e-300:
        return [] if abs(b) < 1e-300 else [-c / b]
    disc = b * b - 4.0 * a * c
    if disc < 0:
        return []
    s = math.sqrt(disc)
    q = -0.5 * (b + math.copysign(s, b))           # the stable form of the quadratic formula
    out = [q / a] if q != 0 else []
    if q != 0:
        out.append(c / q)
    elif abs(a) >= 1e-300:
        out.append(0.0)
    return out


def tier_s_t_required(n_obs: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """The SMALLEST t (per-period Sharpe x sqrt(T)) at which the canonical DSR reaches 0.95 at
    the Tier S bar, for a series of `n_obs` periods with the given skew and NON-excess kurtosis.

    Inverted from `psr_from_moments`, the very arithmetic `deflated_sharpe_ratio` runs on a
    sample -- WITHOUT assuming it is monotone in the Sharpe. It is not, in general: with skew 2
    and kurtosis 3 the PSR variance term 1 - g3*SR + (g4-1)/4*SR^2 is negative on (0.59, 3.41),
    the PSR is 0 there, and it passes again on both sides. A bracket grown until the PSR passes
    and then bisected (the previous form, audit 2026-10-20) returned 16.7 at T=24 where the true
    smallest passing t is 2.07.

    So the pass set is solved, not searched: PSR >= 0.95 with SR > sr0 and a positive variance
    term is (T-1)(SR - sr0)^2 >= z95^2 * (1 - g3 SR + (g4-1)/4 SR^2), a quadratic. Its roots, the
    variance term's roots and sr0 cut (sr0, inf) into intervals on which pass/fail is constant;
    each is judged by the canonical PSR at its midpoint, and the answer is the left end of the
    first passing interval, VERIFIED to pass on the canonical function (nudged up by ulps when a
    root lands a hair short). Returns inf -- an explicit refusal, never a number -- when no Sharpe
    can pass (T < 3, or moments under which no interval passes) or when the verification cannot
    be made."""
    from scipy.stats import norm

    n = int(n_obs)
    if n < 3:
        return math.inf
    sr0 = tier_s_sr0(n)
    g3, g4 = float(skew), float(kurtosis)
    if not (math.isfinite(g3) and math.isfinite(g4)):
        return math.inf

    def psr(sr: float) -> float:
        return psr_from_moments(sr, n, g3, g4, sr_benchmark=sr0)

    def passes(sr: float) -> bool:
        return psr(sr) >= TIER_S_DSR_THRESHOLD

    z2 = float(norm.ppf(TIER_S_DSR_THRESHOLD)) ** 2
    k = (g4 - 1.0) / 4.0
    cuts = {sr0}
    # (n-1)(sr - sr0)^2 - z2 * (1 - g3 sr + k sr^2) = 0
    cuts.update(_real_roots((n - 1) - z2 * k, -2.0 * (n - 1) * sr0 + z2 * g3,
                            (n - 1) * sr0 * sr0 - z2))
    cuts.update(_real_roots(k, -g3, 1.0))           # the PSR variance term's zeros
    pts = sorted(x for x in cuts if math.isfinite(x) and x >= sr0)
    edges = [*pts, max(pts[-1], 1.0) * 4.0 + 1.0]
    for left, right in itertools.pairwise(edges):
        if not right > left or not passes(0.5 * (left + right)):
            continue
        sr = left
        for _ in range(8):                          # a root a few ulps short: step to the pass
            if passes(sr):
                return float(sr * math.sqrt(n))
            sr = math.nextafter(sr, math.inf)
        # the interval passes but its left edge did not verify (sr0 itself, or a variance-term
        # zero where the PSR is 0 but every Sharpe just above passes): bisect INSIDE it, never
        # outside -- its midpoint passes, so [left, mid] holds the smallest passing Sharpe
        lo, hi = left, 0.5 * (left + right)
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if passes(mid):
                hi = mid
            else:
                lo = mid
            if hi - lo < 1e-15 * max(1.0, hi):
                break
        return float(hi * math.sqrt(n)) if passes(hi) else math.inf
    return math.inf


def tier_s_passes(returns: Sequence[float] | np.ndarray) -> tuple[bool, float]:
    """(passed, dsr) from the canonical `deflated_sharpe_ratio` on `returns` at the Tier S bar.
    A series too short to carry a null variance (T < 2) is (False, 0.0): never a pass."""
    r = np.asarray(returns, dtype="float64")
    if r.size < 2:
        return False, 0.0
    res = deflated_sharpe_ratio(r, n_trials=bar_n(), variance_of_sharpes=tier_s_variance(r.size),
                                threshold=TIER_S_DSR_THRESHOLD)
    return bool(res.passed), float(res.dsr)
