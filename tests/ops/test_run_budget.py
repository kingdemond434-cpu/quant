"""libs/ops/run_budget: one deadline for a whole run, interruptible reads, a hard backstop."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from libs.ops.run_budget import EXIT_OVERRUN, RunBudget


def test_stages_run_until_the_deadline_and_are_recorded_after_it() -> None:
    t = [0.0]
    rb = RunBudget(10.0, clock=lambda: t[0])
    with rb.stage("read") as go:
        assert go
        t[0] = 4.0
    with rb.stage("build") as go:
        assert go
        t[0] = 12.0
    with rb.stage("publish") as go:
        assert not go
    s = rb.summary()
    assert s["skipped_stages"] == ["publish"] and s["expired"]
    assert [r["stage"] for r in s["stages"]] == ["read", "build", "publish"]
    assert s["stages"][1]["overran_deadline"] is True


def test_guard_interrupts_a_query_that_outlives_the_deadline() -> None:
    """The full-table GROUP BY that never returned: the progress handler is what returns it."""
    rb = RunBudget(-1.0)                       # already past its deadline
    con = rb.guard(sqlite3.connect(":memory:"), every=100)
    try:
        with pytest.raises(sqlite3.OperationalError, match="interrupt"):
            con.execute("with recursive c(x) as (select 1 union all select x + 1 from c "
                        "where x < 10000000) select count(*) from c").fetchone()
    finally:
        con.close()


def test_guard_leaves_a_connection_without_progress_handlers_alone() -> None:
    class _Fake:
        pass

    fake = _Fake()
    assert RunBudget(1.0).guard(fake) is fake


def test_the_watchdog_publishes_then_exits_with_the_overrun_code() -> None:
    order: list[str] = []
    done = threading.Event()

    def _exit(code: int) -> None:
        order.append(f"exit:{code}")
        done.set()

    rb = RunBudget(0.0)
    rb.watchdog(0.01, lambda: order.append("publish"), name="t", _exit=_exit)
    assert done.wait(5.0)
    assert order == ["publish", f"exit:{EXIT_OVERRUN}"]


def test_a_disarmed_watchdog_never_fires() -> None:
    fired: list[int] = []
    rb = RunBudget(0.2)
    rb.watchdog(0.0, None, _exit=fired.append)
    rb.disarm()
    threading.Event().wait(0.4)
    assert fired == []
