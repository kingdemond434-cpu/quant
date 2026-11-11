from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "memory_guard", Path(__file__).resolve().parents[2] / "ops" / "memory_guard.py")
assert _spec is not None and _spec.loader is not None
mg = importlib.util.module_from_spec(_spec)
sys.modules["memory_guard"] = mg
_spec.loader.exec_module(mg)

BOX = {"total_phys_mb": 98_298, "free_phys_mb": 44_000, "commit_charge_mb": 150_000,
       "commit_limit_mb": 251_700}


FRONTIER_CMD = r"C:\opt\quant\ops\run_frontier_audit.cmd"
LANE = {"pid": 500, "name": "cmd.exe", "cmdline": ["cmd.exe", "/c", FRONTIER_CMD]}
TASKS = [{"TaskName": "\\MT5-FrontierAudit", "Task To Run": FRONTIER_CMD, "Status": "Ready"},
         {"TaskName": "\\MT5-Other", "Task To Run": r"C:\opt\quant\ops\other.cmd",
          "Status": "Running"}]


def proc(pid: int, mb: float, cmd: str, name: str = "python.exe",
         ancestors: list | None = None) -> dict:
    return {"pid": pid, "name": name, "private_mb": mb, "cmdline": cmd.split(),
            "cwd": "C:\\opt\\quant", "owner": "VMI\\Administrator",
            "ancestors": [LANE] if ancestors is None else ancestors}


SCALING = r"C:\Program Files\Python314\python.exe -m libs.ops.scaling_laws"


def test_healthy_box_touches_nothing() -> None:
    d = mg.plan(BOX, [proc(1, 9_000, SCALING)], set())
    assert d["stop"] is None and d["rule"] == "CLEAR"


def test_a_leak_over_the_hard_cap_is_stopped_even_without_pressure() -> None:
    d = mg.plan(BOX, [proc(1, 9_000, "python -m judge"), proc(13224, 30_000, SCALING)], set())
    assert d["rule"] == "HARD_CAP" and d["stop"]["pid"] == 13224


def test_pressure_stops_the_largest_research_job_only() -> None:
    low = {**BOX, "free_phys_mb": 6_000}
    d = mg.plan(low, [proc(1, 3_000, "python -m a"), proc(2, 8_000, "python -m b")], set())
    assert d["rule"] == "PRESSURE" and d["stop"]["pid"] == 2


def test_small_jobs_are_never_blamed_for_pressure() -> None:
    low = {**BOX, "free_phys_mb": 6_000}
    d = mg.plan(low, [proc(1, 500, "python -m a")], set())
    assert d["stop"] is None and d["rule"] == "PRESSURE_NO_CANDIDATE"


def test_commit_near_limit_is_pressure() -> None:
    hot = {**BOX, "commit_charge_mb": 240_000}
    d = mg.plan(hot, [proc(2, 8_000, "python -m b")], set())
    assert d["rule"] == "PRESSURE"


def test_live_path_and_terminals_are_never_candidates() -> None:
    low = {**BOX, "free_phys_mb": 1_000}
    procs = [
        proc(1, 60_000, "terminal64.exe /portable", name="terminal64.exe"),
        proc(2, 60_000, r"python desks\mt5\mt5desk\gateway.py"),
        proc(3, 60_000, r"python -m desks.mt5.prop.e8_gold"),
        proc(4, 60_000, r"python desks\mt5\ftmo_allocator.py"),
        proc(5, 60_000, r"python desks\mt5\recorders\tick_recorder.py"),
        proc(6, 60_000, r"python proposals\fusion_deadman.py"),
        proc(7, 60_000, "python -m ops.memory_guard --apply"),
        proc(8, 60_000, "cmd.exe /c run_frontier_audit.cmd", name="cmd.exe"),
    ]
    d = mg.plan(low, procs, set())
    assert d["stop"] is None
    d2 = mg.plan(low, [proc(9, 60_000, SCALING)], {9})
    assert d2["stop"] is None  # our own tree


def test_requeue_cycle_caps_attempts_per_day() -> None:
    at = "2026-11-11T14:20:00+00:00"
    task = mg.owning_task(proc(13224, 30_000, SCALING), TASKS)
    assert task == "\\MT5-FrontierAudit"
    rows = mg.enqueue([], proc(13224, 30_000, SCALING), "HARD_CAP", "leak", at, task)
    rows = mg.enqueue(rows, proc(13224, 31_000, SCALING), "HARD_CAP", "leak", at, task)
    assert len(rows) == 1 and rows[0]["peak_mb"] == 31_000
    assert rows[0]["owner"] == "VMI\\Administrator"
    for _ in range(mg.MAX_ATTEMPTS):
        r = mg.next_requeue(rows, at, set())
        assert r is not None
        r["attempts"]["2026-11-11"] = r["attempts"].get("2026-11-11", 0) + 1
    assert mg.next_requeue(rows, at, set()) is None
    assert rows[0]["state"] == "GAVE_UP" and "stream" in rows[0]["gave_up_why"]


