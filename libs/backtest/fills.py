"""Fill engine — turns an order delta into a fill price with slippage and commission."""

from __future__ import annotations

import pandas as pd

from libs.backtest.events import FillEvent


class FillEngine:
    """Computes fills. Slippage worsens the price in the direction of the trade."""

    def __init__(self, *, slippage_frac: float = 0.0, commission_per_unit: float = 0.0) -> None:
        self.slippage_frac = slippage_frac
        self.commission_per_unit = commission_per_unit

    def fill(
        self, timestamp: pd.Timestamp, units_delta: float, ref_price: float
    ) -> FillEvent:
        """Fill ``units_delta`` at ``ref_price`` adjusted for slippage/commission."""
        direction = 1.0 if units_delta > 0 else -1.0
        price = ref_price * (1.0 + direction * self.slippage_frac)
        commission = abs(units_delta) * self.commission_per_unit
        return FillEvent(
            timestamp=timestamp, units_delta=units_delta, price=price, commission=commission
        )
