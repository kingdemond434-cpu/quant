"""Dynamic latent factors, tail dependence and the four heats: what 20% nominal is REALLY made of.

    R_i = B_i f + eps_i

estimated on an exponentially weighted, shrunk covariance so B_t and Sigma_t move with the
market: when stress begins, edges that looked independent collapse onto one latent factor and
the desk must see N_eff fall BEFORE the drawdown teaches it. Alongside the average-state
picture the module carries the bad-state one -- tail dependence per pair and correlations on the
book's own worst days -- because capital should be sized on how the sleeves behave when the
book is hurting, not on how they behave on a Tuesday.

THE FOUR HEATS of a book h (fractions of equity at stop):

    nominal      sum |h_i|                                 what the floor and the ceiling count
    covariance   sqrt(h' rho h)                            the same variance as this many
                                                            perfectly correlated sleeves
    factor       sqrt(h' rho_factor h)                     rho implied by the k-factor model:
                                                            latent common exposure only
    tail         sqrt(h' rho_stress h)                     rho on the worst-decile days

    H_eff = max(covariance, factor, tail)

Between nominal / sqrt(N) (all independent) and nominal (one bet). `effective` reports all four
and N_eff under each, and `drift` says whether the correlation structure has moved away from its
long-run shape -- the change-point signal the allocator's crisis overlay should hear.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


def _ew_weights(n: int, halflife: float) -> np.ndarray:
    lam = 0.5 ** (1.0 / max(halflife, 1.0))
    w = lam ** np.arange(n - 1, -1, -1)
    out: np.ndarray = w / w.sum()
    return out


def ew_cov(m: np.ndarray, halflife: float = 60.0, shrink: float = 0.2) -> np.ndarray:
    w = _ew_weights(m.shape[0], halflife)
    mu = w @ m
    x = m - mu
    c = (x * w[:, None]).T @ x
    d = np.diag(np.diag(c))
    out: np.ndarray = (1.0 - shrink) * c + shrink * d + 1e-12 * np.eye(c.shape[0])
    return out


def corr_of(cov: np.ndarray) -> np.ndarray:
    sd = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    return cov / np.outer(sd, sd)


def factor_model(m: np.ndarray, k: int = 3, halflife: float = 60.0) -> dict[str, Any]:
    """PCA on the EW correlation: loadings B (N x k), factor variances, and the implied rho."""
    cov = ew_cov(m, halflife)
    rho = corr_of(cov)
    vals, vecs = np.linalg.eigh(rho)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    k = int(min(k, len(vals)))
    b = vecs[:, :k] * np.sqrt(np.clip(vals[:k], 0.0, None))
    common = b @ b.T
    spec = np.clip(1.0 - np.diag(common), 1e-6, None)
    rho_f = common + np.diag(spec)
    explained = float(np.clip(vals[:k], 0, None).sum() / max(vals.clip(0).sum(), 1e-12))
    return {"loadings": b, "factor_var": vals[:k], "rho_factor": rho_f, "rho": rho,
            "explained": explained, "cov": cov}


def stress_corr(m: np.ndarray, q: float = 0.1) -> tuple[np.ndarray, int]:
    """Correlation on the days the equal-weight book was in its worst `q` decile."""
    ew = m.mean(axis=1)
    k = max(5, int(q * m.shape[0]))
    idx = np.argsort(ew)[:k]
    sub = m[idx]
    sd = sub.std(axis=0)
    if sub.shape[0] < 5 or not np.all(sd > 0):
        return corr_of(ew_cov(m)), int(sub.shape[0])
    return np.corrcoef(sub, rowvar=False), int(sub.shape[0])


def tail_dependence(m: np.ndarray, q: float = 0.1) -> np.ndarray:
    """lambda_ij = P(R_i < q_i, R_j < q_j) / q -- 1.0 is perfect lower-tail dependence."""
    n = m.shape[1]
    thr = np.quantile(m, q, axis=0)
    below = m < thr
    out = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            out[i, j] = out[j, i] = float((below[:, i] & below[:, j]).mean() / q)
    return out


def n_eff(rho: np.ndarray, w: np.ndarray) -> float:
    w = w / w.sum() if w.sum() > 0 else np.full_like(w, 1.0 / max(w.size, 1))
    d = float(w @ rho @ w)
    return float(1.0 / d) if d > 0 else float(w.size)


def effective(ev: Sequence[Any], book: Mapping[str, float], *, k: int = 3,
              halflife: float = 60.0) -> dict[str, Any]:
    names = [e.name for e in ev if float(book.get(e.name, 0.0)) > 1e-6]
    if len(names) < 2:
        h1 = float(sum(book.values()))
        return {"nominal": h1, "covariance": h1, "factor": h1, "tail": h1, "effective": h1,
                "n_eff": {"covariance": 1.0, "factor": 1.0, "tail": 1.0}, "note": "single leg"}
    by = {e.name: e for e in ev}
    obs = min(int(by[n].daily_r.size) for n in names)
    m = np.stack([np.asarray(by[n].daily_r[-obs:], dtype=float) for n in names], axis=1)
    h = np.array([float(book[n]) for n in names])
    fm = factor_model(m, k=k, halflife=halflife)
    rho_s, n_stress = stress_corr(m)
    nominal = float(np.abs(h).sum())
    cov_heat = float(np.sqrt(max(float(h @ fm["rho"] @ h), 0.0)))
    fac_heat = float(np.sqrt(max(float(h @ fm["rho_factor"] @ h), 0.0)))
    tail_heat = float(np.sqrt(max(float(h @ rho_s @ h), 0.0)))
    td = tail_dependence(m)
    return {"nominal": round(nominal, 6), "covariance": round(cov_heat, 6),
            "factor": round(fac_heat, 6), "tail": round(tail_heat, 6),
            "effective": round(max(cov_heat, fac_heat, tail_heat), 6),
            "n_eff": {"covariance": round(n_eff(fm["rho"], h), 3),
                      "factor": round(n_eff(fm["rho_factor"], h), 3),
                      "tail": round(n_eff(rho_s, h), 3)},
            "factor_explained": round(fm["explained"], 4), "stress_days": n_stress,
            "max_tail_dependence": round(float(np.max(td - np.eye(len(names)))), 3),
            "top_loading": {names[i]: round(float(fm["loadings"][i, 0]), 3)
                            for i in np.argsort(-np.abs(fm["loadings"][:, 0]))[:5]},
            "rule": "H_eff = max(covariance, factor, tail) heat; 20% nominal on one latent "
                    "factor is 20% effective, 20% across independent mechanisms is far less"}


def drift(m: np.ndarray, recent: int = 40, halflife: float = 60.0) -> dict[str, Any]:
    """Has the correlation topology moved? Frobenius distance recent-vs-long-run, in units of
    the long-run's own between-window variation (a z-score a threshold can be set on)."""
    if m.shape[0] < 3 * recent:
        return {"z": None, "why": f"need {3 * recent} rows"}
    rho_long = corr_of(ew_cov(m, halflife=halflife))
    rho_now = np.corrcoef(m[-recent:], rowvar=False)
    dist_now = float(np.linalg.norm(rho_now - rho_long))
    past = []
    for end in range(recent, m.shape[0] - recent, recent):
        blk = m[end - recent:end]
        if np.all(blk.std(axis=0) > 0):
            past.append(float(np.linalg.norm(np.corrcoef(blk, rowvar=False) - rho_long)))
    if len(past) < 3:
        return {"z": None, "distance": dist_now, "why": "not enough past windows"}
    mu, sd = float(np.mean(past)), float(np.std(past, ddof=1))
    z = (dist_now - mu) / sd if sd > 0 else 0.0
    return {"z": round(z, 3), "distance": round(dist_now, 4), "baseline_mean": round(mu, 4),
            "verdict": ("STRUCTURE_SHIFTED" if z > 2.0 else "STABLE"), "windows": len(past)}
