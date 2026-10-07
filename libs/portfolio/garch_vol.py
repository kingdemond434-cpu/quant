"""GARCH(1,1) volatility forecast per sleeve: how much wider the next H days are than usual.

WHY THIS EXISTS (ALLOC-13). `model_roles.FAMILIES["garch_vol"]` declared a slot whose
`reaches_allocator` read "NO: no GARCH model reaches the allocator": the desk's only volatility
organ, `libs/research/volatility_signals.py`, is EWMA/Garman-Klass and feeds research only. So
every world `robust_elog` sampled drew a sleeve's dispersion from its WHOLE history, equally
weighted -- a sleeve two weeks into a volatility burst was sized as if the burst were its average
day, and one coming out of a quiet month as if the quiet were permanent. Volatility clusters; that
is the one stylised fact of daily returns nobody disputes, and the allocator ignored it.

WHAT IT IS ALLOWED TO DO. Its roles are VOLATILITY_SCALE + UNCERTAINTY_WIDTH and nothing else
(`model_roles.py`: "Volatility sizes a bet; it never signs one"). The number it returns is a
DISPERSION multiplier: a caller scales each sleeve's deviations about its mean,
`mean + ratio * (r - mean)`, and never the mean itself. A high-volatility forecast is a reason to
be smaller, not a reason to think the edge moved.

THE FIT. Gaussian quasi-maximum likelihood of

    e_t       = r_t - mean(r)                       (the sleeve's own sample mean, past-only)
    sigma2_t  = omega + alpha * e_{t-1}^2 + beta * sigma2_{t-1}

on the sleeve's own daily R with NaN days DROPPED (a non-trading day is not a zero-return day,
and filling it with zero would manufacture calm). The parameters are optimised in an unconstrained
space -- omega = exp(a), persistence p = alpha + beta = logistic(b), alpha share = logistic(c) --
so stationarity (alpha + beta < 1) and positivity hold by construction and the optimiser never
has to be told about a boundary. The recursion is one `scipy.signal.lfilter` call, so a fit over
a few thousand days costs milliseconds, not the seconds a Python loop would.

PAST-ONLY. A fit at day t sees r[0..t] and nothing else; the forecast it emits is for t+1..t+H.
`forecast_at(r, t, H)` exists so the tests can PROVE that, by perturbing every day after t and
showing the forecast at t does not move.

UNMEASURED IS AN ANSWER, AND ITS RATIO IS EXACTLY 1.0. Any of these returns status UNMEASURED and
leaves the sleeve's dispersion exactly as the allocator had it before this file existed:

  * fewer than MIN_OBS non-NaN days;
  * the optimiser failed, or the likelihood was not finite;
  * the fitted persistence is so close to one that a shock's half-life exceeds the sample itself
    (ln 0.5 / ln p > n). That is the operational form of "alpha + beta >= 1": the sample cannot
    tell such a process from an integrated one, so its unconditional variance -- the anchor every
    multi-step forecast decays toward -- is not identified by the data in hand;
  * the likelihood's curvature at the optimum is not positive definite, so the fit cannot state
    its own uncertainty, and an estimate that cannot state its uncertainty does not get applied.

THE BAND IS THE FIT'S OWN UNCERTAINTY, NOT A CONSTANT. The forecast ratio carries a standard error
by the delta method: the inverse Hessian of the negative log-likelihood (in the unconstrained
space) is the parameter covariance, and the numerical gradient of log(ratio) with respect to those
parameters carries it through. The band is ratio * exp(+-Z * se_log). How it is APPLIED is
asymmetric, and the asymmetry is the desk's staleness doctrine (`model_roles.staleness_clamp`: an
uncertain input may only reduce or hold risk), not taste:

  * ratio >= 1 (vol forecast ABOVE normal -> the sleeve gets SMALLER): the point estimate is
    applied. Shrinking a risk-reducing estimate toward 1 because it is noisy would be adding risk
    on the strength of noise.
  * ratio <  1 (vol forecast BELOW normal -> the sleeve would get LARGER): only what the fit can
    prove is applied -- the band's UPPER edge, capped at 1. A calm the fit cannot distinguish from
    normal at Z standard errors earns nothing.

Z is the two-sided 95% normal quantile. It is a confidence convention, the same one every
interval on this desk is quoted at, not a tuning constant fitted to make this organ behave.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.signal import lfilter
from scipy.stats import norm

#: The decision roles this organ holds in `desks/mt5/research/model_roles.py`. It scales the
#: dispersion a sleeve's worlds are drawn with and widens/narrows uncertainty; it never moves a
#: mean and never signs a bet.
FAMILY = "garch_vol"
ROLES: tuple[str, ...] = ("VOLATILITY_SCALE", "UNCERTAINTY_WIDTH")

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: Non-NaN days a sleeve needs before a GARCH(1,1) is fitted at all. One trading year. Below it
#: the alpha/beta split is barely identified: simulation studies of GARCH(1,1) QMLE (e.g. Hwang &
#: Valls Pereira 2006) put the sample where persistence estimates stop being biased toward the
#: boundary and the optimiser stops failing at roughly 250-500 observations, so 250 is the floor
#: of that range, not a number tuned here. A sleeve below it keeps its historical dispersion.
MIN_OBS = 250

#: Two-sided 95% normal quantile for the band (see the module docstring for why a convention, not
#: a fit). Written as the quantile, not 1.96, so the reader sees which convention.
Z = float(norm.ppf(0.975))

#: Forecast horizon the allocator asks about when a caller does not say. Its worlds are daily and
#: its rebalance trigger is days, not weeks; the multi-step forecast decays toward unconditional
#: at rate p per day, so a long horizon would wash out exactly the clustering this file measures.
DEFAULT_HORIZON_DAYS = 5

#: Relative step for the finite-difference Hessian/gradient in the unconstrained space.
_FD_STEP = 1e-4


@dataclass
class GarchFit:
    """One GARCH(1,1) fit and its forecast. `ratio` is what a caller applies; everything else is
    the evidence for it."""

    status: str
    n: int
    horizon_days: int
    ratio: float = 1.0
    ratio_point: float | None = None
    band: tuple[float, float] | None = None
    se_log_ratio: float | None = None
    omega: float | None = None
    alpha: float | None = None
    beta: float | None = None
    mu: float | None = None
    loglik: float | None = None
    persistence: float | None = None
    half_life_days: float | None = None
    sample_vol: float | None = None
    forecast_var: list[float] = field(default_factory=list)
    param_se: dict[str, float] | None = None
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        def rnd(x: Any) -> Any:
            return None if x is None else round(float(x), 8)
        return {
            "status": self.status, "n": self.n, "horizon_days": self.horizon_days,
            "ratio": float(self.ratio),           # unrounded: readers apply it exactly
            "ratio_point": rnd(self.ratio_point),
            "band": (None if self.band is None
                     else [round(self.band[0], 6), round(self.band[1], 6)]),
            "se_log_ratio": rnd(self.se_log_ratio),
            "params": {"omega": rnd(self.omega), "alpha": rnd(self.alpha),
                       "beta": rnd(self.beta), "mu": rnd(self.mu)},
            "param_se": self.param_se, "loglik": rnd(self.loglik),
            "persistence": rnd(self.persistence), "half_life_days": rnd(self.half_life_days),
            "sample_vol": rnd(self.sample_vol),
            "forecast_var": [round(float(v), 10) for v in self.forecast_var],
            "why": self.why,
        }


def _clean(r: Iterable[float]) -> np.ndarray:
    a = np.asarray(list(r) if not isinstance(r, np.ndarray) else r, dtype=float).ravel()
    out: np.ndarray = a[np.isfinite(a)]
    return out


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x)) if x >= 0 else math.exp(x) / (1.0 + math.exp(x))


def _params(theta: np.ndarray) -> tuple[float, float, float]:
    """Unconstrained theta -> (omega, alpha, beta) with omega > 0 and 0 <= alpha + beta < 1."""
    omega = math.exp(float(theta[0]))
    p = _logistic(float(theta[1]))
    s = _logistic(float(theta[2]))
    return omega, p * s, p * (1.0 - s)


def _sigma2(theta: np.ndarray, e2: np.ndarray, s0: float) -> tuple[np.ndarray, float]:
    """In-sample conditional variances sigma2_0..sigma2_{n-1}, and the one-step forecast
    sigma2_n. sigma2_0 is the sample variance -- the conventional backcast, and past-only because
    the sample is the past."""
    omega, alpha, beta = _params(theta)
    x = np.empty(len(e2) + 1)
    x[0] = s0
    x[1:] = omega + alpha * e2
    y = lfilter([1.0], [1.0, -beta], x)
    return y[:-1], float(y[-1])


def _negloglik(theta: np.ndarray, e2: np.ndarray, s0: float) -> float:
    s2, _ = _sigma2(theta, e2, s0)
    if not np.all(np.isfinite(s2)) or np.any(s2 <= 0):
        return 1e300
    return float(0.5 * np.sum(np.log(2.0 * np.pi) + np.log(s2) + e2 / s2))


def _theta0(var: float, p: float, s: float) -> np.ndarray:
    omega = var * (1.0 - p)
    return np.array([math.log(omega), math.log(p / (1 - p)), math.log(s / (1 - s))])


def _hessian(f: Any, x: np.ndarray) -> np.ndarray:
    k = len(x)
    h = _FD_STEP * np.maximum(1.0, np.abs(x))
    out = np.empty((k, k))
    f0 = f(x)
    for i in range(k):
        for j in range(i, k):
            if i == j:
                xp, xm = x.copy(), x.copy()
                xp[i] += h[i]
                xm[i] -= h[i]
                out[i, i] = (f(xp) - 2 * f0 + f(xm)) / h[i] ** 2
            else:
                pp, pm, mp, mm = x.copy(), x.copy(), x.copy(), x.copy()
                pp[i] += h[i]
                pp[j] += h[j]
                pm[i] += h[i]
                pm[j] -= h[j]
                mp[i] -= h[i]
                mp[j] += h[j]
                mm[i] -= h[i]
                mm[j] -= h[j]
                out[i, j] = out[j, i] = (f(pp) - f(pm) - f(mp) + f(mm)) / (4 * h[i] * h[j])
    return out


def _grad(f: Any, x: np.ndarray) -> np.ndarray:
    h = _FD_STEP * np.maximum(1.0, np.abs(x))
    g = np.empty(len(x))
    for i in range(len(x)):
        xp, xm = x.copy(), x.copy()
        xp[i] += h[i]
        xm[i] -= h[i]
        g[i] = (f(xp) - f(xm)) / (2 * h[i])
    return g


def _variance_path(theta: np.ndarray, e2: np.ndarray, s0: float, horizon: int) -> np.ndarray:
    """E[sigma2_{n+h} | data to n-1] for h = 1..H: sbar + p^(h-1) (sigma2_n - sbar)."""
    omega, alpha, beta = _params(theta)
    p = alpha + beta
    sbar = omega / (1.0 - p)
    _, s_next = _sigma2(theta, e2, s0)
    return sbar + p ** np.arange(horizon) * (s_next - sbar)


def fit_garch11(r: Iterable[float], horizon_days: int = DEFAULT_HORIZON_DAYS,
                min_obs: int = MIN_OBS) -> GarchFit:
    """Fit GARCH(1,1) on `r` (NaNs dropped) and forecast the next `horizon_days` days.

    Every return path is a GarchFit; nothing raises on data. `ratio` is 1.0 unless MEASURED.
    """
    horizon = max(1, int(horizon_days))
    x = _clean(r)
    n = len(x)
    if n < min_obs:
        return GarchFit(UNMEASURED, n, horizon,
                        why=f"{n} non-NaN days < MIN_OBS={min_obs}: alpha/beta not identified")
    mu = float(np.mean(x))
    e = x - mu
    e2 = e * e
    var = float(np.var(x, ddof=1))
    if not math.isfinite(var) or var <= 0:
        return GarchFit(UNMEASURED, n, horizon, mu=mu,
                        why="sample variance is zero or not finite: nothing to scale")
    sample_vol = math.sqrt(var)

    def nll(th: np.ndarray) -> float:
        return _negloglik(th, e2, var)

    best = None
    # Three starts spanning the persistence range daily returns actually show; the likelihood is
    # well behaved in this parametrisation but a single start can stall on a flat ridge.
    for p0, s0 in ((0.95, 0.08), (0.80, 0.25), (0.50, 0.50)):
        try:
            res = minimize(nll, _theta0(var, p0, s0), method="L-BFGS-B")
        except (ValueError, FloatingPointError, OverflowError):  # pragma: no cover
            continue                    # one bad start is not a failed fit; the others decide
        if np.isfinite(res.fun) and (best is None or res.fun < best.fun):
            best = res
    if best is None or not np.isfinite(best.fun) or best.fun >= 1e299:
        return GarchFit(UNMEASURED, n, horizon, mu=mu, sample_vol=sample_vol,
                        why="optimiser found no finite likelihood")
    theta = np.asarray(best.x, dtype=float)
    omega, alpha, beta = _params(theta)
    p = alpha + beta
    loglik = -float(best.fun)
    half_life = (math.log(0.5) / math.log(p)) if 0 < p < 1 else (0.0 if p <= 0 else math.inf)
    base: dict[str, Any] = {"n": n, "horizon_days": horizon, "omega": omega, "alpha": alpha,
                            "beta": beta, "mu": mu, "loglik": loglik, "persistence": p,
                            "half_life_days": half_life, "sample_vol": sample_vol}
    if not (p < 1.0) or half_life > n:
        return GarchFit(UNMEASURED, **base,
                        why=(f"persistence {p:.6f}: shock half-life {half_life:.0f}d exceeds the "
                             f"{n}d sample, so the unconditional variance is not identified "
                             "(operationally alpha+beta >= 1)"))
    path = _variance_path(theta, e2, var, horizon)
    if not np.all(np.isfinite(path)) or np.any(path <= 0):
        return GarchFit(UNMEASURED, **base, why="forecast variance path not finite/positive")

    def log_ratio(th: np.ndarray) -> float:
        pv = _variance_path(th, e2, var, horizon)
        return 0.5 * math.log(float(np.mean(pv))) - math.log(sample_vol)

    lr = log_ratio(theta)
    try:
        hess = _hessian(nll, theta)
        cov = np.linalg.inv(hess)
        eig = np.linalg.eigvalsh(0.5 * (hess + hess.T))
    except np.linalg.LinAlgError:
        cov, eig = None, np.array([-1.0])
    if cov is None or not np.all(np.isfinite(cov)) or np.min(eig) <= 0:
        return GarchFit(UNMEASURED, **base, forecast_var=list(path),
                        ratio_point=math.exp(lr),
                        why="likelihood curvature not positive definite: the fit cannot state "
                            "its own uncertainty, so it is not applied")
    g = _grad(log_ratio, theta)
    var_lr = float(g @ cov @ g)
    if not math.isfinite(var_lr) or var_lr < 0:
        return GarchFit(UNMEASURED, **base, forecast_var=list(path), ratio_point=math.exp(lr),
                        why="delta-method variance of the ratio not finite")
    se = math.sqrt(var_lr)
    point = math.exp(lr)
    band = (math.exp(lr - Z * se), math.exp(lr + Z * se))
    # The asymmetric application (module docstring): risk-reducing estimates apply as measured,
    # risk-adding ones only by what the band proves.
    applied = point if point >= 1.0 else min(1.0, band[1])
    # Parameter standard errors in natural units, delta method through _params.
    try:
        jac = np.empty((3, 3))
        for i, fn in enumerate((lambda t: _params(t)[0], lambda t: _params(t)[1],
                                lambda t: _params(t)[2])):
            jac[i] = _grad(fn, theta)
        pcov = jac @ cov @ jac.T
        pse = {k: round(float(math.sqrt(max(v, 0.0))), 8)
               for k, v in zip(("omega", "alpha", "beta"), np.diag(pcov), strict=True)}
    except (ValueError, OverflowError):                                     # pragma: no cover
        pse = None
    return GarchFit(MEASURED, **base, ratio=applied, ratio_point=point, band=band,
                    se_log_ratio=se, forecast_var=list(path), param_se=pse,
                    why=("ratio>=1 applied as measured (risk-reducing)" if point >= 1.0 else
                         "ratio<1 applied only to the band's upper edge (risk-adding needs "
                         "proof)"))


def forecast_at(r: Iterable[float], t: int, horizon_days: int = DEFAULT_HORIZON_DAYS,
                min_obs: int = MIN_OBS) -> GarchFit:
    """The forecast an observer standing at index t would have made: fit on r[0..t] ONLY."""
    a = np.asarray(list(r) if not isinstance(r, np.ndarray) else r, dtype=float).ravel()
    return fit_garch11(a[: int(t) + 1], horizon_days=horizon_days, min_obs=min_obs)


def vol_scale_by_sleeve(ev: Iterable[Any], horizon_days: int = DEFAULT_HORIZON_DAYS,
                        min_obs: int = MIN_OBS) -> tuple[dict[str, float], dict[str, Any]]:
    """{sleeve name: dispersion ratio} for objects with `.name` and `.daily_r`, plus diagnostics.

    A sleeve whose fit is UNMEASURED gets exactly 1.0 -- its dispersion is what it was. The
    ratio scales DEVIATIONS about the sleeve's mean (`mean + ratio * (r - mean)`); a caller that
    multiplies the raw series instead would move the mean, which this family may not do.
    """
    scales: dict[str, float] = {}
    rows: dict[str, Any] = {}
    for e in ev:
        name = str(getattr(e, "name", ""))
        if not name:
            continue
        try:
            f = fit_garch11(getattr(e, "daily_r", []), horizon_days=horizon_days,
                            min_obs=min_obs)
        except Exception as exc:          # one sleeve's bad data never fails the pass
            f = GarchFit(UNMEASURED, 0, int(horizon_days),
                         why=f"fit raised {type(exc).__name__}: {exc}")
        scales[name] = float(f.ratio)
        rows[name] = f.as_dict()
    measured = [n for n, r in rows.items() if r["status"] == MEASURED]
    diag: dict[str, Any] = {
        "family": FAMILY, "roles": list(ROLES),
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "horizon_days": int(horizon_days), "min_obs": int(min_obs), "z": round(Z, 6),
        "n_sleeves": len(rows), "n_measured": len(measured),
        "n_scaled_up": sum(1 for n in measured if scales[n] > 1.0),
        "n_scaled_down": sum(1 for n in measured if scales[n] < 1.0),
        "by_sleeve": rows,
        "rule": ("GARCH(1,1) QMLE per sleeve on its own NaN-dropped daily R; ratio = "
                 f"sqrt(mean forecast var over {int(horizon_days)}d) / sample vol. Applied: "
                 "point if >= 1, else min(1, upper edge of the Z-sigma delta-method band). "
                 "UNMEASURED (n<min_obs, failed fit, half-life > sample, non-PD curvature) -> "
                 "1.0. Scales dispersion about the mean, never the mean."),
    }
    return scales, diag


def apply_vol_scale(daily_r: np.ndarray, ratio: float) -> np.ndarray:
    """`mean + ratio * (r - mean)` over the finite days; NaNs stay NaN. The mean is unchanged by
    construction, which is the whole of this family's contract with the allocator."""
    a = np.asarray(daily_r, dtype=float)
    fin = np.isfinite(a)
    if not fin.any() or not math.isfinite(ratio) or ratio <= 0:
        return a.copy()
    m = float(np.mean(a[fin]))
    out = a.copy()
    out[fin] = m + float(ratio) * (a[fin] - m)
    return out


def scales_from(diag: Mapping[str, Any]) -> dict[str, float]:
    """The applied ratios back out of a published diagnostics block (for a reader of the JSON)."""
    return {k: float(v.get("ratio", 1.0)) for k, v in (diag.get("by_sleeve") or {}).items()}
