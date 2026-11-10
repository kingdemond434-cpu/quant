"""Kalman time-varying hedge ratio -- measured against the rolling-OLS hedge it would replace.

WHY THIS EXISTS. The desk's only Kalman filter is the macro dynamic-factor model in
`macro_state_engine.py`. Every pair/residual family (`cross_asset_residual`, cointegration cells)
estimates its hedge ratio with a fixed or rolling regression. A rolling window forgets abruptly
and weights a 60-day-old bar the same as yesterday's; the Kalman filter is the same regression
with a hedge ratio that drifts as a random walk, so it adapts continuously and carries its own
uncertainty. Whether that is BETTER on these markets is an empirical question, and this module
answers it instead of assuming it.

    observation:  y_t = alpha_t + beta_t * x_t + e_t,        e_t ~ N(0, r)
    state:        (alpha_t, beta_t) = (alpha_{t-1}, beta_{t-1}) + w_t,   w_t ~ N(0, q * I)

`q / r` is the only real knob (how fast the hedge may drift). It is chosen on the TRAINING window
by one-step predictive likelihood, never on the bars it is then scored on.

WHAT IS MEASURED. For each bar the filter gives a forecast of y_t from x_t using only bars before
t. `compare_to_rolling_ols` scores that forecast's squared error against rolling OLS on the same
out-of-sample bars with a Newey-West Diebold-Mariano statistic. A hedge that predicts y better
leaves a smaller, more stationary spread -- which is what a residual sleeve trades.

PASS RETURNS, NOT PRICE LEVELS -- measured, 2026-11-10. On log price LEVELS the filter "beat"
rolling OLS on six of six pairs (MSE ratio 0.26-0.79, DM t up to 7), and it was an illusion: with
a fast drift the random-walk intercept simply follows y, so the forecast collapses toward
yesterday's price, and plain y[t-1] did as well or better (EURUSD/GBPUSD: 2.1e-5 against the
filter's 3.7e-5). That says nothing about the hedge. `compare_to_rolling_ols` therefore also
scores the carry-forward forecast y[t-1], and raises `level_trap` when y is near unit-root on
the training window (lag-1 autocorrelation above `LEVEL_AC1`). On RETURNS the same
pairs are a near tie (see the PR table), which is the honest answer.

NOTHING HERE TRADES OR SIZES. It returns a measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "DELTA_GRID",
    "KalmanPath",
    "compare_to_rolling_ols",
    "kalman_regression",
    "rolling_ols_forecast",
    "select_delta",
]

#: Candidate state-noise ratios q / r, slow to fast. 1e-7 is nearly a fixed regression; 1e-2 lets
#: the hedge move materially in a day.
DELTA_GRID: tuple[float, ...] = (1e-7, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2)
#: Training-window lag-1 autocorrelation of y above this means levels, not returns, were passed.
LEVEL_AC1 = 0.9
#: Fewer common out-of-sample bars than this and the comparison is UNMEASURED.
MIN_OOS = 250


@dataclass(frozen=True)
class KalmanPath:
    """Filter output. Every array is aligned so index i uses only bars strictly before i."""

    forecast: np.ndarray        # E[y_i | x_i, bars < i]
    innovation: np.ndarray      # y_i - forecast_i  (the tradable spread, out of sample)
    innovation_var: np.ndarray  # predictive variance of that innovation
    alpha: np.ndarray           # prior intercept used for bar i
    beta: np.ndarray            # prior hedge ratio used for bar i
    loglik: float               # sum of one-step predictive log densities


def kalman_regression(y: np.ndarray, x: np.ndarray, *, delta: float = 1e-5,
                      warmup: int = 30) -> KalmanPath:
    """Random-walk-coefficient regression of y on x, filtered forward once.

    The state starts from an OLS fit on the first `warmup` bars with a wide prior, and the
    observation variance r is re-estimated online from past innovations (EWMA), so the filter is
    scale-free. Bars up to `warmup` carry NaN forecasts. A bar with a non-finite y or x is skipped:
    the state is carried, its uncertainty grows, and no forecast is issued for it.
    """
    y = np.asarray(y, dtype="float64")
    x = np.asarray(x, dtype="float64")
    n = len(y)
    if len(x) != n:
        raise ValueError("y and x must be the same length")
    nan = np.full(n, np.nan)
    out = {k: nan.copy() for k in ("f", "e", "s", "a", "b")}
    w = int(warmup)
    ok0 = np.isfinite(y[:w]) & np.isfinite(x[:w])
    if n <= w or ok0.sum() < 10 or float(np.var(x[:w][ok0])) <= 0.0:
        return KalmanPath(out["f"], out["e"], out["s"], out["a"], out["b"], float("nan"))
    X0 = np.column_stack([np.ones(int(ok0.sum())), x[:w][ok0]])
    theta, *_ = np.linalg.lstsq(X0, y[:w][ok0], rcond=None)
    resid = y[:w][ok0] - X0 @ theta
    r = max(float(np.var(resid)), 1e-18)
    P = np.linalg.inv(X0.T @ X0) * r * 10.0
    q_scale = float(delta)
    loglik = 0.0
    eye = np.eye(2)
    for i in range(w, n):
        P = P + eye * (q_scale * r)                      # predict: coefficients drift
        if not (np.isfinite(y[i]) and np.isfinite(x[i])):
            continue
        h = np.array([1.0, x[i]])
        f = float(h @ theta)
        s = float(h @ P @ h) + r
        e = y[i] - f
        out["f"][i], out["e"][i], out["s"][i] = f, e, s
        out["a"][i], out["b"][i] = theta[0], theta[1]
        loglik += -0.5 * (np.log(2.0 * np.pi * s) + e * e / s)
        k = (P @ h) / s                                  # update, AFTER the forecast is recorded
        theta = theta + k * e
        P = P - np.outer(k, h) @ P
        P = 0.5 * (P + P.T)
        # Observation noise learned from PAST post-fit residuals only (this bar feeds the next).
        post = y[i] - float(h @ theta)
        r = max(0.98 * r + 0.02 * post * post, 1e-18)
    return KalmanPath(out["f"], out["e"], out["s"], out["a"], out["b"], loglik)


def select_delta(y: np.ndarray, x: np.ndarray, *, grid: tuple[float, ...] = DELTA_GRID,
                 warmup: int = 30) -> float | None:
    """The drift speed with the best one-step predictive likelihood on THIS window. None when the
    window cannot support a filter at all."""
    best, best_ll = None, -np.inf
    for d in grid:
        ll = kalman_regression(y, x, delta=d, warmup=warmup).loglik
        if np.isfinite(ll) and ll > best_ll:
            best, best_ll = d, ll
    return best


def rolling_ols_forecast(y: np.ndarray, x: np.ndarray, *, window: int = 60) -> np.ndarray:
    """The incumbent: forecast y_i from x_i with an OLS line fitted on the `window` bars BEFORE i.
    NaN until a full window of finite pairs exists."""
    y = np.asarray(y, dtype="float64")
    x = np.asarray(x, dtype="float64")
    out = np.full(len(y), np.nan)
    w = int(window)
    for i in range(w, len(y)):
        ys, xs = y[i - w:i], x[i - w:i]
        ok = np.isfinite(ys) & np.isfinite(xs)
        if ok.sum() < w or not np.isfinite(x[i]):
            continue
        vx = float(np.var(xs))
        if vx <= 0.0:
            continue
        b = float(np.cov(xs, ys, bias=True)[0, 1]) / vx
        a = float(ys.mean() - b * xs.mean())
        out[i] = a + b * x[i]
    return out


def compare_to_rolling_ols(y: np.ndarray, x: np.ndarray, *, train: int = 500,
                           windows: tuple[int, ...] = (30, 60, 120),
                           warmup: int = 30) -> dict[str, object]:
    """Kalman hedge vs rolling OLS on the SAME out-of-sample bars (index >= `train`).

    Both sides tune on the first `train` bars only: the Kalman drift speed by predictive
    likelihood, the OLS window by forecast MSE. So the incumbent is the BEST rolling window, not a
    straw man. `dm_t` > 0 favours Kalman. `level_trap` True means do not read the result: pass
    returns instead of levels. `status` is UNMEASURED, never a silent zero, when the
    series are too short or degenerate.
    """
    y = np.asarray(y, dtype="float64")
    x = np.asarray(x, dtype="float64")
    n = len(y)
    if n < train + MIN_OOS:
        return {"status": "UNMEASURED", "why": f"{n} bars, need {train + MIN_OOS}"}
    delta = select_delta(y[:train], x[:train], warmup=warmup)
    if delta is None:
        return {"status": "UNMEASURED", "why": "no finite likelihood on the training window"}
    best_w, best_mse = None, np.inf
    for w in windows:
        f = rolling_ols_forecast(y[:train], x[:train], window=w)
        err = (y[:train] - f)[max(windows):]            # same scored bars for every window
        err = err[np.isfinite(err)]
        if len(err) and float(np.mean(err * err)) < best_mse:
            best_w, best_mse = w, float(np.mean(err * err))
    if best_w is None:
        return {"status": "UNMEASURED", "why": "rolling OLS produced no training forecasts"}
    kf = kalman_regression(y, x, delta=delta, warmup=warmup)
    ols = rolling_ols_forecast(y, x, window=best_w)
    ek, eo = y - kf.forecast, y - ols
    ok = np.isfinite(ek) & np.isfinite(eo)
    ok[:train] = False
    m = int(ok.sum())
    if m < MIN_OOS:
        return {"status": "UNMEASURED", "why": f"only {m} common out-of-sample bars"}
    lk, lo = ek[ok] ** 2, eo[ok] ** 2
    prev = np.concatenate([[np.nan], y[:-1]])
    lc = (y - prev)[ok] ** 2
    carry = float(np.nanmean(lc)) if np.isfinite(lc).any() else float("nan")
    return {
        "status": "MEASURED", "n_oos": m, "delta": delta, "ols_window": best_w,
        "mse": {"kalman": float(lk.mean()), "rolling_ols": float(lo.mean()),
                "carry_forward": carry},
        # A near-unit-root y means price LEVELS were passed. There a fast filter wins by
        # following y (its intercept is a random walk), which says nothing about the hedge.
        "level_trap": bool(_ac1(y[:train][np.isfinite(y[:train])]) > LEVEL_AC1),
        "mse_ratio": float(lk.mean() / lo.mean()),
        "dm_t": _nw_tstat(lo - lk),
        "spread_ac1": {"kalman": _ac1(ek[ok]), "rolling_ols": _ac1(eo[ok])},
        "best": "kalman" if lk.mean() < lo.mean() else "rolling_ols",
    }


def _ac1(e: np.ndarray) -> float:
    e = e - e.mean()
    d = float(e @ e)
    return float(e[1:] @ e[:-1] / d) if d > 0 else float("nan")


def _nw_tstat(d: np.ndarray) -> float:
    """t-statistic of mean(d) with a Newey-West (Bartlett) long-run variance."""
    n = len(d)
    if n < 2:
        return float("nan")
    z = d - d.mean()
    lags = int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    lrv = float(z @ z) / n
    for k in range(1, min(lags, n - 1) + 1):
        lrv += 2.0 * (1.0 - k / (lags + 1.0)) * float(z[k:] @ z[:-k]) / n
    if not np.isfinite(lrv) or lrv <= 0:
        return float("nan")
    return float(d.mean() / np.sqrt(lrv / n))
