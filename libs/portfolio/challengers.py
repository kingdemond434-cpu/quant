"""Challenger allocators: the books anyone could have written, scored on the desk's own worlds.

The dynamic E[log W] allocator keeps its authority only while it beats every one of these at
equal total heat on the same sampled worlds (`allocator_proof.contest`). Riskfolio and skfolio
between them ship most of the public portfolio-construction canon; the desk needs the CANDIDATES,
not the libraries, so they are reimplemented here in numpy from `SleeveEvidence.daily_r`:

    hrp             hierarchical risk parity (correlation-distance tree, recursive bisection)
    herc            hierarchical equal-risk contribution, variance version
    nco             nested clustered optimization: min-variance within clusters, then across
    min_variance    long-only minimum variance on a shrunk covariance
    max_diversification  maximises the diversification ratio w'sigma / sqrt(w' Sigma w)
    mean_variance   Markowitz frontier point at the book's own budget, risk aversion stated
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
#: Risk aversion for the mean-variance challenger. STATED, not fitted: every book here is
#: rescaled to the same total heat, so lambda changes only the DIRECTION -- how hard the frontier
#: point leans toward return against variance -- and 5 is the textbook moderate value. Fitting it
#: to whatever beats the incumbent would make the baseline a second optimiser rather than the
#: obvious thing a competent person would have written.
MV_RISK_AVERSION = 5.0


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


def _clusters(order: list[int], k: int) -> list[list[int]]:
    """Cut the quasi-diagonalised order into `k` contiguous blocks.

    Legitimate because of what the ordering IS: single-linkage quasi-diagonalisation puts
    correlated names next to each other, so a contiguous block of it is a correlation cluster.
    This is the cut HRP already relies on implicitly at every bisection; NCO just needs it named.
    """
    k = max(1, min(int(k), len(order)))
    return [list(b) for b in np.array_split(np.asarray(order, dtype=int), k) if len(b)]


def nco(ev: Sequence[Any], total: float) -> dict[str, float]:
    """Nested clustered optimization: min-variance INSIDE each cluster, then ACROSS clusters.

    Lopez de Prado's answer to the instability of a single big optimisation: the covariance
    matrix's smallest eigenvalues are the noisiest, and inverting the whole thing at once lets
    that noise set the weights. Solving inside clusters and then between the cluster portfolios
    only ever inverts well-conditioned blocks. sqrt(n) clusters is the standard rule of thumb and
    is stated here rather than searched, for the same reason the other baselines are textbook.
    """
    m, names = _matrix(ev)
    if len(names) == 1:
        return {names[0]: total}
    cov = _cov(m)
    groups = _clusters(_linkage_order(_corr(cov)), int(np.sqrt(len(names))))
    w = np.zeros(len(names))
    inner: list[np.ndarray] = []
    for g in groups:
        sub = cov[np.ix_(g, g)]
        wi = _long_only_min_var(sub)
        inner.append(wi)
        w[g] = wi
    # The reduced problem: each cluster is one asset whose returns are its own min-var portfolio.
    red = np.zeros((len(groups), len(groups)))
    for a, ga in enumerate(groups):
        for b, gb in enumerate(groups):
            red[a, b] = float(inner[a] @ cov[np.ix_(ga, gb)] @ inner[b])
    red += 1e-12 * np.eye(len(groups))
    across = _long_only_min_var(red)
    for a, g in enumerate(groups):
        w[g] *= across[a]
    return _scale(w, names, total)


# --------------------------------------------------------------------------- classical
def _long_only_min_var(cov: np.ndarray) -> np.ndarray:
    """Minimum-variance weights summing to 1, long-only by iterative clipping."""
    n = cov.shape[0]
    if n == 1:
        return np.ones(1)
    w = np.linalg.solve(cov, np.ones(n))
    for _ in range(10):
        neg = w < 0
        if not neg.any():
            break
        keep = ~neg
        if not keep.any():
            return np.full(n, 1.0 / n)
        w = np.zeros_like(w)
        sub = cov[np.ix_(keep, keep)]
        w[keep] = np.linalg.solve(sub, np.ones(int(keep.sum())))
    s = float(w.sum())
    out: np.ndarray = w / s if s > 0 else np.full(n, 1.0 / n)
    return out


def min_variance(ev: Sequence[Any], total: float) -> dict[str, float]:
    m, names = _matrix(ev)
    return _scale(_long_only_min_var(_cov(m)), names, total)


def max_diversification(ev: Sequence[Any], total: float) -> dict[str, float]:
    """Maximise the diversification ratio DR(w) = w'sigma / sqrt(w' Sigma w).

    Choueifaty's portfolio, and the one baseline that asks the desk's own question directly: it
    maximises the ratio of the weighted-average volatility the book PAYS for to the volatility it
    actually RUNS, which is precisely "how much of this nominal heat is real independent risk".
    Solved as min-variance on the correlation matrix (the standard equivalence), then divided
    back by each sleeve's own volatility.
    """
    m, names = _matrix(ev)
    cov = _cov(m)
    sd = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    w = _long_only_min_var(_corr(cov)) / sd
    return _scale(w, names, total)


def mean_variance(ev: Sequence[Any], total: float, lam: float = MV_RISK_AVERSION,
                  ) -> dict[str, float]:
    """Markowitz: max mu'w - (lam/2) w' Sigma w at the book's own budget, long-only.

    NOT the same book as `kelly`. Kelly here is the unconstrained tangency direction
    Sigma^-1 mu; this is the frontier point under a BUDGET constraint, w = Sigma^-1(mu - g 1)/lam
    with g set so the weights sum to the budget -- so it mixes Sigma^-1 mu with the minimum
    variance leg Sigma^-1 1, and the two books differ whenever the sleeves' Sharpes differ from
    their inverse variances. That difference is the whole point of entering both.
    """
    m, names = _matrix(ev)
    cov = _cov(m)
    mu = m.mean(axis=0)
    n = len(names)
    ones = np.ones(n)
    a = np.linalg.solve(cov, mu)
    b = np.linalg.solve(cov, ones)
    budget = max(float(total), 1e-9)
    g = (float(a.sum()) - lam * budget) / max(float(b.sum()), 1e-12)
    w = (a - g * b) / max(lam, 1e-9)
    if not np.all(w >= 0):                                # long-only by iterative clipping
        keep = w > 0
        for _ in range(10):
            if not keep.any():
                return _scale(np.clip(mu, 0.0, None), names, total)
            sub = cov[np.ix_(keep, keep)]
            a2 = np.linalg.solve(sub, mu[keep])
            b2 = np.linalg.solve(sub, np.ones(int(keep.sum())))
            g2 = (float(a2.sum()) - lam * budget) / max(float(b2.sum()), 1e-12)
            w = np.zeros(n)
            w[keep] = (a2 - g2 * b2) / max(lam, 1e-9)
            if np.all(w >= -1e-15):
                break
            keep = w > 0
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
    "hrp": hrp, "herc": herc, "nco": nco, "min_variance": min_variance,
    "max_diversification": max_diversification, "mean_variance": mean_variance,
    "mean_cvar": mean_cvar,
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
