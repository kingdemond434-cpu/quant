"""STATE-SPACE FILTERS, CAUSAL AND SHARED (2026-10-06).

One module for every Kalman state the desk mines: the EliteQuant thread's price-level residual
families (dynamic fair value, hedge ratio, beta, spread mean, correlation, trend, volatility level;
Roman rows 0833-0843) and World sensor's macro states import from here rather than each writing a
filter. Re-derived from the textbook recursions (Durbin & Koopman, "Time Series Analysis by State
Space Methods", ch. 2-3); Quant Guild's lecture (no licence) is the idea, nothing is copied.

EVERY OUTPUT IS ONE-STEP-AHEAD. Row t of `pred` and `innov` is the prediction of y[t] from y[0..t-1]
and its standardized surprise; row t of `filt` uses y[t] itself. A family that trades on row t at
bar t's close may read both; a family that must decide BEFORE y[t] is known reads `pred` only. NaN
in y is skipped (the state propagates, nothing updates), so a gap is never filled with a guess.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Filtered:
    """Per-row outputs of a scalar-observation filter."""

    filt: np.ndarray      # state estimate after y[t] (rows x k)
    pred: np.ndarray      # one-step prediction of y[t] from y[..t-1]
    var: np.ndarray       # predictive variance of y[t]
    innov: np.ndarray     # (y[t] - pred[t]) / sqrt(var[t])


def _run(y: np.ndarray, z: np.ndarray, T: np.ndarray, Q: np.ndarray, r: np.ndarray | float,
         a0: np.ndarray, p0: np.ndarray) -> Filtered:
    """The general recursion for y_t = Z_t a_t + e_t, a_{t+1} = T a_t + w_t.

    `z` is (n, k): the observation loading per row (constant rows for a time-invariant model, the
    regressor for a time-varying regression). `r` is the observation variance, scalar or per row.
    """
    n, k = z.shape
    rr = np.broadcast_to(np.asarray(r, dtype=float), (n,))
    a, P = a0.astype(float).copy(), p0.astype(float).copy()
    filt = np.full((n, k), np.nan)
    pred = np.full(n, np.nan)
    var = np.full(n, np.nan)
    innov = np.full(n, np.nan)
    for t in range(n):
        zt = z[t]
        if np.all(np.isfinite(zt)):
            f = float(zt @ P @ zt + rr[t])
            yhat = float(zt @ a)
            pred[t], var[t] = yhat, f
            if math.isfinite(y[t]) and f > 0:
                v = float(y[t]) - yhat
                innov[t] = v / math.sqrt(f)
                K = P @ zt / f
                a = a + K * v
                P = P - np.outer(K, zt @ P)
        filt[t] = a
        a = T @ a
        P = T @ P @ T.T + Q
    return Filtered(filt, pred, var, innov)


def local_level(y: np.ndarray, q: float, r: float, *, phi: float = 1.0,
                mu: float = 0.0) -> Filtered:
    """Random-walk (phi = 1) or AR(1)/OU (phi < 1, mean `mu`) level observed with noise r."""
    y = np.asarray(y, dtype=float)
    first = y[np.isfinite(y)]
    if first.size == 0:
        nan = np.full(y.size, np.nan)
        return Filtered(nan[:, None], nan, nan, nan)
    if phi < 1.0:
        # an OU level in deviations from mu: x_t = phi x_{t-1} + w_t, y_t = mu + x_t + e_t
        out = _run(y - mu, np.ones((y.size, 1)), np.array([[phi]]), np.array([[q]]), r,
                   np.array([first[0] - mu]), np.array([[q / max(1e-12, 1 - phi * phi)]]))
        return Filtered(out.filt + mu, out.pred + mu, out.var, out.innov)
    return _run(y, np.ones((y.size, 1)), np.array([[1.0]]), np.array([[q]]), r,
                np.array([first[0]]), np.array([[max(q, r) * 10.0]]))


def local_linear_trend(y: np.ndarray, q_level: float, q_slope: float, r: float) -> Filtered:
    """Level + slope (both random walks) observed with noise r; `filt[:, 1]` is the slope."""
    y = np.asarray(y, dtype=float)
    first = y[np.isfinite(y)]
    a0 = np.array([first[0] if first.size else 0.0, 0.0])
    big = max(q_level, r) * 10.0
    return _run(y, np.tile([1.0, 0.0], (y.size, 1)), np.array([[1.0, 1.0], [0.0, 1.0]]),
                np.diag([q_level, q_slope]), r, a0, np.diag([big, big]))


def dynamic_regression(y: np.ndarray, x: np.ndarray, *, delta: float = 1e-4, r: float = 1e-3,
                       intercept: bool = True) -> Filtered:
    """y_t = alpha_t + beta_t x_t + e_t with (alpha, beta) random walks of variance delta / (1 -
    delta) scaled to r: the dynamic hedge ratio / beta. `filt[:, -1]` is beta, `innov` the
    standardized spread surprise before y[t] updates it."""
    y, x = np.asarray(y, dtype=float), np.asarray(x, dtype=float)
    z = np.column_stack([np.ones_like(x), x]) if intercept else x[:, None]
    k = z.shape[1]
    w = delta / (1.0 - delta)
    return _run(y, z, np.eye(k), np.eye(k) * w * r, r, np.zeros(k), np.eye(k) * 1.0)


def dynamic_correlation(a: np.ndarray, b: np.ndarray, *, q: float = 1e-3,
                        vol_halflife: float = 60.0) -> np.ndarray:
    """A filtered correlation of two return series: each is scaled by its own trailing EWMA
    volatility (read before the row), and the product of the scaled pair is a noisy observation
    of rho tracked by a local level, clipped to [-1, 1]. Causal: row t uses rows <= t."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    lam = 0.5 ** (1.0 / vol_halflife)

    def scaled(s: np.ndarray) -> np.ndarray:
        out = np.full(s.size, np.nan)
        v = np.nan
        for t in range(s.size):
            if math.isfinite(v) and v > 0 and math.isfinite(s[t]):
                out[t] = s[t] / math.sqrt(v)
            if math.isfinite(s[t]):
                v = s[t] * s[t] if not math.isfinite(v) else lam * v + (1 - lam) * s[t] * s[t]
        return out

    prod = scaled(a) * scaled(b)
    return np.clip(local_level(prod, q, 1.0).filt[:, 0], -1.0, 1.0)


def log_variance_level(r: np.ndarray, q: float = 0.01) -> Filtered:
    """The volatility level: log r^2 observed around a random-walk log variance. The observation
    noise of log chi-square(1) is pi^2 / 2 and its mean -1.27 is removed (Harvey, Ruiz &
    Shephard 1994). `filt[:, 0]` is the filtered log variance; `innov` a vol surprise."""
    r = np.asarray(r, dtype=float)
    obs = np.log(np.where(np.isfinite(r), r * r + 1e-18, np.nan)) + 1.2704
    return local_level(obs, q, math.pi ** 2 / 2.0)
