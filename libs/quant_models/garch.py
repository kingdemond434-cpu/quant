"""GARCH(1,1) and EWMA conditional variance on daily log returns (measure P).

GARCH(1,1)  h_{t+1} = omega + alpha r_t^2 + beta h_t, fitted by Gaussian MLE (scipy L-BFGS-B on
            bounded parameters, alpha + beta < 1 enforced by a penalty). Multi-step forecast
            E[h_{t+k}] = hbar + (alpha + beta)^{k-1} (h_{t+1} - hbar). Pricing and simulation use
            Duan's (1995) locally risk-neutral dynamics r_t = r - q - h_t / 2 + sqrt(h_t) z_t.
EWMA        RiskMetrics recursion through `libs.research.volatility_signals.ewma_variance` (the
            desk's one EWMA, no second lane); the decay is fitted by the same Gaussian likelihood
            on a bounded scalar search. The forecast is flat, so EWMA prices as Black-Scholes at
            its one-step vol.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from libs.quant_models.base import YEAR_DAYS, MarketData, OptionSpec, StochasticModel
from libs.quant_models.black_scholes import BlackScholes, BSParams
from libs.quant_models.numerics import FArr, normals
from libs.research.volatility_signals import ewma_variance

TRADING_YEAR = 252.0


@dataclass(frozen=True)
class GarchParams:
    omega: float = 2e-6
    alpha: float = 0.08
    beta: float = 0.9
    #: the one-step-ahead conditional variance at as_of (daily units)
    h_next: float = 1e-4

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def long_run_var(self) -> float:
        return self.omega / max(1.0 - self.persistence, 1e-6)


def garch_filter(r: FArr, omega: float, alpha: float, beta: float, h0: float) -> FArr:
    """Conditional variances h_1..h_{n+1} (h_{n+1} is the forecast after the last return)."""
    h = np.empty(r.size + 1)
    h[0] = h0
    for i in range(r.size):
        h[i + 1] = omega + alpha * r[i] * r[i] + beta * h[i]
    return h


def garch_nll(x: FArr, r: FArr, h0: float) -> float:
    omega, alpha, beta = float(x[0]), float(x[1]), float(x[2])
    if alpha + beta >= 0.9999:
        return 1e10 + 1e10 * (alpha + beta)
    h = garch_filter(r, omega, alpha, beta, h0)[:-1]
    if (h <= 0).any():
        return 1e12
    return float(0.5 * np.sum(np.log(h) + r * r / h))


def fit_garch(returns: FArr) -> GarchParams:
    """Gaussian MLE of GARCH(1,1) on demeaned daily log returns, from a grid of starts."""
    from scipy.optimize import minimize
    r = np.asarray(returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    r = r - r.mean()
    var = float(r.var())
    if r.size < 100 or var <= 0:
        return GarchParams(omega=var * 0.05, alpha=0.05, beta=0.9, h_next=max(var, 1e-10))
    scale = 1.0 / math.sqrt(var)            # fit on unit-variance returns: well conditioned
    z = r * scale
    best = None
    for a0, b0 in ((0.05, 0.9), (0.1, 0.85), (0.03, 0.95), (0.15, 0.7)):
        x0 = np.asarray([1.0 - a0 - b0, a0, b0])
        sol = minimize(garch_nll, x0, args=(z, 1.0), method="L-BFGS-B",
                       bounds=[(1e-6, 2.0), (1e-6, 0.6), (0.0, 0.9989)])
        if best is None or sol.fun < best.fun:
            best = sol
    assert best is not None
    om, al, be = (float(v) for v in best.x)
    h = garch_filter(z, om, al, be, 1.0)
    return GarchParams(omega=om / (scale * scale), alpha=al, beta=be,
                       h_next=float(h[-1]) / (scale * scale))


def simulate_garch(p: GarchParams, n_paths: int, n_days: int, seed: int,
                   rate: float = 0.0, div: float = 0.0, antithetic: bool = False) -> FArr:
    """Daily log-return paths (n_paths, n_days) under Duan's risk-neutral dynamics."""
    z = normals(np.random.default_rng(seed), n_paths, n_days, antithetic)
    h = np.full(n_paths, p.h_next)
    out = np.empty((n_paths, n_days))
    mu = (rate - div) / TRADING_YEAR
    for i in range(n_days):
        eps = np.sqrt(h) * z[:, i]
        out[:, i] = mu - 0.5 * h + eps
        h = p.omega + p.alpha * eps * eps + p.beta * h
    return out