def test_a_job_no_task_launched_is_stopped_but_never_re_run() -> None:
    at = "2026-11-11T14:20:00+00:00"
    orphan = proc(7, 30_000, r"python C:\Users\x\evil.py", ancestors=[
        {"name": "explorer.exe", "cmdline": ["explorer.exe"]}])
    assert mg.owning_task(orphan, TASKS) is None
    rows = mg.enqueue([], orphan, "HARD_CAP", "leak", at, None)
    assert rows[0]["state"] == "GAVE_UP" and "not re-run as SYSTEM" in rows[0]["gave_up_why"]
    assert mg.next_requeue(rows, at, set()) is None


def test_running_rerun_is_not_started_twice_and_settles_done() -> None:
    at = "2026-11-11T14:20:00+00:00"
    rows = mg.enqueue([], proc(1, 30_000, SCALING), "HARD_CAP", "leak", at,
                      "\\MT5-FrontierAudit")
    assert mg.next_requeue(rows, at, {"\\MT5-FrontierAudit"}) is None
    rows[0]["state"] = "RUNNING"
    rows = mg.settle(rows, {"\\MT5-FrontierAudit"}, at)
    assert rows[0]["state"] == "RUNNING"
    rows = mg.settle(rows, set(), at)
    assert rows[0]["state"] == "DONE"
    rows = mg.settle(rows, set(), "2026-11-20T00:00:00+00:00")
    assert rows == []


def test_the_guard_never_starts_a_recorded_command_line() -> None:
    src = (Path(__file__).resolve().parents[2] / "ops" / "memory_guard.py").read_text("utf-8")
    assert "Popen" not in src and "CreateJobObject" not in src
    assert '["schtasks", "/Run", "/TN", task]' in src


@pytest.mark.parametrize("token", [
    "promoter", "shadow_forward", "sleeve", "decision_core", "sizing", "adopt", "seal",
    "sign_train", "release", "selfheal", "workflow_gate", "root_pin", "gateway", "tape"])
def test_each_protected_token_keeps_a_process_out(token: str) -> None:
    p = proc(1, 60_000, f"python -m desks.mt5.research.x_{token}_y")
    assert not mg.is_candidate(p, set())


def test_a_child_of_the_money_path_or_a_terminal_is_protected_by_ancestry() -> None:
    gw = {"name": "python.exe", "cmdline": ["python", r"desks\mt5\mt5desk\gateway.py"]}
    adopt = {"name": "powershell.exe", "cmdline": ["powershell", "-File", "Adopt-And-Seal.ps1"]}
    term = {"name": "terminal64.exe", "cmdline": ["terminal64.exe"]}
    for anc in (gw, adopt, term):
        assert not mg.is_candidate(proc(2, 60_000, "python -m helper", ancestors=[anc]), set())
    assert not mg.is_candidate(proc(3, 60_000, "python -m helper", ancestors=None) | {
        "ancestors": None}, set())
    assert mg.is_candidate(proc(4, 60_000, "python -m helper"), set())


def test_headroom_needs_twice_the_floor() -> None:
    th = mg.thresholds(BOX)
    assert mg.headroom(BOX, th)
    assert not mg.headroom({**BOX, "free_phys_mb": 20_000}, th)


def test_dry_pass_writes_a_report_and_changes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REPORT", tmp_path / "MEMORY_GUARD.json")
    monkeypatch.setattr(mg, "QUEUE", tmp_path / "q.json")
    monkeypatch.setattr(mg, "SEEN", tmp_path / "seen.json")
    stopped: list[int] = []
    monkeypatch.setattr(mg, "stop", lambda pid: stopped.append(pid) or {"result": "STOPPED"})
    monkeypatch.setattr(mg, "_processes", lambda: [proc(13224, 10**7, SCALING)])
    monkeypatch.setattr(mg, "_own_pids", lambda: set())
    monkeypatch.setattr(mg, "_tasks", lambda: (TASKS, "OK"))
    doc = mg.run_pass(apply=False)
    assert doc["verdict"] == "HARD_CAP" and doc["actions"] == [] and stopped == []
    assert not (tmp_path / "q.json").exists()
    assert json.loads((tmp_path / "MEMORY_GUARD.json").read_text("utf-8"))["verdict"] == "HARD_CAP"


