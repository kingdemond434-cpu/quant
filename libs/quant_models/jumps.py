"""Merton (1976) jump-diffusion: GBM plus compound-Poisson lognormal jumps.

Closed form: the Poisson-weighted series of Black-Scholes prices. The CF (diffusion exponent plus
the compensated jump exponent) also prices it by Lewis inversion; the two must agree, and with
zero jump intensity both must equal Black-Scholes (a seeded-defect test).

Jump parameters are estimated from daily returns by a robust threshold rule (`estimate_jumps`):
returns beyond `k` robust standard deviations of the median are jumps. A count of jumps below
`min_jumps` leaves the jump intensity at zero rather than inventing one.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from libs.quant_models.base import MarketData, OptionSpec
from libs.quant_models.cfmodel import CFModel
from libs.quant_models.numerics import CArr, CharFn, FArr, bs_price, normals

TRADING_YEAR = 252.0


@dataclass(frozen=True)
class JumpParams:
    lam: float = 0.0       # jumps per year
    mu_j: float = 0.0      # mean log jump
    delta_j: float = 0.0   # sd of the log jump

    @property
    def kbar(self) -> float:
        """E[e^J] - 1, the compensator per jump."""
        return math.exp(self.mu_j + 0.5 * self.delta_j ** 2) - 1.0

    @property
    def var_per_year(self) -> float:
        return self.lam * (self.mu_j ** 2 + self.delta_j ** 2)


def jump_exponent(j: JumpParams, u: CArr) -> CArr:
    """Compensated jump characteristic exponent (per unit time)."""
    return np.asarray(j.lam * (np.exp(1j * u * j.mu_j - 0.5 * j.delta_j ** 2 * u * u) - 1.0)
                      - 1j * u * j.lam * j.kbar, dtype=np.complex128)


def estimate_jumps(returns: FArr, k: float = 4.0, min_jumps: int = 2) -> JumpParams:
    """Threshold jump estimate on daily log returns (MAD-scaled)."""
    r = np.asarray(returns, dtype=np.float64)
    r = r[np.isfinite(r)]
    if r.size < 60:
        return JumpParams()
    med = float(np.median(r))
    mad = float(np.median(np.abs(r - med))) * 1.4826
    if mad <= 0:
        return JumpParams()
    hits = r[np.abs(r - med) > k * mad]
    if hits.size < min_jumps:
        return JumpParams()
    lam = hits.size / (r.size / TRADING_YEAR)
    sd = float(hits.std(ddof=1)) if hits.size > 1 else abs(float(hits.mean()))
    return JumpParams(lam=float(lam), mu_j=float(hits.mean()), delta_j=sd)


def add_jumps(log_incr: FArr, j: JumpParams, dt: float, rng: np.random.Generator) -> FArr:
    """Add compensated compound-Poisson lognormal jumps to per-step log increments."""
    if j.lam <= 0:
        return log_incr
    n = rng.poisson(j.lam * dt, size=log_incr.shape)
    jump = n * j.mu_j + np.sqrt(n) * j.delta_j * rng.standard_normal(log_incr.shape)
    return np.asarray(log_incr + jump - j.lam * j.kbar * dt, dtype=np.float64)


@dataclass(frozen=True)
class MertonParams:
    vol: float = 0.2
    lam: float = 0.0
    mu_j: float = 0.0
    delta_j: float = 0.0

    @property
    def jumps(self) -> JumpParams:
        return JumpParams(self.lam, self.mu_j, self.delta_j)


class Merton(CFModel):
    name = "merton_jd"
    measure = "Q"
    max_terms = 80

    def __init__(self, params: MertonParams | None = None) -> None:
        self.params = params or MertonParams()

    def calibrate(self, data: MarketData) -> Merton:
        """Jumps from returns (physical estimate, used as the Q jump law); diffusion vol so the
        model's total 30-day variance matches the market ATM IV."""
        j = estimate_jumps(data.returns)
        iv = data.atm_iv()
        if iv is None:
            r = np.asarray(data.returns, dtype=np.float64)
            iv = float(r.std(ddof=1) * math.sqrt(TRADING_YEAR)) if r.size > 20 else self.params.vol
        diff_var = max(iv * iv - j.var_per_year, 0.1 * iv * iv)
        self.params = MertonParams(math.sqrt(diff_var), j.lam, j.mu_j, j.delta_j)
        return self

    def cf(self, t: float) -> CharFn:
        p = self.params

        def phi(u: CArr) -> CArr:
            diff = -0.5 * p.vol ** 2 * (1j * u + u * u)
            return np.asarray(np.exp(t * (diff + jump_exponent(p.jumps, u))),
                              dtype=np.complex128)
        return phi

    def expected_var(self, t: float) -> float:
        return self.params.vol ** 2 + self.params.jumps.var_per_year

    def price(self, spec: OptionSpec) -> float:
        """Merton's series: sum_n Pois(n; lam' T) * BS(sigma_n, r_n)."""
        p, t = self.params, spec.expiry_years
        if p.lam <= 0 or t <= 0:
            return bs_price(spec.kind, spec.spot, spec.strike, t, spec.rate, spec.div, p.vol)
        k = p.jumps.kbar
        lam_p = p.lam * (1.0 + k)
        total, log_w = 0.0, -lam_p * t
        for n in range(self.max_terms):
            if n > 0:
                log_w += math.log(lam_p * t) - math.log(n)
            vol_n = math.sqrt(p.vol ** 2 + n * p.delta_j ** 2 / t)
            r_n = spec.rate - p.lam * k + n * math.log(1.0 + k) / t
            # Pois(n; lam' T) BS(r_n, sigma_n) == Pois(n; lam T) e^{(r_n - r) T} BS(r_n, ...)
            total += math.exp(log_w) * bs_price(spec.kind, spec.spot, spec.strike, t, r_n,
                                                spec.div, vol_n)
            if n > lam_p * t + 10 and math.exp(log_w) < 1e-16:
                break
        return total

    def shift_vol(self, dvol: float) -> Merton:
        return self.copy_with(vol=max(self.params.vol + dvol, 1e-6))

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        rng = np.random.default_rng(seed)
        z = normals(rng, n_paths, n_steps, antithetic)
        dt = horizon / n_steps
        v = self.params.vol
        incr = (rate - div - 0.5 * v * v) * dt + v * math.sqrt(dt) * z
        incr = add_jumps(incr, self.params.jumps, dt, rng)
        logs = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(incr, axis=1)], axis=1)
        return np.asarray(spot * np.exp(logs), dtype=np.float64)
