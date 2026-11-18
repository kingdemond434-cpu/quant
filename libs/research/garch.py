"""Self-contained GARCH(1,1) / GJR-GARCH(1,1) -- the challenger `volatility_signals.ewma_variance`
was written to be beaten by, measured rather than assumed.

WHY THIS EXISTS. `volatility_signals.py` chose EWMA "because `arch` is not installed" and recorded
that GARCH must BEAT that baseline to justify itself. Nobody then ran the comparison, so every
vol-conditioned consumer has been using the baseline by default, not by evidence. This module is
the comparison: a small audited quasi-maximum-likelihood fit (the same choice `libs/regime/hmm.py`
made for HMMs: no heavy dependency for a three-parameter model), a walk-forward forecaster with no
look-ahead, and the QLIKE loss that ranks variance forecasts consistently even though the target
(squared return) is a noisy proxy for true variance (Patton 2011).

    GARCH(1,1):   h_t = omega + alpha * r_{t-1}^2                       + beta * h_{t-1}
    GJR(1,1):     h_t = omega + (alpha + gamma * 1[r_{t-1} < 0]) r_{t-1}^2 + beta * h_{t-1}

WHAT EWMA CANNOT DO, and so where a win would come from: EWMA is the omega = 0, alpha + beta = 1
corner. It has no long-run variance to revert to, so after a shock its forecast stays high for
exactly as long as lambda says, and it treats up and down moves identically. GARCH adds mean
reversion; GJR adds the asymmetry (down moves raise variance more) that is routine in equities and
gold and an open question in FX.

NOTHING HERE SIZES A TRADE. `compare_to_ewma` returns a measurement. Routing a winning forecast
into vol-target sizing is a money-path change with its own review.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from libs.research.volatility_signals import EWMA_LAMBDA, ewma_variance

__all__ = [
    "GarchFit",
    "compare_to_ewma",
    "filter_variance",
    "fit",
    "qlike",
    "walk_forward_variance",
]

#: Same floor, same reason, as `volatility_signals._VAR_FLOOR`: float dust is not variance.
_VAR_FLOOR = 1e-20
#: Fewer observations than this and three or four parameters are not identified; refuse to fit.
MIN_FIT_OBS = 250
#: Walk-forward forecasts never fall below this fraction of the training-window variance.
FORECAST_FLOOR_FRAC = 0.01
#: alpha + beta (+ gamma / 2) is capped just under 1 so the long-run variance stays finite.
_MAX_PERSISTENCE = 0.9995


@dataclass(frozen=True)
class GarchFit:
    """One fitted model. `persistence` at or above 1 never leaves `fit` (it is constrained)."""

    omega: float
    alpha: float
    beta: float
    gamma: float            # 0.0 for plain GARCH
    loglik: float
    n_obs: int
    converged: bool

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta + 0.5 * self.gamma

    @property
    def long_run_variance(self) -> float:
        return self.omega / max(1.0 - self.persistence, 1.0 - _MAX_PERSISTENCE)


def filter_variance(returns: np.ndarray, omega: float, alpha: float, beta: float,
                    gamma: float = 0.0, *, h0: float | None = None) -> np.ndarray:
    """Conditional variance path. `out[i]` is the forecast FOR bar i from returns strictly before
    it -- the same convention as `ewma_variance`, so the two are comparable bar for bar.

    `out` has length `len(returns) + 1`: the last element is the forecast for the bar after the
    sample, which is what a live consumer wants. A non-finite return carries the variance forward
    on its own persistence (no shock is invented for a missing bar).
    """
    r = np.asarray(returns, dtype="float64")
    out = np.empty(len(r) + 1)
    finite = r[np.isfinite(r)]
    h = float(h0) if h0 is not None else (float(np.var(finite)) if len(finite) else 0.0)
    h = max(h, _VAR_FLOOR)
    out[0] = h
    for i in range(len(r)):
        x = r[i]
        if np.isfinite(x):
            h = omega + (alpha + (gamma if x < 0 else 0.0)) * x * x + beta * h
        else:
            h = omega + (alpha + 0.5 * gamma + beta) * h
        h = max(h, _VAR_FLOOR)
        out[i + 1] = h
    return out


def _neg_loglik(theta: np.ndarray, r: np.ndarray, h0: float, gjr: bool) -> float:
    omega, alpha, beta = theta[0], theta[1], theta[2]
    gamma = theta[3] if gjr else 0.0
    h = filter_variance(r, omega, alpha, beta, gamma, h0=h0)[:-1]
    ok = np.isfinite(r)
    ll = -0.5 * np.sum(np.log(h[ok]) + r[ok] * r[ok] / h[ok])
    return float(-ll) if np.isfinite(ll) else 1e300


def fit(returns: np.ndarray, *, gjr: bool = False) -> GarchFit | None:
    """Gaussian quasi-maximum-likelihood fit. Returns None when the series cannot support one
    (too short, or no measurable variance) -- a refusal, never a made-up parameter set.

    Returns are rescaled to unit variance before optimising so the same bounds and tolerances
    work for a 1e-4 FX return and a 1e-2 crypto return; omega is scaled back afterwards.
    """
    r = np.asarray(returns, dtype="float64")
    finite = r[np.isfinite(r)]
    if len(finite) < MIN_FIT_OBS:
        return None
    var = float(np.var(finite))
    if not np.isfinite(var) or var <= _VAR_FLOOR:
        return None
    scale = np.sqrt(var)
    z = r / scale

    x0 = [0.05, 0.05, 0.90] + ([0.02] if gjr else [])
    bounds = [(1e-8, 10.0), (0.0, 1.0), (0.0, 1.0)] + ([(0.0, 1.0)] if gjr else [])
    half_gamma = 0.5 if gjr else 0.0
    cons = [{"type": "ineq",
             "fun": lambda t: _MAX_PERSISTENCE - t[1] - t[2] - (half_gamma * t[3] if gjr else 0.0)}]
    best = None
    for start in (x0, [0.10, 0.10, 0.80] + ([0.05] if gjr else [])):
        res = minimize(_neg_loglik, np.array(start), args=(z, 1.0, gjr), method="SLSQP",
                       bounds=bounds, constraints=cons, options={"maxiter": 300, "ftol": 1e-10})
        if np.all(np.isfinite(res.x)) and (best is None or res.fun < best.fun):
            best = res
    if best is None or not np.isfinite(best.fun) or best.fun >= 1e299:
        return None
    omega, alpha, beta = (float(v) for v in best.x[:3])
    gamma = float(best.x[3]) if gjr else 0.0
    n = int(np.isfinite(z).sum())
    # Log-likelihood back in the caller's units: h scales by var, so subtract n/2 * log(var).
    loglik = -float(best.fun) - 0.5 * n * np.log(var) - 0.5 * n * np.log(2.0 * np.pi)
    return GarchFit(omega=omega * var, alpha=alpha, beta=beta, gamma=gamma, loglik=loglik,
                    n_obs=n, converged=bool(best.success))


def walk_forward_variance(returns: np.ndarray, *, gjr: bool = False, min_train: int = 500,
                          refit_every: int = 63) -> np.ndarray:
    """Out-of-sample one-step forecasts. `out[i]` is the forecast for bar i using parameters
    fitted ONLY on returns before the most recent refit point at or before i, and a variance
    state filtered only through bar i-1. NaN before `min_train` and wherever a fit is refused.

    The parameters are refit every `refit_every` bars on an expanding window. Between refits the
    state keeps updating bar by bar, which is what a live deployment would do.
    """
    r = np.asarray(returns, dtype="float64")
    out = np.full(len(r), np.nan)
    start = max(int(min_train), MIN_FIT_OBS)
    for a in range(start, len(r), max(1, int(refit_every))):
        model = fit(r[:a], gjr=gjr)
        if model is None:
            continue
        b = min(a + max(1, int(refit_every)), len(r))
        # h0 from the training window only: the default would read the variance of r[:b].
        path = filter_variance(r[:b], model.omega, model.alpha, model.beta, model.gamma,
                               h0=model.long_run_variance)
        # A boundary fit (omega ~ 0, alpha ~ 0) lets the forecast decay geometrically toward zero,
        # and one ordinary return against a near-zero variance is an unbounded QLIKE loss
        # (measured: USDJPY daily, 2026-11-10, mean QLIKE +352 against -9.4 for EWMA). No market
        # is 10x calmer in volatility than its own history, so the forecast is floored at 1% of
        # the TRAINING window's variance -- past data only.
        train = r[:a]
        floor = FORECAST_FLOOR_FRAC * float(np.var(train[np.isfinite(train)]))
        out[a:b] = np.maximum(path[a:b], floor)
    return out


def qlike(forecast: np.ndarray, returns: np.ndarray) -> float:
    """Mean QLIKE loss, log(h) + r^2 / h, over bars where both are usable. Lower is better.

    QLIKE is used rather than squared error on variances because it stays a consistent ranking
    when the target is the noisy proxy r^2, and it is not dominated by the few largest shocks.
    Returns NaN when no bar is usable.
    """
    h = np.asarray(forecast, dtype="float64")
    r = np.asarray(returns, dtype="float64")
    ok = np.isfinite(h) & np.isfinite(r) & (h > _VAR_FLOOR)
    if not ok.any():
        return float("nan")
    return float(np.mean(np.log(h[ok]) + r[ok] * r[ok] / h[ok]))


def compare_to_ewma(returns: np.ndarray, *, min_train: int = 500, refit_every: int = 63,
                    lam: float = EWMA_LAMBDA) -> dict[str, object]:
    """EWMA baseline vs GARCH vs GJR on the SAME out-of-sample bars. A measurement, not a verdict.

    `ewma` is the correctly aligned RiskMetrics forecast and is the baseline every `dm_t` is
    measured against; `ewma_as_shipped` is scored beside it for the record.

    `dm_t` is a Diebold-Mariano style t-statistic on the per-bar QLIKE difference (EWMA minus
    challenger; positive favours the challenger), with a Newey-West variance so serially
    correlated loss differences do not inflate it. `status` is UNMEASURED, never a silent zero,
    when there are too few common bars to say anything.
    """
    r = np.asarray(returns, dtype="float64")
    warm = r[:max(int(min_train), MIN_FIT_OBS)]
    warm = warm[np.isfinite(warm)]
    h0 = float(np.var(warm)) if len(warm) else 0.0
    forecasts = {
        # The baseline at its best: RiskMetrics as the omega=0 corner of the same filter, using
        # every return up to i-1. `ewma_as_shipped` is `volatility_signals.ewma_variance`, whose
        # forecast for bar i stops at r[i-2] (one bar staler). Both are scored so beating the
        # shipped function is never mistaken for beating EWMA.
        "ewma": filter_variance(r, 0.0, 1.0 - lam, lam, h0=h0)[:-1],
        "ewma_as_shipped": ewma_variance(r, lam=lam),
        "garch": walk_forward_variance(r, min_train=min_train, refit_every=refit_every),
        "gjr": walk_forward_variance(r, gjr=True, min_train=min_train, refit_every=refit_every),
    }
    ok = np.isfinite(r)
    for h in forecasts.values():
        ok &= np.isfinite(h) & (h > _VAR_FLOOR)
    n = int(ok.sum())
    if n < MIN_FIT_OBS:
        return {"status": "UNMEASURED", "n_oos": n,
                "why": f"only {n} common out-of-sample bars, need {MIN_FIT_OBS}"}
    loss = {k: np.log(h[ok]) + r[ok] * r[ok] / h[ok] for k, h in forecasts.items()}
    out: dict[str, object] = {"status": "MEASURED", "n_oos": n,
                              "qlike": {k: float(v.mean()) for k, v in loss.items()}}
    dm = {}
    for k in ("garch", "gjr"):
        d = loss["ewma"] - loss[k]
        dm[k] = _nw_tstat(d)
    out["dm_t"] = dm
    out["best"] = min(loss, key=lambda k: float(loss[k].mean()))
    return out


def _nw_tstat(d: np.ndarray) -> float:
    """t-statistic of mean(d) with a Newey-West (Bartlett) long-run variance."""
    n = len(d)
    if n < 2:
        return float("nan")
    x = d - d.mean()
    lags = int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0)))
    lrv = float(x @ x) / n
    for k in range(1, min(lags, n - 1) + 1):
        lrv += 2.0 * (1.0 - k / (lags + 1.0)) * float(x[k:] @ x[:-k]) / n
    if not np.isfinite(lrv) or lrv <= 0:
        return float("nan")
    return float(d.mean() / np.sqrt(lrv / n))
