"""Stress-cost validation.

An edge must survive *pessimistic* costs, not just base costs. Gross trade PnL is reduced by
the cost model scaled across BASE/2X/3X/5X; the candidate must remain net-positive at the
required stress scenario.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.costs.scenarios import CostScenario
from libs.validation.errors import ValidationError


class StressScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario: str
    multiplier: float
    gross_pnl: float
    cost: float
    net_pnl: float
    survived: bool


class StressCostResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    passed: bool
    required_scenario: str
    by_scenario: list[StressScenarioResult]
    message: str

    def __bool__(self) -> bool:
        return self.passed


def stress_cost_validation(
    gross_pnls: Sequence[float],
    base_costs: Sequence[float],
    *,
    required_scenario: CostScenario = CostScenario.X3,
    scenarios: Sequence[CostScenario] = (
        CostScenario.BASE,
        CostScenario.X2,
        CostScenario.X3,
        CostScenario.X5,
    ),
) -> StressCostResult:
    """Check net PnL stays positive at increasing cost multiples; pass at ``required_scenario``."""
    gross = np.asarray(gross_pnls, dtype="float64")
    costs = np.asarray(base_costs, dtype="float64")
    if len(gross) != len(costs):
        raise ValidationError("gross_pnls and base_costs must have equal length")
    if (costs < 0).any():
        raise ValidationError("base_costs must be non-negative")

    gross_total = float(gross.sum())
    cost_total = float(costs.sum())
    results: list[StressScenarioResult] = []
    passed = False
    for scenario in scenarios:
        net = gross_total - scenario.multiplier * cost_total
        survived = net > 0.0
        results.append(
            StressScenarioResult(
                scenario=scenario.value, multiplier=scenario.multiplier,
                gross_pnl=gross_total, cost=scenario.multiplier * cost_total,
                net_pnl=net, survived=survived,
            )
        )
        if scenario == required_scenario:
            passed = survived
    message = (
        f"survives {required_scenario.value} stress"
        if passed
        else f"fails {required_scenario.value} stress"
    )
    return StressCostResult(
        passed=passed, required_scenario=required_scenario.value, by_scenario=results,
        message=message,
    )
