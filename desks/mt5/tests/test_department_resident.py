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


# ---------------------------------------------------- supervised restart-on-exit (BACKLOG 09-29)
def _isolate(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")


def test_supervisor_restarts_the_worker_on_every_exit_without_waiting_for_the_trigger(
        monkeypatch, tmp_path):
    """A recycle used to leave the department dead until the next ten-minute keep-alive."""
    _isolate(monkeypatch, tmp_path)
    exits = iter([0, 0, 0])
    naps: list[float] = []
    n = dr.supervise("intel", spawn=lambda _d: next(exits), sleep=naps.append,
                     digest=lambda: "same", max_workers=3)
    assert n == 0
    assert naps == [dr.RESPAWN_S] * 3 and dr.RESPAWN_S < 60
    # the supervisor held the department for its whole life and released it at the end
    again = dr.claim_singleton("intel")
    assert again is not None
    again.close()


def test_supervisor_refuses_a_second_copy_of_the_department(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    held = dr.claim_singleton("intel")
    assert held is not None
    spawned: list[str] = []
    assert dr.supervise("intel", spawn=lambda d: spawned.append(d) or 0, sleep=lambda _s: None,
                        digest=lambda: "same", max_workers=1) == 0
    assert spawned == []
    held.close()


def test_crash_backoff_is_bounded_and_resets_after_a_healthy_life():
    delay, deaths = dr.respawn_delay(1, 5.0, 0)
    assert (delay, deaths) == (dr.CRASH_BACKOFF_S, 1)
    for _ in range(20):
        delay, deaths = dr.respawn_delay(1, 5.0, deaths)
    assert delay == dr.CRASH_BACKOFF_MAX_S
    # never slower than the ten-minute keep-alive it replaces
    assert dr.CRASH_BACKOFF_MAX_S < 600
    assert dr.respawn_delay(1, dr.YOUNG_DEATH_S + 1, deaths) == (dr.CRASH_BACKOFF_S, 1)
    assert dr.respawn_delay(0, 5.0, deaths) == (dr.RESPAWN_S, 0)
    assert dr.respawn_delay(dr.WORKER_BUSY_RC, 1.0, 2) == (dr.WORKER_BUSY_WAIT_S, 2)


def test_an_orphaned_worker_is_never_doubled(monkeypatch, tmp_path):
    """A killed supervisor can leave its worker alive; the next one's worker must step aside."""
    _isolate(monkeypatch, tmp_path)
    orphan = dr.claim_worker("intel")
    assert orphan is not None
    assert dr.main(["--dept", "intel", "--worker"]) == dr.WORKER_BUSY_RC
    orphan.close()
    # the worker lock sits outside the dept_*.lock glob the moat registry reads as departments
    assert not list((tmp_path / "locks").glob("dept_*.lock"))


def test_supervisor_exits_when_its_own_code_is_adopted(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path)
    digests = iter(["old", "new"])
    spawned: list[str] = []
    assert dr.supervise("intel", spawn=lambda d: spawned.append(d) or 0, sleep=lambda _s: None,
                        digest=lambda: next(digests), max_workers=5) == 0
    assert spawned == ["intel"]


def test_the_task_entrypoint_is_the_supervisor(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(dr, "supervise", lambda d: called.append(d) or 0)
    assert dr.main(["--dept", "Intel"]) == 0
    assert called == ["intel"]
