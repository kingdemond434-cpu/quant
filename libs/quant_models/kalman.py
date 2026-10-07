"""LINEAR-GAUSSIAN STATE SPACE -- the one Kalman filter/smoother every desk and thread uses.

    y_t     = Z_t a_t + d_t + eps_t,     eps_t ~ N(0, H_t)          (p observations)
    a_{t+1} = T_t a_t + eta_t,           eta_t ~ N(0, Q_t)          (m states)

Any of Z, H, T, Q may be constant ((p, m), (p, p), (m, m), (m, m)) or time-varying (a leading
axis of length n). A NaN in y is a MISSING observation: the filter updates on the observed
components only (all missing = pure prediction), which is how mixed-frequency panels (a monthly
print among daily market series) live on one daily clock.

WHAT IS HERE
  kalman_filter       predicted state a_{t|t-1}, filtered a_{t|t}, their covariances, one-step-
                      ahead forecasts y_hat_{t|t-1}, innovations v_t and their covariances F_t,
                      and the exact Gaussian log-likelihood by prediction-error decomposition
                      (Joseph-form covariance update; the first `n_diffuse` observed steps are
                      left out of the likelihood -- approximate diffuse initialisation).
  rts_smoother        Rauch-Tung-Striebel smoothed states. RESEARCH ONLY: a smoothed value at t
                      uses observations after t and must never be written to a PIT series.
  local_level         the random-walk-plus-noise model
  tvp_regression      time-varying-coefficient regression, coefficients random walks
  fit_mle             MLE of variance parameters (log-parameterised) by the prediction-error
                      decomposition: scipy L-BFGS-B when importable, else the repository's
                      dependency-free Nelder-Mead (`libs.models.classical_baselines`)
  fit_local_level / fit_tvp_regression
                      the two models' MLE wrappers

THE OLDER KALMAN CODE IN THIS TREE. `libs/tiers/cross_science.kalman_lab` is a hand-rolled
scalar local-level filter with a FIXED q and the sample variance as R (a lab probe of innovation
autocorrelation, no likelihood and no smoother); it is a consumer, not an estimator, and could
call `local_level` + `kalman_filter` here. Left in place for its owner.

PIT. Everything the filter returns at index t (a_pred, y_hat, v, F, a_filt) uses y_0..y_t only;
a_pred and y_hat use y_0..y_{t-1}. Hyperparameters fitted by `fit_mle` on a sample are a
look-ahead for any t inside that sample: a PIT engine fits them on a TRAINING window and filters
forward with them frozen (or refits on expanding windows), and says which.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

UNMEASURED = "UNMEASURED"
LOG2PI = math.log(2.0 * math.pi)


@dataclass(frozen=True)
class StateSpace:
    Z: np.ndarray
    H: np.ndarray
    T: np.ndarray
    Q: np.ndarray
    a0: np.ndarray
    P0: np.ndarray
    d: np.ndarray | None = None
    n_diffuse: int = 0

    @property
    def m(self) -> int:
        return int(self.a0.size)


@dataclass(frozen=True)
class FilterResult:
    a_pred: np.ndarray      # (n, m)   a_{t|t-1}
    P_pred: np.ndarray      # (n, m, m)
    a_filt: np.ndarray      # (n, m)   a_{t|t}
    P_filt: np.ndarray      # (n, m, m)
    y_hat: np.ndarray       # (n, p)   one-step-ahead forecast of y_t
    v: np.ndarray           # (n, p)   innovations (NaN where missing)
    F: np.ndarray           # (n, p, p) innovation covariance (NaN where missing)
    loglik: float
    nobs: int

    def innovation_z(self) -> np.ndarray:
        """v_t / sqrt(F_t[i, i]) per component: N(0, 1) under the model."""
        diag = np.diagonal(self.F, axis1=1, axis2=2)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.asarray(self.v / np.sqrt(diag), dtype=float)

    def state_update_z(self, i: int = 0) -> np.ndarray:
        """(a_{t|t} - a_{t|t-1})[i] / sd of that update: the state's own surprise, N(0, 1)
        under the model (its variance is P_pred - P_filt). NaN where nothing was observed."""
        upd = self.a_filt[:, i] - self.a_pred[:, i]
        var = self.P_pred[:, i, i] - self.P_filt[:, i, i]
        with np.errstate(invalid="ignore", divide="ignore"):
            out = np.where(var > 1e-14, upd / np.sqrt(np.maximum(var, 1e-300)), np.nan)
        return np.asarray(out, dtype=float)


def _at(x: np.ndarray, t: int, base_ndim: int) -> np.ndarray:
    return x[t] if x.ndim == base_ndim + 1 else x


def kalman_filter(y: Sequence[float] | np.ndarray, model: StateSpace) -> FilterResult:
    """Forward pass. `y` is (n,) or (n, p); NaN = missing."""
    ya = np.asarray(y, dtype=float)
    if ya.ndim == 1:
        ya = ya[:, None]
    n, p = ya.shape
    m = model.m
    a = np.asarray(model.a0, dtype=float).copy()
    P = np.asarray(model.P0, dtype=float).copy()
    a_pred = np.zeros((n, m))
    P_pred = np.zeros((n, m, m))
    a_filt = np.zeros((n, m))
    P_filt = np.zeros((n, m, m))
    y_hat = np.full((n, p), np.nan)
    v_out = np.full((n, p), np.nan)
    F_out = np.full((n, p, p), np.nan)
    ll = 0.0
    nobs = 0
    seen = 0
    eye = np.eye(m)
    d_arr = None if model.d is None else np.asarray(model.d, dtype=float)
    ident_T = model.T.ndim == 2 and bool(np.array_equal(model.T, np.eye(m)))
    diag_H = model.H.ndim == 2 and bool(np.count_nonzero(model.H - np.diag(np.diag(model.H))) == 0)
    for t in range(n):
        Zt = _at(model.Z, t, 2)
        Ht = _at(model.H, t, 2)
        dt = np.zeros(p) if d_arr is None else _at(d_arr, t, 1)
        a_pred[t] = a
        P_pred[t] = P
        y_hat[t] = Zt @ a + dt
        if p == 1:
            # SCALAR FAST PATH (local level, TVP regression): no fancy indexing, same algebra.
            yt = float(ya[t, 0])
            if math.isfinite(yt):
                z = Zt[0]
                h = float(Ht[0, 0])
                pz = P @ z
                f = float(z @ pz) + h
                if not f > 0:
                    raise np.linalg.LinAlgError("non-positive innovation variance")
                vt = yt - float(z @ a) - float(dt[0])
                kg = pz / f
                a = a + kg * vt
                P = P - np.outer(kg, pz)
                P = 0.5 * (P + P.T)
                v_out[t, 0] = vt
                F_out[t, 0, 0] = f
                if seen >= model.n_diffuse:
                    ll += -0.5 * (LOG2PI + math.log(f) + vt * vt / f)
                    nobs += 1
                seen += 1
            a_filt[t] = a
            P_filt[t] = P
            Tt = _at(model.T, t, 2)
            Qt = _at(model.Q, t, 2)
            if not ident_T:
                a = Tt @ a
                P = Tt @ P @ Tt.T
            P = P + Qt
            continue
        obs = np.isfinite(ya[t])
        if obs.any():
            full = bool(obs.all())
            Zo = Zt if full else Zt[obs]
            Ho = Ht if full else Ht[np.ix_(obs, obs)]
            v = ya[t, obs] - Zo @ a - dt[obs]
            if m == 1 and diag_H:
                # ONE STATE, DIAGONAL H: Sherman-Morrison, exact and O(p) (mixed-frequency
                # factor panels such as the latent inflation state run here).
                z = Zo[:, 0]
                hv = np.diag(Ho)
                pp = float(P[0, 0])
                zh = z / hv
                denom = 1.0 + pp * float(z @ zh)
                u = float(zh @ v)
                logdet = float(np.log(hv).sum()) + math.log(denom)
                quad = float((v * v / hv).sum()) - pp * u * u / denom
                a = a + pp * u / denom
                P = np.array([[pp / denom]])
                v_out[t, obs] = v
                F_out[t][np.ix_(obs, obs)] = pp * np.outer(z, z) + np.diag(hv)
                if seen >= model.n_diffuse:
                    ll += -0.5 * (int(obs.sum()) * LOG2PI + logdet + quad)
                    nobs += int(obs.sum())
                seen += 1
                a_filt[t] = a
                P_filt[t] = P
                Tt = _at(model.T, t, 2)
                Qt = _at(model.Q, t, 2)
                a = Tt @ a
                P = Tt @ P @ Tt.T + Qt
                continue
            PZ = P @ Zo.T
            F = Zo @ PZ + Ho
            F = 0.5 * (F + F.T)
            if obs.sum() == 1:
                f = float(F[0, 0])
                if not f > 0:
                    raise np.linalg.LinAlgError("non-positive innovation variance")
                K = PZ / f
                logdet = math.log(f)
                quad = float(v[0] * v[0] / f)
            else:
                cf = np.linalg.cholesky(F)
                K = np.linalg.solve(F, PZ.T).T
                logdet = 2.0 * float(np.log(np.diag(cf)).sum())
                w = np.linalg.solve(cf, v)
                quad = float(w @ w)
            a = a + K @ v
            IKZ = eye - K @ Zo
            P = IKZ @ P @ IKZ.T + K @ Ho @ K.T
            P = 0.5 * (P + P.T)
            v_out[t, obs] = v
            F_out[t][np.ix_(obs, obs)] = F
            if seen >= model.n_diffuse:
                ll += -0.5 * (int(obs.sum()) * LOG2PI + logdet + quad)
                nobs += int(obs.sum())
            seen += 1
        a_filt[t] = a
        P_filt[t] = P
        Tt = _at(model.T, t, 2)
        Qt = _at(model.Q, t, 2)
        a = Tt @ a
        P = Tt @ P @ Tt.T + Qt
        P = 0.5 * (P + P.T)
    return FilterResult(a_pred=a_pred, P_pred=P_pred, a_filt=a_filt, P_filt=P_filt,
                        y_hat=y_hat, v=v_out, F=F_out, loglik=float(ll), nobs=nobs)


def rts_smoother(result: FilterResult, model: StateSpace) -> tuple[np.ndarray, np.ndarray]:
    """Rauch-Tung-Striebel smoothed (a_{t|n}, P_{t|n}). RESEARCH ONLY -- never a PIT series:
    the value at t is computed from observations after t."""
    n = result.a_filt.shape[0]
    a_s = result.a_filt.copy()
    P_s = result.P_filt.copy()
    for t in range(n - 2, -1, -1):
        Tt = _at(model.T, t, 2)
        Pp = result.P_pred[t + 1]
        J = np.linalg.solve(Pp.T, (result.P_filt[t] @ Tt.T).T).T
        a_s[t] = result.a_filt[t] + J @ (a_s[t + 1] - result.a_pred[t + 1])
        P_s[t] = result.P_filt[t] + J @ (P_s[t + 1] - Pp) @ J.T
        P_s[t] = 0.5 * (P_s[t] + P_s[t].T)
    return a_s, P_s


# ============================================================================== models
def _diffuse_scale(y: np.ndarray) -> float:
    """A diffuse prior variance from the FIRST observation only (1e6 x max(1, y_0^2)): a scale
    taken from the whole sample would let later data shape early filtered values."""
    fin = y[np.isfinite(y)]
    y0 = float(fin[0]) if fin.size else 1.0
    return 1e6 * max(1.0, y0 * y0)


def local_level(y: Sequence[float] | np.ndarray, sigma2_eps: float, sigma2_eta: float,
                a0: float | None = None, P0: float | None = None) -> StateSpace:
    """y_t = mu_t + eps_t, mu_{t+1} = mu_t + eta_t. Diffuse start unless a0/P0 are given."""
    ya = np.asarray(y, dtype=float)
    first = ya[np.isfinite(ya)]
    start = float(first[0]) if a0 is None and first.size else float(a0 or 0.0)
    p0 = _diffuse_scale(ya) if P0 is None else float(P0)
    return StateSpace(Z=np.array([[1.0]]), H=np.array([[float(sigma2_eps)]]),
                      T=np.array([[1.0]]), Q=np.array([[float(sigma2_eta)]]),
                      a0=np.array([start]), P0=np.array([[p0]]),
                      n_diffuse=1 if P0 is None else 0)


def tvp_regression(y: Sequence[float] | np.ndarray, X: Sequence[Sequence[float]] | np.ndarray,
                   sigma2_eps: float, q: Sequence[float] | np.ndarray | float,
                   a0: Sequence[float] | np.ndarray | None = None,
                   P0: np.ndarray | None = None) -> StateSpace:
    """y_t = x_t' beta_t + eps_t, beta_{t+1} = beta_t + eta_t, eta ~ N(0, diag(q)).

    A row of X with a NaN is treated as missing y (the regression cannot be evaluated)."""
    ya = np.asarray(y, dtype=float)
    Xa = np.asarray(X, dtype=float)
    if Xa.ndim == 1:
        Xa = Xa[:, None]
    k = Xa.shape[1]
    qv = (np.full(k, float(q)) if isinstance(q, int | float)
          else np.asarray(q, dtype=float).reshape(-1) * np.ones(k))
    Xc = np.where(np.isfinite(Xa), Xa, 0.0)
    p0 = np.eye(k) * _diffuse_scale(ya) if P0 is None else np.asarray(P0, dtype=float)
    return StateSpace(Z=Xc[:, None, :], H=np.array([[float(sigma2_eps)]]), T=np.eye(k),
                      Q=np.diag(qv), a0=(np.zeros(k) if a0 is None
                                         else np.asarray(a0, dtype=float)),
                      P0=p0, n_diffuse=k if P0 is None else 0)


def tvp_y(y: Sequence[float] | np.ndarray, X: Sequence[Sequence[float]] | np.ndarray
          ) -> np.ndarray:
    """y with NaN wherever any regressor is missing (pair with `tvp_regression`)."""
    ya = np.asarray(y, dtype=float).copy()
    Xa = np.asarray(X, dtype=float)
    if Xa.ndim == 1:
        Xa = Xa[:, None]
    ya[~np.all(np.isfinite(Xa), axis=1)] = np.nan
    return ya


# ============================================================================== estimation
@dataclass(frozen=True)
class MLEResult:
    params: np.ndarray          # the natural (positive) parameters
    loglik: float
    nobs: int
    method: str
    converged: bool
    model: StateSpace

    def to_dict(self) -> dict[str, Any]:
        return {"status": "MEASURED", "params": [float(x) for x in self.params],
                "loglik": round(self.loglik, 6), "nobs": self.nobs, "method": self.method,
                "converged": self.converged}


def fit_mle(y: Sequence[float] | np.ndarray, build: Callable[[np.ndarray], StateSpace],
            x0: Sequence[float] | np.ndarray, *, use_scipy: bool = True,
            log_bounds: tuple[float, float] = (-30.0, 15.0), maxiter: int = 400
            ) -> MLEResult:
    """Maximise the prediction-error-decomposition likelihood over positive parameters.

    `build(params)` returns the StateSpace for positive `params`; the search runs on log params
    (inside `log_bounds`) starting from log(x0)."""
    ya = np.asarray(y, dtype=float)
    lo, hi = log_bounds

    def nll(theta: np.ndarray) -> float:
        th = np.clip(np.asarray(theta, dtype=float), lo, hi)
        try:
            res = kalman_filter(ya, build(np.exp(th)))
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            return 1e300
        return -res.loglik if math.isfinite(res.loglik) else 1e300

    x_init = np.log(np.maximum(np.asarray(x0, dtype=float), 1e-300))
    # MULTI-START on a common log shift (x0 x 1e-2, 1, 1e2): one starting point too far from
    # the optimum left L-BFGS-B converged at its start on flat likelihood (measured).
    starts = [x_init + s for s in (math.log(1e-2), 0.0, math.log(1e2))]
    vals = [nll(s) for s in starts]
    start = starts[int(np.argmin(vals))]
    method = "nelder_mead_fallback"
    converged = True
    theta = start
    done = False
    if use_scipy:
        try:
            from scipy.optimize import minimize
            # eps 1e-4 in LOG parameters: the diffuse start leaves ~1e-7 numerical noise in
            # the log-likelihood, which a default 1e-8 finite-difference step turns into a
            # useless gradient (measured: the search stalled after two iterations).
            res = minimize(nll, start, method="L-BFGS-B", bounds=[(lo, hi)] * start.size,
                           options={"maxiter": maxiter, "eps": 1e-4})
            theta = np.asarray(res.x, dtype=float)
            method = "lbfgsb_numeric_gradient"
            converged = bool(res.success)
            if start.size <= 4 and int(res.nit) < 3:
                # L-BFGS-B stopped at (or next to) its start: a derivative-free polish, cheap
                # at this size and immune to gradient noise
                pol = minimize(nll, theta, method="Nelder-Mead",
                               options={"maxfev": 60 * start.size, "xatol": 1e-3,
                                        "fatol": 1e-4})
                if float(pol.fun) < float(res.fun):
                    theta = np.asarray(pol.x, dtype=float)
                    method = "lbfgsb_then_nelder_mead"
            done = True
        except ImportError:     # pragma: no cover - scipy is installed on both boxes
            done = False
    if not done:
        from libs.models.classical_baselines import nelder_mead
        theta, _ = nelder_mead(nll, start, iters=min(maxiter, 80 * start.size), step=0.5)
    params = np.exp(np.clip(theta, lo, hi))
    model = build(params)
    out = kalman_filter(ya, model)
    return MLEResult(params=params, loglik=out.loglik, nobs=out.nobs, method=method,
                     converged=converged, model=model)


def fit_local_level(y: Sequence[float] | np.ndarray, **kw: Any) -> MLEResult:
    """MLE of (sigma2_eps, sigma2_eta) for the local-level model."""
    ya = np.asarray(y, dtype=float)
    fin = ya[np.isfinite(ya)]
    v = float(np.var(np.diff(fin))) if fin.size > 2 else 1.0
    v = max(v, 1e-12)
    return fit_mle(ya, lambda th: local_level(ya, th[0], th[1]), [v / 2.0, v / 2.0], **kw)


def fit_tvp_regression(y: Sequence[float] | np.ndarray,
                       X: Sequence[Sequence[float]] | np.ndarray, *, shared_q: bool = False,
                       **kw: Any) -> MLEResult:
    """MLE of sigma2_eps and the coefficient random-walk variances (one per coefficient, or
    one shared when `shared_q`). params = [sigma2_eps, q...]."""
    Xa = np.asarray(X, dtype=float)
    if Xa.ndim == 1:
        Xa = Xa[:, None]
    ya = tvp_y(y, Xa)
    k = Xa.shape[1]
    fin = ya[np.isfinite(ya)]
    v = max(float(np.var(fin)) if fin.size > 2 else 1.0, 1e-12)

    def build(th: np.ndarray) -> StateSpace:
        q = np.full(k, th[1]) if shared_q else th[1:]
        return tvp_regression(ya, Xa, th[0], q)

    x0 = [v * 0.1] + ([v * 1e-4] if shared_q else [v * 1e-4] * k)
    return fit_mle(ya, build, x0, **kw)
