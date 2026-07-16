"""Demo->live execution-gap stress (committee Lever 2 / T4).

A backtest run on demo spreads is optimistic: live trading reveals wider spreads, slippage, and
requotes -- often exactly when the signal fires. We model this as a cost multiplier and require any
candidate to stay net-positive with only modest edge erosion under it. This is the gate that stops
a demo-only "edge" from being deployed into a venue that quietly eats it.
"""

from __future__ import annotations

from dataclasses import dataclass

from libs.costs.errors import CostError

_DEFAULT_MULTIPLIER = 2.5   # live all-in cost ~ 2-3x calibrated demo cost (conservative prior)
_MAX_EROSION = 0.30         # a real edge should lose <= 30% of its net return to the gap


@dataclass(frozen=True)
class ExecutionGap:
    """Conservative demo->live degradation as a multiplier on per-turnover cost."""

    cost_multiplier: float = _DEFAULT_MULTIPLIER

    def __post_init__(self) -> None:
        if self.cost_multiplier < 1.0:
            raise CostError("cost_multiplier must be >= 1.0 (live is never cheaper than demo)")

    def stress(self, per_side_cost: float) -> float:
        """The per-turnover cost to use for the stressed re-run."""
        return per_side_cost * self.cost_multiplier


def edge_erosion(base_net: float, stressed_net: float) -> float:
    """Fraction of base net return lost under the gap (1.0 if base was non-positive)."""
    if base_net <= 0:
        return 1.0
    return max(0.0, (base_net - stressed_net) / base_net)


def survives_execution_gap(
    base_net: float, stressed_net: float, *, max_erosion: float = _MAX_EROSION
) -> bool:
    """A candidate survives the gap iff it stays net-positive AND keeps most of its edge."""
    return stressed_net > 0.0 and edge_erosion(base_net, stressed_net) <= max_erosion
