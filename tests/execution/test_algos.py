"""Execution algorithms — TWAP, POV, Implementation Shortfall."""

from __future__ import annotations

import pytest

from libs.execution.algos import ExecutionScheduler
from libs.execution.errors import ExecutionError


def test_twap_splits_evenly_and_sums_to_total() -> None:
    plan = ExecutionScheduler().twap(
        symbol="XAUUSD", side="buy", total_qty=10.0, n_slices=5, interval_seconds=60
    )
    assert plan.algo == "twap"
    assert len(plan.slices) == 5
    assert plan.scheduled_qty == pytest.approx(10.0)
    assert [c.offset_seconds for c in plan.slices] == [0, 60, 120, 180, 240]
    assert all(c.qty == pytest.approx(2.0) for c in plan.slices)


def test_pov_paces_to_volume_and_completes() -> None:
    plan = ExecutionScheduler().pov(
        symbol="XAUUSD", side="sell", total_qty=10.0,
        volume_curve=[100.0, 100.0, 100.0], participation_rate=0.05, interval_seconds=30,
    )
    # 5% of 100 = 5 per bucket -> 5 + 5 fills the 10 in two slices
    assert plan.scheduled_qty == pytest.approx(10.0)
    assert len(plan.slices) == 2


def test_pov_absorbs_remainder_when_curve_too_small() -> None:
    plan = ExecutionScheduler().pov(
        symbol="XAUUSD", side="buy", total_qty=10.0, volume_curve=[10.0],
        participation_rate=0.1, interval_seconds=30,
    )  # 0.1*10 = 1 per bucket, only one bucket -> remainder folded into last slice
    assert plan.scheduled_qty == pytest.approx(10.0)


def test_implementation_shortfall_is_front_loaded() -> None:
    plan = ExecutionScheduler().implementation_shortfall(
        symbol="XAUUSD", side="buy", total_qty=10.0, n_slices=4, interval_seconds=60, urgency=0.9
    )
    assert plan.scheduled_qty == pytest.approx(10.0)
    qtys = [c.qty for c in plan.slices]
    assert qtys[0] > qtys[-1]  # earlier slices larger under high urgency


def test_algos_validate_inputs() -> None:
    sched = ExecutionScheduler()
    with pytest.raises(ExecutionError):
        sched.twap(symbol="X", side="buy", total_qty=0.0, n_slices=3, interval_seconds=1)
    with pytest.raises(ExecutionError):
        sched.twap(symbol="X", side="hold", total_qty=1.0, n_slices=3, interval_seconds=1)
    with pytest.raises(ExecutionError):
        sched.pov(symbol="X", side="buy", total_qty=1.0, volume_curve=[1.0],
                  participation_rate=1.5, interval_seconds=1)
