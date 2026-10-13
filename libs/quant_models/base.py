"""THE SHARED STOCHASTIC-MODEL INTERFACE (ROMAN-0379..0387, ROMAN-0584; cards QG-QFIN-005,
QG-ADH-003).

Every model in this package is a `StochasticModel`: parameters in a dataclass, `calibrate` on a
`MarketData` snapshot, `price` / `greeks` an `OptionSpec`, `simulate` spot paths, and answer
`vol_forecast(horizon_days)` and `tail_prob(threshold_return, horizon_days)`. Models are
interchangeable: the disagreement factory (`desks/mt5/macro/model_disagreement.py`) runs a list
of them through exactly these calls and never asks which one it holds.

THE CLOCK IS INJECTED (QG-ADH-003). No model reads the wall clock. Time to expiry is a number on
the `OptionSpec`; when it must come from dates, `year_fraction(expiry, now)` takes `now` as an
argument and `MarketData.as_of` is a required field. Re-running on another day must yield the
same numbers, and a source-scan test fails the build if `datetime.now` / `date.today` /
`time.time` ever appear in this package.

MEASURE. A model calibrated to implied vols answers in the risk-neutral measure (`measure="Q"`);
one fitted to realised returns answers under the physical measure (`measure="P"`). Every output
the factory writes carries that label, because a Q tail probability is not a forecast.
"""
from __future__ import annotations

import copy
import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, replace
from datetime import datetime
from itertools import pairwise
from typing import Any, Literal, TypeVar

import numpy as np

from libs.quant_models.numerics import FArr, MCResult, mc_estimate

Kind = Literal["call", "put"]
YEAR_DAYS = 365.0
TRADING_DAYS = 252.0
M = TypeVar("M", bound="StochasticModel")


def year_fraction(expiry: datetime, now: datetime) -> float:
    """ACT/365 year fraction from an INJECTED `now` (never today). Both must be tz-aware."""
    if expiry.tzinfo is None or now.tzinfo is None:
        raise ValueError("year_fraction needs tz-aware datetimes; a naive clock is a guess")
    return max((expiry - now).total_seconds(), 0.0) / (YEAR_DAYS * 86400.0)


@dataclass(frozen=True)
class OptionSpec:
    kind: Kind
    strike: float
    expiry_years: float
    spot: float
    rate: float = 0.0
    div: float = 0.0

    @classmethod
    def from_dates(cls, kind: Kind, strike: float, expiry: datetime, now: datetime,
                   spot: float, rate: float = 0.0, div: float = 0.0) -> OptionSpec:
        return cls(kind, strike, year_fraction(expiry, now), spot, rate, div)

    @property
    def forward(self) -> float:
        return self.spot * math.exp((self.rate - self.div) * self.expiry_years)


