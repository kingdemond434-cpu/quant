"""FUNCTIONAL PATH REPRESENTATIONS, SHARED (Roman rows 1000 and 0743, 2026-10-06).

A window of log prices is a path, and a path has shape the return series alone does not carry.
These are the textbook representations (re-derived; Quant Guild's lectures are the idea only):

  hurst_variogram      H from the scaling of E|x_{t+k} - x_t|^2 ~ k^{2H} over small lags: the
                       fractional-Brownian roughness of the path (H > 0.5 persistent, < 0.5
                       anti-persistent).
  rough_vol_hurst      the same estimator on log realised volatility: Gatheral, Jaisson &
                       Rosenbaum (2018) find H ~ 0.1 for log vol; a smoother vol path (higher H)
                       is a slower-reverting vol regime.
  bridge_excursion     the path's largest departure from the straight line joining its ends, in
                       units of its own increment sd times sqrt(n): the Brownian-bridge statistic
                       (Kolmogorov-type), small when the path hugs a line.
  kl_basis / kl_coeffs the Karhunen-Loeve (principal-component) basis of normalised windows fitted
                       on a TRAINING span, and each later window's coefficients on it.
  signature_level2     the depth-2 signature of the (time, price) path: increments and the Levy
                       area, the lead-lag term (`sandboxes/path_signature_lab.py` goes to depth 3).

Every function reads only the window it is handed; rolling versions read trailing windows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def hurst_variogram(x: np.ndarray, lags: tuple[int, ...] = (1, 2, 4, 8, 16)) -> float:
    """H from the log-log slope of the mean squared increment against the lag."""
    x = np.asarray(x, dtype=float)
    pts = []
    for k in lags:
        if x.size <= k + 2:
            break
        d = x[k:] - x[:-k]
        d = d[np.isfinite(d)]
        m = float(np.mean(d * d)) if d.size else 0.0
        if m > 0:
            pts.append((np.log(k), np.log(m)))
    if len(pts) < 3:
        return float("nan")
    a = np.asarray(pts)
    return float(np.polyfit(a[:, 0], a[:, 1], 1)[0] / 2.0)


def rolling_hurst(x: np.ndarray, window: int, step: int = 1,
                  lags: tuple[int, ...] = (1, 2, 4, 8, 16)) -> np.ndarray:
    """H of the trailing `window` values at every `step`-th row (forward-filled between)."""
    x = np.asarray(x, dtype=float)
    out = np.full(x.size, np.nan)
    for t in range(window - 1, x.size, step):
        out[t] = hurst_variogram(x[t - window + 1:t + 1], lags)
    return pd.Series(out).ffill(limit=max(0, step - 1)).to_numpy()


def realised_log_vol(r: np.ndarray, block: int) -> np.ndarray:
    """log sqrt(sum of squared returns) over trailing non-overlapping blocks, one per row."""
    r2 = pd.Series(np.asarray(r, dtype=float) ** 2)
    rv = r2.rolling(block, min_periods=block).sum().to_numpy()
    with np.errstate(divide="ignore"):
        return np.where(rv > 0, 0.5 * np.log(rv), np.nan)


def rough_vol_hurst(r: np.ndarray, *, block: int = 24, window_blocks: int = 60) -> float:
    """H of log realised vol sampled every `block` rows over the last `window_blocks` blocks."""
    lv = realised_log_vol(r, block)[block - 1::block]
    lv = lv[np.isfinite(lv)][-window_blocks:]
    return hurst_variogram(lv, (1, 2, 3, 5, 8))


def bridge_excursion(x: np.ndarray) -> float:
    """max |x_t - line(x_0, x_n)| / (sd(increments) * sqrt(n))."""
    x = np.asarray(x, dtype=float)
    n = x.size - 1
    if n < 4 or not np.all(np.isfinite(x)):
        return float("nan")
    line = x[0] + (x[-1] - x[0]) * np.arange(n + 1) / n
    sd = float(np.diff(x).std(ddof=1))
    return float(np.max(np.abs(x - line)) / (sd * np.sqrt(n))) if sd > 0 else float("nan")


def _windows(x: np.ndarray, n: int) -> np.ndarray:
    w = np.lib.stride_tricks.sliding_window_view(np.asarray(x, dtype=float), n)
    w = w - w[:, :1]                                            # each window starts at zero
    sd = np.diff(w, axis=1).std(axis=1, ddof=1, keepdims=True)
    return np.where(sd > 0, w / np.where(sd > 0, sd, 1.0), np.nan)


def kl_basis(x_train: np.ndarray, n: int, k: int = 3) -> np.ndarray:
    """(k, n) leading Karhunen-Loeve basis of normalised length-n windows of the training path."""
    w = _windows(x_train, n)
    w = w[np.all(np.isfinite(w), axis=1)]
    w = w - w.mean(axis=0)
    _, _, vt = np.linalg.svd(w, full_matrices=False)
    return vt[:k]


def kl_coeffs(x: np.ndarray, basis: np.ndarray) -> np.ndarray:
    """(rows, k) coefficients of each trailing window on the basis; NaN until a window exists."""
    n = basis.shape[1]
    out = np.full((len(x), basis.shape[0]), np.nan)
    if len(x) >= n:
        out[n - 1:] = _windows(x, n) @ basis.T
    return out


def signature_level2(t: np.ndarray, x: np.ndarray) -> dict[str, float]:
    """Depth-2 signature of the piecewise-linear path (t, x): S1, S2 and the Levy area."""
    dt, dx = np.diff(np.asarray(t, float)), np.diff(np.asarray(x, float))
    ct, cx = np.r_[0.0, np.cumsum(dt)][:-1], np.r_[0.0, np.cumsum(dx)][:-1]
    s_tx = float(np.sum(ct * dx + 0.5 * dt * dx))
    s_xt = float(np.sum(cx * dt + 0.5 * dx * dt))
    return {"t": float(dt.sum()), "x": float(dx.sum()), "tx": s_tx, "xt": s_xt,
            "levy_area": 0.5 * (s_tx - s_xt)}
