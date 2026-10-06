"""Models with a known characteristic function: price by Lewis inversion, tail probability by
Gil-Pelaez inversion, vol forecast from the expected integrated variance. Heston, Bates and
Merton subclass this."""
from __future__ import annotations

import math
from abc import abstractmethod

from libs.quant_models.base import YEAR_DAYS, OptionSpec, StochasticModel
from libs.quant_models.numerics import CharFn, cf_price, cf_tail_prob


class CFModel(StochasticModel):
    """A model that exposes `cf(t)` of the martingale log return and `expected_var(t)`."""

    @abstractmethod
    def cf(self, t: float) -> CharFn:
        """Characteristic function of X_t = ln(S_t / S_0) - (r - q) t."""

    @abstractmethod
    def expected_var(self, t: float) -> float:
        """E[quadratic variation of ln S over (0, t)] per year (annualised variance)."""

    def price(self, spec: OptionSpec) -> float:
        t = spec.expiry_years
        if t <= 0:
            intrinsic = spec.spot - spec.strike if spec.kind == "call" else spec.strike - spec.spot
            return max(intrinsic, 0.0)
        return cf_price(self.cf(t), spec.kind, spec.spot, spec.strike, t, spec.rate, spec.div,
                        self.expected_var(t) * t)

    def vol_forecast(self, horizon_days: float) -> float:
        return math.sqrt(max(self.expected_var(horizon_days / YEAR_DAYS), 0.0))

    def tail_prob(self, threshold_return: float, horizon_days: float) -> float:
        t = horizon_days / YEAR_DAYS
        return cf_tail_prob(self.cf(t), threshold_return, 0.0, self.expected_var(t) * t)
