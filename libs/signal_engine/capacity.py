"""Signal capacity forecaster — forward scalability before capital is allocated.

Reuses the discovery capacity model (square-root market impact) and turns it into a forward
0-100 capacity score plus slippage/impact estimates and the maximum efficient capital. Signals
whose intended size approaches capacity score lower and must rank lower / size smaller.
"""

from __future__ import annotations

import math

from libs.discovery.capacity import capacity_estimate
from libs.signal_engine.models import CapacityForecast

_EPS = 1e-9


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class SignalCapacityForecaster:
    """Forecasts future capacity, slippage, and impact for an intended order size."""

    def forecast(
        self,
        *,
        adv_usd: float,
        intended_notional: float,
        edge_bps: float = 10.0,
        turnover_per_year: float = 50.0,
        participation_cap: float = 0.01,
        impact_coefficient: float = 0.1,
    ) -> CapacityForecast:
        result = capacity_estimate(
            adv_usd=adv_usd,
            participation_cap=participation_cap,
            turnover_per_year=turnover_per_year,
            impact_coefficient=impact_coefficient,
            edge_bps=edge_bps,
        )
        capacity = result.capacity_usd
        utilization = intended_notional / capacity if capacity > _EPS else 1.0
        # adv_usd > 0 is guaranteed: capacity_estimate raises otherwise.
        slippage = impact_coefficient * math.sqrt(max(intended_notional, 0.0) / adv_usd)
        return CapacityForecast(
            future_capacity_score=100.0 * _clip01(1.0 - utilization),
            future_slippage_estimate=slippage,
            future_market_impact_estimate=slippage * 1e4,
            maximum_efficient_capital=capacity,
            capacity_confidence=_clip01(1.0 - utilization),
        )
