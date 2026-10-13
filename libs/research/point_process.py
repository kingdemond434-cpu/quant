"""HAWKES POINT PROCESSES, SHARED (2026-10-06).

One module for every self-exciting intensity the desk mines: the EliteQuant thread's bar-event
intensities (signed activity, large prints, spread depletion, jumps, vol shocks; Roman rows
0819-0832) and World sensor's news intensities. Re-derived from Hawkes (1971) and Ogata (1981);
nothing copied.

THE MODEL. d event types, a common exponential decay beta, and a normalised kernel, so alpha[i, j]
is directly the expected number of type-i children of one type-j event (the branching matrix):

    lambda_i(t) = mu_i + sum_j alpha[i, j] * sum_{t_k^j < t} beta * exp(-beta (t - t_k^j))

For a FIXED beta the log-likelihood is concave in (mu, alpha), so (mu, alpha) are fitted exactly
by bounded L-BFGS on that convex problem, and beta is chosen from a grid by likelihood. The
process is stationary when the spectral radius of alpha is below one; `fit` reports it and never
returns a non-stationary fit for a univariate process.

Times are in BARS (any unit works if it is consistent). Every intensity the module returns at a
time t counts events at times <= t only, so a family reading it at bar t's close is causal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

#: Decay grid in 1/bars: half-lives of about 1, 3, 8, 24 and 72 bars.
BETA_GRID = (0.7, 0.23, 0.087, 0.029, 0.0096)


@dataclass(frozen=True)
class HawkesFit:
    mu: np.ndarray            # (d,) baseline rates per bar
    alpha: np.ndarray         # (d, d) branching matrix: children of type i per type-j event
    beta: float               # common decay per bar
    loglik: float
    n_events: int
    span: float

    @property
    def spectral_radius(self) -> float:
        return float(max(abs(np.linalg.eigvals(self.alpha)))) if self.alpha.size else 0.0

    @property
    def stationary(self) -> bool:
        return self.spectral_radius < 1.0


def _excitation(times: np.ndarray, types: np.ndarray, d: int, beta: float) -> np.ndarray:
    """S[e, j] = sum over earlier type-j events of beta * exp(-beta * gap), at event e."""
    s = np.zeros(d)
    out = np.zeros((times.size, d))
    last = times[0] if times.size else 0.0
    for e in range(times.size):
        s *= math.exp(-beta * (times[e] - last))
        last = times[e]
        out[e] = s
        s[types[e]] += beta
    return out


def fit(times: np.ndarray, types: np.ndarray | None = None, *, d: int | None = None,
        span: float | None = None, betas: tuple[float, ...] = BETA_GRID,
        max_events: int = 2000) -> HawkesFit | None:
    """MLE of a d-type exponential Hawkes process on events in [0, span]. None when there are
    too few events of some type to identify its baseline (fewer than 5)."""
    from scipy.optimize import minimize

    times = np.asarray(times, dtype=float)
    types = np.zeros(times.size, dtype=int) if types is None else np.asarray(types, dtype=int)
    order = np.argsort(times, kind="stable")
    times, types = times[order], types[order]
    d = int(d or (types.max() + 1 if types.size else 1))
    T = float(span if span is not None else (times[-1] if times.size else 0.0))
    if times.size > max_events:
        # keep the most recent events and observe the process from the first one kept, so the
        # baseline is not diluted by a span whose events were dropped
        times, types = times[-max_events:], types[-max_events:]
        T -= times[0]
        times = times - times[0]
    if not T > 0 or np.bincount(types, minlength=d).min() < 5:
        return None
    best: HawkesFit | None = None
    for beta in betas:
        S = _excitation(times, types, d, beta)
        tail = 1.0 - np.exp(-beta * (T - times))                     # compensator per parent
        comp_alpha = np.array([tail[types == j].sum() for j in range(d)])  # (d,)

        def nll(v: np.ndarray, S: np.ndarray = S, comp_alpha: np.ndarray = comp_alpha
                ) -> tuple[float, np.ndarray]:
            mu, a = v[:d], v[d:].reshape(d, d)
            lam = mu[types] + np.einsum("ej,ej->e", a[types], S)
            lam = np.maximum(lam, 1e-300)
            ll = float(np.log(lam).sum() - mu.sum() * T - (a * comp_alpha[None, :]).sum())
            inv = 1.0 / lam
            g_mu = np.bincount(types, weights=inv, minlength=d) - T
            g_a = np.zeros((d, d))
            for i in range(d):
                m = types == i
                g_a[i] = (S[m] * inv[m, None]).sum(axis=0) - comp_alpha
            return -ll, -np.r_[g_mu, g_a.ravel()]

        counts = np.bincount(types, minlength=d).astype(float)
        x0 = np.r_[0.5 * counts / T, np.full(d * d, 0.1 / d)]
        ub = 0.999 if d == 1 else None
        bounds = [(1e-9, None)] * d + [(0.0, ub)] * (d * d)
        res = minimize(nll, x0, jac=True, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 500})
        if not np.all(np.isfinite(res.x)):
            continue
        cand = HawkesFit(res.x[:d].copy(), res.x[d:].reshape(d, d).copy(), float(beta),
                         float(-res.fun), int(times.size), float(T))
        if best is None or cand.loglik > best.loglik:
            best = cand
    return best


def intensity_at(grid: np.ndarray, times: np.ndarray, types: np.ndarray | None,
                 fit_: HawkesFit) -> np.ndarray:
    """(len(grid), d) intensities at each grid time, counting events at times <= that time."""
    grid = np.asarray(grid, dtype=float)
    times = np.asarray(times, dtype=float)
    types = np.zeros(times.size, dtype=int) if types is None else np.asarray(types, dtype=int)
    order = np.argsort(times, kind="stable")
    times, types = times[order], types[order]
    d, b = fit_.mu.size, fit_.beta
    out = np.empty((grid.size, d))
    s = np.zeros(d)
    last = min(grid[0] if grid.size else 0.0, times[0] if times.size else 0.0)
    e = 0
    for g in range(grid.size):
        t = grid[g]
        while e < times.size and times[e] <= t:
            s *= math.exp(-b * (times[e] - last))
            last = times[e]
            s[types[e]] += b
            e += 1
        s_now = s * math.exp(-b * (t - last))
        out[g] = fit_.mu + fit_.alpha @ s_now
    return out


def excitation_table(fit_: HawkesFit, names: list[str]) -> dict[str, object]:
    """The branching matrix as a report row: who excites whom, and whether it is stationary."""
    return {"types": list(names), "beta_per_bar": fit_.beta,
            "half_life_bars": round(math.log(2.0) / fit_.beta, 2),
            "mu_per_bar": [round(float(m), 6) for m in fit_.mu],
            "branching": {names[i]: {names[j]: round(float(fit_.alpha[i, j]), 4)
                                     for j in range(len(names))} for i in range(len(names))},
            "spectral_radius": round(fit_.spectral_radius, 4),
            "stationary": fit_.stationary, "n_events": fit_.n_events, "span_bars": fit_.span,
            "loglik": round(fit_.loglik, 3)}
