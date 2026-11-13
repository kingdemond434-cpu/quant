"""Black-Scholes(-Merton): constant volatility, the reference every other model collapses to.

`BlackScholes` is calibrated to the market ATM implied vol (measure Q). The realised-vol models
in `realised.py` subclass it and calibrate the same constant vol from returns (measure P), so
they price, hedge and simulate through exactly the same closed forms.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from libs.quant_models.base import YEAR_DAYS, Greeks, MarketData, OptionSpec, StochasticModel
from libs.quant_models.numerics import (
    FArr,
    bs_greeks,
    bs_price,
    gbm_paths,
    norm_cdf,
    normals,
)


@dataclass(frozen=True)
class BSParams:
    vol: float = 0.2


class BlackScholes(StochasticModel):
    name = "black_scholes"
    params: BSParams

    def __init__(self, params: BSParams | None = None) -> None:
        self.params = params or BSParams()

    @property
    def vol(self) -> float:
        return float(self.params.vol)

    def calibrate(self, data: MarketData) -> BlackScholes:
        iv = data.atm_iv()
        if iv is not None:
            self.params = BSParams(vol=iv)
        elif data.quotes:
            self.params = BSParams(vol=float(np.mean([q.implied_vol for q in data.quotes])))
        return self

    def price(self, spec: OptionSpec) -> float:
        return bs_price(spec.kind, spec.spot, spec.strike, spec.expiry_years, spec.rate,
                        spec.div, self.vol)

    def greeks(self, spec: OptionSpec) -> Greeks:
        g = bs_greeks(spec.kind, spec.spot, spec.strike, spec.expiry_years, spec.rate,
                      spec.div, self.vol)
        return Greeks(g["delta"], g["gamma"], g["vega"], g["theta"], g["rho"])

    def shift_vol(self, dvol: float) -> BlackScholes:
        return self.copy_with(vol=max(self.vol + dvol, 1e-6))

    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        z = normals(np.random.default_rng(seed), n_paths, n_steps, antithetic)
        return gbm_paths(spot, np.full_like(z, self.vol), horizon, rate, div, z)

    def vol_forecast(self, horizon_days: float) -> float:
        return self.vol

    def tail_prob(self, threshold_return: float, horizon_days: float) -> float:
        t = horizon_days / YEAR_DAYS
        sd = self.vol * math.sqrt(t)
        mu = -0.5 * sd * sd
        return (1.0 - norm_cdf((threshold_return - mu) / sd)) + norm_cdf(
            (-threshold_return - mu) / sd)
