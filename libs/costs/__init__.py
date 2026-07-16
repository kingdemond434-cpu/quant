"""``libs.costs`` — the Fusion all-in cost model.

Spread + commission + slippage + financing + gap risk, in account currency, round-turn.
Stress scenarios (BASE/2X/3X/5X) and NET-PnL helpers. The platform reports NET PnL only.
"""

from __future__ import annotations

from libs.costs.errors import CostError
from libs.costs.gap import estimate_gap_cost
from libs.costs.model import (
    PortfolioCost,
    TradeCost,
    TradeSpec,
    apply_stress_costs,
    estimate_portfolio_cost,
    estimate_trade_cost,
    net_pnl,
)
from libs.costs.params import DEFAULT_COST_PARAMS, CostParams, get_cost_params
from libs.costs.scenarios import CostScenario

__all__ = [  # noqa: RUF022  # grouped by concern
    # params
    "CostParams",
    "DEFAULT_COST_PARAMS",
    "get_cost_params",
    # scenarios
    "CostScenario",
    # model
    "TradeSpec",
    "TradeCost",
    "PortfolioCost",
    "estimate_trade_cost",
    "estimate_portfolio_cost",
    "apply_stress_costs",
    "net_pnl",
    # gap
    "estimate_gap_cost",
    # errors
    "CostError",
]
