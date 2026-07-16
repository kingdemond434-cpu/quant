"""Portfolio capacity scoring and ENFORCEMENT.

Scoring alone does not protect capital — many strategies die from capacity before alpha decay. The
governor enforces: scale positions when utilization is high, block allocation when forecast
slippage exceeds a threshold, and zero the allocation when impact cost exceeds the edge.
"""

from __future__ import annotations

from libs.stage14.models import CapacityGovernorAction, PortfolioCapacityResult


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


class PortfolioCapacityEngine:
    """Scores portfolio capacity from utilization, forecast slippage, and impact."""

    def evaluate(
        self,
        *,
        deployed_capital: float,
        max_efficient_capital: float,
        forecast_slippage: float,
        impact_cost: float,
    ) -> PortfolioCapacityResult:
        utilization = (
            deployed_capital / max_efficient_capital if max_efficient_capital > 0 else 1.0
        )
        score = 100.0 * (1.0 - _clip01(utilization))
        return PortfolioCapacityResult(
            capacity_utilization=_clip01(utilization),
            capacity_score=score,
            forecast_slippage=forecast_slippage,
            impact_cost=impact_cost,
        )


class PortfolioCapacityGovernor:
    """Enforces capacity limits (not just scores them)."""

    def __init__(
        self,
        *,
        scale_threshold: float = 0.80,
        slippage_threshold: float = 0.0020,
    ) -> None:
        self.scale_threshold = scale_threshold
        self.slippage_threshold = slippage_threshold

    def govern(self, capacity: PortfolioCapacityResult, *, edge: float) -> CapacityGovernorAction:
        # impact cost exceeding the edge destroys the trade -> zero it.
        if capacity.impact_cost > edge:
            return CapacityGovernorAction(
                action="zero", scale_factor=0.0,
                reason=f"impact_cost {capacity.impact_cost:.4f} > edge {edge:.4f}",
            )
        # forecast slippage above the threshold -> block new allocation.
        if capacity.forecast_slippage > self.slippage_threshold:
            return CapacityGovernorAction(
                action="block", scale_factor=0.0,
                reason=f"forecast_slippage {capacity.forecast_slippage:.4f} "
                f"> {self.slippage_threshold:.4f}",
            )
        # high utilization -> scale positions down proportionally toward the threshold.
        if capacity.capacity_utilization > self.scale_threshold:
            scale = self.scale_threshold / capacity.capacity_utilization
            return CapacityGovernorAction(
                action="scale", scale_factor=_clip01(scale),
                reason=f"utilization {capacity.capacity_utilization:.2f} "
                f"> {self.scale_threshold:.2f}",
            )
        return CapacityGovernorAction(action="ok", scale_factor=1.0, reason="capacity ok")
