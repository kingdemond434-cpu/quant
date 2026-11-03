"""Data-driven (James-Stein / empirical-Bayes) shrinkage strength for the sleeve posterior.

WHAT THIS REPLACES. `robust_elog._posterior_mu` pools sleeve -> family -> asset class -> zero
by `n / (n + k)` with k FIXED: k_sleeve=60, k_family=120. A fixed k says every family is
exactly as heterogeneous as every other. It is not: a family of near-identical gold windows
carries almost no true spread between its members, so the spread its sample means show is
mostly noise and should be pooled hard; a family of genuinely different instruments carries
real spread and should be pooled less. The normal-normal model says the optimal weight on the
sleeve's own mean is

    lam_i = tau^2 / (tau^2 + s_i^2 / n_i) = n_i / (n_i + k_i),   k_i = s_i^2 / tau^2

and `tau^2`, the true between-member variance, is ESTIMATED from the family itself by the
method of moments (positive-part James-Stein):

    tau^2_f = max(0, var(m_i in f) - mean(se_i^2 in f))

TWO-SIDED, BOUNDED (GROWTH GOVERNANCE: every capital modifier is two-sided). `k_i =
clip(s_i^2 / tau^2_f, K_MIN_RATIO * k_fixed, K_MAX)`: a family whose members are alike is pooled
harder than today, and a family whose members measurably differ is pooled LESS -- strong
evidence may raise a sleeve's capital, down to a quarter of today's k and no further. A family
with fewer than `MIN_GROUP` members cannot estimate its own spread honestly (the positive-part
James-Stein moment divides by g - 3, so four members), so it keeps the fixed k unchanged.
Precision is never overstated either way: the posterior se keeps today's fixed-k widening.

VOLATILITY IS POOLED TOO. A sleeve with 40 days has a noisy standard deviation; the Bayesian
answer pools it toward its family's (`NU0` pseudo-degrees of freedom of the family variance).
The pooled s drives k (a steadier denominator), while the posterior standard error uses
`max(s_raw, s_pooled)`: pooling may WIDEN a sleeve's uncertainty, never narrow it.

ARMING. Everything here is inert until armed (env `QUANT_EB_SHRINKAGE=1`, or the flag file
`desks/mt5/data/EB_SHRINKAGE_ARMED`). `WorldConfig.eb_shrinkage` reads the arm at
construction, so the E8 book (pf_allocator), the Fusion book (kelly_survival) and the FTMO /
prop book (prop_challenge_allocator) -- all of which read the same `sample_worlds` posterior --
switch together: account parity by construction. The arm is placed ONLY after the
preregistered out-of-sample test (`docs/research/EB_SHRINKAGE_PREREGISTRATION.md`, harness
`desks/mt5/research/eb_shrinkage_oos.py`) passes on the box's own sleeve evidence.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np

#: The positive-part James-Stein moment divides by (g - 3), so it needs four members.
MIN_GROUP = 4
#: Pseudo-degrees of freedom the family variance carries when pooling a sleeve's vol.
NU0 = 30.0
#: Ceiling on k: tau^2 == 0 means "no detectable true spread", i.e. pool (almost) fully.
K_MAX = 1.0e6
#: Lower bound on k as a share of the fixed k (preregistered): a heterogeneous family may be
#: pooled at most 4x less than today.
K_MIN_RATIO = 0.25

ARM_ENV = "QUANT_EB_SHRINKAGE"
ARM_FILE = Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "EB_SHRINKAGE_ARMED"


def eb_armed() -> bool:
    """True when the desk has armed data-driven shrinkage (env wins over the flag file)."""
    env = os.environ.get(ARM_ENV)
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    try:
        return ARM_FILE.exists()
    except OSError:
        return False


def pooled_vol(s: np.ndarray, obs: np.ndarray, groups: Sequence[str],
               nu0: float = NU0) -> np.ndarray:
    """Each sleeve's sd pooled toward its group's df-weighted variance (nu0 pseudo-df).

    A sleeve with no usable sd (obs < 2 or s == 0) takes its group's sd outright; a group with
    no usable member leaves its rows as they are."""
    s = np.asarray(s, dtype=float)
    obs = np.asarray(obs, dtype=float)
    df = np.maximum(obs - 1.0, 0.0) * (s > 0)
    out = s.copy()
    g = np.asarray(list(groups), dtype=object)
    for key in set(g.tolist()):
        rows = np.flatnonzero(g == key)
        dfw = df[rows]
        if dfw.sum() <= 0:
            continue
        var_g = float(np.sum(dfw * s[rows] ** 2) / dfw.sum())
        out[rows] = np.sqrt((dfw * s[rows] ** 2 + nu0 * var_g) / (dfw + nu0))
    return out


def eb_k(m: np.ndarray, s_pool: np.ndarray, eff: np.ndarray, groups: Sequence[str],
         k_fixed: float, *, min_group: int = MIN_GROUP, k_max: float = K_MAX,
         k_min_ratio: float = K_MIN_RATIO,
         diag: dict[str, dict[str, float]] | None = None) -> np.ndarray:
    """Per-row shrinkage strength k_i = clip(s_i^2 / tau^2_g, k_min_ratio * k_fixed, k_max).

    `m` are the estimates being pooled toward their group mean, `s_pool` their per-observation
    sd and `eff` their effective observation counts, so se_i^2 = s_i^2 / eff_i. A group below
    `min_group` members, or with no positive evidence, keeps `k_fixed`."""
    m = np.asarray(m, dtype=float)
    s_pool = np.asarray(s_pool, dtype=float)
    eff = np.asarray(eff, dtype=float)
    k = np.full(m.shape, float(k_fixed))
    k_lo = float(k_min_ratio) * float(k_fixed)
    g = np.asarray(list(groups), dtype=object)
    for key in set(g.tolist()):
        rows = np.flatnonzero(g == key)
        ok = rows[(eff[rows] > 0) & np.isfinite(m[rows]) & (s_pool[rows] > 0)]
        if ok.size < min_group:
            if diag is not None:
                diag[str(key)] = {"n": float(ok.size), "tau2": float("nan"), "k_fixed": k_fixed}
            continue
        se2 = s_pool[ok] ** 2 / eff[ok]
        # The James-Stein moment, not the plain one: dividing the spread by (g - 3) instead of
        # (g - 1) is what makes the positive-part estimator dominate the unpooled one, and it
        # pools LESS than the naive moment does in small families, where tau^2 is noisiest.
        ss = float(np.sum((m[ok] - m[ok].mean()) ** 2))
        tau2 = max(0.0, ss / (ok.size - 3) - float(se2.mean()))
        k_rows = s_pool[rows] ** 2 / tau2 if tau2 > 0.0 else np.full(rows.size, k_max)
        k[rows] = np.clip(k_rows, k_lo, k_max)
        if diag is not None:
            diag[str(key)] = {"n": float(ok.size), "tau2": tau2,
                              "k_median": float(np.median(k[rows]))}
    return k


def group_rollup(values: np.ndarray, weights: np.ndarray, groups: Sequence[str]
                 ) -> tuple[list[str], np.ndarray, np.ndarray]:
    """(group keys, weight-averaged value per group, summed weight per group)."""
    g = list(groups)
    keys = sorted(set(g))
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    mean = np.zeros(len(keys))
    tot = np.zeros(len(keys))
    for j, key in enumerate(keys):
        rows = [i for i, x in enumerate(g) if x == key]
        ww = w[rows]
        tot[j] = float(ww.sum())
        mean[j] = float(np.average(v[rows], weights=ww)) if ww.sum() > 0 else 0.0
    return keys, mean, tot