def test_applied_pass_stops_and_queues(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REPORT", tmp_path / "MEMORY_GUARD.json")
    monkeypatch.setattr(mg, "QUEUE", tmp_path / "q.json")
    monkeypatch.setattr(mg, "SEEN", tmp_path / "seen.json")
    monkeypatch.setattr(mg, "stop", lambda pid: {"pid": pid, "result": "STOPPED"})
    big = {**proc(13224, 10**7, SCALING), "cpu_s": 5.0, "started": 1.0}
    monkeypatch.setattr(mg, "_processes", lambda: [big])
    monkeypatch.setattr(mg, "_own_pids", lambda: set())
    monkeypatch.setattr(mg, "_tasks", lambda: (TASKS, "OK"))
    doc = mg.run_pass(apply=True)
    assert doc["actions"][0]["action"] == "STOP"
    assert doc["actions"][0]["task"] == "\\MT5-FrontierAudit"
    assert "13224" in json.loads((tmp_path / "seen.json").read_text("utf-8"))
    assert mg.load_queue(tmp_path / "q.json")[0]["state"] == "QUEUED"


def test_requeue_pass_runs_the_task_not_the_command(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REPORT", tmp_path / "MEMORY_GUARD.json")
    monkeypatch.setattr(mg, "QUEUE", tmp_path / "q.json")
    monkeypatch.setattr(mg, "SEEN", tmp_path / "seen.json")
    at = "2026-11-11T14:20:00+00:00"
    mg.save_queue(mg.enqueue([], proc(1, 30_000, SCALING), "HARD_CAP", "leak", at,
                             "\\MT5-FrontierAudit"), tmp_path / "q.json")
    ran: list[str] = []
    monkeypatch.setattr(mg, "rerun_task", lambda t: ran.append(t) or {"task": t, "rc": 0,
                                                                       "out": "SUCCESS"})
    monkeypatch.setattr(mg, "_processes", lambda: [])
    monkeypatch.setattr(mg, "_own_pids", lambda: set())
    monkeypatch.setattr(mg, "_tasks", lambda: (TASKS, "OK"))
    doc = mg.run_pass(apply=True)
    assert ran == ["\\MT5-FrontierAudit"] and doc["actions"][0]["action"] == "REQUEUE"
    assert mg.load_queue(tmp_path / "q.json")[0]["state"] == "RUNNING"


def test_a_day_old_job_burning_no_cpu_is_stalled_and_a_working_one_is_not() -> None:
    now = 1_800_000_000.0
    started = now - 43 * 3600
    stuck = {**proc(36280, 15_000, "python -m merge_hypotheses"), "started": started,
             "cpu_s": 59.78}
    busy = {**proc(2, 3_000, "python -m judge"), "started": started, "cpu_s": 900.0}
    prev = {"36280": {"started": started, "cpu_s": 59.78, "at_ts": now - 120},
            "2": {"started": started, "cpu_s": 800.0, "at_ts": now - 120}}
    d = mg.plan(BOX, [busy, stuck], set(), prev=prev, now_ts=now)
    assert d["rule"] == "STALLED" and d["stop"]["pid"] == 36280


def test_stall_needs_age_the_same_instance_and_a_real_gap() -> None:
    now = 1_800_000_000.0
    young = {**proc(1, 3_000, "python -m a"), "started": now - 3600, "cpu_s": 1.0}
    reused = {**proc(2, 3_000, "python -m b"), "started": now - 30 * 3600, "cpu_s": 1.0}
    close = {**proc(3, 3_000, "python -m c"), "started": now - 30 * 3600, "cpu_s": 1.0}
    prev = {"1": {"started": now - 3600, "cpu_s": 1.0, "at_ts": now - 120},
            "2": {"started": now - 99 * 3600, "cpu_s": 1.0, "at_ts": now - 120},
            "3": {"started": now - 30 * 3600, "cpu_s": 1.0, "at_ts": now - 10}}
    d = mg.plan(BOX, [young, reused, close], set(), prev=prev, now_ts=now)
    assert d["rule"] == "CLEAR"


def test_money_path_is_never_stalled_out() -> None:
    now = 1_800_000_000.0
    gw = {**proc(9, 3_000, r"python desks\mt5\mt5desk\gateway.py"), "started": now - 99 * 3600,
          "cpu_s": 1.0}
    prev = {"9": {"started": now - 99 * 3600, "cpu_s": 1.0, "at_ts": now - 120}}
    assert mg.plan(BOX, [gw], set(), prev=prev, now_ts=now)["stop"] is None
