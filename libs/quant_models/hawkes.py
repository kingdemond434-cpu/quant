"""EXPONENTIAL-KERNEL HAWKES PROCESSES -- the one implementation every desk and thread uses.

    lambda_d(t) = mu_d + sum_j alpha[d, j] * sum_{t_l < t, k_l = j} exp(-beta * (t - t_l))

Univariate is the D = 1 case of the marked (multivariate) model; every public function takes
`marks=None` for it. One decay `beta` is shared by all (target, source) pairs: it keeps the
model identified on the short, sparse event sets a desk actually holds (a news family over a
year, payroll releases over a decade) and makes the excitation half-life ONE number per family.

WHAT IS HERE
  log_likelihood        the exact log-likelihood (recursive excitation, closed-form compensator)
  fit                   maximum likelihood: L-BFGS-B with the analytic gradient when scipy is
                        importable, warm-started by EM; without scipy, EM profiled over beta by a
                        log-grid + golden-section search (the robust fallback). Both maximise the
                        same likelihood and agree to optimiser tolerance (tested).
  intensity_at          lambda at ARBITRARY instants using only events STRICTLY BEFORE each
                        instant -- the PIT form a series row may carry
  compensator_at        the integrated intensity, for time rescaling
  time_rescaling_residuals / ks_exponential / goodness_of_fit
                        Papangelopoulou/Ogata residual analysis: under the fitted model the
                        compensator increments between events are i.i.d. Exp(1); KS against it
  simulate              Ogata thinning, for tests and for parametric nulls
  HawkesParams          branching matrix, branching ratio (spectral radius), half-life,
                        stationary intensity

WHAT THE OLDER HAWKES CODE IN THIS TREE IS, AND WHY THIS DOES NOT WRAP IT
  libs/research/overlays.hawkes_process        an exponential FILTER of a value series with a
                                               fixed kappa (an EWMA with no likelihood, no
                                               baseline, no branching ratio): not an estimator.
  libs/autodiscovery/generators._hawkes_vol_expansion
                                               the same fixed-decay recursion over threshold
                                               events inside a trading rule: not an estimator.
  libs/models/classical_baselines.HawkesIntensity
                                               a 5x40 likelihood GRID, univariate; it now
                                               delegates to `fit` here (same state keys).
  desks/mt5/research/mathlab/scientists._hawkes
                                               a Nelder-Mead univariate fit; its bar series
                                               counts an event AT bar t in lambda(t) (events
                                               <= t, not < t) -- left in place for its owner,
                                               noted here so nobody copies that PIT choice.

TIME UNITS are the caller's (hours are the desk's convention for news). Internally times are
rescaled so the mean inter-event gap is 1, which conditions the optimiser; parameters come back
in the caller's units. Ties: events at the same instant excite each other in sort order -- a
caller that means one event (several headlines of one release) must de-duplicate first.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
LN2 = math.log(2.0)
_EPS = 1e-12


# ============================================================================== parameters
@dataclass(frozen=True)
class HawkesParams:
    """mu (D,), alpha (D, D) with alpha[d, j] the jump in lambda_d per event of kind j, beta."""

    mu: np.ndarray
    alpha: np.ndarray
    beta: float

    @classmethod
    def univariate(cls, mu: float, alpha: float, beta: float) -> HawkesParams:
        return cls(np.array([float(mu)]), np.array([[float(alpha)]]), float(beta))

    @property
    def dims(self) -> int:
        return int(self.mu.size)

    @property
    def branching_matrix(self) -> np.ndarray:
        """Expected number of kind-d children of one kind-j event: alpha / beta."""
        return np.asarray(self.alpha / self.beta, dtype=float)

    @property
    def branching_ratio(self) -> float:
        """Spectral radius of the branching matrix (alpha / beta when D = 1); < 1 is stationary."""
        m = self.branching_matrix
        if m.shape == (1, 1):
            return float(m[0, 0])
        return float(np.max(np.abs(np.linalg.eigvals(m))))

    @property
    def half_life(self) -> float:
        """Time for one event's excitation to halve: ln 2 / beta, in the caller's units."""
        return LN2 / self.beta

    def stationary_intensity(self) -> np.ndarray | None:
        """(I - alpha/beta)^-1 mu, or None when the process is not stationary."""
        if self.branching_ratio >= 1.0:
            return None
        return np.asarray(np.linalg.solve(np.eye(self.dims) - self.branching_matrix, self.mu),
                          dtype=float)

    def to_dict(self) -> dict[str, Any]:
        stat = self.stationary_intensity()
        return {"mu": [float(x) for x in self.mu],
                "alpha": [[float(x) for x in row] for row in self.alpha],
                "beta": float(self.beta), "branching_ratio": round(self.branching_ratio, 6),
                "half_life": float(self.half_life),
                "stationary_intensity": None if stat is None else [float(x) for x in stat]}


@dataclass(frozen=True)
class HawkesFit:
    params: HawkesParams
    loglik: float
    poisson_loglik: float
    n_events: int
    t0: float
    t_end: float
    method: str
    converged: bool
    counts: tuple[int, ...] = field(default_factory=tuple)

    @property
    def lr_stat(self) -> float:
        """2 x (Hawkes - homogeneous Poisson) log-likelihood: evidence of self-excitation."""
        return 2.0 * (self.loglik - self.poisson_loglik)

    @property
    def aic(self) -> float:
        d = self.params.dims
        return 2.0 * (d + d * d + 1) - 2.0 * self.loglik

    def to_dict(self) -> dict[str, Any]:
        return {"status": "MEASURED", **self.params.to_dict(), "loglik": round(self.loglik, 6),
                "poisson_loglik": round(self.poisson_loglik, 6),
                "lr_stat": round(self.lr_stat, 6), "aic": round(self.aic, 6),
                "n_events": self.n_events, "counts": list(self.counts), "t0": self.t0,
                "t_end": self.t_end, "method": self.method, "converged": self.converged}


# ============================================================================== input hygiene
def _prep(times: Sequence[float] | np.ndarray, marks: Sequence[int] | np.ndarray | None,
          n_dims: int | None = None) -> tuple[np.ndarray, np.ndarray, int]:
    t = np.asarray(times, dtype=float).ravel()
    k = (np.zeros(t.size, dtype=np.int64) if marks is None
         else np.asarray(marks, dtype=np.int64).ravel())
    if k.size != t.size:
        raise ValueError(f"{t.size} times but {k.size} marks")
    if t.size and not np.all(np.isfinite(t)):
        raise ValueError("event times must be finite")
    if k.size and int(k.min()) < 0:
        raise ValueError("marks must be non-negative integers")
    d = int(n_dims if n_dims is not None else (int(k.max()) + 1 if k.size else 1))
    if k.size and int(k.max()) >= d:
        raise ValueError(f"a mark {int(k.max())} is outside n_dims={d}")
    order = np.argsort(t, kind="mergesort")
    return t[order], k[order], d


def _excitation(times: np.ndarray, marks: np.ndarray, beta: float, d: int,
                with_lag: bool = False) -> tuple[np.ndarray, np.ndarray | None]:
    """R[i, j] = sum_{l < i, k_l = j} exp(-beta (t_i - t_l)) and, if asked,
    S[i, j] = sum_{l < i, k_l = j} (t_i - t_l) exp(-beta (t_i - t_l)) (the beta-derivative)."""
    n = times.size
    r_out = np.zeros((n, d), dtype=float)
    s_out = np.zeros((n, d), dtype=float) if with_lag else None
    if n < 2:
        return r_out, s_out
    gaps = np.diff(times)
    dec = np.exp(-beta * gaps).tolist()
    gl = gaps.tolist()
    for j in range(d):
        ind = (marks == j).astype(float).tolist()
        r = 0.0
        s = 0.0
        col_r = [0.0] * n
        col_s = [0.0] * n
        for i in range(1, n):
            r = dec[i - 1] * (r + ind[i - 1])
            col_r[i] = r
            if with_lag:
                s = dec[i - 1] * s + gl[i - 1] * r
                col_s[i] = s
        r_out[:, j] = col_r
        if s_out is not None:
            s_out[:, j] = col_s
    return r_out, s_out


def _tail(times: np.ndarray, marks: np.ndarray, beta: float, t_end: float, d: int
          ) -> tuple[np.ndarray, np.ndarray]:
    """G_j = sum_{k_l = j} (1 - exp(-beta (T - t_l))) and dG_j/dbeta."""
    lag = t_end - times
    e = np.exp(-beta * lag)
    g = np.bincount(marks, weights=1.0 - e, minlength=d).astype(float)
    dg = np.bincount(marks, weights=lag * e, minlength=d).astype(float)
    return g, dg


# ============================================================================== likelihood
def log_likelihood(params: HawkesParams, times: Sequence[float] | np.ndarray,
                   t_end: float, marks: Sequence[int] | np.ndarray | None = None,
                   t0: float = 0.0) -> float:
    """Exact log-likelihood of the events on [t0, t_end] under `params`."""
    t, k, d = _prep(times, marks, params.dims)
    if t.size and (t[0] < t0 or t[-1] > t_end):
        raise ValueError("events must lie inside [t0, t_end]")
    return _loglik(params.mu, params.alpha, params.beta, t, k, d, t0, t_end)


def _loglik(mu: np.ndarray, alpha: np.ndarray, beta: float, t: np.ndarray, k: np.ndarray,
            d: int, t0: float, t_end: float) -> float:
    r, _ = _excitation(t, k, beta, d)
    lam = mu[k] + np.einsum("ij,ij->i", alpha[k], r)
    if np.any(lam <= 0):
        return -math.inf
    g, _ = _tail(t, k, beta, t_end, d)
    comp = float(mu.sum()) * (t_end - t0) + float(alpha.sum(axis=0) @ g) / beta
    return float(np.log(lam).sum()) - comp


def _poisson_loglik(k: np.ndarray, d: int, span: float) -> float:
    counts = np.bincount(k, minlength=d).astype(float)
    pos = counts > 0
    return float(np.sum(counts[pos] * np.log(counts[pos] / span)) - counts.sum())


# ============================================================================== estimation
def _em(t: np.ndarray, k: np.ndarray, d: int, beta: float, span: float, t_end: float,
        mu: np.ndarray, alpha: np.ndarray, n_iter: int = 200, tol: float = 1e-8
        ) -> tuple[np.ndarray, np.ndarray, float]:
    """EM for mu, alpha at fixed beta (branching-structure latent variables)."""
    r, _ = _excitation(t, k, beta, d)
    g, _ = _tail(t, k, beta, t_end, d)
    denom = np.where(g > 0, g / beta, np.inf)
    prev = -math.inf
    ll = -math.inf
    for _ in range(n_iter):
        contrib = alpha[k] * r
        lam = mu[k] + contrib.sum(axis=1)
        lam = np.maximum(lam, _EPS)
        ll = float(np.log(lam).sum()) - float(mu.sum()) * span - float(
            alpha.sum(axis=0) @ np.where(np.isfinite(denom), denom, 0.0))
        bg = mu[k] / lam
        num = np.zeros((d, d), dtype=float)
        np.add.at(num, k, contrib / lam[:, None])
        mu = np.maximum(np.bincount(k, weights=bg, minlength=d).astype(float) / span, _EPS)
        alpha = num / denom[None, :]
        if abs(ll - prev) <= tol * (1.0 + abs(ll)):
            break
        prev = ll
    return mu, alpha, _loglik(mu, alpha, beta, t, k, d, t_end - span, t_end)


def _profile_beta(t: np.ndarray, k: np.ndarray, d: int, span: float, t_end: float,
                  lo: float, hi: float, grid: int = 14, golden_iter: int = 30,
                  em_iter: int = 300) -> tuple[np.ndarray, np.ndarray, float, float]:
    """max over beta of the EM-maximised likelihood: log-grid, then golden section."""
    counts = np.bincount(k, minlength=d).astype(float)
    mu0 = np.maximum(counts / span * 0.5, _EPS)
    best: tuple[float, float, np.ndarray, np.ndarray] | None = None
    cache: dict[float, tuple[float, np.ndarray, np.ndarray]] = {}

    def score(log_beta: float) -> float:
        if log_beta in cache:
            return cache[log_beta][0]
        beta = math.exp(log_beta)
        a0 = np.full((d, d), 0.25 * beta / d)
        mu, alpha, ll = _em(t, k, d, beta, span, t_end, mu0.copy(), a0, n_iter=em_iter)
        cache[log_beta] = (ll, mu, alpha)
        return ll

    xs = np.linspace(math.log(lo), math.log(hi), grid)
    vals = [score(float(x)) for x in xs]
    i = int(np.nanargmax(vals))
    a = float(xs[max(0, i - 1)])
    b = float(xs[min(grid - 1, i + 1)])
    phi = (math.sqrt(5.0) - 1.0) / 2.0
    c, e = b - phi * (b - a), a + phi * (b - a)
    fc, fe = score(c), score(e)
    for _ in range(golden_iter):
        if fc > fe:
            b, e, fe = e, c, fc
            c = b - phi * (b - a)
            fc = score(c)
        else:
            a, c, fc = c, e, fe
            e = a + phi * (b - a)
            fe = score(e)
        if b - a < 1e-4:
            break
    for lb, (ll, mu, alpha) in cache.items():
        if best is None or ll > best[0]:
            best = (ll, lb, mu, alpha)
    assert best is not None
    return best[2], best[3], math.exp(best[1]), best[0]


def _neg_ll_grad(x: np.ndarray, t: np.ndarray, k: np.ndarray, d: int, span: float,
                 t_end: float) -> tuple[float, np.ndarray]:
    mu = x[:d]
    alpha = x[d:d + d * d].reshape(d, d)
    beta = math.exp(float(x[-1]))
    r, s = _excitation(t, k, beta, d, with_lag=True)
    assert s is not None
    lam = mu[k] + np.einsum("ij,ij->i", alpha[k], r)
    lam = np.maximum(lam, _EPS)
    inv = 1.0 / lam
    g, dg = _tail(t, k, beta, t_end, d)
    colsum = alpha.sum(axis=0)
    ll = float(np.log(lam).sum()) - float(mu.sum()) * span - float(colsum @ g) / beta
    g_mu = np.bincount(k, weights=inv, minlength=d).astype(float) - span
    g_alpha = np.zeros((d, d), dtype=float)
    np.add.at(g_alpha, k, r * inv[:, None])
    g_alpha -= (g / beta)[None, :]
    dlam_dbeta = -np.einsum("ij,ij->i", alpha[k], s)
    g_beta = float((dlam_dbeta * inv).sum()) - float(colsum @ ((beta * dg - g) / beta ** 2))
    grad = np.concatenate([g_mu, g_alpha.ravel(), [g_beta * beta]])
    return -ll, -grad


def fit(times: Sequence[float] | np.ndarray, *, t_end: float | None = None,
        t0: float | None = None, marks: Sequence[int] | np.ndarray | None = None,
        n_dims: int | None = None, beta_bounds: tuple[float, float] | None = None,
        min_events: int = 10, use_scipy: bool = True) -> HawkesFit | dict[str, Any]:
    """Maximum-likelihood fit on [t0, t_end] (defaults: first and last event).

    Returns a HawkesFit, or {"status": "UNMEASURED", "why": ...} when the sample cannot carry
    the model (fewer than `min_events` events, or no span). `beta_bounds` are in the caller's
    time units (decay rates, 1/time); default half-lives from 1/100 to 100 mean gaps."""
    t, k, d = _prep(times, marks, n_dims)
    if t.size < max(2, min_events):
        return {"status": UNMEASURED, "why": f"{t.size} events < {max(2, min_events)}"}
    start = float(t[0] if t0 is None else t0)
    end = float(t[-1] if t_end is None else t_end)
    if not end > start or t[0] < start or t[-1] > end:
        return {"status": UNMEASURED, "why": "the observation window has no span or excludes "
                                              "events"}
    scale = (end - start) / t.size
    ts = (t - start) / scale
    span = (end - start) / scale
    if beta_bounds is None:
        lo, hi = LN2 / 100.0, LN2 * 100.0
    else:
        lo, hi = float(beta_bounds[0]) * scale, float(beta_bounds[1]) * scale
    if not 0 < lo < hi:
        raise ValueError(f"bad beta_bounds {beta_bounds}")
    method = "em_profile_golden"
    converged = True
    scipy_ok = False
    if use_scipy:
        try:
            from scipy.optimize import minimize
            scipy_ok = True
        except Exception:       # pragma: no cover - scipy is installed on both boxes
            scipy_ok = False
    if scipy_ok:
        mu, alpha, beta, ll = _profile_beta(ts, k, d, span, span, lo, hi, grid=10,
                                            golden_iter=0, em_iter=60)
        x0 = np.concatenate([mu, alpha.ravel(), [math.log(beta)]])
        bounds = ([(1e-10, None)] * d + [(0.0, None)] * (d * d)
                  + [(math.log(lo), math.log(hi))])
        res = minimize(_neg_ll_grad, x0, args=(ts, k, d, span, span), jac=True,
                       method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 500, "ftol": 1e-12, "gtol": 1e-7})
        x = np.asarray(res.x, dtype=float)
        cand_ll = -float(res.fun)
        if math.isfinite(cand_ll) and cand_ll >= ll - 1e-9:
            mu, alpha, beta, ll = (x[:d].copy(), x[d:d + d * d].reshape(d, d).copy(),
                                   math.exp(float(x[-1])), cand_ll)
        method = "lbfgsb_analytic_gradient"
        converged = bool(res.success)
    else:
        mu, alpha, beta, ll = _profile_beta(ts, k, d, span, span, lo, hi)
    params = HawkesParams(mu=np.asarray(mu, dtype=float) / scale,
                          alpha=np.asarray(alpha, dtype=float) / scale, beta=beta / scale)
    # log-likelihood in the caller's units: each event's log-density shifts by -log(scale)
    ll_units = float(ll) - t.size * math.log(scale)
    pois = _poisson_loglik(k, d, end - start)
    return HawkesFit(params=params, loglik=ll_units, poisson_loglik=pois, n_events=int(t.size),
                     t0=start, t_end=end, method=method, converged=converged,
                     counts=tuple(int(c) for c in np.bincount(k, minlength=d)))


# ============================================================================== PIT intensity
def intensity_at(params: HawkesParams, times: Sequence[float] | np.ndarray,
                 eval_times: Sequence[float] | np.ndarray,
                 marks: Sequence[int] | np.ndarray | None = None) -> np.ndarray:
    """lambda_d(tau) for every tau, from events STRICTLY BEFORE tau only. Shape (M, D).

    An event stamped exactly at tau is not in lambda(tau): a row available at tau cannot have
    reacted to something knowable only at tau."""
    t, k, d = _prep(times, marks, params.dims)
    tau = np.asarray(eval_times, dtype=float).ravel()
    out = np.tile(params.mu, (tau.size, 1)).astype(float)
    if t.size == 0 or tau.size == 0:
        return out
    r, _ = _excitation(t, k, params.beta, d)
    after = r.copy()
    after[np.arange(t.size), k] += 1.0           # state just after each event
    idx = np.searchsorted(t, tau, side="left")   # number of events < tau
    has = idx > 0
    last = idx[has] - 1
    decayed = after[last] * np.exp(-params.beta * (tau[has] - t[last]))[:, None]
    out[has] += decayed @ params.alpha.T
    return out


def compensator_at(params: HawkesParams, times: Sequence[float] | np.ndarray,
                   eval_times: Sequence[float] | np.ndarray,
                   marks: Sequence[int] | np.ndarray | None = None, t0: float = 0.0
                   ) -> np.ndarray:
    """Lambda_d(t0, tau) = integral of lambda_d over [t0, tau], events strictly before tau."""
    t, k, d = _prep(times, marks, params.dims)
    tau = np.asarray(eval_times, dtype=float).ravel()
    out = np.outer(tau - t0, params.mu)
    if t.size == 0:
        return out
    r, _ = _excitation(t, k, params.beta, d)
    after = r.copy()
    after[np.arange(t.size), k] += 1.0
    cum = np.zeros((t.size, d), dtype=float)
    np.add.at(cum, (np.arange(t.size), k), 1.0)
    cum = np.cumsum(cum, axis=0)                 # counts of each kind up to and incl. event i
    idx = np.searchsorted(t, tau, side="left")
    has = idx > 0
    last = idx[has] - 1
    rem = after[last] * np.exp(-params.beta * (tau[has] - t[last]))[:, None]
    out[has] += ((cum[last] - rem) / params.beta) @ params.alpha.T
    return out


# ============================================================================== goodness of fit
def time_rescaling_residuals(params: HawkesParams, times: Sequence[float] | np.ndarray,
                             marks: Sequence[int] | np.ndarray | None = None, t0: float = 0.0
                             ) -> dict[int, np.ndarray]:
    """Per kind d, the compensator increments between successive kind-d events (from t0).
    Under the true model they are i.i.d. Exp(1) (the time-rescaling theorem)."""
    t, k, d = _prep(times, marks, params.dims)
    lam_int = compensator_at(params, t, t, k, t0=t0)
    out: dict[int, np.ndarray] = {}
    for j in range(d):
        sel = k == j
        vals = lam_int[sel, j]
        out[j] = np.diff(np.concatenate([[0.0], vals]))
    return out


def ks_exponential(x: Sequence[float] | np.ndarray) -> tuple[float | None, float | None]:
    """KS statistic of `x` against Exp(1) and its p-value (scipy, else the Kolmogorov series)."""
    a = np.sort(np.asarray(x, dtype=float))
    a = a[np.isfinite(a)]
    n = a.size
    if n < 5:
        return None, None
    cdf = 1.0 - np.exp(-np.maximum(a, 0.0))
    i = np.arange(1, n + 1)
    stat = float(max(np.max(i / n - cdf), np.max(cdf - (i - 1) / n)))
    try:
        from scipy.stats import kstwo
        p = float(kstwo.sf(stat, n))
    except Exception:           # pragma: no cover - fallback when scipy.stats is absent
        lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * stat
        p = float(min(1.0, max(0.0, 2.0 * sum((-1) ** (j - 1) * math.exp(-2.0 * j * j * lam * lam)
                                              for j in range(1, 101)))))
    return stat, p


def goodness_of_fit(params: HawkesParams, times: Sequence[float] | np.ndarray,
                    marks: Sequence[int] | np.ndarray | None = None, t0: float = 0.0
                    ) -> dict[str, Any]:
    """Time-rescaling residuals per kind and pooled: KS stat/p vs Exp(1), residual mean."""
    res = time_rescaling_residuals(params, times, marks, t0=t0)
    per: dict[str, Any] = {}
    for j, r in res.items():
        stat, p = ks_exponential(r)
        per[str(j)] = {"n": int(r.size), "ks_stat": stat, "ks_p": p,
                       "mean": float(r.mean()) if r.size else None}
    pooled = np.concatenate(list(res.values())) if res else np.array([])
    stat, p = ks_exponential(pooled)
    return {"status": "MEASURED" if stat is not None else UNMEASURED, "ks_stat": stat,
            "ks_p": p, "n": int(pooled.size), "per_kind": per,
            "rule": "residuals are i.i.d. Exp(1) under the fitted model; a small ks_p rejects it"}


# ============================================================================== simulation
def simulate(params: HawkesParams, t_end: float, *, t0: float = 0.0, seed: int = 0,
             max_events: int = 1_000_000) -> tuple[np.ndarray, np.ndarray]:
    """Ogata thinning. Returns (times, marks). Exact: between events every lambda only decays,
    so the intensity just after the last event bounds it until the next candidate."""
    rng = np.random.default_rng(seed)
    d = params.dims
    mu, alpha, beta = params.mu, params.alpha, params.beta
    state = np.zeros(d, dtype=float)
    t = float(t0)
    ts: list[float] = []
    ks: list[int] = []
    while len(ts) < max_events:
        bound = float((mu + alpha @ state).sum())
        if bound <= 0:
            break
        w = float(rng.exponential(1.0 / bound))
        t += w
        if t >= t_end:
            break
        state *= math.exp(-beta * w)
        lam = mu + alpha @ state
        u = float(rng.uniform()) * bound
        cum = np.cumsum(lam)
        if u <= cum[-1]:
            j = int(np.searchsorted(cum, u))
            ts.append(t)
            ks.append(j)
            state[j] += 1.0
    return np.asarray(ts, dtype=float), np.asarray(ks, dtype=np.int64)
