"""Challenger allocators: the books anyone could have written, scored on the desk's own worlds.

The dynamic E[log W] allocator keeps its authority only while it beats every one of these at
equal total heat on the same sampled worlds (`allocator_proof.contest`). Riskfolio and skfolio
between them ship most of the public portfolio-construction canon; the desk needs the CANDIDATES,
not the libraries, so they are reimplemented here in numpy from `SleeveEvidence.daily_r`:

    hrp             hierarchical risk parity (correlation-distance tree, recursive bisection)
    herc            hierarchical equal-risk contribution, variance version
    min_variance    long-only minimum variance on a shrunk covariance
    mean_cvar       weights by mean return per unit of conditional value-at-risk
    kelly           unconstrained Kelly  Sigma^-1 mu, long-only, scaled
    robust_kelly    Kelly on mu shrunk by one standard error
    bayesian_kelly  Kelly on mu shrunk toward zero by n / (n + 250)

Every book is long-only and rescaled to the dynamic book's total heat, so the contest compares
allocation, never leverage. Adding a challenger can only make the proof HARDER to pass.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

SHRINK = 0.20
BAYES_K = 250.0


def _matrix(ev: Sequence[Any]) -> tuple[np.ndarray, list[str]]:
    obs = min(int(e.daily_r.size) for e in ev)
    m = np.stack([np.asarray(e.daily_r[-obs:], dtype=float) for e in ev], axis=1)
    return m, [e.name for e in ev]


def _cov(m: np.ndarray, shrink: float = SHRINK) -> np.ndarray:
    c = np.cov(m, rowvar=False)
    c = np.atleast_2d(c)
    d = np.diag(np.diag(c))
    return (1.0 - shrink) * c + shrink * d + 1e-12 * np.eye(c.shape[0])


def _corr(cov: np.ndarray) -> np.ndarray:
    sd = np.sqrt(np.diag(cov))
    sd = np.where(sd > 0, sd, 1.0)
    out: np.ndarray = cov / np.outer(sd, sd)
    return out


def _scale(w: np.ndarray, names: list[str], total: float) -> dict[str, float]:
    w = np.clip(np.nan_to_num(w, nan=0.0), 0.0, None)
    s = float(w.sum())
    if s <= 0:
        w = np.ones_like(w)
        s = float(w.sum())
    return {n: float(total * x / s) for n, x in zip(names, w, strict=True)}


# --------------------------------------------------------------------------- hierarchical
def _linkage_order(corr: np.ndarray) -> list[int]:
    """Quasi-diagonalisation via single linkage on correlation distance (no scipy needed)."""
    n = corr.shape[0]
    dist = np.sqrt(np.clip(0.5 * (1.0 - corr), 0.0, None))
    clusters: list[list[int]] = [[i] for i in range(n)]
    while len(clusters) > 1:
        best = (float("inf"), 0, 1)
        for a in range(len(clusters)):
            for b in range(a + 1, len(clusters)):
                d = min(dist[i, j] for i in clusters[a] for j in clusters[b])
                if d < best[0]:
                    best = (d, a, b)
        _, a, b = best
        merged = clusters[a] + clusters[b]
        clusters = [c for k, c in enumerate(clusters) if k not in (a, b)] + [merged]
    return clusters[0]


def _cluster_var(cov: np.ndarray, idx: list[int]) -> float:
    sub = cov[np.ix_(idx, idx)]
    ivp = 1.0 / np.diag(sub)
    w = ivp / ivp.sum()
    return float(w @ sub @ w)


def hrp(ev: Sequence[Any], total: float) -> dict[str, float]:
    m, names = _matrix(ev)
    if len(names) == 1:
        return {names[0]: total}
    cov = _cov(m)
    order = _linkage_order(_corr(cov))
    w = np.ones(len(names))
    stack = [order]
    while stack:
        items = stack.pop()
        if len(items) <= 1:
            continue
        half = len(items) // 2
        left, right = items[:half], items[half:]
        vl, vr = _cluster_var(cov, left), _cluster_var(cov, right)
        alpha = 1.0 - vl / (vl + vr) if (vl + vr) > 0 else 0.5
        w[left] *= alpha
        w[right] *= 1.0 - alpha
        stack.extend([left, right])
    return _scale(w, names, total)


def herc(ev: Sequence[Any], total: float) -> dict[str, float]:
    """Equal risk contribution between the two halves at every split, inverse variance within."""
    m, names = _matrix(ev)
    if len(names) == 1:
        return {names[0]: total}
    cov = _cov(m)
    order = _linkage_order(_corr(cov))
    w = np.zeros(len(names))
    ivp = 1.0 / np.diag(cov)

    def _assign(items: list[int], budget: float) -> None:
        if len(items) == 1:
            w[items[0]] = budget
            return
        half = len(items) // 2
        left, right = items[:half], items[half:]
        rl, rr = np.sqrt(_cluster_var(cov, left)), np.sqrt(_cluster_var(cov, right))
        share = (1.0 / rl) / (1.0 / rl + 1.0 / rr) if rl > 0 and rr > 0 else 0.5
        _assign(left, budget * share)
        _assign(right, budget * (1.0 - share))
    _assign(order, 1.0)
    # within-leaf inverse variance is implicit at the leaves; tilt the raw weights by ivp share
    w = w * ivp / ivp.mean()
    return _scale(w, names, total)


# --------------------------------------------------------------------------- classical
def min_variance(ev: Sequence[Any], total: float) -> dict[str, float]:
    m, names = _matrix(ev)
    cov = _cov(m)
    w = np.linalg.solve(cov, np.ones(len(names)))
    for _ in range(10):                                  # long-only by iterative clipping
        neg = w < 0
        if not neg.any():
            break
        keep = ~neg
        w = np.zeros_like(w)
        sub = cov[np.ix_(keep, keep)]
        w[keep] = np.linalg.solve(sub, np.ones(int(keep.sum())))
    return _scale(w, names, total)


def mean_cvar(ev: Sequence[Any], total: float, alpha: float = 0.1) -> dict[str, float]:
    m, names = _matrix(ev)
    w = np.zeros(len(names))
    for j in range(len(names)):
        r = m[:, j]
        k = max(1, int(alpha * r.size))
        cvar = -float(np.sort(r)[:k].mean())
        w[j] = max(float(r.mean()), 0.0) / max(cvar, 1e-9)
    return _scale(w, names, total)


def _kelly(m: np.ndarray, mu: np.ndarray) -> np.ndarray:
    cov = _cov(m)
    out: np.ndarray = np.clip(np.linalg.solve(cov, mu), 0.0, None)
    return out


def kelly(ev: Sequence[Any], total: float) -> dict[str, float]:
    m, names = _matrix(ev)
    return _scale(_kelly(m, m.mean(axis=0)), names, total)


def robust_kelly(ev: Sequence[Any], total: float) -> dict[str, float]:
    m, names = _matrix(ev)
    se = m.std(axis=0, ddof=1) / np.sqrt(m.shape[0])
    return _scale(_kelly(m, m.mean(axis=0) - se), names, total)


def bayesian_kelly(ev: Sequence[Any], total: float, k: float = BAYES_K) -> dict[str, float]:
    m, names = _matrix(ev)
    n = m.shape[0]
    return _scale(_kelly(m, m.mean(axis=0) * (n / (n + k))), names, total)


CHALLENGERS: dict[str, Callable[[Sequence[Any], float], dict[str, float]]] = {
    "hrp": hrp, "herc": herc, "min_variance": min_variance, "mean_cvar": mean_cvar,
    "kelly": kelly, "robust_kelly": robust_kelly, "bayesian_kelly": bayesian_kelly,
}


def all_books(ev: Sequence[Any], total: float) -> dict[str, dict[str, float]]:
    """Every challenger that can be built on this evidence; a failure is skipped, not faked."""
    out: dict[str, dict[str, float]] = {}
    if not ev or total <= 0:
        return out
    for name, fn in CHALLENGERS.items():
        try:
            book = fn(ev, total)
            if book and all(np.isfinite(v) for v in book.values()):
                out[name] = book
        except (ValueError, np.linalg.LinAlgError, ZeroDivisionError):
            continue
    return out
