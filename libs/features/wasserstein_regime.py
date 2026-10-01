"""Wasserstein k-means regimes and the trend-scanning target, ported for the model search.

Source: github.com/stefan-jansen/machine-learning-for-trading (3rd edition),
`09_model_based_features/12_wasserstein_regimes.py` (`lift_stream`, `wasserstein_distance_1d`,
`distances_to_centroid`, `wasserstein_barycenter_1d`, `WassersteinKMeans1D`) and the
trend-scanning labeler used in `07_defining_the_learning_task/03_label_methods.py`.
MIT License, Copyright (c) 2024-2026 Stefan Jansen; the notice is kept verbatim in
`libs/features/LICENSE_machine-learning-for-trading`.

WHAT CHANGED IN THE PORT, AND WHY.
  * The notebook clusters every window of the sample at once, so a window's regime label is
    decided by centroids that saw the whole future. Used as a feature in a walk-forward fold
    that is a leak of the whole test set into the train set. Here the centroids are REFITTED
    on an expanding past only: at refit point r the fit sees windows that ended before r, and
    those centroids label bars r .. r + refit - 1. Bars before the first fit are NaN.
  * A label's NUMBER is arbitrary between fits (k-means has no order), so a learner reading it
    across a refit would read noise. Centroids are ordered by their dispersion after every fit,
    so regime 0 is always the calmest distribution and regime k-1 the widest.
  * `wshift` -- the W1 distance between the current window and the window just before it --
    needs no fit at all: the distribution-change detector the notebook's centroids imply, in
    its causal form.
  * The trend-scanning t-value is bounded to `horizon` bars of future (the same look-ahead the
    sign target already uses). ml4t's own note stands: the max-|t| over windows is selected and
    its residuals are autocorrelated, so the t-value is a TARGET to rank by, never a p-value.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: H1 bars per window: two trading days of hourly returns.
WINDOW = 48
N_CLUSTERS = 3
#: Bars between refits, and the fewest past windows a fit may use.
REFIT = 500
MIN_FIT_WINDOWS = 60
#: Past windows are subsampled at this stride for the fit (overlap buys windows, not information).
FIT_STRIDE = 6


def lift_stream(returns: np.ndarray, window_len: int) -> np.ndarray:
    """Every window of `window_len` consecutive returns ending at bar t (row t - window_len + 1),
    sorted ascending -- each row is an empirical distribution."""
    if returns.ndim != 1 or returns.shape[0] < window_len:
        return np.empty((0, window_len))
    view = np.lib.stride_tricks.sliding_window_view(returns, window_shape=window_len)
    return np.sort(np.ascontiguousarray(view, dtype=np.float64), axis=1)


def wasserstein_distance_1d(sorted_a: np.ndarray, sorted_b: np.ndarray, p: float = 1.0) -> float:
    """The p-Wasserstein distance between two equal-sized sorted samples."""
    return float((np.abs(sorted_a - sorted_b) ** p).mean() ** (1.0 / p))


def distances_to_centroid(sorted_segments: np.ndarray, centroid: np.ndarray,
                          p: float = 1.0) -> np.ndarray:
    return (np.abs(sorted_segments - centroid[None, :]) ** p).mean(axis=1) ** (1.0 / p)


def barycenter(sorted_members: np.ndarray, p: float = 1.0) -> np.ndarray:
    """Quantile-wise median (p = 1) or mean (p = 2): the closed-form Wasserstein barycenter."""
    if p == 1.0:
        return np.median(sorted_members, axis=0)
    if p == 2.0:
        return sorted_members.mean(axis=0)
    raise ValueError("p must be 1 or 2, the exponents with a closed-form barycenter")


def kmeans(sorted_segments: np.ndarray, k: int = N_CLUSTERS, *, p: float = 1.0, n_init: int = 3,
           max_iter: int = 30, tol: float = 1e-6, seed: int = 0) -> np.ndarray:
    """Lloyd's algorithm under W_p with k-means++ seeding; the best of `n_init` fits' centroids,
    ordered by dispersion (calmest first)."""
    n = sorted_segments.shape[0]
    if n < k:
        raise ValueError("there must be at least as many windows as clusters")
    rng = np.random.default_rng(seed)
    best, best_inertia = None, np.inf
    for _ in range(n_init):
        cent = np.empty((k, sorted_segments.shape[1]))
        cent[0] = sorted_segments[int(rng.integers(0, n))]
        closest = distances_to_centroid(sorted_segments, cent[0], p) ** 2
        for j in range(1, k):
            tot = float(closest.sum())
            pick = int(rng.choice(n, p=closest / tot)) if tot > 0 else int(rng.integers(0, n))
            cent[j] = sorted_segments[pick]
            closest = np.minimum(closest, distances_to_centroid(sorted_segments, cent[j], p) ** 2)
        for _it in range(max_iter):
            dist = np.column_stack([distances_to_centroid(sorted_segments, c, p) for c in cent])
            lab = dist.argmin(axis=1)
            prev = cent.copy()
            for j in range(k):
                members = sorted_segments[lab == j]
                cent[j] = (barycenter(members, p) if members.shape[0]
                           else sorted_segments[int(dist.min(axis=1).argmax())])
            if sum(wasserstein_distance_1d(prev[j], cent[j], p) for j in range(k)) < tol:
                break
        dist = np.column_stack([distances_to_centroid(sorted_segments, c, p) for c in cent])
        inertia = float(dist.min(axis=1).sum())
        if inertia < best_inertia:
            best, best_inertia = cent.copy(), inertia
    assert best is not None
    return best[np.argsort(best[:, -1] - best[:, 0])]


def features(df: pd.DataFrame, *, window: int = WINDOW, k: int = N_CLUSTERS,
             refit: int = REFIT) -> pd.DataFrame:
    """Causal regime coordinates on H1 bars: the W1 distance from the trailing window to each
    centroid (scaled by their mean, so the columns read alike on every instrument), the nearest
    regime, and the W1 shift from the previous non-overlapping window."""
    ret = np.log(df["close"].astype(float)).diff().to_numpy()
    n = ret.size
    out = {f"wd{j}": np.full(n, np.nan) for j in range(k)}
    out["wregime"] = np.full(n, np.nan)
    out["wshift"] = np.full(n, np.nan)
    r = np.nan_to_num(ret[1:], nan=0.0)                     # bar 0 has no return
    segs = lift_stream(r, window)                           # row i ends at bar i + window
    if segs.shape[0] == 0:
        return pd.DataFrame(out, index=df.index)
    end = np.arange(segs.shape[0]) + window                 # the bar each window ends at
    out["wshift"][end[window:]] = (np.abs(segs[window:] - segs[:-window]).mean(axis=1))
    first = window + MIN_FIT_WINDOWS * FIT_STRIDE
    for start in range(first, n, refit):
        past = segs[(end < start)][::FIT_STRIDE]            # windows wholly before `start`
        if past.shape[0] < max(k, MIN_FIT_WINDOWS):
            continue
        cent = kmeans(past, k, seed=start)
        rows = np.flatnonzero((end >= start) & (end < start + refit))
        if rows.size == 0:
            continue
        dist = np.column_stack([distances_to_centroid(segs[rows], c) for c in cent])
        scale = dist.mean(axis=1, keepdims=True)
        scale[scale == 0] = np.nan
        for j in range(k):
            out[f"wd{j}"][end[rows]] = dist[:, j] / scale[:, 0]
        out["wregime"][end[rows]] = dist.argmin(axis=1).astype(float)
    return pd.DataFrame(out, index=df.index)


def trend_scan_t(close: pd.Series, *, horizon: int, min_window: int = 3) -> np.ndarray:
    """At each bar, the OLS t-value of log price on time over the forward window [t, t + L]
    with the largest |t|, L in [min_window, horizon]; NaN where `horizon` bars are not ahead."""
    lc = np.log(close.astype(float)).to_numpy()
    n = lc.size
    best = np.full(n, np.nan)
    best_abs = np.zeros(n)
    for L in range(max(2, min_window), horizon + 1):
        m = L + 1                                           # points t .. t + L
        view = np.lib.stride_tricks.sliding_window_view(lc, m)   # row i: lc[i .. i + L]
        x = np.arange(m, dtype=float) - L / 2.0
        sxx = float((x * x).sum())
        yc = view - view.mean(axis=1, keepdims=True)
        beta = (yc * x).sum(axis=1) / sxx
        resid = yc - beta[:, None] * x
        s2 = (resid * resid).sum(axis=1) / (m - 2)
        with np.errstate(all="ignore"):
            t = beta / np.sqrt(s2 / sxx)
        t = np.where(np.isfinite(t), t, np.nan)
        rows = view.shape[0]
        a = np.abs(t)
        better = np.isfinite(a) & (a > best_abs[:rows])
        best[:rows] = np.where(better, t, best[:rows])
        best_abs[:rows] = np.where(better, a, best_abs[:rows])
    best[n - horizon:] = np.nan                             # every bar sees the same look-ahead
    return best
