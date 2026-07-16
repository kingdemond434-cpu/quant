"""The Fusion cost model: all-in trade and portfolio cost, stress scaling, and NET PnL.

Every cost is in account currency and round-turn. The platform reports **net** PnL only —
:func:`net_pnl` is the single sanctioned way to turn a gross figure into a reportable one.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from libs.costs.errors import CostError
from libs.costs.gap import estimate_gap_cost
from libs.costs.params import CostParams, get_cost_params
from libs.costs.scenarios import CostScenario

Side = Literal["buy", "sell"]


class TradeSpec(BaseModel):
    """A single round-turn trade to be costed."""

    model_config = ConfigDict(frozen=True)

    instrument: str
    qty_lots: float = Field(gt=0)
    price: float = Field(gt=0)
    side: Side = "buy"
    holding_nights: int = Field(ge=0, default=0)
    include_gap: bool = False


class TradeCost(BaseModel):
    """All-in cost breakdown for one round-turn trade (account currency)."""

    model_config = ConfigDict(frozen=True)

    instrument: str
    qty_lots: float
    spread: float
    commission: float
    slippage: float
    financing: float
    gap: float
    total: float


class PortfolioCost(BaseModel):
    """Aggregated cost across many trades."""

    model_config = ConfigDict(frozen=True)

    total: float
    by_instrument: dict[str, float]
    n_trades: int


def estimate_trade_cost(
    instrument: str,
    qty_lots: float,
    *,
    price: float,
    side: Side = "buy",
    holding_nights: int = 0,
    include_gap: bool = False,
    registry: dict[str, CostParams] | None = None,
) -> TradeCost:
    """Estimate the all-in round-turn cost of a trade."""
    if qty_lots <= 0:
        raise CostError("qty_lots must be positive")
    if price <= 0:
        raise CostError("price must be positive")
    p = get_cost_params(instrument, registry)

    spread = p.spread_price * p.contract_size * qty_lots
    commission = p.commission_per_lot * qty_lots
    slippage = p.slippage_price_per_side * p.contract_size * qty_lots * 2.0
    swap = p.swap_long_per_lot_per_night if side == "buy" else p.swap_short_per_lot_per_night
    financing = swap * qty_lots * holding_nights
    gap = estimate_gap_cost(p, qty_lots, price) if include_gap else 0.0
    total = spread + commission + slippage + financing + gap

    return TradeCost(
        instrument=instrument,
        qty_lots=qty_lots,
        spread=spread,
        commission=commission,
        slippage=slippage,
        financing=financing,
        gap=gap,
        total=total,
    )


def estimate_portfolio_cost(
    trades: Sequence[TradeSpec], *, registry: dict[str, CostParams] | None = None
) -> PortfolioCost:
    """Estimate the aggregate cost of a list of trades, with a per-instrument breakdown."""
    by_instrument: dict[str, float] = {}
    total = 0.0
    for spec in trades:
        cost = estimate_trade_cost(
            spec.instrument,
            spec.qty_lots,
            price=spec.price,
            side=spec.side,
            holding_nights=spec.holding_nights,
            include_gap=spec.include_gap,
            registry=registry,
        )
        total += cost.total
        by_instrument[spec.instrument] = by_instrument.get(spec.instrument, 0.0) + cost.total
    return PortfolioCost(total=total, by_instrument=by_instrument, n_trades=len(trades))


def apply_stress_costs(cost: TradeCost, scenario: CostScenario) -> TradeCost:
    """Scale the market-driven cost components (spread, slippage, gap) by the scenario."""
    m = scenario.multiplier
    spread = cost.spread * m
    slippage = cost.slippage * m
    gap = cost.gap * m
    total = spread + cost.commission + slippage + cost.financing + gap
    return TradeCost(
        instrument=cost.instrument,
        qty_lots=cost.qty_lots,
        spread=spread,
        commission=cost.commission,
        slippage=slippage,
        financing=cost.financing,
        gap=gap,
        total=total,
    )


def net_pnl(gross_pnl: float, cost: TradeCost) -> float:
    """Return NET PnL = gross PnL minus all-in cost. The only sanctioned PnL to report."""
    return gross_pnl - cost.total
