"""Post-trade transaction cost analysis.

Measures realized execution quality against the arrival (pre-trade) and decision (signal) prices:
slippage in bps, implementation shortfall, realized vs forecast cost, and an attribution of the
realized slippage into spread / impact / timing using the pre-trade cost forecast. Closes the loop
so execution shortfall feeds back into edge/EV and capacity estimates.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from libs.costs.model import TradeCost
from libs.execution.errors import ExecutionError

_BPS = 1e4


def _avg_fill(fills: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Volume-weighted average fill price and total filled quantity."""
    total_qty = sum(q for _, q in fills)
    if total_qty <= 0:
        raise ExecutionError("TCA requires at least one non-zero fill")
    vwap = sum(p * q for p, q in fills) / total_qty
    return vwap, total_qty


class TcaResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    side: str  # "buy" | "sell"
    arrival_price: float
    decision_price: float
    avg_fill_price: float
    qty: float
    notional: float
    slippage_bps: float            # vs arrival price (positive = adverse)
    implementation_shortfall: float  # fractional, vs decision price (positive = adverse)
    realized_cost: float           # account-currency adverse cost vs arrival
    forecast_cost: float
    cost_error: float              # realized - forecast


class PostTradeTCA:
    """Computes realized execution quality for one parent order."""

    def analyze(
        self,
        *,
        symbol: str,
        side: str,
        arrival_price: float,
        decision_price: float,
        fills: Sequence[tuple[float, float]],
        forecast_cost: float = 0.0,
    ) -> TcaResult:
        if side not in ("buy", "sell"):
            raise ExecutionError(f"side must be 'buy' or 'sell', got {side!r}")
        if arrival_price <= 0 or decision_price <= 0:
            raise ExecutionError("arrival and decision prices must be positive")
        avg_fill, qty = _avg_fill(fills)
        sign = 1.0 if side == "buy" else -1.0  # buy: paying up is adverse; sell: receiving less
        slippage_bps = sign * (avg_fill - arrival_price) / arrival_price * _BPS
        shortfall = sign * (avg_fill - decision_price) / decision_price
        notional = avg_fill * qty
        realized_cost = sign * (avg_fill - arrival_price) * qty
        return TcaResult(
            symbol=symbol, side=side, arrival_price=arrival_price, decision_price=decision_price,
            avg_fill_price=avg_fill, qty=qty, notional=notional, slippage_bps=slippage_bps,
            implementation_shortfall=shortfall, realized_cost=realized_cost,
            forecast_cost=forecast_cost, cost_error=realized_cost - forecast_cost,
        )


class SlippageAttribution:
    """Attributes realized slippage into spread / impact / timing using the cost forecast."""

    def attribute(self, tca: TcaResult, forecast: TradeCost) -> dict[str, float]:
        """Decompose realized adverse cost into spread, impact, and residual timing components."""
        realized = max(0.0, tca.realized_cost)
        spread = min(realized, forecast.spread)
        impact = min(max(0.0, realized - spread), forecast.slippage)
        timing = max(0.0, realized - spread - impact)
        return {"spread": spread, "impact": impact, "timing": timing}
