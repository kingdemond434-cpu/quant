"""Random-matrix cleaning of a correlation matrix, for the allocator's cross-sleeve structure.

    "Random-matrix cleaning of the cert correlation matrix before the allocator solve"
                                                    -- GAP_MAP, Max-growth row (2026-11-13)

WHY. The allocator prices a few hundred sleeves on a few hundred to a few thousand common days.
With q = N / T well above 0.1 most of the sample correlation matrix's spectrum is noise: the
Marchenko-Pastur law says a matrix of PURE noise already spreads its eigenvalues over
[(1 - sqrt q)^2, (1 + sqrt q)^2], so a small eigenvalue that looks like a "hedge" direction is
usually an estimation artefact, and a growth solve leans hardest into exactly those directions
(Sigma^-1 amplifies the smallest eigenvalues). Every tier-1 desk that solves on a sample
covariance cleans it first (Laloux, Cizeau, Bouchaud & Potters 1999; Bun, Bouchaud & Potters
2017; Lopez de Prado 2020 ch. 2).

WHAT THIS GIVES. Four estimators of one correlation matrix, all pure numpy:

    sample    the pairwise-complete sample correlation, repaired to PSD (Higham 2002)
    clipped   eigenvalue clipping: every eigenvalue inside the fitted MP bulk is replaced by
              their mean, so the trace (= N) is preserved and the signal modes are untouched
    rie       the rotationally invariant estimator (Ledoit-Peche 2011, Bun-Bouchaud-Potters
              2016): the oracle-optimal nonlinear shrinkage of every eigenvalue, with the
              finite-N debiasing of Bun-Bouchaud-Potters 2017 eq. (35)
    lw        linear Ledoit-Wolf shrinkage to the identity, the textbook baseline the two
              nonlinear cleaners must beat

and the diagnostics a reader needs to trust one: the MP edge, the fitted noise variance sigma^2
(fitted to the bulk, not assumed 1, because a market mode eats variance from the bulk), the
number of signal eigenvalues above the edge, the market-mode share, and the effective number of
independent bets read off the cleaned spectrum (exp of the eigen-share entropy).

MISSING DATA. Sleeves have unequal histories. The correlation is pairwise-complete over days both
sleeves have, and T for the MP law is the MEDIAN pairwise overlap, which is the honest effective
sample length; pairs below `min_overlap` days are set to 0 (unknown is not correlated) and the
result is repaired to the nearest correlation matrix.

Nothing here touches capital. `research/allocator_structure_lab.py` measures whether a cleaned
matrix raises out-of-sample log growth before anything may consume it (GROWTH_GOVERNANCE Rule 1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Days two sleeves must share before their correlation is estimated at all.
MIN_OVERLAP = 60
#: Higham alternating-projection iterations for the nearest correlation matrix.
HIGHAM_ITERS = 100
EPS = 1e-10


# --------------------------------------------------------------------------- sample estimation
def pairwise_corr(x: np.ndarray, min_overlap: int = MIN_OVERLAP) -> tuple[np.ndarray, np.ndarray]:
    """(corr, overlap): the pairwise-complete Pearson correlation of the columns of `x` (T x N,
    NaN = no observation) and the day count each pair shares. A pair below `min_overlap` reads 0
    correlation -- an unmeasured pair is not evidence of co-movement."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 2:
        raise ValueError("x must be T x N")
    ok = np.isfinite(x)
    xz = np.where(ok, x, 0.0)
    okf = ok.astype(float)
    n_ij = okf.T @ okf
    s_i = xz.T @ okf                      # sum of x_i over days where j is also observed
    ss_i = (xz * xz).T @ okf
    s_ij = xz.T @ xz
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_i = s_i / n_ij
        mean_j = mean_i.T
        cov = s_ij / n_ij - mean_i * mean_j
        var_i = ss_i / n_ij - mean_i ** 2
        var_j = var_i.T
        corr = cov / np.sqrt(var_i * var_j)
    corr = np.where((n_ij >= min_overlap) & np.isfinite(corr), corr, 0.0)
    corr = np.clip(corr, -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    corr = 0.5 * (corr + corr.T)
    return corr, n_ij


def nearest_correlation(a: np.ndarray, iters: int = HIGHAM_ITERS, tol: float = 1e-9) -> np.ndarray:
    """Higham (2002) alternating projections with Dykstra's correction: the nearest (Frobenius)
    symmetric PSD matrix with unit diagonal."""
    y = 0.5 * (np.asarray(a, dtype=float) + np.asarray(a, dtype=float).T)
    ds = np.zeros_like(y)
    x = y.copy()
    for _ in range(iters):
        r = y - ds
        w, v = np.linalg.eigh(0.5 * (r + r.T))
        x = (v * np.clip(w, 0.0, None)) @ v.T
        ds = x - r
        y_new = x.copy()
        np.fill_diagonal(y_new, 1.0)
        if np.linalg.norm(y_new - y, "fro") < tol * max(1.0, np.linalg.norm(y, "fro")):
            y = y_new
            break
        y = y_new
    w, v = np.linalg.eigh(0.5 * (y + y.T))
    y = (v * np.clip(w, EPS, None)) @ v.T
    d = np.sqrt(np.clip(np.diag(y), EPS, None))
    out: np.ndarray = y / np.outer(d, d)
    np.fill_diagonal(out, 1.0)
    sym: np.ndarray = 0.5 * (out + out.T)
    return sym


# --------------------------------------------------------------------------- Marchenko-Pastur
def mp_edges(q: float, sigma2: float = 1.0) -> tuple[float, float]:
    """The Marchenko-Pastur support [lambda-, lambda+] for aspect ratio q = N/T (q <= 1 here;
    for q > 1 the same formula bounds the non-zero part)."""
    s = math.sqrt(max(q, 0.0))
    return sigma2 * (1.0 - s) ** 2, sigma2 * (1.0 + s) ** 2


def mp_pdf(lam: np.ndarray, q: float, sigma2: float = 1.0) -> np.ndarray:
    lo, hi = mp_edges(q, sigma2)
    lam = np.asarray(lam, dtype=float)
    inside = (lam > lo) & (lam < hi)
    out = np.zeros_like(lam)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[inside] = (np.sqrt((hi - lam[inside]) * (lam[inside] - lo))
                       / (2.0 * math.pi * q * sigma2 * lam[inside]))
    return out


def fit_sigma2(eig: np.ndarray, q: float, grid: int = 60) -> tuple[float, float]:
    """(sigma2, ks): the noise variance whose MP law best fits the bulk of `eig`, by minimising the
    Kolmogorov distance between the MP CDF and the empirical CDF of the eigenvalues below the
    candidate edge. sigma2 < 1 is the norm: a market mode removes variance from the bulk.
    Lopez de Prado (2020) fits the same quantity by KDE least squares; KS is bandwidth-free."""
    e = np.sort(np.asarray(eig, dtype=float))
    if e.size < 4 or not (q > 0):
        return 1.0, float("nan")
    best = (float("inf"), 1.0)
    for s2 in np.linspace(0.20, 1.0, grid):
        lo, hi = mp_edges(min(q, 1.0), s2)
        bulk = e[e <= hi * 1.05]
        if bulk.size < 4:
            continue
        xs = np.linspace(lo, hi, 400)
        pdf = mp_pdf(xs, min(q, 1.0), s2)
        cdf = np.cumsum(pdf)
        if cdf[-1] <= 0:
            continue
        cdf /= cdf[-1]
        emp = np.searchsorted(bulk, xs, side="right") / bulk.size
        ks = float(np.max(np.abs(emp - cdf)))
        if ks < best[0]:
            best = (ks, float(s2))
    return best[1], best[0]


# --------------------------------------------------------------------------- cleaners
def clip_eigen(corr: np.ndarray, q: float, sigma2: float | None = None
               ) -> tuple[np.ndarray, dict[str, Any]]:
    """Eigenvalue clipping (Laloux et al. 1999): noise eigenvalues -> their mean, trace kept."""
    w, v = np.linalg.eigh(corr)
    s2 = fit_sigma2(w, q)[0] if sigma2 is None else sigma2
    edge = mp_edges(min(q, 1.0), s2)[1]
    noise = w <= edge
    w2 = w.copy()
    if noise.any() and (~noise).any():
        w2[noise] = w[noise].mean()
    elif noise.all():
        w2[:] = w.mean()
    c = (v * w2) @ v.T
    d = np.sqrt(np.clip(np.diag(c), EPS, None))
    c = c / np.outer(d, d)
    np.fill_diagonal(c, 1.0)
    sym: np.ndarray = 0.5 * (c + c.T)
    return sym, {"sigma2": s2, "edge": edge, "n_signal": int((~noise).sum())}


def rie(corr: np.ndarray, t_eff: float) -> np.ndarray:
    """Rotationally invariant estimator with finite-size debiasing.

    For each sample eigenvalue lambda_k at z_k = lambda_k - i*eta (eta = N^-1/2), with the sample
    Stieltjes transform g(z) = 1/N sum_j 1/(z - lambda_j):

        xi_k = lambda_k / |1 - q + q z_k g(z_k)|^2                    (Ledoit-Peche / BBP 2016)

    then the debiasing of Bun-Bouchaud-Potters (2017) eq. (35): xi_k is multiplied by
    max(1, Gamma_k), Gamma_k = sigma^2 |1 - q + q z_k g_mp(z_k)|^2 / lambda_k, where g_mp is the
    Stieltjes transform of the fitted Marchenko-Pastur law -- it lifts only the smallest modes the
    finite-N RIE over-shrinks, which are exactly the ones Sigma^-1 leans on. Trace restored to N."""
    w, v = np.linalg.eigh(corr)
    n = w.size
    q = min(n / max(t_eff, 1.0), 0.95)
    eta = n ** -0.5
    z = w - 1j * eta
    diff = z[:, None] - w[None, :]
    g = (1.0 / diff).sum(axis=1) / n
    xi = w / np.abs(1.0 - q + q * z * g) ** 2
    s2, _ = fit_sigma2(w, q)
    # Stieltjes transform of MP with variance s2, branch with Im g_mp > 0 for Im z < 0 handled by
    # choosing the root that decays as 1/z.
    a = z
    disc = np.sqrt((a - s2 * (1 + q)) ** 2 - 4 * q * s2 * s2 + 0j)
    g_mp = (a - s2 * (1 - q) - disc) / (2 * q * s2 * a)
    g_alt = (a - s2 * (1 - q) + disc) / (2 * q * s2 * a)
    pick = np.abs(a * g_mp - 1.0) > np.abs(a * g_alt - 1.0)
    g_mp = np.where(pick, g_alt, g_mp)
    gamma = s2 * np.abs(1.0 - q + q * z * g_mp) ** 2 / np.where(w > EPS, w, EPS)
    # BBP 2017 eq. (35): xi_hat = xi * max(1, Gamma). Gamma > 1 only where the RIE pushed a
    # small mode below what pure MP noise would leave it, which is the over-shrinkage at fixed N.
    xi = xi * np.maximum(1.0, np.where(np.isfinite(gamma), gamma, 1.0))
    xi = np.clip(xi, EPS, None)
    xi *= n / xi.sum()
    c = (v * xi) @ v.T
    d = np.sqrt(np.clip(np.diag(c), EPS, None))
    c = c / np.outer(d, d)
    np.fill_diagonal(c, 1.0)
    sym: np.ndarray = 0.5 * (c + c.T)
    return sym


def ledoit_wolf_identity(x: np.ndarray, corr: np.ndarray) -> tuple[np.ndarray, float]:
    """Linear shrinkage of the correlation toward I with the Ledoit-Wolf (2004) intensity, computed
    on the standardised panel (NaN treated as 0 after standardising, which is the pairwise-
    complete approximation). Returns (matrix, delta)."""
    x = np.asarray(x, dtype=float)
    mu = np.nanmean(x, axis=0)
    sd = np.nanstd(x, axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    z = np.nan_to_num((x - mu) / sd, nan=0.0)
    t = z.shape[0]
    if t < 3:
        return corr, 1.0
    n = corr.shape[0]
    target = np.eye(n)
    zz = np.einsum("ti,tj->tij", z, z) if n <= 400 else None
    if zz is not None:
        pi = float(((zz - corr) ** 2).mean(axis=0).sum())
    else:
        pi = float(sum(((np.outer(r, r) - corr) ** 2).sum() for r in z) / t)
    gamma = float(((corr - target) ** 2).sum())
    delta = 0.0 if gamma <= 0 else max(0.0, min(1.0, (pi / gamma) / t))
    out = delta * target + (1.0 - delta) * corr
    return out, delta


# --------------------------------------------------------------------------- diagnostics
def effective_bets(corr: np.ndarray) -> float:
    """exp(entropy of the eigenvalue shares) -- Meucci's effective number of bets on the
    principal-component basis: N for an identity, 1 for a single common factor."""
    w = np.clip(np.linalg.eigvalsh(corr), 0.0, None)
    s = w.sum()
    if s <= 0:
        return float("nan")
    p = w[w > 0] / s
    return float(math.exp(-(p * np.log(p)).sum()))


def condition_number(corr: np.ndarray) -> float:
    w = np.linalg.eigvalsh(corr)
    return float(w.max() / max(w.min(), EPS))


@dataclass
class Cleaned:
    names: list[str]
    t_eff: float
    q: float
    sigma2: float
    ks: float
    mp_lower: float
    mp_upper: float
    n_signal: int
    market_share: float
    eigenvalues: list[float]
    sample: np.ndarray
    clipped: np.ndarray
    rie: np.ndarray
    lw: np.ndarray
    lw_delta: float
    notes: list[str] = field(default_factory=list)

    def matrix(self, kind: str) -> np.ndarray:
        return {"sample": self.sample, "clipped": self.clipped, "rie": self.rie,
                "lw": self.lw}[kind]

    def summary(self) -> dict[str, Any]:
        def r(v: float) -> float | None:
            return None if not math.isfinite(v) else round(float(v), 6)
        return {
            "n": len(self.names), "t_eff": r(self.t_eff), "q": r(self.q),
            "sigma2_bulk": r(self.sigma2), "mp_fit_ks": r(self.ks),
            "mp_lower": r(self.mp_lower), "mp_upper": r(self.mp_upper),
            "n_signal_eigen": self.n_signal,
            "noise_share_of_spectrum": r(1.0 - self.n_signal / max(len(self.names), 1)),
            "market_mode_share": r(self.market_share),
            "top_eigenvalues": [r(x) for x in self.eigenvalues[:10]],
            "effective_bets": {k: r(effective_bets(self.matrix(k)))
                               for k in ("sample", "clipped", "rie", "lw")},
            "condition_number": {k: r(condition_number(self.matrix(k)))
                                 for k in ("sample", "clipped", "rie", "lw")},
            "lw_delta": r(self.lw_delta),
            "notes": self.notes,
        }


def clean(x: np.ndarray, names: list[str], min_overlap: int = MIN_OVERLAP) -> Cleaned:
    """Every estimator on one T x N panel (NaN = no observation)."""
    raw, overlap = pairwise_corr(x, min_overlap)
    notes: list[str] = []
    n = raw.shape[0]
    iu = np.triu_indices(n, 1)
    ov = overlap[iu]
    t_eff = float(np.median(ov)) if ov.size else float(np.sum(np.isfinite(x[:, 0])))
    unmeasured = int((ov < min_overlap).sum()) if ov.size else 0
    if unmeasured:
        notes.append(f"{unmeasured} of {ov.size} pairs below {min_overlap} common days read 0")
    sample = nearest_correlation(raw)
    q = n / max(t_eff, 1.0)
    if q >= 1.0:
        notes.append(f"q = N/T = {q:.2f} >= 1: the sample matrix is singular; only the cleaned "
                     "estimators are usable")
    w = np.sort(np.linalg.eigvalsh(sample))[::-1]
    s2, ks = fit_sigma2(w, min(q, 0.95))
    lo, hi = mp_edges(min(q, 0.95), s2)
    clipped, info = clip_eigen(sample, min(q, 0.95), s2)
    r = rie(sample, t_eff)
    lw, delta = ledoit_wolf_identity(x, sample)
    return Cleaned(names=list(names), t_eff=t_eff, q=q, sigma2=s2, ks=ks, mp_lower=lo,
                   mp_upper=hi, n_signal=int(info["n_signal"]),
                   market_share=float(w[0] / max(w.sum(), EPS)) if w.size else float("nan"),
                   eigenvalues=[float(v) for v in w], sample=sample, clipped=clipped, rie=r,
                   lw=lw, lw_delta=delta, notes=notes)


def to_cov(corr: np.ndarray, sd: np.ndarray) -> np.ndarray:
    sd = np.asarray(sd, dtype=float)
    out: np.ndarray = corr * np.outer(sd, sd)
    return out
