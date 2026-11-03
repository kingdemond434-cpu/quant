"""The department resident: singleton, one pass under the department plan, the cycle floor."""
from __future__ import annotations

import sys
import subprocess
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import department_resident as dr  # noqa: E402


def test_recycled_resident_records_durable_completion_not_process_start(monkeypatch):
    from libs.moat import registry
    from libs.ops.control_plane import watermarks

    monkeypatch.setattr(registry, "worker_heartbeat", lambda *args, **kwargs: None)
    state = {"value": 48}
    updates = []
    monkeypatch.setattr(watermarks, "read", lambda _component: state.copy())

    def record(component, metric, value, **kwargs):
        updates.append((component, metric, value, kwargs))
        state["value"] = value

    monkeypatch.setattr(watermarks, "progress", record)
    dr.heartbeat("discovery", 1)
    assert not updates, "starting a recycled process is not completed work"
    dr.heartbeat("discovery", 1, done_inc=1)
    dr.heartbeat("discovery", 2, done_inc=1)
    dr.heartbeat("discovery", 2, status="stopped")
    assert [row[2] for row in updates] == [49, 50]
    assert updates[-1][0:2] == ("resident:dept_discovery", "passes")
    assert updates[-1][3]["local_pass"] == 2


def test_singleton_lock_is_exclusive(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    a = dr.claim_singleton("intel")
    assert a is not None
    assert dr.claim_singleton("intel") is None          # a second holder is refused
    m = dr.claim_singleton("macro")
    assert m is not None                                # another department is free
    m.close()
    a.close()
    b = dr.claim_singleton("intel")
    assert b is not None                                # released when the holder closes
    b.close()


def test_capacity_slots_bound_cross_department_passes(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    first = dr.claim_capacity_slot(2)
    second = dr.claim_capacity_slot(2)
    assert first is not None and second is not None
    assert dr.claim_capacity_slot(2) is None
    first.close()
    replacement = dr.claim_capacity_slot(2)
    assert replacement is not None
    replacement.close()
    second.close()


def test_capacity_waiters_are_fifo_and_a_completed_pass_rejoins_at_tail(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _path, _pid: True)
    first = dr._wait_ticket("discovery")
    time.sleep(0.001)
    second = dr._wait_ticket("macro")
    assert dr._oldest_waiter() == first
    first.unlink()
    rejoined = dr._wait_ticket("discovery")
    assert dr._oldest_waiter() == second
    second.unlink()
    assert dr._oldest_waiter() == rejoined
    rejoined.unlink()


def test_crashed_waiter_cannot_starve_a_live_department(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    old = dr._wait_ticket("stale")
    live = dr._wait_ticket("discovery")
    monkeypatch.setattr(dr, "_ticket_alive", lambda path, _pid: path != old)
    assert dr._oldest_waiter() == live
    assert not old.exists()
    live.unlink()


def test_one_pass_runs_the_cycle_under_the_department_plan(monkeypatch, tmp_path):
    fake = tmp_path / "cycle.py"
    fake.write_text(
        "import os, sys\n"
        "ok = os.environ.get('HOURLY_PLAN') == 'dept:intel'\n"
        "ok = ok and int(os.environ.get('HOURLY_BUDGET_S', 0)) == 49\n"
        "sys.exit(0 if ok else 3)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dr, "CYCLE", fake)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.setattr(dr, "PASS_BUDGET_FILL", 0.82)
    monkeypatch.delenv("HOURLY_BUDGET_S", raising=False)
    def owned_child(args, **kwargs):
        # Assert the resident requested its production priority; scheduling fairness on
        # the busy VPS is outside this environment/plan contract. Execute the owned
        # child at normal priority so production workers cannot starve the fixture.
        assert args[-1] == str(fake)
        if sys.platform == "win32":
            assert kwargs.pop("creationflags") == dr.BELOW_NORMAL_PRIORITY_CLASS
        return subprocess.run(args, **kwargs)
    monkeypatch.setattr(dr, "_run_tree", owned_child)
    res = dr.run_pass("intel", timeout_s=60)
    assert res["status"] == "ok" and res["rc"] == 0
    res2 = dr.run_pass("macro", timeout_s=60)
    assert res2["status"] == "exit" and res2["rc"] == 3


def test_timeout_is_reported_not_raised(monkeypatch, tmp_path):
    fake = tmp_path / "slow.py"
    fake.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", fake)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    assert dr.run_pass("intel", timeout_s=1)["status"] == "timeout"


def test_main_once_exits_with_the_pass_result(monkeypatch, tmp_path):
    fake = tmp_path / "cycle.py"
    fake.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", fake)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "free_phys_mb", lambda: None)
    assert dr.main(["--dept", "intel", "--once"]) == 0
    assert (tmp_path / "logs" / "department_resident.log").exists()


def test_queue_order_is_longest_wait_from_readiness_not_arrival(monkeypatch, tmp_path):
    """A resident that sat in the memory guard became ready FIRST; it must not be served after
    every resident that reached the queue while it waited (2026-10-29: 3-5 h waits)."""
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _path, _pid: True)
    ready_early = time.time_ns() - 1_800 * 10**9          # ready 30 min ago, held by memory
    arrived_first = dr._wait_ticket("forward")
    time.sleep(0.001)
    longest = dr._wait_ticket("forest_europe", ready_ns=ready_early)
    assert dr._oldest_waiter() == longest
    longest.unlink()
    assert dr._oldest_waiter() == arrived_first
    arrived_first.unlink()


def test_admission_records_the_wait_and_never_cuts_a_slot(monkeypatch, tmp_path):
    import json
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _path, _pid: True)
    monkeypatch.setattr(dr, "MAX_WAIT_S", 5.0)
    held = [dr.claim_capacity_slot(3) for _ in range(2)]
    handle = dr.wait_for_capacity("execution", slots=3, poll_s=1,
                                  ready_ns=time.time_ns() - 10 * 10**9)
    try:
        doc = json.loads((tmp_path / "locks" / "dept_queue_execution.json").read_text("utf-8"))
        assert doc["waited_s"] >= 10.0 and doc["slots"] == dr.CONCURRENT_PASSES
        log = (tmp_path / "logs" / "department_resident.log").read_text("utf-8")
        assert "PAST the 5s wait bound" in log
        assert dr.claim_capacity_slot(3) is None, "all three slots stay in use: none was cut"
    finally:
        handle.close()
        for h in held:
            h.close()
    assert not list((tmp_path / "locks").glob("dept_wait_*.ticket")), "ticket released"


def test_longest_waiters_are_admitted_in_order_as_slots_free(monkeypatch, tmp_path):
    """Seven waiters, two slots: each freed slot goes to the longest waiter still queued."""
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _path, _pid: True)
    base = time.time_ns()
    order = ["rest", "data", "intel", "forest_japan", "validate", "forward", "execution"]
    tickets = {d: dr._wait_ticket(d, ready_ns=base - (len(order) - i) * 10**9)
               for i, d in enumerate(order)}
    served = []
    while tickets:
        head = dr._oldest_waiter()
        dept = next(d for d, t in tickets.items() if t == head)
        served.append(dept)
        tickets.pop(dept).unlink()
    assert served == order
