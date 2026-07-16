"""Cost stress scenarios (BASE / 2X / 3X / 5X).

The validation gauntlet requires every edge to survive *pessimistic* costs. These scenarios
scale the market-driven components (spread, slippage, gap) — the parts that blow out in
stress — while leaving contractual commission and rate-based financing unchanged.
"""

from __future__ import annotations

from enum import StrEnum

_MULTIPLIERS: dict[str, float] = {"base": 1.0, "2x": 2.0, "3x": 3.0, "5x": 5.0}


class CostScenario(StrEnum):
    BASE = "base"
    X2 = "2x"
    X3 = "3x"
    X5 = "5x"

    @property
    def multiplier(self) -> float:
        return _MULTIPLIERS[self.value]
