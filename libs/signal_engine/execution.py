"""Execution feasibility — can this signal actually be filled at acceptable cost?

Estimates fill probability and the spread/slippage/impact drag, blends them into a 0-100
execution score, and rejects signals below threshold. This composes with ``libs.costs`` at the
execution layer; here it works in basis points so it stays independent of the instrument registry.
"""

from __future__ import annotations

from libs.signal_engine.models import ExecutionFeasibility


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class ExecutionFeasibilityEngine:
    """Scores executability; below ``threshold`` the signal is rejected."""

    def __init__(self, *, threshold: float = 50.0, cost_cap_bps: float = 50.0) -> None:
        self.threshold = threshold
        self.cost_cap_bps = cost_cap_bps

    def assess(
        self,
        *,
        spread_bps: float,
        expected_slippage_bps: float,
        market_impact_bps: float,
        liquidity_score: float,
        latency_risk: float = 0.0,
    ) -> ExecutionFeasibility:
        fill_probability = _clip01(liquidity_score * (1.0 - _clip01(latency_risk)))
        total_cost_bps = spread_bps + expected_slippage_bps + market_impact_bps
        cost_drag = _clip01(total_cost_bps / self.cost_cap_bps)
        execution_score = 100.0 * fill_probability * (1.0 - cost_drag)
        return ExecutionFeasibility(
            execution_score=execution_score,
            fill_probability=fill_probability,
            expected_slippage_bps=expected_slippage_bps,
            market_impact_bps=market_impact_bps,
            spread_cost_bps=spread_bps,
            passed=execution_score >= self.threshold,
        )
