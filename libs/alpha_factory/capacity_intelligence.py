"""Capacity intelligence — prioritize concepts that can hold THIS DESK'S size.

Reuses the discovery capacity model (square-root market impact) to estimate deployable capital,
slippage, and a 0-100 scalability score.

§39: the reference was $10m, so a $50k-capacity edge scored 0.5/100 on scalability — a 200x
penalty on the capacity-bound niche the desk's own spec calls its structural advantage. "Can hold
size" is a fund's question; the desk's question is "can hold OUR size", and the answer above
sufficiency is yes-or-yes. `reference_capital` therefore now means the equity being deployed, and
scoring is delegated to the shared `capacity_fit` so this cannot drift back out of line with the
survival gate and the two rank scorers.
"""

from __future__ import annotations

from libs.alpha_factory.models import CapacityIntelligenceResult
from libs.discovery.capacity import capacity_estimate
from libs.research.capacity_policy import DEFAULT_BOOK_USD, DEFAULT_SLEEVES, capacity_fit

_REFERENCE_CAPITAL = DEFAULT_BOOK_USD  # USD of DEPLOYED equity the concept is scored against


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
        n_sleeves: int = DEFAULT_SLEEVES,
    ) -> CapacityIntelligenceResult:
        result = capacity_estimate(
            adv_usd=adv_usd, participation_cap=participation_cap,
            turnover_per_year=turnover_per_year, impact_coefficient=impact_coefficient,
            edge_bps=edge_bps,
        )
        # `reference_capital` is a whole-BOOK figure, so it is sleeved: a concept is filled with
        # one allocation, not with the entire desk.
        scalability = 100.0 * capacity_fit(result.capacity_usd, reference_capital, n_sleeves)
        return CapacityIntelligenceResult(
            market_capacity_usd=result.capacity_usd,
            expected_slippage=result.market_impact_bps_at_capacity / 1e4,
            liquidity_depth=adv_usd * participation_cap,
            scalability_score=scalability,
        )
