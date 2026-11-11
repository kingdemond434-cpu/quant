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


def test_hung_live_holder_past_its_own_budget_is_reclaimed_and_logged(monkeypatch, tmp_path):
    """2026-11-11: Mathlab waited 8 h on 'bounded department slots'. A live holder hung past its
    own budget (proctree.run's unbounded Popen.__exit__ wait after a failed tree kill) must stop
    counting against the bound; an in-budget live holder must not."""
    import json
    import os
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    held = dr.claim_capacity_slot(1, dept="validate")
    assert held is not None
    assert dr.claim_capacity_slot(1, dept="mathlab") is None   # in budget: still busy
    record = json.loads(dr._holder_path(held.lock_path).read_text(encoding="utf-8"))
    assert record["pid"] == os.getpid() and record["dept"] == "validate"
    record["admitted_epoch"] -= dr.holder_budget_s() + 60     # same live pid, now over budget
    dr._holder_path(held.lock_path).write_text(json.dumps(record), encoding="utf-8")
    reclaimed = dr.claim_capacity_slot(1, dept="mathlab")
    assert reclaimed is not None, "a hung holder past its own budget kept the slot"
    assert reclaimed.record["generation"] == 1
    assert dr.claim_capacity_slot(1, dept="macro") is None     # still bounded for live passes
    log = (tmp_path / "logs" / "department_resident.log").read_text(encoding="utf-8")
    assert "RECLAIM department slot 0 generation 0" in log and "dept[validate]" in log
    reclaimed.close()
    held.close()
    assert not dr._holder_path(held.lock_path).exists()


def test_locked_slot_with_dead_or_unrecorded_holder_is_busy_not_reclaimed(monkeypatch, tmp_path):
    """The kernel frees a dead holder's lock, so a dead pid on a LOCKED slot is a new holder
    mid-write: never a reason to over-admit. Same for a missing record (unmeasured)."""
    import json
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    held = dr.claim_capacity_slot(1, dept="validate")
    record = dict(held.record, admitted_epoch=0.0)
    monkeypatch.setattr(dr, "_pid_state", lambda _pid, _ct: "dead")
    dr._holder_path(held.lock_path).write_text(json.dumps(record), encoding="utf-8")
    assert dr.claim_capacity_slot(1, dept="mathlab") is None
    dr._holder_path(held.lock_path).unlink()
    assert dr.claim_capacity_slot(1, dept="mathlab") is None
    held.close()


def test_abandoned_ticket_with_unmeasurable_owner_cannot_hold_the_queue_head(monkeypatch,
                                                                              tmp_path):
    """A hard-killed waiter skips its finally; if its PID reads alive or unmeasurable
    (reuse, AccessDenied) the old code kept it as the FIFO head forever. A live waiter
    refreshes its ticket every poll, so an untouched one is reclaimed and logged."""
    import os
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _path, _pid: True)   # unmeasured = alive
    abandoned = dr._wait_ticket("ghost")
    live = dr._wait_ticket("mathlab")
    old = time.time() - dr.TICKET_STALE_S - 120
    os.utime(abandoned, (old, old))
    assert dr._oldest_waiter() == live
    assert not abandoned.exists()
    log = (tmp_path / "logs" / "department_resident.log").read_text(encoding="utf-8")
    assert "RECLAIM wait ticket" in log and "dept[ghost]" in log
    live.unlink()


def test_waiter_heartbeats_its_ticket_and_is_admitted(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    handle = dr.wait_for_capacity("mathlab", slots=1, poll_s=1)
    assert handle is not None and handle.record["dept"] == "mathlab"
    handle.close()
    assert not list((tmp_path / "locks").glob("dept_wait_*.ticket"))
