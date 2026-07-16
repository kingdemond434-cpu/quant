"""capacity_optimization_engine — maximum deployable capital and a slippage curve.

Optimizes CAGR x Capacity, not CAGR alone: a strategy that is brilliant at $10k and dead at $1M
is scored at its real capacity. Estimates the size at which market impact erodes the edge.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.discovery.errors import DiscoveryError


class CapacityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    capacity_usd: float
    slippage_curve: dict[float, float]  # notional -> expected slippage (fraction)
    market_impact_bps_at_capacity: float


def capacity_estimate(
    *,
    adv_usd: float,
    participation_cap: float = 0.01,
    turnover_per_year: float = 50.0,
    impact_coefficient: float = 0.1,
    edge_bps: float = 10.0,
) -> CapacityResult:
    """Estimate deployable capital where square-root market impact stays below the edge."""
    if adv_usd <= 0:
        raise DiscoveryError("adv_usd must be positive")
    # Per-trade tradeable notional from participation, annualized by turnover.
    per_trade = adv_usd * participation_cap
    # Square-root impact model: impact_bps = coeff * sqrt(notional / adv) * 1e4.
    # Capacity = size where impact_bps == edge_bps.
    capacity_per_trade = adv_usd * (edge_bps / (impact_coefficient * 1e4)) ** 2
    capacity_usd = min(per_trade, capacity_per_trade) * max(1.0, 252.0 / turnover_per_year)

    curve_points = [per_trade * f for f in (0.25, 0.5, 1.0, 2.0, 4.0)]
    slippage_curve = {
        float(round(notional, 2)): float(
            impact_coefficient * np.sqrt(max(notional, 0.0) / adv_usd)
        )
        for notional in curve_points
    }
    impact_at_capacity = float(
        impact_coefficient * np.sqrt(max(capacity_usd, 0.0) / adv_usd) * 1e4
    )
    return CapacityResult(
        capacity_usd=capacity_usd,
        slippage_curve=slippage_curve,
        market_impact_bps_at_capacity=impact_at_capacity,
    )
