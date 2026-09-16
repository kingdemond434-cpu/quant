"""The department resident: singleton, one pass under the department plan, the cycle floor."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import department_resident as dr  # noqa: E402


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


def test_one_pass_runs_the_cycle_under_the_department_plan(monkeypatch, tmp_path):
    fake = tmp_path / "cycle.py"
    fake.write_text("import os, sys\nprint(os.environ.get('HOURLY_PLAN'))\n"
                    "sys.exit(0 if os.environ.get('HOURLY_PLAN') == 'dept:intel' else 3)\n",
                    encoding="utf-8")
    monkeypatch.setattr(dr, "CYCLE", fake)
    monkeypatch.setattr(dr, "DESK", tmp_path)
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
