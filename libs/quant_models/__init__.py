"""libs.quant_models -- the desk's ONE shared stochastic-model interface and its models
(ROMAN-0379..0387, ROMAN-0584, ROMAN-0969; cards QG-QFIN-005, QG-ADH-003).

STATE ONLY. Options are never traded on this desk (MT5/Fusion CFDs only): these models turn
implied-vol indices and the desk's own bars into state features for the underlying CFD. Nothing
here sizes, sides or routes an order.

    from libs.quant_models import MODELS, OptionSpec, MarketData
    m = MODELS["heston"]().calibrate(data)
    m.price(OptionSpec("call", 100, 30 / 365, 100)), m.greeks(...), m.vol_forecast(30)
"""
from __future__ import annotations

from collections.abc import Callable

from libs.quant_models.base import (
    Greeks,
    MarketData,
    OptionQuote,
    OptionSpec,
    Payoff,
    StochasticModel,
    asian_arithmetic,
    european,
    fd_greeks,
    lookback_floating,
    straddle,
    up_and_out,
    year_fraction,
)
from libs.quant_models.black_scholes import BlackScholes, BSParams
from libs.quant_models.garch import Ewma, EwmaParams, Garch, GarchParams, fit_garch
from libs.quant_models.heston import Bates, BatesParams, Heston, HestonParams
from libs.quant_models.jumps import JumpParams, Merton, MertonParams, estimate_jumps
from libs.quant_models.local_vol import ImpliedSurface, LocalVol, LocalVolParams
from libs.quant_models.numerics import MCResult, bs_greeks, bs_price, implied_vol, mc_estimate
from libs.quant_models.realised import HFRVParams, HighFrequencyRV, HistoricalRV, RVParams
from libs.quant_models.regime import RegimeHMM, RegimeParams
from libs.quant_models.rough import RoughParams, RoughVol

#: Every model, by name: interchangeable through `StochasticModel`.
MODELS: dict[str, Callable[[], StochasticModel]] = {
    "black_scholes": BlackScholes,
    "heston": Heston,
    "merton_jd": Merton,
    "bates": Bates,
    "local_vol": LocalVol,
    "rough_vol": RoughVol,
    "garch": Garch,
    "ewma": Ewma,
    "historical_rv": HistoricalRV,
    "hf_rv": HighFrequencyRV,
    "regime_hmm": RegimeHMM,
}

__all__ = [
    "MODELS",
    "BSParams",
    "Bates",
    "BatesParams",
    "BlackScholes",
    "Ewma",
    "EwmaParams",
    "Garch",
    "GarchParams",
    "Greeks",
    "HFRVParams",
    "Heston",
    "HestonParams",
    "HighFrequencyRV",
    "HistoricalRV",
    "ImpliedSurface",
    "JumpParams",
    "LocalVol",
    "LocalVolParams",
    "MCResult",
    "MarketData",
    "Merton",
    "MertonParams",
    "OptionQuote",
    "OptionSpec",
    "Payoff",
    "RVParams",
    "RegimeHMM",
    "RegimeParams",
    "RoughParams",
    "RoughVol",
    "StochasticModel",
    "asian_arithmetic",
    "bs_greeks",
    "bs_price",
    "estimate_jumps",
    "european",
    "fd_greeks",
    "fit_garch",
    "implied_vol",
    "lookback_floating",
    "mc_estimate",
    "straddle",
    "up_and_out",
    "year_fraction",
]
