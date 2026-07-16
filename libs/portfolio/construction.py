"""Crypto sleeve-allocation primitives (portfolio construction).

Pure, tested functions that turn per-sleeve Sharpes + a correlation matrix into long-only sleeve
weights -- the capital-allocation step that sits above the sleeves. Deliberately small and numeric
(no pydantic models) so it wires straight onto crypto_portfolio.json. Reuses risk_parity_weights for
the RP variant. Everything is in-sample by construction; the caller is responsible for the
anti-overfit blend and for treating results as SHADOW until forward-validated.
"""

from __future__ import annotations

import numpy as np


def portfolio_sharpe(weights: np.ndarray, sharpes: np.ndarray, corr: np.ndarray) -> float:
    """Expected portfolio Sharpe for sleeve weights, treating each sleeve's vol as 1 (Sharpe space):
    S_p = wᵀμ / sqrt(wᵀ C w). This is the standard quadrature combine, correlation-aware."""
    w = np.asarray(weights, float)
    mu = np.asarray(sharpes, float)
    c = np.asarray(corr, float)
    var = float(w @ c @ w)
    return float(w @ mu) / (var ** 0.5) if var > 0 else 0.0


def max_sharpe_weights(sharpes: np.ndarray, corr: np.ndarray, *,
                       ridge: float = 1e-2, floor: float = 0.0) -> np.ndarray:
    """Long-only max-Sharpe sleeve weights, w proportional to inv(corr) @ Sharpes; negatives clipped
    to `floor`, renormalised. Ridge-regularised so a near-singular correlation stays invertible."""
    mu = np.asarray(sharpes, float)
    n = len(mu)
    c = np.asarray(corr, float) + ridge * np.eye(n)
    try:
        w = np.linalg.solve(c, mu)
    except np.linalg.LinAlgError:
        w = np.linalg.pinv(c) @ mu
    w = np.clip(w, floor, None)
    s = w.sum()
    return w / s if s > 0 else np.full(n, 1.0 / n)


def concentration_cap(weights: np.ndarray, cap: float = 0.35) -> np.ndarray:
    """Enforce a hard per-sleeve weight cap, redistributing the excess pro-rata to uncapped sleeves
    (the 35% concentration control). Iterates until every weight respects the cap."""
    w = np.asarray(weights, float).copy()
    if cap >= 1.0 or w.sum() <= 0:
        return w
    for _ in range(200):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        under = ~over
        pool = float(w[under].sum())
        if pool <= 0:
            break
        w[under] += excess * w[under] / pool
    return w


def marginal_sharpe(weights: np.ndarray, sharpes: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """Each sleeve's marginal contribution to portfolio Sharpe = S_p(with) - S_p(without), holding
    the other weights' proportions. The honest 'is this sleeve pulling its weight' number."""
    w = np.asarray(weights, float)
    full = portfolio_sharpe(w, sharpes, corr)
    out = np.zeros(len(w))
    for i in range(len(w)):
        w2 = w.copy()
        w2[i] = 0.0
        s = w2.sum()
        out[i] = full - (portfolio_sharpe(w2 / s, sharpes, corr) if s > 0 else 0.0)
    return out


def blend(w1: np.ndarray, w2: np.ndarray, alpha: float) -> np.ndarray:
    """Convex blend alpha*w1 + (1-alpha)*w2 -- the anti-overfit cap (e.g. 50% model / 50% equal)."""
    return alpha * np.asarray(w1, float) + (1.0 - alpha) * np.asarray(w2, float)


def turnover(old: dict[str, float], new: dict[str, float]) -> float:
    """One-way turnover between two weight books, 0.5 * sum|new-old| (drives the rebalance call)."""
    keys = set(old) | set(new)
    return 0.5 * sum(abs(new.get(k, 0.0) - old.get(k, 0.0)) for k in keys)
