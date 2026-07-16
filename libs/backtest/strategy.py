"""Strategy protocol and a couple of reference strategies.

A strategy sees only data up to and including the current bar's close (no look-ahead) and
returns a target position. The engine executes the resulting order at the *next* bar's open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from libs.backtest.events import SignalEvent


@dataclass(frozen=True)
class BarContext:
    """What a strategy sees on each bar."""

    index: int
    timestamp: pd.Timestamp
    bars: pd.DataFrame
    equity: float
    position_units: float


@runtime_checkable
class Strategy(Protocol):
    def on_bar(self, ctx: BarContext) -> SignalEvent | None: ...


class SignalStrategy:
    """Replays a precomputed target series (units or signed fraction)."""

    def __init__(
        self,
        targets: np.ndarray | list[float],
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        trailing: float | None = None,
    ) -> None:
        self._targets = np.asarray(targets, dtype="float64")
        self._stop_loss = stop_loss
        self._take_profit = take_profit
        self._trailing = trailing

    def on_bar(self, ctx: BarContext) -> SignalEvent | None:
        if ctx.index >= len(self._targets):
            return None
        return SignalEvent(
            timestamp=ctx.timestamp,
            target=float(self._targets[ctx.index]),
            stop_loss=self._stop_loss,
            take_profit=self._take_profit,
            trailing=self._trailing,
        )


class MovingAverageCrossStrategy:
    """Long when the fast SMA is above the slow SMA (optionally short otherwise)."""

    def __init__(self, *, fast: int, slow: int, long_only: bool = True) -> None:
        if fast >= slow:
            raise ValueError("fast window must be shorter than slow window")
        self.fast = fast
        self.slow = slow
        self.long_only = long_only

    def on_bar(self, ctx: BarContext) -> SignalEvent | None:
        closes = ctx.bars["close"].iloc[: ctx.index + 1]
        if len(closes) < self.slow:
            return SignalEvent(timestamp=ctx.timestamp, target=0.0)
        fast_ma = float(closes.iloc[-self.fast :].mean())
        slow_ma = float(closes.iloc[-self.slow :].mean())
        flat_or_short = 0.0 if self.long_only else -1.0
        target = 1.0 if fast_ma > slow_ma else flat_or_short
        return SignalEvent(timestamp=ctx.timestamp, target=target)
