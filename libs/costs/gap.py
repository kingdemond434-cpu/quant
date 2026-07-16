"""Gap-risk component.

Stops do not guarantee fills: gold gaps on the Sunday open, CFDs gap on news. The expected
adverse gap is modelled as a fraction of notional and can be included in a trade's cost when
sizing for the gap-through scenario rather than the stop level.
"""

from __future__ import annotations

from libs.costs.params import CostParams


def estimate_gap_cost(params: CostParams, qty_lots: float, price: float) -> float:
    """Expected adverse-gap cost in account currency for holding ``qty_lots`` at ``price``."""
    return params.gap_risk_fraction * price * params.contract_size * qty_lots
