"""Pre-registered Alpha Campaign 1 strategies — deterministic, causal (no lookahead).

Each hypothesis is a rule over OHLC bars that emits a position series in {-1, 0, +1}; positions are
applied to the *next* bar's return (lag 1) so there is no lookahead. The same rules also produce
live :class:`AlphaSignal` votes for ``MT5Feed`` (the ``signal_builder`` hook). These are simple,
economically-anchored rules — the point of the campaign is to let the validation gauntlet decide
whether any of them is real, not to curve-fit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy as np

from app.mt5_adapter import Bar
from libs.signal_engine.models import AlphaSignal, Direction, MarketState
from libs.validation.economic_prior import MechanismType

# name -> (positions_fn, economic mechanism, human rationale)
Strategy = Callable[["Bars"], np.ndarray]


class Bars:
    """Columnar OHLC view over a bar history (close/high/low as float arrays)."""

    def __init__(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> None:
        self.close = np.asarray(close, dtype="float64")
        self.high = np.asarray(high, dtype="float64")
        self.low = np.asarray(low, dtype="float64")

    @classmethod
    def from_mt5(cls, bars: list[Bar]) -> Bars:
        return cls(
            close=np.array([b.close for b in bars], dtype="float64"),
            high=np.array([b.high for b in bars], dtype="float64"),
            low=np.array([b.low for b in bars], dtype="float64"),
        )

    def __len__(self) -> int:
        return len(self.close)


def _roll_mean(x: np.ndarray, w: int) -> np.ndarray:
    out = np.full(len(x), np.nan, dtype="float64")
    if len(x) >= w:
        out[w - 1:] = np.convolve(x, np.ones(w) / w, "valid")
    return out


def _roll_apply(x: np.ndarray, w: int, fn: Callable[[np.ndarray], float]) -> np.ndarray:
    out = np.full(len(x), np.nan, dtype="float64")
    for i in range(w - 1, len(x)):
        out[i] = fn(x[i - w + 1: i + 1])
    return out


def _bar_returns(close: np.ndarray) -> np.ndarray:
    out = np.zeros(len(close), dtype="float64")
    out[1:] = close[1:] / close[:-1] - 1.0
    return out


def _sign_nan0(x: np.ndarray) -> np.ndarray:
    s = np.sign(np.nan_to_num(x, nan=0.0))
    return cast("np.ndarray", s.astype("float64"))


def trend_positions(bars: Bars, *, fast: int = 20, slow: int = 50) -> np.ndarray:
    return _sign_nan0(_roll_mean(bars.close, fast) - _roll_mean(bars.close, slow))


def momentum_positions(bars: Bars, *, lookback: int = 20) -> np.ndarray:
    c = bars.close
    mom = np.zeros(len(c), dtype="float64")
    mom[lookback:] = c[lookback:] - c[:-lookback]
    return _sign_nan0(mom)


def breakout_positions(bars: Bars, *, window: int = 20) -> np.ndarray:
    hh = _roll_apply(bars.high, window, lambda a: float(a.max()))
    ll = _roll_apply(bars.low, window, lambda a: float(a.min()))
    prev_hh = np.roll(hh, 1)
    prev_ll = np.roll(ll, 1)
    pos = np.where(bars.close > prev_hh, 1.0, np.where(bars.close < prev_ll, -1.0, 0.0))
    pos[: window + 1] = 0.0
    return pos.astype("float64")


def vol_compression_positions(bars: Bars, *, window: int = 20, vol_window: int = 20) -> np.ndarray:
    rets = _bar_returns(bars.close)
    vol = _roll_apply(rets, vol_window, lambda a: float(a.std()))
    median_vol = float(np.nanmedian(vol)) if np.any(~np.isnan(vol)) else 0.0
    compressed = np.nan_to_num(vol, nan=median_vol + 1.0) < median_vol  # low-vol regime
    pos = breakout_positions(bars, window=window) * compressed
    return cast("np.ndarray", pos.astype("float64"))


def vol_expansion_positions(bars: Bars, *, vol_window: int = 20, lookback: int = 20) -> np.ndarray:
    rets = _bar_returns(bars.close)
    vol = _roll_apply(rets, vol_window, lambda a: float(a.std()))
    rising = np.zeros(len(vol), dtype=bool)
    rising[1:] = np.nan_to_num(vol[1:], nan=0.0) > np.nan_to_num(vol[:-1], nan=0.0)
    pos = momentum_positions(bars, lookback=lookback) * rising
    return pos.astype("float64")


def mean_reversion_positions(bars: Bars, *, window: int = 20, z_entry: float = 2.0) -> np.ndarray:
    mean = _roll_mean(bars.close, window)
    std = _roll_apply(bars.close, window, lambda a: float(a.std()))
    with np.errstate(divide="ignore", invalid="ignore"):
        z = (bars.close - mean) / std
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    pos = np.where(z > z_entry, -1.0, np.where(z < -z_entry, 1.0, 0.0))
    return pos.astype("float64")


# The fixed, pre-registered Campaign 1 strategy set (frozen; scope may not expand mid-campaign).
_BEH = MechanismType.BEHAVIORAL
_STR = MechanismType.STRUCTURAL
_LIQ = MechanismType.LIQUIDITY
STRATEGIES: dict[str, tuple[Strategy, MechanismType, str]] = {
    "trend_persistence": (trend_positions, _BEH, "trend persistence / underreaction"),
    "momentum_continuation": (momentum_positions, _BEH, "momentum continuation"),
    "donchian_breakout": (breakout_positions, _STR, "range breakout"),
    "vol_compression_breakout": (vol_compression_positions, _STR, "vol compression -> expansion"),
    "vol_expansion_momentum": (vol_expansion_positions, _STR, "volatility-expansion trend"),
    "range_mean_reversion": (mean_reversion_positions, _LIQ, "mean reversion / liquidity"),
}


def strategy_returns(
    bars: Bars, positions: np.ndarray, *, cost_per_turnover: float = 0.0003
) -> np.ndarray:
    """Net per-bar returns of a position series, lag-1 (no lookahead), minus pessimistic costs."""
    bar_ret = _bar_returns(bars.close)
    pos_lag = np.roll(positions, 1)
    pos_lag[0] = 0.0
    turnover = np.abs(np.diff(pos_lag, prepend=0.0))
    net = bar_ret * pos_lag - cost_per_turnover * turnover
    return cast("np.ndarray", net[1:])  # drop the first (no prior bar)


def build_live_signals(state: MarketState, bars: list[Bar]) -> list[AlphaSignal]:
    """``MT5Feed`` hook: emit the latest vote from each pre-registered strategy."""
    if len(bars) < 60:
        return []
    cols = Bars.from_mt5(bars)
    signals: list[AlphaSignal] = []
    for name, (fn, _mechanism, _why) in STRATEGIES.items():
        latest = float(fn(cols)[-1])
        if latest == 0.0:
            continue
        signals.append(
            AlphaSignal(
                alpha_id=f"{name}:{state.symbol}", symbol=state.symbol,
                direction=Direction.BUY if latest > 0 else Direction.SELL,
                strength=0.6, governance_passed=False,
            )
        )
    return signals
