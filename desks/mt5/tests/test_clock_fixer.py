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