@dataclass(frozen=True)
class Greeks:
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    method: str = "closed_form"

    def as_dict(self) -> dict[str, float | str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class OptionQuote:
    spec: OptionSpec
    implied_vol: float


@dataclass
class MarketData:
    """What a model may see at `as_of` and nothing after it.

    returns          daily log returns up to as_of (oldest first)
    iv_term          {tenor_years: implied vol} (e.g. VIX9D/VIX/VIX3M/VIX6M)
    iv_history       daily ATM implied vols up to as_of (oldest first), for vol-of-vol and rho
    quotes           option quotes (strike / expiry / IV) where a chain exists
    intraday_returns per-day arrays of intraday log returns (high-frequency RV)
    daily_ranges     per-day ln(high/low) (Parkinson)
    """

    as_of: datetime
    spot: float = 1.0
    rate: float = 0.0
    div: float = 0.0
    returns: FArr = field(default_factory=lambda: np.zeros(0))
    iv_term: Mapping[float, float] = field(default_factory=dict)
    iv_history: FArr = field(default_factory=lambda: np.zeros(0))
    quotes: Sequence[OptionQuote] = ()
    intraday_returns: Sequence[FArr] = ()
    daily_ranges: FArr = field(default_factory=lambda: np.zeros(0))

    def atm_iv(self, tenor_years: float = 30.0 / YEAR_DAYS) -> float | None:
        """The term-point IV nearest `tenor_years` (total variance interpolated when bracketed)."""
        pts = sorted((float(t), float(v)) for t, v in self.iv_term.items()
                     if t > 0 and v > 0 and math.isfinite(v))
        if not pts:
            return None
        if tenor_years <= pts[0][0]:
            return pts[0][1]
        if tenor_years >= pts[-1][0]:
            return pts[-1][1]
        for (t0, v0), (t1, v1) in pairwise(pts):
            if t0 <= tenor_years <= t1:
                w0, w1 = v0 * v0 * t0, v1 * v1 * t1
                w = w0 + (w1 - w0) * (tenor_years - t0) / (t1 - t0)
                return math.sqrt(max(w, 0.0) / tenor_years)
        return pts[-1][1]


class StochasticModel(ABC):
    """The interface. Subclasses set `name`, `measure`, `params` and implement the abstract
    methods; greeks default to central finite differences on `price`, vol forecasts and tail
    probabilities default to simulation (seeded, so deterministic)."""

    name: str = "model"
    measure: Literal["P", "Q"] = "Q"
    params: Any
    #: Seed for every internal simulation (vol forecast, tail probability, MC pricing).
    seed: int = 20260101
    mc_paths: int = 20000

    # ---------------------------------------------------------------- required
    @abstractmethod
    def calibrate(self: M, data: MarketData) -> M:
        """Fit parameters on `data` (and nothing after data.as_of); return self."""

    @abstractmethod
    def price(self, spec: OptionSpec) -> float:
        """Present value of the European option."""

    @abstractmethod
    def simulate(self, n_paths: int, n_steps: int, horizon: float, seed: int,
                 spot: float = 1.0, rate: float = 0.0, div: float = 0.0,
                 antithetic: bool = False) -> FArr:
        """Spot paths (n_paths, n_steps + 1) over `horizon` years, starting at `spot`."""

    @abstractmethod
    def shift_vol(self: M, dvol: float) -> M:
        """A copy whose volatility LEVEL is shifted by `dvol` (absolute vol units): the bump
        behind the FD vega."""

    # ---------------------------------------------------------------- defaults
    def greeks(self, spec: OptionSpec) -> Greeks:
        return fd_greeks(self, spec)

    def vol_forecast(self, horizon_days: float) -> float:
        """Annualised vol of the log return over `horizon_days` calendar days."""
        t = horizon_days / YEAR_DAYS
        n_steps = max(1, min(round(horizon_days), 64))
        paths = self.simulate(self.mc_paths, n_steps, t, self.seed)
        lr = np.log(paths[:, -1] / paths[:, 0])
        return float(lr.std(ddof=1) / math.sqrt(t))

    def tail_prob(self, threshold_return: float, horizon_days: float) -> float:
        """P(|ln S_{t+h} / S_t| > threshold_return) over `horizon_days` calendar days, under
        this model's own measure (`self.measure`)."""
        t = horizon_days / YEAR_DAYS
        n_steps = max(1, min(round(horizon_days), 64))
        paths = self.simulate(self.mc_paths, n_steps, t, self.seed)
        lr = np.log(paths[:, -1] / paths[:, 0])
        return float(np.mean(np.abs(lr) > threshold_return))

    def mc_price(self, spec: OptionSpec, payoff: Payoff | None = None, n_paths: int = 20000,
                 n_steps: int = 32, seed: int | None = None, antithetic: bool = True,
                 control: bool = True) -> MCResult:
        """Monte Carlo price of a (possibly path-dependent) payoff with control variates.

        Controls (ROMAN-0969): the discounted terminal spot (known mean S e^{-qT}) and, for a
        path-dependent payoff, the discounted European payoff at the same strike, whose mean is
        this model's own `price` (closed form or CF where it exists)."""
        pay = payoff or european(spec.kind, spec.strike)
        paths = self.simulate(n_paths, n_steps, spec.expiry_years,
                              self.seed if seed is None else seed, spec.spot, spec.rate,
                              spec.div, antithetic=antithetic)
        disc = math.exp(-spec.rate * spec.expiry_years)
        y = disc * pay(paths)
        ctrls: list[tuple[FArr, float]] = []
        if control:
            ctrls.append((np.asarray(disc * paths[:, -1], dtype=np.float64),
                          spec.spot * math.exp(-spec.div * spec.expiry_years)))
            if payoff is not None and self.has_fast_price():
                ctrls.append((np.asarray(disc * european(spec.kind, spec.strike)(paths),
                                         dtype=np.float64), self.price(spec)))
        return mc_estimate(np.asarray(y, dtype=np.float64), ctrls, antithetic=antithetic)

    def has_fast_price(self) -> bool:
        """True when `price` is closed form / CF (so it may serve as a control's known mean)."""
        return True

    def implied_vol(self, spec: OptionSpec) -> float | None:
        from libs.quant_models.numerics import implied_vol
        return implied_vol(self.price(spec), spec.kind, spec.spot, spec.strike,
                           spec.expiry_years, spec.rate, spec.div)

    def describe(self) -> dict[str, Any]:
        p = self.params
        vals = ({f.name: getattr(p, f.name) for f in fields(p)}
                if p is not None and hasattr(p, "__dataclass_fields__") else {})
        return {"name": self.name, "measure": self.measure, "params": vals}

    def copy_with(self: M, **changes: Any) -> M:
        out = copy.copy(self)
        out.params = replace(self.params, **changes)
        return out


# ============================================================================== payoffs
class Payoff:
    """A payoff on spot paths (n_paths, n_steps + 1) -> (n_paths,)."""

    def __init__(self, name: str, fn: Any) -> None:
        self.name = name
        self._fn = fn

    def __call__(self, paths: FArr) -> FArr:
        return np.asarray(self._fn(paths), dtype=np.float64)


def european(kind: str, strike: float) -> Payoff:
    sign = 1.0 if kind == "call" else -1.0
    return Payoff(f"european_{kind}", lambda p: np.maximum(sign * (p[:, -1] - strike), 0.0))


def asian_arithmetic(kind: str, strike: float) -> Payoff:
    """Arithmetic-average (fixings at every step after t0) Asian option."""
    sign = 1.0 if kind == "call" else -1.0
    return Payoff(f"asian_{kind}",
                  lambda p: np.maximum(sign * (p[:, 1:].mean(axis=1) - strike), 0.0))


def up_and_out(kind: str, strike: float, barrier: float) -> Payoff:
    """Discretely monitored up-and-out (knocked out when any fixing >= barrier)."""
    sign = 1.0 if kind == "call" else -1.0

    def fn(p: FArr) -> FArr:
        alive = p.max(axis=1) < barrier
        return np.asarray(np.where(alive, np.maximum(sign * (p[:, -1] - strike), 0.0), 0.0),
                          dtype=np.float64)
    return Payoff(f"up_and_out_{kind}", fn)


def lookback_floating(kind: str) -> Payoff:
    """Floating-strike lookback: call S_T - min S, put max S - S_T."""
    if kind == "call":
        return Payoff("lookback_call", lambda p: p[:, -1] - p.min(axis=1))
    return Payoff("lookback_put", lambda p: p.max(axis=1) - p[:, -1])


# ============================================================================== FD greeks
def fd_greeks(model: StochasticModel, spec: OptionSpec, rel_spot: float = 1e-3,
              dvol: float = 1e-3, dr: float = 1e-4, dt: float = 1.0 / 365.0) -> Greeks:
    """Central finite differences on `model.price`. Theta is dV/dt = -dV/dT."""
    h = spec.spot * rel_spot
    p0 = model.price(spec)
    up, dn = model.price(replace(spec, spot=spec.spot + h)), model.price(
        replace(spec, spot=spec.spot - h))
    delta = (up - dn) / (2 * h)
    gamma = (up - 2 * p0 + dn) / (h * h)
    vega = (model.shift_vol(dvol).price(spec) - model.shift_vol(-dvol).price(spec)) / (2 * dvol)
    rho = (model.price(replace(spec, rate=spec.rate + dr))
           - model.price(replace(spec, rate=spec.rate - dr))) / (2 * dr)
    t = spec.expiry_years
    step = min(dt, 0.5 * t)
    theta = -(model.price(replace(spec, expiry_years=t + step))
              - model.price(replace(spec, expiry_years=t - step))) / (2 * step)
    return Greeks(delta, gamma, vega, theta, rho, method="central_fd")


def straddle(model: StochasticModel, spot: float, t: float, rate: float = 0.0,
             div: float = 0.0, strike: float | None = None) -> float:
    k = spot * math.exp((rate - div) * t) if strike is None else strike
    return (model.price(OptionSpec("call", k, t, spot, rate, div))
            + model.price(OptionSpec("put", k, t, spot, rate, div)))
