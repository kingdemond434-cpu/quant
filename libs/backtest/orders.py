"""Order manager — protective exits (stop-loss, take-profit, trailing stop).

Given an open position and the current bar, decides whether a protective level was breached
and at what price the exit fills (gap-aware: a gap through the level fills at the open).
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.backtest.events import MarketEvent


@dataclass
class ProtectiveState:
    """Mutable protective configuration for the currently open position."""

    entry_price: float
    sign: int  # +1 long, -1 short
    stop_loss: float | None = None  # fraction of entry
    take_profit: float | None = None  # fraction of entry
    trailing: float | None = None  # fraction
    anchor: float = 0.0  # best price since entry (high for long, low for short)


class OrderManager:
    """Evaluates protective exits for the open position."""

    @staticmethod
    def check_protective(state: ProtectiveState, bar: MarketEvent) -> float | None:
        """Return the exit price if a protective level triggered this bar, else ``None``."""
        if state.sign > 0:
            return OrderManager._check_long(state, bar)
        return OrderManager._check_short(state, bar)

    @staticmethod
    def _check_long(state: ProtectiveState, bar: MarketEvent) -> float | None:
        state.anchor = max(state.anchor, bar.high)
        stops: list[float] = []
        if state.stop_loss is not None:
            stops.append(state.entry_price * (1.0 - state.stop_loss))
        if state.trailing is not None:
            stops.append(state.anchor * (1.0 - state.trailing))
        effective_stop = max(stops) if stops else None

        if effective_stop is not None and bar.low <= effective_stop:
            return min(effective_stop, bar.open)  # gap-down fills at the open
        if state.take_profit is not None:
            tp = state.entry_price * (1.0 + state.take_profit)
            if bar.high >= tp:
                return max(tp, bar.open)  # gap-up fills at the open
        return None

    @staticmethod
    def _check_short(state: ProtectiveState, bar: MarketEvent) -> float | None:
        state.anchor = min(state.anchor, bar.low) if state.anchor else bar.low
        stops: list[float] = []
        if state.stop_loss is not None:
            stops.append(state.entry_price * (1.0 + state.stop_loss))
        if state.trailing is not None:
            stops.append(state.anchor * (1.0 + state.trailing))
        effective_stop = min(stops) if stops else None

        if effective_stop is not None and bar.high >= effective_stop:
            return max(effective_stop, bar.open)
        if state.take_profit is not None:
            tp = state.entry_price * (1.0 - state.take_profit)
            if bar.low <= tp:
                return min(tp, bar.open)
        return None
