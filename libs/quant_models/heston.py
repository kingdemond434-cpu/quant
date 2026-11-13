"""Heston (1993) stochastic variance and Bates (1996) = Heston + Merton jumps.

PRICING: Lewis inversion of the "little trap" characteristic function (Albrecher et al. 2007),
which keeps the complex logarithm on its principal branch for long maturities; integration is
composite Gauss-Legendre on an adaptively truncated domain (`numerics.lewis_call`). As the
vol-of-vol goes to zero the CF degenerates (division by sigma^2), so below `SIGMA_MIN` the
deterministic-variance limit is used -- which IS Black-Scholes with the integrated variance.

SIMULATION: full-truncation Euler for the variance (Lord, Koekkoek, van Dijk 2010), log-Euler for
spot with the truncated variance, correlated by rho. Bates adds compensated lognormal jumps.

CALIBRATION, AS THE DESK'S DATA ALLOWS. With an ATM term structure only (VIX 9D/30D/3M/6M) the
smile parameters are not identified, so:
  v0, theta, kappa  least squares of the Heston expected-variance curve on the term points
                    (one point: v0 = iv^2, theta = mean IV^2 of the history, kappa from the AR(1)
                    of the IV^2 history);
  sigma             vol-of-vol of the IV^2 history: sd(dv) / sqrt(mean v * dt);
  rho               corr(daily return, daily change in IV) over the overlap;
and with a strike chain (`MarketData.quotes`) all five are refined by least squares on IVs.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from libs.quant_models.base import MarketData
from libs.quant_models.cfmodel import CFModel
from libs.quant_models.jumps import JumpParams, add_jumps, estimate_jumps, jump_exponent
from libs.quant_models.numerics import CArr, CharFn, FArr, implied_vol, normals

SIGMA_MIN = 1e-5
DT_IV = 1.0 / 252.0


@dataclass(frozen=True)
class HestonParams:
    v0: float = 0.04
    kappa: float = 2.0
    theta: float = 0.04
    sigma: float = 0.5
    rho: float = -0.7


def heston_expected_var(p: HestonParams, t: float) -> float:
    """(1/t) E[int_0^t v_s ds]."""
    if t <= 0:
        return p.v0
    kt = p.kappa * t
    w = (1.0 - math.exp(-kt)) / kt if kt > 1e-10 else 1.0
    return p.theta + (p.v0 - p.theta) * w


def heston_exponent(p: HestonParams, t: float, u: CArr) -> CArr:
    """ln phi(u) of the martingale log return (little-trap form)."""
    if p.sigma < SIGMA_MIN:
        return np.asarray(-0.5 * heston_expected_var(p, t) * t * (1j * u + u * u),
                          dtype=np.complex128)
    s2 = p.sigma * p.sigma
    b = p.kappa - p.rho * p.sigma * 1j * u
    d = np.sqrt(b * b + s2 * (1j * u + u * u))
    g = (b - d) / (b + d)
    e = np.exp(-d * t)
    big_b = (b - d) / s2 * (1.0 - e) / (1.0 - g * e)
    big_a = p.kappa * p.theta / s2 * ((b - d) * t - 2.0 * np.log((1.0 - g * e) / (1.0 - g)))
    return np.asarray(big_a + big_b * p.v0, dtype=np.complex128)


def _term_points(data: MarketData) -> list[tuple[float, float]]:
    return sorted((float(t), float(v) ** 2) for t, v in data.iv_term.items()
                  if t > 0 and v > 0 and math.isfinite(v))


def _ar1_kappa(v: FArr) -> float | None:
    if v.size < 60:
        return None
    x, y = v[:-1], v[1:]
    xc = x - x.mean()
    den = float((xc * xc).sum())
    if den <= 0:
        return None
    phi = float((xc * (y - y.mean())).sum() / den)
    if not 0.0 < phi < 1.0:
        return None
    return float(min(max(-math.log(phi) / DT_IV, 0.1), 50.0))


def _vol_of_vol(v: FArr) -> float | None:
    if v.size < 30:
        return None
    dv = np.diff(v)
    m = float(v.mean())
    if m <= 0:
        return None
    return float(min(max(float(dv.std(ddof=1)) / math.sqrt(m * DT_IV), 0.05), 5.0))


def _rho(returns: FArr, iv_hist: FArr) -> float | None:
    n = min(returns.size, iv_hist.size - 1)
    if n < 30:
        return None
    r, div = returns[-n:], np.diff(iv_hist)[-n:]
    if r.std() <= 0 or div.std() <= 0:
        return None
    return float(min(max(float(np.corrcoef(r, div)[0, 1]), -0.95), 0.95))


def fit_term(points: list[tuple[float, float]], kappa0: float, theta0: float
             ) -> tuple[float, float, float]:
    """(v0, kappa, theta) from term-structure variance points."""
    if len(points) == 1:
        t, w = points[0]
        p = HestonParams(v0=w, kappa=kappa0, theta=theta0)
        # solve v0 so the model's expected variance at t equals the quote
        kt = kappa0 * t
        wt = (1.0 - math.exp(-kt)) / kt if kt > 1e-10 else 1.0
        v0 = max((w - theta0 * (1.0 - wt)) / wt, 1e-6)
        return v0, p.kappa, theta0
    from scipy.optimize import least_squares
    ts = np.asarray([p[0] for p in points])
    ws = np.asarray([p[1] for p in points])

    def resid(x: FArr) -> FArr:
        q = HestonParams(v0=x[0], kappa=x[1], theta=x[2])
        model = np.asarray([heston_expected_var(q, t) for t in ts], dtype=np.float64)
        return np.asarray(model - ws, dtype=np.float64)
    x0 = np.asarray([ws[0], kappa0, max(theta0, 1e-4)])
    lo, hi = np.asarray([1e-6, 0.05, 1e-6]), np.asarray([4.0, 50.0, 4.0])
    sol = least_squares(resid, np.clip(x0, lo * 1.0001, hi * 0.9999), bounds=(lo, hi))
    return float(sol.x[0]), float(sol.x[1]), float(sol.x[2])


class Heston(CFModel):
    name = "heston"
    measure = "Q"
    params: HestonParams

    def __init__(self, params: HestonParams | None = None) -> None:
        self.params = params or HestonParams()

    # ---------------------------------------------------------------- calibration
    def _base_calibrate(self, data: MarketData) -> HestonParams:
        p = self.params
        ivh = np.asarray(data.iv_history, dtype=np.float64)
        ivh = ivh[np.isfinite(ivh) & (ivh > 0)]
        v_hist = ivh * ivh
        kappa = _ar1_kappa(v_hist) or p.kappa
        sigma = _vol_of_vol(v_hist) or p.sigma
        rho = _rho(np.asarray(data.returns, dtype=np.float64), ivh) or p.rho
        points = _term_points(data)
        theta0 = float(v_hist.mean()) if v_hist.size >= 20 else (points[-1][1] if points
                                                                   else p.theta)
        if points:
            v0, kappa, theta = fit_term(points, kappa, theta0)
        else:
            v0, theta = p.v0, theta0
        return HestonParams(v0=v0, kappa=kappa, theta=theta, sigma=sigma, rho=rho)

    def calibrate(self, data: MarketData) -> Heston:
        self.params = self._base_calibrate(data)
        if len(data.quotes) >= 5:
            self.params = self._fit_quotes(data)
        return self

    def _fit_quotes(self, data: MarketData) -> HestonParams:
        from scipy.optimize import least_squares
        quotes = list(data.quotes)
        p0 = self.params

        def resid(x: FArr) -> FArr:
            m = self.copy_with(v0=float(x[0]), kappa=float(x[1]), theta=float(x[2]),
                               sigma=float(x[3]), rho=float(x[4]))
            out = []
            for qt in quotes:
                iv = implied_vol(m.price(qt.spec), qt.spec.kind, qt.spec.spot, qt.spec.strike,
                                 qt.spec.expiry_years, qt.spec.rate, qt.spec.div)
                out.append((iv if iv is not None else 0.0) - qt.implied_vol)
            return np.asarray(out, dtype=np.float64)
        lo = np.asarray([1e-4, 0.05, 1e-4, 0.01, -0.99])
        hi = np.asarray([2.0, 30.0, 2.0, 4.0, 0.99])
        x0 = np.clip(np.asarray([p0.v0, p0.kappa, p0.theta, p0.sigma, p0.rho]), lo + 1e-6,
                     hi - 1e-6)
        sol = least_squares(resid, x0, bounds=(lo, hi), max_nfev=60)
        return replace(p0, v0=float(sol.x[0]), kappa=float(sol.x[1]), theta=float(sol.x[2]),
                       sigma=float(sol.x[3]), rho=float(sol.x[4]))

    # ---------------------------------------------------------------- CF interface
    def cf(self, t: float) -> CharFn:
        p = self.params

        def phi(u: CArr) -> CArr:
            return np.asarray(np.exp(heston_exponent(p, t, u)), dtype=np.complex128)
        return phi

    def expected_var(self, t: float) -> float:
        return heston_expected_var(self.params, t)

    def shift_vol(self, dvol: float) -> Heston:
        """Shift sqrt(v0) and sqrt(theta) together: a parallel move of the vol level."""
        p = self.params
        v0 = (math.sqrt(p.v0) + dvol) ** 2
        th = (math.sqrt(p.theta) + dvol) ** 2
        return self.copy_with(v0=max(v0, 1e-10), theta=max(th, 1e-10))

    # ---------------------------------------------------------------- simulation
    def _variance_paths(self, rng: np.random.Generator, n_paths: int, n_steps: int,
                        dt: float, antithetic: bool) -> tuple[FArr, FArr]:
        """Full-truncation Euler: (truncated variance per step, spot normals)."""
        p = self.params
        zv = normals(rng, n_paths, n_steps, antithetic)
        zp = normals(rng, n_paths, n_steps, antithetic)
        zs = p.rho * zv + math.sqrt(max(1.0 - p.rho ** 2, 0.0)) * zp
        v = np.full(n_paths, p.v0)
        vplus = np.empty((n_paths, n_steps))
        for i in range(n_steps):
            vp = np.maximum(v, 0.0)
            vplus[:, i] = vp
            v = v + p.kappa * (p.theta - vp) * dt + p.sigma * np.sqrt(vp * dt) * zv[:, i]
        return vplus, np.asarray(zs, dtype=np.float64)

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        rng = np.random.default_rng(seed)
        dt = horizon / n_steps
        vplus, zs = self._variance_paths(rng, n_paths, n_steps, dt, antithetic)
        incr = (rate - div - 0.5 * vplus) * dt + np.sqrt(vplus * dt) * zs
        incr = self._jumps(incr, dt, rng)
        logs = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(incr, axis=1)], axis=1)
        return np.asarray(spot * np.exp(logs), dtype=np.float64)

    def _jumps(self, incr: FArr, dt: float, rng: np.random.Generator) -> FArr:
        return incr


@dataclass(frozen=True)
class BatesParams(HestonParams):
    lam: float = 0.0
    mu_j: float = 0.0
    delta_j: float = 0.0

    @property
    def jumps(self) -> JumpParams:
        return JumpParams(self.lam, self.mu_j, self.delta_j)


class Bates(Heston):
    """Heston variance plus Merton lognormal jumps (Bates 1996)."""

    name = "bates"
    params: BatesParams

    def __init__(self, params: BatesParams | None = None) -> None:
        self.params = params or BatesParams()

    def calibrate(self, data: MarketData) -> Bates:
        base = self._base_calibrate(data)
        j = estimate_jumps(np.asarray(data.returns, dtype=np.float64))
        # the jumps carry part of the quoted variance: take it out of the diffusive level
        jv = j.var_per_year
        v0 = max(base.v0 - jv, 0.1 * base.v0)
        theta = max(base.theta - jv, 0.1 * base.theta)
        self.params = BatesParams(v0=v0, kappa=base.kappa, theta=theta, sigma=base.sigma,
                                  rho=base.rho, lam=j.lam, mu_j=j.mu_j, delta_j=j.delta_j)
        return self

    def cf(self, t: float) -> CharFn:
        p = self.params

        def phi(u: CArr) -> CArr:
            return np.asarray(np.exp(heston_exponent(p, t, u) + t * jump_exponent(p.jumps, u)),
                              dtype=np.complex128)
        return phi

    def expected_var(self, t: float) -> float:
        return heston_expected_var(self.params, t) + self.params.jumps.var_per_year

    def _jumps(self, incr: FArr, dt: float, rng: np.random.Generator) -> FArr:
        return add_jumps(incr, self.params.jumps, dt, rng)

    def heston_part(self) -> Heston:
        p = self.params
        return Heston(HestonParams(p.v0, p.kappa, p.theta, p.sigma, p.rho))


def as_bates(h: Heston, jumps: JumpParams) -> Bates:
    p = h.params
    return Bates(replace(BatesParams(), v0=p.v0, kappa=p.kappa, theta=p.theta, sigma=p.sigma,
                         rho=p.rho, lam=jumps.lam, mu_j=jumps.mu_j, delta_j=jumps.delta_j))
