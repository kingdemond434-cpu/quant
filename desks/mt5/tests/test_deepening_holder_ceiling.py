"""A hung deepening holder ends itself, so the single-flight lock cannot go dark for hours."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import deepening_worker as dw  # noqa: E402


def test_the_ceiling_fires_past_twice_the_budget_with_the_exit_code() -> None:
    fired = threading.Event()
    got: list[int] = []

    def _exit(rc: int) -> None:
        got.append(rc)
        fired.set()

    t = dw.arm_holder_ceiling(0.01, exit_fn=_exit)
    assert t.daemon and fired.wait(2.0)
    assert got == [dw.HOLDER_EXIT_RC]


def test_a_run_that_finishes_cancels_the_ceiling() -> None:
    got: list[int] = []
    t = dw.arm_holder_ceiling(5.0, exit_fn=got.append)
    t.cancel()
    t.join(1.0)
    assert got == []


def test_the_ceiling_is_the_same_bound_callers_use_as_stale() -> None:
    src = (DESK / "research" / "deepening_worker.py").read_text("utf-8")
    assert "stale_after = RUN_BUDGET_SEC * 2.0" in src
    assert dw.HOLDER_CEILING_FACTOR == 2.0
    assert "ceiling = arm_holder_ceiling()" in src and "ceiling.cancel()" in src


def test_the_swarm_launches_one_single_flight_worker_with_parallel_seats() -> None:
    src = (DESK.parent.parent / "ops" / "convert_swarm.py").read_text("utf-8")
    assert "for model in models[:1]:" in src
    assert 'env["DEEPEN_SEAT_WORKERS"] = str(max(1, len(models)))' in src
    assert 'env["OPENROUTER_MODEL"]' not in src
