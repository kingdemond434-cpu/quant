"""The fifteen-minute clock fixer: residents verified by observation, dead ones restarted through
their keep-alive task, every healer time-boxed, the report written only when applying."""
from __future__ import annotations

import os
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import clock_fixer as cf  # noqa: E402


def test_residents_are_judged_by_lock_holder_and_log_age(monkeypatch, tmp_path: Path):
    locks = tmp_path / "locks"
    logs = tmp_path / "logs"
    locks.mkdir()
    logs.mkdir()
    monkeypatch.setattr(cf, "LOCKS", locks)
    monkeypatch.setattr(cf, "LOGS", logs)
    monkeypatch.setattr(cf, "RESIDENTS", {
        "dept_alive": ("MT5-Alive", "alive.log", 3600),
        "dept_dead": ("MT5-Dead", "dead.log", 3600),
        "dept_silent": ("MT5-Silent", "silent.log", 1),
    })
    (locks / "dept_alive.lock").write_text(f"{os.getpid()} now\n")
    (logs / "alive.log").write_text("x")
    (locks / "dept_dead.lock").write_text("999999999 old\n")
    (locks / "dept_silent.lock").write_text(f"{os.getpid()} now\n")
    (logs / "silent.log").write_text("x")
    os.utime(logs / "silent.log", (1, 1))
    monkeypatch.setattr(cf, "_task_exists", lambda task: task != "MT5-Dead")
    started: list[str] = []
    monkeypatch.setattr(cf, "_run_task", lambda task: started.append(task) or "started")
    rows = {r["resident"]: r for r in cf.check_residents(apply=True)}
    assert rows["dept_alive"]["state"] == "ALIVE" and "action" not in rows["dept_alive"]
    assert rows["dept_dead"]["state"] == "DEAD" and rows["dept_dead"]["action"] == "task_missing"
    assert rows["dept_silent"]["state"] == "SILENT" and rows["dept_silent"]["action"] == "started"
    assert started == ["MT5-Silent"]
    dry = {r["resident"]: r for r in cf.check_residents(apply=False)}
    assert dry["dept_silent"]["action"] == "would_start"


def test_dry_run_repairs_nothing_and_writes_nothing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cf, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(cf, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(cf, "REPORT", tmp_path / "CLOCK_FIXER.json")
    monkeypatch.setattr(cf, "LEDGER", tmp_path / "clock_fixer.jsonl")
    monkeypatch.setattr(cf, "RESIDENTS", {})
    monkeypatch.setattr(cf, "_task_exists", lambda task: False)
    assert cf.main(["--dry-run"]) == 0
    assert not (tmp_path / "CLOCK_FIXER.json").exists()
    assert cf.run_step("x", ["nowhere.py"], 5, apply=False)["status"] == "dry_run"


def test_a_missing_healer_is_named_not_crashed(tmp_path: Path):
    res = cf.run_step("gone", [str(tmp_path / "absent.py")], 5, apply=True)
    assert res["status"] == "MISSING"


def test_budget_exhaustion_skips_steps_by_name(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(cf, "LOCKS", tmp_path / "locks")
    monkeypatch.setattr(cf, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(cf, "REPORT", tmp_path / "CLOCK_FIXER.json")
    monkeypatch.setattr(cf, "LEDGER", tmp_path / "clock_fixer.jsonl")
    monkeypatch.setattr(cf, "RESIDENTS", {})
    monkeypatch.setattr(cf, "STEPS", (("one", [str(tmp_path / "absent.py")], 5),))
    monkeypatch.setattr(cf, "certificates_without_clocks", lambda: {"n": 0})
    assert cf.main(["--budget-s", "1"]) == 0
    doc = __import__("json").loads((tmp_path / "CLOCK_FIXER.json").read_text())
    assert doc["steps"][0]["status"] == "skipped" and doc["steps"][-1]["status"] == "skipped"
    assert (tmp_path / "clock_fixer.jsonl").exists()

def test_an_unreadable_lock_is_a_HELD_lock_not_a_dead_resident(monkeypatch, tmp_path):
    """MEASURED 2026-09-17: twenty-two healthy residents were reported DEAD and restarted every
    fifteen minutes because their lock files could not be READ -- and they could not be read
    precisely because each resident holds a Windows byte-range lock on byte 0 for the life of the
    process. "I cannot read it" and "nobody holds it" are opposite facts."""
    locks = tmp_path / "locks"
    logs = tmp_path / "logs"
    locks.mkdir()
    logs.mkdir()
    monkeypatch.setattr(cf, "LOCKS", locks)
    monkeypatch.setattr(cf, "LOGS", logs)
    monkeypatch.setattr(cf, "RESIDENTS", {"dept_held": ("MT5-Held", "held.log", 3600)})
    (locks / "dept_held.lock").write_text("123 now")
    (logs / "held.log").write_text("x")
    real_read = Path.read_text

    def refuse(self, *a, **k):
        if self.name == "dept_held.lock":
            raise PermissionError(13, "the resident holds this byte")
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", refuse)
    started: list[str] = []
    monkeypatch.setattr(cf, "_task_exists", lambda task: True)
    monkeypatch.setattr(cf, "_run_task", lambda task: started.append(task) or "started")
    rows = {r["resident"]: r for r in cf.check_residents(apply=True)}
    assert rows["dept_held"]["state"] == "ALIVE" and rows["dept_held"]["lock"] == cf.LOCK_HELD
    assert started == [], "a live resident must never be restarted"


def test_a_lock_with_no_pid_and_no_process_is_dead(monkeypatch, tmp_path):
    locks = tmp_path / "locks"
    locks.mkdir()
    (tmp_path / "logs").mkdir()
    monkeypatch.setattr(cf, "LOCKS", locks)
    monkeypatch.setattr(cf, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(cf, "RESIDENTS", {"dept_stale": ("MT5-Stale", "s.log", 3600)})
    (locks / "dept_stale.lock").write_text("")
    monkeypatch.setattr(cf, "_task_exists", lambda task: True)
    monkeypatch.setattr(cf, "_run_task", lambda task: "started")
    rows = {r["resident"]: r for r in cf.check_residents(apply=True)}
    assert rows["dept_stale"]["state"] == "DEAD" and rows["dept_stale"]["lock"] == cf.LOCK_STALE
