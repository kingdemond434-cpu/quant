"""A step that hangs is stopped at its wall budget and the chain goes on (box 2026-11-22..24).

research_bandit ran 9 h on 11-23 and futures_curves 5 h 20 min on 11-22; the 10 h task limit
killed the one-process chain both nights and 37 of 39 steps never ran.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


def test_the_steps_that_hung_carry_a_budget_and_exist() -> None:
    names = {n for n, _ in daily_cycle.STEPS}
    assert set(daily_cycle.STEP_WALL_S) <= names
    assert {"research_bandit", "futures_curves"} <= set(daily_cycle.STEP_WALL_S)


def test_a_timed_out_step_is_failed_and_the_chain_goes_on(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "s.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "l.log")
    ran: list[str] = []

    def fn(name):
        return lambda: ran.append(name)
    monkeypatch.setattr(daily_cycle, "STEPS", (("slow", fn("slow")), ("after", fn("after"))))
    monkeypatch.setattr(daily_cycle, "STEP_WALL_S", {"slow": 5.0})
    seen: dict = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["timeout"] = cmd, kw.get("timeout")
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert daily_cycle.main([]) == 1
    assert ran == ["after"]
    assert seen["cmd"][-2:] == ["--step", "slow"] and seen["timeout"] == 5.0
    import json
    st = json.loads((tmp_path / "s.json").read_text("utf-8"))
    assert st["steps"]["slow"]["ok"] is False and "TIMEOUT" in st["steps"]["slow"]["error"]
    assert st["steps"]["after"]["ok"] is True


def test_a_child_that_fails_is_a_failed_step(monkeypatch) -> None:
    monkeypatch.setattr(daily_cycle, "LOG", Path("/dev/null"))
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 1, stdout="", stderr="boom\nRuntimeError: x"))
    out = daily_cycle.run_step_isolated("research_bandit", 10.0)
    assert out["ok"] is False and "RuntimeError: x" in out["error"] and out["isolated"]
