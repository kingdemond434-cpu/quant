"""Department slots (2026-11-03): pass heartbeat reclaim, CPU-gated six slots, the 90-minute
clock with tail resume, and strict FIFO that never skips an unreadable (SYSTEM) owner."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import department_resident as dr  # noqa: E402

from libs.ops import leg_rotation as LR  # noqa: E402


def _locks(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(dr, "REPORTS", tmp_path / "reports")
    (tmp_path / "locks").mkdir(parents=True, exist_ok=True)


def _ticket(tmp_path, ns: int, pid: int, dept: str) -> Path:
    path = tmp_path / "locks" / f"dept_wait_{ns}_{pid}_{dept}.ticket"
    path.touch()
    return path


# ------------------------------------------------------------------ 1. the pass heartbeat
def test_a_hung_child_is_reclaimed_by_its_own_resident(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    hung = tmp_path / "hung.py"
    hung.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", hung)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.setattr(dr, "_tree_cpu_progress", lambda _pid, _seen: False)  # measured, idle
    killed = []
    real_kill = dr._kill_own_tree

    def kill(proc):
        killed.append(proc.pid)
        return real_kill(proc)

    monkeypatch.setattr(dr, "_kill_own_tree", kill)
    t0 = time.monotonic()
    res = dr.run_pass("regions", timeout_s=60, slot="dept_capacity_0", stall_s=1, poll_s=0.2)
    assert res["status"] == "stalled" and "no heartbeat" in res["why"]
    assert time.monotonic() - t0 < 30
    assert len(killed) == 1                                  # its own child, exactly once
    assert not dr.pass_heartbeat_path("regions").exists()   # released


def test_cpu_progress_or_leg_beats_keep_a_long_pass_alive(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    beating = tmp_path / "beating.py"
    beating.write_text(
        "import os, time, pathlib\n"
        "for _ in range(8):\n"
        "    pathlib.Path(os.environ['DEPT_PASS_HEARTBEAT']).write_text('leg')\n"
        "    time.sleep(0.3)\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", beating)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.setattr(dr, "_tree_cpu_progress", lambda _pid, _seen: False)
    res = dr.run_pass("meta", timeout_s=60, stall_s=1, poll_s=0.2)
    assert res["status"] == "ok", res


def test_unmeasurable_tree_never_kills_on_stall(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    quiet = tmp_path / "quiet.py"
    quiet.write_text("import time\ntime.sleep(1.5)\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", quiet)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.setattr(dr, "_tree_cpu_progress", lambda _pid, _seen: None)
    assert dr.run_pass("asean", timeout_s=60, stall_s=0, poll_s=0.2)["status"] == "ok"


def test_hourly_cycle_touches_the_pass_heartbeat_at_leg_boundaries(monkeypatch, tmp_path):
    import hourly_cycle as hc
    beat = tmp_path / "beat"
    monkeypatch.setenv("DEPT_PASS_HEARTBEAT", str(beat))
    hc._pass_heartbeat("deepen", "start")
    doc = json.loads(beat.read_text(encoding="utf-8"))
    assert doc["leg"] == "deepen" and doc["source"] == "leg" and doc["child_pid"] == os.getpid()
    monkeypatch.delenv("DEPT_PASS_HEARTBEAT")
    beat.unlink()
    hc._pass_heartbeat("deepen", "end")
    assert not beat.exists()


def test_a_stalled_pass_releases_the_slot_and_requeues(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "free_phys_mb", lambda: None)
    monkeypatch.setattr(dr, "admission_slots", lambda: (2, "test"))
    monkeypatch.setattr(dr, "heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(dr, "PAUSE_S", 0)
    monkeypatch.setattr(dr, "RECYCLE_PASSES", 2)
    monkeypatch.setattr(dr, "cycle_floor_s", lambda: (0.0, "test"))
    results = iter([{"status": "stalled", "rc": None, "seconds": 1.0, "why": "no heartbeat",
                     "killed": {"pid": 1}},
                    {"status": "ok", "rc": 0, "seconds": 1.0}])
    held = []

    def fake_pass(dept, slot=""):
        # the slot is held during the pass, and released before the requeued pass
        probe = dr.claim_capacity_slot(1)
        held.append(probe is None)
        if probe is not None:
            probe.close()
        return next(results)

    monkeypatch.setattr(dr, "run_pass", fake_pass)
    assert dr.main(["--dept", "regions"]) == 0
    assert held == [True, True]
    log = (tmp_path / "logs" / "department_resident.log").read_text(encoding="utf-8")
    assert "RECLAIMED dept_capacity_0" in log and "requeued" in log
    free = dr.claim_capacity_slot(1)
    assert free is not None                                 # nothing left holding slot 0
    free.close()


# ------------------------------------------------------------- 2. six slots, CPU-gated
def test_defaults_are_six_slots_and_ninety_minutes():
    assert int(os.environ.get("DEPT_CONCURRENT_PASSES", "6")) == dr.CONCURRENT_PASSES
    assert int(os.environ.get("DEPT_PASS_TIMEOUT_S", "5400")) == dr.PASS_TIMEOUT_S
    assert dr.JUDGE_RESERVED_CORES == 8 and dr.MIN_FREE_CORES_TO_ADMIT == 2


def test_admission_requires_two_free_cores_after_the_judge(monkeypatch):
    monkeypatch.setattr(dr, "CONCURRENT_PASSES", 6)
    monkeypatch.setattr(dr, "_logical_cores", lambda: 18)
    monkeypatch.setattr(dr, "busy_cores", lambda: (7.5, "t"))       # 18-8-7.5 = 2.5
    assert dr.admission_slots()[0] == 6
    monkeypatch.setattr(dr, "busy_cores", lambda: (8.5, "t"))       # 1.5 free
    slots, why = dr.admission_slots()
    assert slots == 1 and "floor of 1 slot" in why                # anti-starvation floor
    monkeypatch.setattr(dr, "busy_cores", lambda: (None, "UNMEASURED"))
    slots, why = dr.admission_slots()
    assert slots == 3 and "UNMEASURED" in why                      # never more than before


def test_busy_cores_counts_only_judge_use_above_its_reservation(monkeypatch):
    fake = types.ModuleType("judging_throughput")
    fake.measure_cpu = lambda _s=1.0: {"busy_other_cores": 4.0, "busy_judge_cores": 10.0}
    monkeypatch.setitem(sys.modules, "judging_throughput", fake)
    busy, _ = dr.busy_cores()
    assert busy == 6.0
    fake.measure_cpu = lambda _s=1.0: {"busy_other_cores": 4.0, "busy_judge_cores": 3.0}
    assert dr.busy_cores()[0] == 4.0


def test_head_waits_for_cpu_and_six_slots_bound_admission(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    monkeypatch.setattr(dr, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(dr, "_ticket_alive", lambda _p, _pid: True)
    calls = iter([(0, "busy"), (0, "busy"), (6, "room")])
    handle = dr.wait_for_capacity("intel", slots=6, poll_s=0, admit=lambda: next(calls))
    assert Path(handle.name).stem == "dept_capacity_0"
    held = [dr.claim_capacity_slot(6) for _ in range(5)]
    assert all(h is not None for h in held)
    assert dr.claim_capacity_slot(6) is None
    for h in (handle, *held):
        h.close()


# ------------------------------------------------- 3. 90-minute clock, the tail resumes
def test_pass_budget_plans_inside_the_ninety_minute_clock():
    assert int(5400 * dr.PASS_BUDGET_FILL) < 5400


def test_a_leg_that_no_longer_fits_yields_and_leads_the_next_pass():
    roster = ["head", "mid", "tail"]
    att = LR.Attendance(runs=dict.fromkeys(roster, 3),
                        costs={"head": [1000.0], "mid": [1000.0], "tail": [1500.0]})
    for i, leg in enumerate(roster):
        att.last_at[leg] = f"2026-11-03T0{i}:00:00+00:00"
    dec = LR.plan_pass(roster, att, plan="dept:regions", budget_s=4428.0)
    assert dec.admitted == set(roster)
    # The head overran: at 3200 s the tail's measured 1500 s would cross 4428 s.
    ok, why = dec.should_run("tail", att, elapsed_s=3200.0)
    assert not ok and "would not fit" in why
    ok, _ = dec.should_run("tail", att, elapsed_s=2000.0)
    assert ok
    # The yielded tail wrote no ledger row, so it is the OLDEST leg and leads the next pass.
    att.last_at["head"] = att.last_at["mid"] = "2026-11-03T05:00:00+00:00"
    nxt = LR.plan_pass(roster, att, plan="dept:regions", budget_s=1600.0)
    assert "tail" in nxt.admitted and "tail" not in nxt.deferred


def test_resident_hands_the_child_a_budget_inside_its_kill_clock(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    seen = {}
    fake = tmp_path / "cycle.py"
    fake.write_text("print('ok')\n", encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", fake)
    monkeypatch.setattr(dr, "DESK", tmp_path)
    monkeypatch.delenv("HOURLY_BUDGET_S", raising=False)

    def spawn(args, **kwargs):
        seen.update(kwargs["env"])
        kwargs.pop("creationflags", None)
        return subprocess.Popen(args, **kwargs)

    monkeypatch.setattr(dr, "_spawn", spawn)
    assert dr.run_pass("europe", timeout_s=5400)["status"] == "ok"
    assert int(seen["HOURLY_BUDGET_S"]) == int(5400 * dr.PASS_BUDGET_FILL)
    assert seen["DEPT_PASS_HEARTBEAT"].endswith("dept_pass_europe.heartbeat")


# ------------------------------------------------ 4. strict FIFO, the europe skip, RED
def test_an_unreadable_system_owner_keeps_its_place_at_the_head(monkeypatch, tmp_path):
    """The europe shape: a SYSTEM-owned ticket whose owner check is refused and whose delete is
    refused. The old code dropped it and admitted the next ticket; it must stay the head."""
    _locks(monkeypatch, tmp_path)
    europe = _ticket(tmp_path, 1_000, 4242, "europe")
    later = _ticket(tmp_path, 2_000, 5151, "intel")

    class AccessDenied(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    def process(pid):
        if pid == 4242:
            raise OSError(5, "Access is denied")      # a raw WinError, not psutil.AccessDenied
        return types.SimpleNamespace(create_time=lambda: 0.0)

    fake = types.SimpleNamespace(Process=process, NoSuchProcess=NoSuchProcess,
                                 AccessDenied=AccessDenied)
    monkeypatch.setitem(sys.modules, "psutil", fake)
    real_unlink = Path.unlink

    def refuse(self, missing_ok=False):
        if self.name == europe.name:
            raise PermissionError(5, "Access is denied")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    assert dr._owner_state(4242, 1e-6) == dr.UNMEASURED
    assert dr._oldest_waiter() == europe
    assert later.exists()


def test_a_proven_dead_owner_leaves_even_when_its_delete_is_refused(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    ghost = _ticket(tmp_path, 1_000, 999_999, "ghost")
    live = _ticket(tmp_path, 2_000, os.getpid(), "intel")

    class NoSuchProcess(Exception):
        pass

    def process(pid):
        if pid == 999_999:
            raise NoSuchProcess(pid)
        return types.SimpleNamespace(create_time=lambda: 0.0)

    monkeypatch.setitem(sys.modules, "psutil",
                        types.SimpleNamespace(Process=process, NoSuchProcess=NoSuchProcess))
    real_unlink = Path.unlink

    def refuse(self, missing_ok=False):
        if self.name == ghost.name:
            raise PermissionError(5, "Access is denied")
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    contenders, set_aside = dr._queue()
    assert [c["path"] for c in contenders] == [live]
    assert any("delete refused" in x for x in set_aside)


def test_pid_reuse_after_the_ticket_is_dead_and_admission_is_by_ticket_time(monkeypatch,
                                                                            tmp_path):
    _locks(monkeypatch, tmp_path)

    class NoSuchProcess(Exception):
        pass

    born = {11: 5.0, 22: 0.5, 33: 0.5}                    # pid 11 was born after its ticket
    monkeypatch.setitem(sys.modules, "psutil", types.SimpleNamespace(
        Process=lambda pid: types.SimpleNamespace(create_time=lambda: born[pid]),
        NoSuchProcess=NoSuchProcess))
    reused = _ticket(tmp_path, 1_000_000_000, 11, "a")
    late = _ticket(tmp_path, 3_000_000_000, 22, "zz")
    early = _ticket(tmp_path, 2_000_000_000, 33, "zz_older")
    os.utime(late, (1, 1))                                # mtime is never the clock
    assert dr._oldest_waiter() == early
    assert not reused.exists()
    assert dr._parse_ticket(early) == (2_000_000_000, 33, "zz_older")
    assert dr._parse_ticket(Path("dept_wait_x_1_a.ticket")) is None


def test_os_fallback_without_psutil(monkeypatch):
    monkeypatch.setattr(dr.sys, "platform", "linux")
    assert dr._owner_state_os(os.getpid()) == dr.ALIVE

    def denied(_pid, _sig):
        raise PermissionError

    monkeypatch.setattr(dr.os, "kill", denied)
    assert dr._owner_state_os(1) == dr.UNMEASURED           # refused is not dead

    def gone(_pid, _sig):
        raise ProcessLookupError

    monkeypatch.setattr(dr.os, "kill", gone)
    assert dr._owner_state_os(1) == dr.DEAD


def test_a_ticket_waiting_over_two_hours_writes_red(monkeypatch, tmp_path):
    _locks(monkeypatch, tmp_path)
    now = time.time()
    contenders = [{"entered": int((now - 7.5 * 3600) * 1e9), "name": "t1", "pid": 1,
                   "dept": "europe"},
                  {"entered": int((now - 600) * 1e9), "name": "t2", "pid": 2, "dept": "intel"}]
    doc = dr.write_queue_report(contenders, [], force=True)
    assert doc["verdict"] == "RED" and [x["dept"] for x in doc["starved"]] == ["europe"]
    on_disk = json.loads((tmp_path / "reports" / "DEPT_QUEUE.json").read_text("utf-8"))
    assert on_disk["verdict"] == "RED" and "europe" in on_disk["why"]
    assert dr.write_queue_report(contenders[1:], []) is None     # rate-limited
    assert dr.write_queue_report(contenders[1:], [], force=True)["verdict"] == "GREEN"


def test_process_health_raises_attention_on_a_red_queue(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "process_health_dept_queue_under_test", DESK.parents[1] / "ops" / "process_health.py")
    assert spec is not None and spec.loader is not None
    ph = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ph)
    q = tmp_path / "DEPT_QUEUE.json"
    assert ph.department_queue(q) == {"state": "ABSENT", "fault": False}
    q.write_text(json.dumps({"verdict": "RED", "why": "europe 7.5h",
                             "starved": [{"dept": "europe"}]}), encoding="utf-8")
    got = ph.department_queue(q)
    assert got["fault"] and got["state"] == "RED"
    os.utime(q, (time.time() - 7200, time.time() - 7200))
    assert ph.department_queue(q)["fault"] is False               # stale RED is not live


def _fake_psutil(monkeypatch, cpu_s, io_b):
    """A psutil whose single child process reports the given cpu seconds and io bytes."""
    class _P:
        pid = 4242

        def __init__(self, *_a):
            pass

        def children(self, recursive=True):
            return []

        def cpu_times(self):
            return types.SimpleNamespace(user=cpu_s[0], system=0.0)

        def io_counters(self):
            return types.SimpleNamespace(read_bytes=io_b[0], write_bytes=0, other_bytes=0)
    mod = types.ModuleType("psutil")
    mod.Process = _P
    monkeypatch.setitem(sys.modules, "psutil", mod)


def test_io_bound_leg_with_near_zero_cpu_counts_as_progress(monkeypatch):
    cpu, io = [10.0], [1000]
    _fake_psutil(monkeypatch, cpu, io)
    seen: dict = {}
    assert dr._tree_cpu_progress(4242, seen) is False        # first poll is a baseline
    cpu[0] += 0.01                                           # waiting on a remote queue
    io[0] += 512                                             # but bytes are moving
    assert dr._tree_cpu_progress(4242, seen) is True
    cpu[0] += 0.01                                           # no cpu, no io: really idle
    assert dr._tree_cpu_progress(4242, seen) is False


def test_io_bound_child_is_not_reclaimed(monkeypatch, tmp_path):
    cpu, io = [1.0], [0]
    _fake_psutil(monkeypatch, cpu, io)
    monkeypatch.setattr(dr, "LOCKS", tmp_path)

    class _Proc:
        pid = 4242
        polls = 0

        def wait(self, timeout=None):
            _Proc.polls += 1
            io[0] += 4096                                    # bytes every poll, cpu flat
            if _Proc.polls > 6:
                return 0
            raise dr.subprocess.TimeoutExpired("x", timeout)
    monkeypatch.setattr(dr, "_spawn", lambda *a, **k: _Proc())
    monkeypatch.setattr(dr, "_kill_own_tree", lambda p: pytest.fail("killed an I/O-bound leg"))
    # A heartbeat reads fresh only right after a touch, 2s old otherwise (stall_s=1), so the pass
    # survives only if every poll's I/O produces a touch.
    fresh = {"v": False}
    touched: list = []

    def _touch(path, **i):
        touched.append(i.get("source"))
        fresh["v"] = True

    def _age(path, now=None):
        was, fresh["v"] = fresh["v"], False
        return 0.0 if was else 2.0
    monkeypatch.setattr(dr, "touch_pass_heartbeat", _touch)
    monkeypatch.setattr(dr, "_heartbeat_age_s", _age)
    res = dr.run_pass("era5", timeout_s=3600, stall_s=1, poll_s=0.01)
    assert res["status"] == "ok"
    assert "cpu" in touched


def test_same_leg_reclaimed_twice_goes_red(monkeypatch, tmp_path):
    monkeypatch.setattr(dr, "LOCKS", tmp_path)
    first = dr.note_reclaim("intel", "cds_reader", now=1000.0)
    assert first["repeat"] is False
    second = dr.note_reclaim("intel", "cds_reader", now=1100.0)
    assert second["repeat"] is True and second["count"] == 2
    doc = dr.queue_report([], [], now=1200.0)
    assert doc["verdict"] == "RED" and "RECLAIMED_REPEAT" in doc["why"]
    assert doc["reclaim_repeats"][0]["leg"] == "cds_reader"
    dr.note_reclaim("intel", "other_leg", now=1300.0)        # a different leg resets the count
    assert dr.queue_report([], [], now=1400.0)["verdict"] == "GREEN"
    dr.note_reclaim("intel", "other_leg", now=1500.0)
    dr.clear_reclaim("intel")                                # a completed pass clears it
    assert dr.queue_report([], [], now=1600.0)["verdict"] == "GREEN"
