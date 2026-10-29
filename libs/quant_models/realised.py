"""Realised-volatility models (measure P): a constant vol estimated from the desk's own bars,
priced, hedged and simulated through Black-Scholes.

HistoricalRV     close-to-close: sd of the last `window` daily log returns, annualised.
HighFrequencyRV  realised variance from intraday bars: per day the sum of squared intraday log
                 returns, averaged over `window` days (Andersen-Bollerslev). `estimator =
                 "parkinson"` uses the daily high-low range instead: E[ln(H/L)^2] = 4 ln2 sigma^2.
Both are the "empirical / nonparametric" members of the ensemble (ROMAN-0393, 0394, 0804, 0805).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from libs.quant_models.base import MarketData
from libs.quant_models.black_scholes import BlackScholes, BSParams

TRADING_YEAR = 252.0


@dataclass(frozen=True)
class RVParams(BSParams):
    window: int = 21


class HistoricalRV(BlackScholes):
    name = "historical_rv"
    measure = "P"
    params: RVParams

    def __init__(self, params: RVParams | None = None) -> None:
        self.params = params or RVParams()

    def calibrate(self, data: MarketData) -> HistoricalRV:
        r = np.asarray(data.returns, dtype=np.float64)
        r = r[np.isfinite(r)][-self.params.window:]
        if r.size >= max(5, self.params.window // 2):
            self.params = RVParams(vol=float(r.std(ddof=1)) * math.sqrt(TRADING_YEAR),
                                   window=self.params.window)
        return self


@dataclass(frozen=True)
class HFRVParams(RVParams):
    estimator: Literal["realised", "parkinson"] = "realised"


def daily_realised_var(intraday: list[np.ndarray] | tuple[np.ndarray, ...]) -> np.ndarray:
    """Per day, the sum of squared intraday log returns (daily units)."""
    return np.asarray([float(np.nansum(np.asarray(x, dtype=np.float64) ** 2))
                       for x in intraday], dtype=np.float64)


def parkinson_var(log_ranges: np.ndarray) -> np.ndarray:
    lr = np.asarray(log_ranges, dtype=np.float64)
    return np.asarray(lr * lr / (4.0 * math.log(2.0)), dtype=np.float64)


class HighFrequencyRV(BlackScholes):
    name = "hf_rv"
    measure = "P"
    params: HFRVParams

    def __init__(self, params: HFRVParams | None = None) -> None:
        self.params = params or HFRVParams()

    def calibrate(self, data: MarketData) -> HighFrequencyRV:
        p = self.params
        if p.estimator == "parkinson":
            dv = parkinson_var(np.asarray(data.daily_ranges, dtype=np.float64))
        else:
            dv = daily_realised_var(list(data.intraday_returns))
        dv = dv[np.isfinite(dv) & (dv > 0)][-p.window:]
        if dv.size >= max(5, p.window // 2):
            self.params = HFRVParams(vol=math.sqrt(float(dv.mean()) * TRADING_YEAR),
                                     window=p.window, estimator=p.estimator)
        return self
