"""Dupire local volatility from an implied-vol surface function.

THE SURFACE. `ImpliedSurface` is a parametric implied-vol function of log-moneyness
y = ln(K / F) and maturity T: ATM vol from the term points (total variance linearly interpolated
in T, flat vol beyond the ends) plus a smile `skew * y + curv * y^2`. With the desk's data (CBOE
term points, no chain) skew = curv = 0 and the model is TERM-STRUCTURE local vol,
sigma_LV^2(T) = d(sigma_imp^2 T)/dT, exactly.

LOCAL VARIANCE (Gatheral's form of Dupire in total implied variance w(y, T)):

    sigma_LV^2 = (dw/dT) / [1 - (y/w) w_y + 1/4 (-1/4 - 1/w + y^2/w^2) w_y^2 + 1/2 w_yy]

with derivatives by central differences of the surface function.

PRICING. A local-vol model reprices its own input smile by construction, so `price` is BS at the
surface IV for that strike and maturity (exact). `simulate` runs log-Euler under the local vol;
a test checks the simulated price against `price` within Monte Carlo error.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from libs.quant_models.base import YEAR_DAYS, MarketData, OptionSpec, StochasticModel
from libs.quant_models.numerics import FArr, bs_price, normals

MIN_VOL = 0.01


@dataclass(frozen=True)
class ImpliedSurface:
    tenors: tuple[float, ...] = (30.0 / YEAR_DAYS,)
    atm_vols: tuple[float, ...] = (0.2,)
    skew: float = 0.0
    curv: float = 0.0

    def atm_var(self, t: FArr) -> FArr:
        """ATM total variance w(0, T): linear in T between term points, flat vol outside."""
        ts = np.asarray(self.tenors, dtype=np.float64)
        ws = np.asarray(self.atm_vols, dtype=np.float64) ** 2 * ts
        tt = np.asarray(t, dtype=np.float64)
        inner = np.interp(tt, ts, ws)
        lo = (self.atm_vols[0] ** 2) * tt
        hi = (self.atm_vols[-1] ** 2) * tt
        return np.asarray(np.where(tt < ts[0], lo, np.where(tt > ts[-1], hi, inner)),
                          dtype=np.float64)

    def iv(self, y: FArr, t: FArr) -> FArr:
        tt = np.maximum(np.asarray(t, dtype=np.float64), 1e-8)
        atm = np.sqrt(self.atm_var(tt) / tt)
        yy = np.asarray(y, dtype=np.float64)
        return np.asarray(np.maximum(atm + self.skew * yy + self.curv * yy * yy, MIN_VOL),
                          dtype=np.float64)

    def total_var(self, y: FArr, t: FArr) -> FArr:
        tt = np.maximum(np.asarray(t, dtype=np.float64), 1e-8)
        v = self.iv(y, tt)
        return np.asarray(v * v * tt, dtype=np.float64)

    def local_var(self, y: FArr, t: FArr, dy: float = 1e-3, dt: float = 1e-4) -> FArr:
        yy = np.asarray(y, dtype=np.float64)
        tt = np.maximum(np.asarray(t, dtype=np.float64), 2 * dt)
        w = self.total_var(yy, tt)
        w_t = (self.total_var(yy, tt + dt) - self.total_var(yy, tt - dt)) / (2 * dt)
        wp, wm = self.total_var(yy + dy, tt), self.total_var(yy - dy, tt)
        w_y = (wp - wm) / (2 * dy)
        w_yy = (wp - 2 * w + wm) / (dy * dy)
        den = (1.0 - yy / w * w_y + 0.25 * (-0.25 - 1.0 / w + yy * yy / (w * w)) * w_y * w_y
               + 0.5 * w_yy)
        out = np.where(den > 1e-8, w_t / np.maximum(den, 1e-8), w / tt)
        return np.asarray(np.clip(out, MIN_VOL ** 2, 25.0), dtype=np.float64)


def fit_surface(data: MarketData, prior: ImpliedSurface) -> ImpliedSurface:
    pts = sorted((float(t), float(v)) for t, v in data.iv_term.items()
                 if t > 0 and v > 0 and math.isfinite(v))
    surf = (ImpliedSurface(tuple(p[0] for p in pts), tuple(p[1] for p in pts)) if pts
            else prior)
    if len(data.quotes) >= 3:
        ys = np.asarray([math.log(q.spec.strike / q.spec.forward) for q in data.quotes])
        ts = np.asarray([q.spec.expiry_years for q in data.quotes])
        resid = np.asarray([q.implied_vol for q in data.quotes]) - surf.iv(np.zeros_like(ys), ts)
        x = np.column_stack([ys, ys * ys])
        coef, *_ = np.linalg.lstsq(x, resid, rcond=None)
        surf = replace(surf, skew=float(coef[0]), curv=float(coef[1]))
    return surf


@dataclass(frozen=True)
class LocalVolParams:
    surface: ImpliedSurface = ImpliedSurface()


class LocalVol(StochasticModel):
    name = "local_vol"
    measure = "Q"
    params: LocalVolParams

    def __init__(self, params: LocalVolParams | None = None) -> None:
        self.params = params or LocalVolParams()

    @property
    def surface(self) -> ImpliedSurface:
        return self.params.surface

    def calibrate(self, data: MarketData) -> LocalVol:
        self.params = LocalVolParams(fit_surface(data, self.surface))
        return self

    def _iv(self, spec: OptionSpec) -> float:
        y = math.log(spec.strike / spec.forward)
        return float(self.surface.iv(np.asarray([y]), np.asarray([spec.expiry_years]))[0])

    def price(self, spec: OptionSpec) -> float:
        return bs_price(spec.kind, spec.spot, spec.strike, spec.expiry_years, spec.rate,
                        spec.div, self._iv(spec))

    def shift_vol(self, dvol: float) -> LocalVol:
        s = self.surface
        vols = tuple(max(v + dvol, MIN_VOL) for v in s.atm_vols)
        return self.copy_with(surface=replace(s, atm_vols=vols))

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        z = normals(np.random.default_rng(seed), n_paths, n_steps, antithetic)
        dt = horizon / n_steps
        x = np.zeros(n_paths)               # ln(S_t / F_t)
        out = np.empty((n_paths, n_steps + 1))
        out[:, 0] = spot
        for i in range(n_steps):
            lv = self.surface.local_var(x, np.full(n_paths, (i + 0.5) * dt))
            x = x - 0.5 * lv * dt + np.sqrt(lv * dt) * z[:, i]
            out[:, i + 1] = spot * math.exp((rate - div) * (i + 1) * dt) * np.exp(x)
        return out

    def vol_forecast(self, horizon_days: float) -> float:
        t = horizon_days / YEAR_DAYS
        return float(math.sqrt(float(self.surface.atm_var(np.asarray([t]))[0]) / t))

    def tail_prob(self, threshold_return: float, horizon_days: float) -> float:
        """Risk-neutral P(|ln S_T/S_0| > a) from the smile's digitals (-dC/dK, dP/dK)."""
        t = horizon_days / YEAR_DAYS
        up, dn = math.exp(threshold_return), math.exp(-threshold_return)

        def digital_call(k: float) -> float:
            h = 1e-4 * k
            return -(self.price(OptionSpec("call", k + h, t, 1.0))
                     - self.price(OptionSpec("call", k - h, t, 1.0))) / (2 * h)

        def digital_put(k: float) -> float:
            h = 1e-4 * k
            return (self.price(OptionSpec("put", k + h, t, 1.0))
                    - self.price(OptionSpec("put", k - h, t, 1.0))) / (2 * h)
        return float(min(max(digital_call(up) + digital_put(dn), 0.0), 1.0))

    def has_fast_price(self) -> bool:
        return True