def subsample_paths(spot: float, daily: FArr, n_steps: int) -> FArr:
    logs = np.concatenate([np.zeros((daily.shape[0], 1)), np.cumsum(daily, axis=1)], axis=1)
    idx = np.round(np.linspace(0, daily.shape[1], n_steps + 1)).astype(int)
    return np.asarray(spot * np.exp(logs[:, idx]), dtype=np.float64)


class Garch(StochasticModel):
    name = "garch"
    measure = "P"
    params: GarchParams

    def __init__(self, params: GarchParams | None = None) -> None:
        self.params = params or GarchParams()

    def calibrate(self, data: MarketData) -> Garch:
        self.params = fit_garch(np.asarray(data.returns, dtype=np.float64))
        return self

    def update(self, new_returns: FArr) -> Garch:
        """Roll the conditional variance forward over new returns with the parameters fixed (the
        cheap daily step between weekly refits)."""
        p = self.params
        h = garch_filter(np.asarray(new_returns, dtype=np.float64), p.omega, p.alpha, p.beta,
                         p.h_next)
        return self.copy_with(h_next=float(h[-1]))

    def mean_var(self, n_days: int) -> float:
        """Average expected daily variance over the next n_days."""
        p = self.params
        hbar, ph = p.long_run_var, p.persistence
        k = np.arange(n_days)
        return float(np.mean(hbar + ph ** k * (p.h_next - hbar)))

    def vol_forecast(self, horizon_days: float) -> float:
        n = max(1, round(horizon_days * TRADING_YEAR / YEAR_DAYS))
        return math.sqrt(self.mean_var(n) * TRADING_YEAR)

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        n_days = max(1, round(horizon * TRADING_YEAR))
        daily = simulate_garch(self.params, n_paths, n_days, seed, rate, div, antithetic)
        return subsample_paths(spot, daily, n_steps)

    def price(self, spec: OptionSpec) -> float:
        n_days = max(1, round(spec.expiry_years * TRADING_YEAR))
        return self.mc_price(spec, n_paths=self.mc_paths, n_steps=n_days).price

    def has_fast_price(self) -> bool:
        return False

    def shift_vol(self, dvol: float) -> Garch:
        """Shift the vol level: scale omega and h_next so sqrt(long-run var) moves by dvol."""
        p = self.params
        lr = math.sqrt(p.long_run_var * TRADING_YEAR)
        f = (max(lr + dvol, 1e-4) / lr) ** 2
        return self.copy_with(omega=p.omega * f, h_next=p.h_next * f)


@dataclass(frozen=True)
class EwmaParams(BSParams):
    lam: float = 0.94


def ewma_nll(lam: float, r: FArr) -> float:
    h = ewma_variance(r, lam=lam)[1:]
    x = r[1:]
    ok = np.isfinite(h) & (h > 0)
    return float(0.5 * np.sum(np.log(h[ok]) + x[ok] ** 2 / h[ok]))


class Ewma(BlackScholes):
    name = "ewma"
    measure = "P"
    params: EwmaParams

    def __init__(self, params: EwmaParams | None = None) -> None:
        self.params = params or EwmaParams()

    def calibrate(self, data: MarketData) -> Ewma:
        from scipy.optimize import minimize_scalar
        r = np.asarray(data.returns, dtype=np.float64)
        r = r[np.isfinite(r)]
        if r.size < 30:
            return self
        lam = self.params.lam
        if r.size >= 250:
            sol = minimize_scalar(ewma_nll, bounds=(0.8, 0.995), args=(r,), method="bounded")
            lam = float(sol.x)
        h = ewma_variance(np.append(r, 0.0), lam=lam)[-1]   # forecast after the last return
        self.params = EwmaParams(vol=math.sqrt(float(h) * TRADING_YEAR), lam=lam)
        return self
