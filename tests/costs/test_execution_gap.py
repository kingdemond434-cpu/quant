"""Demo->live execution-gap stress (committee Lever 2 / T4)."""

from __future__ import annotations

import pytest

from libs.costs.errors import CostError
from libs.costs.execution_gap import ExecutionGap, edge_erosion, survives_execution_gap


def test_gap_multiplies_cost() -> None:
    gap = ExecutionGap(cost_multiplier=3.0)
    assert gap.stress(0.0001) == pytest.approx(0.0003)


def test_multiplier_below_one_rejected() -> None:
    with pytest.raises(CostError):
        ExecutionGap(cost_multiplier=0.8)


def test_erosion_and_survival() -> None:
    # Edge that barely degrades survives; one that collapses under the gap does not.
    assert survives_execution_gap(base_net=1.0, stressed_net=0.8)        # 20% erosion, positive
    assert not survives_execution_gap(base_net=1.0, stressed_net=0.5)    # 50% erosion -> fail
    assert not survives_execution_gap(base_net=1.0, stressed_net=-0.1)   # goes negative -> fail
    assert edge_erosion(1.0, 0.7) == pytest.approx(0.30)
    assert edge_erosion(-0.2, 0.5) == 1.0       # non-positive base = no edge to erode
