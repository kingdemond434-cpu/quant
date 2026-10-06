"""Rough volatility (rough-Bergomi style) by a Markov lift of the fractional kernel into OU
factors (ROMAN-0392, ROMAN-0803; representation rows ROMAN-0813..0818).

THE LIFT (Abi Jaber & El Euch 2019, own implementation). The Riemann-Liouville kernel

    K(t) = t^{H - 1/2} / Gamma(H + 1/2) = int_0^inf e^{-x t} mu(dx),
    mu(dx) = x^{-(H + 1/2)} / (Gamma(H + 1/2) Gamma(1/2 - H)) dx

is discretised on geometric buckets of x into n factors with weights c_i = mu(bucket_i) and
mean-reversion speeds x_i = (int x mu) / c_i. Then Y_t = sum_i c_i Z^i_t with

    dZ^i_t = -x_i Z^i_t dt + dW_t          (one Brownian motion drives all factors)

is a finite-dimensional MARKOV approximation of the Volterra process int K(t-s) dW_s, and the
variance is v_t = xi0 * exp(eta Y_t - eta^2 / 2 * Var(Y_t)).

THE FACTOR STATES ARE THE REPRESENTATION. `factor_states()` returns Z^1..Z^n at as_of: slow
factors carry vol memory/persistence (ROMAN-0813/0814), the fast ones the most recent shock
(crash-state persistence, ROMAN-0815). The disagreement factory writes them to its lake series.

CALIBRATION FROM DATA THE DESK HOLDS.
  H       the log-RV variogram: E[(log sigma_{t+D} - log sigma_t)^2] ~ D^{2H} (Gatheral, Jaisson
          and Rosenbaum 2018);
  eta     so the lifted stationary variance of eta * Y equals the window's variance of log RV.
  level   the mean log RV of the filtering window (measure P: this model never sees the IV, so
          `market IV - rough forecast` is a premium, not an identity).
  Z       filtered day by day: the observed log-variance deviation is inverted for the day's
          Brownian increment, clipped at 5 sd, and pushed through the exact OU decay.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from libs.quant_models.base import YEAR_DAYS, MarketData, OptionSpec, StochasticModel
from libs.quant_models.numerics import FArr, normals

DAY = 1.0 / 252.0


@dataclass(frozen=True)
class RoughParams:
    xi0: float = 0.04
    hurst: float = 0.1
    eta: float = 1.5
    rho: float = -0.7
    n_factors: int = 8
    x_lo: float = 1.0
    x_hi: float = 1.0e4
    #: Factor states at as_of; empty means "unconditional" (the classic rBergomi start, with a
    #: flat forward variance xi0).
    state: tuple[float, ...] = field(default_factory=tuple)
    #: Mean log annualised variance of the filtering window: with a state, log v = level + eta Y.
    log_level: float = math.log(0.04)


def lift(hurst: float, n: int, x_lo: float, x_hi: float) -> tuple[FArr, FArr]:
    """(weights c_i, speeds x_i) of the OU lift of K(t) = t^{H-1/2}/Gamma(H+1/2)."""
    a = hurst + 0.5
    norm = math.gamma(a) * math.gamma(1.0 - a)
    edges = np.concatenate([[0.0], np.geomspace(x_lo, x_hi, n)])
    lo, hi = edges[:-1], edges[1:]
    c = (hi ** (1.0 - a) - lo ** (1.0 - a)) / ((1.0 - a) * norm)
    m1 = (hi ** (2.0 - a) - lo ** (2.0 - a)) / ((2.0 - a) * norm)
    return np.asarray(c, dtype=np.float64), np.asarray(m1 / c, dtype=np.float64)


def _cov_grow(c: FArr, x: FArr, s: float) -> float:
    """Var of sum c_i int_0^s e^{-x_i (s-u)} dW_u."""
    xs = x[:, None] + x[None, :]
    return float((c[:, None] * c[None, :] * (1.0 - np.exp(-xs * s)) / xs).sum())


def _var_stationary(c: FArr, x: FArr) -> float:
    xs = x[:, None] + x[None, :]
    return float((c[:, None] * c[None, :] / xs).sum())


def estimate_hurst(log_vol: FArr, lags: tuple[int, ...] = (1, 2, 3, 5, 8, 13)
                   ) -> tuple[float, float] | None:
    """(H, m(1 day)) from the log-vol variogram slope: log m(D) = 2H log D + const."""
    lv = np.asarray(log_vol, dtype=np.float64)
    lv = lv[np.isfinite(lv)]
    if lv.size < 60:
        return None
    ms = []
    for d in lags:
        dd = lv[d:] - lv[:-d]
        ms.append(float(np.mean(dd * dd)))
    ms_a = np.asarray(ms)
    if (ms_a <= 0).any():
        return None
    slope = float(np.polyfit(np.log(np.asarray(lags, dtype=np.float64)), np.log(ms_a), 1)[0])
    h = min(max(0.5 * slope, 0.02), 0.45)
    return h, float(ms_a[0])


def daily_log_var(data: MarketData) -> FArr:
    """Daily log variance proxy: HF RV when intraday returns exist, else 5-day squared returns."""
    if len(data.intraday_returns) >= 60:
        rv = np.asarray([float(np.sum(np.asarray(x) ** 2)) for x in data.intraday_returns])
        rv = np.where(rv > 0, rv, np.nan)
        return np.asarray(np.log(rv / DAY), dtype=np.float64)
    r = np.asarray(data.returns, dtype=np.float64)
    if r.size < 10:
        return np.zeros(0)
    sq = np.convolve(r * r, np.ones(5) / 5.0, mode="valid")
    return np.asarray(np.log(np.maximum(sq, 1e-12) / DAY), dtype=np.float64)


class RoughVol(StochasticModel):
    """Measure P: fitted to the desk's own realised variance, so `market IV - rough forecast` is a
    premium of the implied level over the rough-vol forecast (ROMAN-0809)."""

    name = "rough_vol"
    measure = "P"
    params: RoughParams
    mc_paths = 8000

    def __init__(self, params: RoughParams | None = None) -> None:
        self.params = params or RoughParams()

    # ---------------------------------------------------------------- the lift
    def kernel(self) -> tuple[FArr, FArr]:
        p = self.params
        return lift(p.hurst, p.n_factors, p.x_lo, p.x_hi)

    def factor_states(self) -> FArr:
        return np.asarray(self.params.state or np.zeros(self.params.n_factors),
                          dtype=np.float64)

    def _log_var(self, y: FArr, c: FArr, x: FArr, s: float) -> FArr:
        """log v at forward time s given Y: with a state, level + eta Y (Y stationary, mean 0);
        without one, the classic rBergomi exp-martingale with flat forward variance xi0."""
        p = self.params
        if p.state:
            return np.asarray(p.log_level + p.eta * y, dtype=np.float64)
        return np.asarray(math.log(p.xi0) + p.eta * y - 0.5 * p.eta ** 2 * _cov_grow(c, x, s),
                          dtype=np.float64)

    def forward_variance(self, s: float) -> float:
        """E[v_{t+s} | factor states]."""
        p = self.params
        if not p.state:
            return p.xi0
        c, x = self.kernel()
        mean = float((c * np.exp(-x * s) * self.factor_states()).sum())
        return math.exp(p.log_level + p.eta * mean + 0.5 * p.eta ** 2 * _cov_grow(c, x, s))

    # ---------------------------------------------------------------- calibration
    def calibrate(self, data: MarketData) -> RoughVol:
        """H from the log-vol variogram; eta so the lifted stationary variance of eta Y equals
        the window's variance of log RV; level = the window's mean log RV; Z filtered."""
        p = self.params
        lv = daily_log_var(data)
        fin = lv[np.isfinite(lv)]
        window = fin[-504:]
        if window.size < 60:
            return self
        hm = estimate_hurst(0.5 * fin)
        hurst = hm[0] if hm is not None else p.hurst
        c, x = lift(hurst, p.n_factors, p.x_lo, p.x_hi)
        level = float(window.mean())
        v_emp = float(window.var(ddof=1))
        eta = min(max(math.sqrt(v_emp / _var_stationary(c, x)), 0.05), 5.0)
        self.params = RoughParams(xi0=float(np.exp(window).mean()), hurst=hurst, eta=eta,
                                  rho=p.rho, n_factors=p.n_factors, x_lo=p.x_lo, x_hi=p.x_hi,
                                  state=self._filter(window - level, hurst, eta),
                                  log_level=level)
        return self

    def _filter(self, dev: FArr, hurst: float, eta: float) -> tuple[float, ...]:
        """Invert each day's log-variance deviation for the Brownian increment (clipped at 5 sd)
        and push it through the exact OU decay of every factor."""
        p = self.params
        c, x = lift(hurst, p.n_factors, p.x_lo, p.x_hi)
        decay = np.exp(-x * DAY)
        w = (1.0 - decay) / (x * DAY)
        gain = float((c * w).sum())
        z = np.zeros_like(c)
        cap = 5.0 * math.sqrt(DAY)
        for d in dev:
            y_pred = float((c * decay * z).sum())
            dw = min(max((float(d) / eta - y_pred) / gain, -cap), cap)
            z = decay * z + w * dw
        return tuple(float(v) for v in z)

    # ---------------------------------------------------------------- dynamics
    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        p = self.params
        rng = np.random.default_rng(seed)
        dt = horizon / n_steps
        c, x = self.kernel()
        decay = np.exp(-x * dt)
        w = (1.0 - decay) / (x * dt)
        zw = normals(rng, n_paths, n_steps, antithetic)
        zp = normals(rng, n_paths, n_steps, antithetic)
        zs = p.rho * zw + math.sqrt(max(1.0 - p.rho ** 2, 0.0)) * zp
        z = np.tile(self.factor_states(), (n_paths, 1))
        logs = np.zeros((n_paths, n_steps + 1))
        for i in range(n_steps):
            v = np.minimum(np.exp(self._log_var(z @ c, c, x, i * dt)), 25.0)
            logs[:, i + 1] = (logs[:, i] + (rate - div - 0.5 * v) * dt
                              + np.sqrt(v * dt) * zs[:, i])
            z = z * decay[None, :] + (math.sqrt(dt) * zw[:, i])[:, None] * w[None, :]
        return np.asarray(spot * np.exp(logs), dtype=np.float64)

    def price(self, spec: OptionSpec) -> float:
        steps = int(min(max(round(spec.expiry_years * 252), 8), 64))
        return self.mc_price(spec, n_paths=self.mc_paths, n_steps=steps).price

    def has_fast_price(self) -> bool:
        return False

    def shift_vol(self, dvol: float) -> RoughVol:
        p = self.params
        v = max(math.sqrt(p.xi0) + dvol, 1e-4)
        return self.copy_with(xi0=v * v, log_level=p.log_level + 2.0 * math.log(
            v / math.sqrt(p.xi0)))

    def vol_forecast(self, horizon_days: float) -> float:
        t = horizon_days / YEAR_DAYS
        s = np.linspace(0.0, t, 33)
        fv = np.asarray([self.forward_variance(float(si)) for si in s])
        return float(math.sqrt(max(float(np.trapezoid(fv, s)) / t, 0.0)))
