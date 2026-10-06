"""SIMULATION EFFICIENCY: CONTROL VARIATES, ANTITHETICS, INVERSE TRANSFORM, PLANTED TRUTH.

Roman rows 0973 and 1001 (2026-10-06). A Monte Carlo estimate on this desk is only as good as its
variance, and every simulator here (the execution challenger's sampled fills, a strategy path
bootstrap, a stress draw) has been paying for precision with draws. These are the standard
remedies (Glasserman, "Monte Carlo Methods in Financial Engineering", ch. 4), re-derived:

  control_variate     y - b (c - E[c]) with the variance-minimising b = cov(y, c) / var(c). It is
                      unbiased only when E[c] is KNOWN; pass it, never the sample mean of the same
                      draws (that silently returns the plain mean with a narrower, wrong error).
  adjusted_pool       the same adjustment applied to a finite pool sampled with replacement, where
                      E[c] under the pool IS known exactly: sampling the adjusted values has the
                      pool's mean and a smaller variance. This is how an execution simulation that
                      draws measured outcomes uses a correlated measured covariate.
  antithetic_mean     the mean of f over paired draws u and 1 - u (or z and -z).
  inverse_transform   draws from an empirical distribution through its quantile function.
  planted_truth       runs an estimator on draws with a known answer and reports its bias and
                      error, so a variance reduction is proven on a planted number before it is
                      trusted on a real one.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CVResult:
    mean: float
    stderr: float
    plain_stderr: float
    b: float
    variance_ratio: float      # var(adjusted) / var(plain); < 1 is the gain


def control_variate(y: np.ndarray, c: np.ndarray, c_mean: float) -> CVResult:
    """The control-variate estimate of E[y] from paired draws (y, c) and the KNOWN E[c]."""
    y, c = np.asarray(y, dtype=float), np.asarray(c, dtype=float)
    ok = np.isfinite(y) & np.isfinite(c)
    y, c = y[ok], c[ok]
    n = y.size
    if n < 3:
        return CVResult(float("nan"), float("nan"), float("nan"), 0.0, float("nan"))
    vc = float(c.var(ddof=1))
    b = float(np.cov(y, c, ddof=1)[0, 1] / vc) if vc > 0 else 0.0
    adj = y - b * (c - c_mean)
    vy = float(y.var(ddof=1))
    va = float(adj.var(ddof=1))
    return CVResult(float(adj.mean()), (va / n) ** 0.5, (vy / n) ** 0.5, b,
                    va / vy if vy > 0 else float("nan"))


def adjusted_pool(y: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, float]:
    """Pool values adjusted by the pool's own exact control mean; (adjusted, variance ratio).

    Under sampling with replacement from the pool, E[c] is the pool mean exactly and b is the
    pool's own regression slope, so draws of the adjusted values are unbiased for the pool mean
    of y with variance var(y) (1 - rho^2). A pool too small or with a constant control comes back
    unchanged (ratio 1)."""
    y, c = np.asarray(y, dtype=float), np.asarray(c, dtype=float)
    ok = np.isfinite(y) & np.isfinite(c)
    if ok.sum() < 3:
        return y.copy(), 1.0
    vc = float(c[ok].var())
    if vc <= 0:
        return y.copy(), 1.0
    b = float(np.mean((y[ok] - y[ok].mean()) * (c[ok] - c[ok].mean())) / vc)
    adj = y.copy()
    adj[ok] = y[ok] - b * (c[ok] - c[ok].mean())
    vy = float(y[ok].var())
    return adj, (float(adj[ok].var()) / vy) if vy > 0 else 1.0


def antithetic_mean(f: Callable[[np.ndarray], np.ndarray], n: int, rng: np.random.Generator,
                    *, normal: bool = True) -> tuple[float, float]:
    """(mean, stderr) of f over n antithetic pairs: z and -z (normal) or u and 1 - u."""
    x = rng.standard_normal(n) if normal else rng.uniform(size=n)
    pair = 0.5 * (f(x) + f(-x if normal else 1.0 - x))
    return float(pair.mean()), float(pair.std(ddof=1) / n ** 0.5)


def inverse_transform(sample: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """n draws from the empirical distribution of `sample`, through its interpolated quantile
    function (a smooth bootstrap that never leaves the observed range)."""
    s = np.sort(np.asarray(sample, dtype=float)[np.isfinite(sample)])
    if s.size == 0:
        return np.full(n, np.nan)
    u = rng.uniform(size=n)
    out: np.ndarray = np.interp(u, np.linspace(0.0, 1.0, s.size), s)
    return out


def planted_truth(estimator: Callable[[np.random.Generator], float], truth: float, *,
                  reps: int = 200, seed: int = 0) -> dict[str, float]:
    """Bias and RMSE of `estimator` over `reps` independent seeds against a known `truth`."""
    est = np.array([estimator(np.random.default_rng(seed + k)) for k in range(reps)])
    return {"truth": truth, "mean": float(est.mean()), "bias": float(est.mean() - truth),
            "rmse": float(np.sqrt(np.mean((est - truth) ** 2))), "reps": reps}
