"""Portfolio engine — cash, signed position, average-cost realized PnL, equity.

Supports long, short, partial exits, and reversals via average-cost accounting on a single
net position per instrument. Realized trades are recorded for profit-factor/expectancy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from libs.backtest.events import FillEvent


@dataclass(frozen=True)
class Trade:
    """A realized (closed or partially-closed) round-turn portion."""

    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    sign: int
    units: float
    entry_price: float
    exit_price: float
    pnl: float


@dataclass
class PortfolioEngine:
    """Tracks cash, net position, and realized trades through fills."""

    init_cash: float
    cash: float = field(init=False)
    units: float = 0.0
    entry_price: float = 0.0
    entry_time: pd.Timestamp | None = None
    trades: list[Trade] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = self.init_cash

    def apply_fill(self, fill: FillEvent) -> None:
        """Apply a fill to cash/position, recording realized PnL on reductions/reversals."""
        delta = fill.units_delta
        price = fill.price
        self.cash -= delta * price
        self.cash -= fill.commission
        new_units = self.units + delta

        if self.units == 0.0:
            self.entry_price = price
            self.entry_time = fill.timestamp
        elif (self.units > 0 and delta > 0) or (self.units < 0 and delta < 0):
            total = self.entry_price * abs(self.units) + price * abs(delta)
            self.entry_price = total / abs(new_units)
        else:
            closing = min(abs(delta), abs(self.units))
            sign = 1 if self.units > 0 else -1
            pnl = closing * (price - self.entry_price) * sign - fill.commission
            self.trades.append(
                Trade(
                    entry_time=self.entry_time if self.entry_time is not None else fill.timestamp,
                    exit_time=fill.timestamp,
                    sign=sign,
                    units=closing,
                    entry_price=self.entry_price,
                    exit_price=price,
                    pnl=pnl,
                )
            )
            if abs(delta) > abs(self.units):
                self.entry_price = price  # reversal: remainder opens a new position
                self.entry_time = fill.timestamp
            elif new_units == 0.0:
                self.entry_price = 0.0
                self.entry_time = None

        self.units = new_units

    def equity(self, mark_price: float) -> float:
        """Mark-to-market equity at ``mark_price``."""
        return self.cash + self.units * mark_price
