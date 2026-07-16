"""Capacity intelligence — prioritize scalable alpha concepts.

Reuses the discovery capacity model (square-root market impact) to estimate deployable capital,
slippage, and a 0-100 scalability score so research effort favours concepts that can hold size.
"""

from __future__ import annotations

from libs.alpha_factory.models import CapacityIntelligenceResult
from libs.discovery.capacity import capacity_estimate

_REFERENCE_CAPITAL = 1e7  # USD; capacity at/above this scores 100


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class CapacityIntelligence:
    """Estimates market capacity and scalability for a research concept."""

    def assess(
        self,
        *,
        adv_usd: float,
        edge_bps: float = 10.0,
        participation_cap: float = 0.01,
        turnover_per_year: float = 50.0,
        impact_coefficient: float = 0.1,
        reference_capital: float = _REFERENCE_CAPITAL,
    ) -> CapacityIntelligenceResult:
        result = capacity_estimate(
            adv_usd=adv_usd, participation_cap=participation_cap,
            turnover_per_year=turnover_per_year, impact_coefficient=impact_coefficient,
            edge_bps=edge_bps,
        )
        scalability = 100.0 * _clip01(result.capacity_usd / reference_capital)
        return CapacityIntelligenceResult(
            market_capacity_usd=result.capacity_usd,
            expected_slippage=result.market_impact_bps_at_capacity / 1e4,
            liquidity_depth=adv_usd * participation_cap,
            scalability_score=scalability,
        )
