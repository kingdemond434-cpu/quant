"""Market impact forecaster — temporary/permanent impact and fill quality before execution.

A square-root market-impact model scaled by participation and volatility. The forecast feeds the
expected value, edge, and execution scores so a signal that would move the market against itself
is penalized before any order is sent.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict


class ImpactForecast(BaseModel):
    model_config = ConfigDict(frozen=True)

    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    expected_fill_quality: float  # 0..1 (1 = perfect fill)


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class MarketImpactForecaster:
    """Forecasts pre-trade market impact and fill quality."""

    def __init__(
        self,
        *,
        impact_coefficient: float = 0.1,
        permanent_fraction: float = 0.4,
        fill_cost_cap_bps: float = 50.0,
    ) -> None:
        self.impact_coefficient = impact_coefficient
        self.permanent_fraction = permanent_fraction
        self.fill_cost_cap_bps = fill_cost_cap_bps

    def forecast(
        self,
        *,
        notional: float,
        adv_usd: float,
        volatility_state: float = 0.5,
    ) -> ImpactForecast:
        participation = notional / adv_usd if adv_usd > 0 else 1.0
        temporary = (
            self.impact_coefficient * math.sqrt(max(participation, 0.0)) * 1e4
            * (1.0 + _clip01(volatility_state))
        )
        permanent = temporary * self.permanent_fraction
        total = temporary + permanent
        fill_quality = _clip01(1.0 - total / self.fill_cost_cap_bps)
        return ImpactForecast(
            temporary_impact_bps=temporary,
            permanent_impact_bps=permanent,
            total_impact_bps=total,
            expected_fill_quality=fill_quality,
        )
