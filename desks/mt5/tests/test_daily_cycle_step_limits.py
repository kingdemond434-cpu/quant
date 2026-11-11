"""A stalled step may not hold the daily chain: promoter, markout and recertify still run.

The hourly leg kills the chain at its 900 s budget; a step that stalls is never stamped, so it
was restarted every hour and nothing behind it ever ran. A per-step wall limit and a stall count
end that without ever re-running a step that finished.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)


import daily_cycle  # noqa: E402


@pytest.fixture
def cyc(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    calls: list[str] = []

    def step(name):
        def fn():
            calls.append(name)
        return fn
    return type("C", (), {"calls": calls, "step": staticmethod(step), "tmp": tmp_path})


def _stamp(cyc) -> dict:
    return json.loads((cyc.tmp / "daily_cycle_state.json").read_text())["steps"]


def test_a_step_killed_twice_today_is_skipped_by_name_and_the_rest_run(cyc, monkeypatch):
    steps = tuple((n, cyc.step(n)) for n in ("stuck", "recertify", "promoter", "markout"))
    monkeypatch.setattr(daily_cycle, "STEPS", steps)
    today = daily_cycle._utc_today()
    # two earlier passes started `stuck` and were killed around it (no end mark)
    daily_cycle._inflight_start(today, "stuck")
    daily_cycle._inflight_start(today, "stuck")
    assert daily_cycle._run_chain(False) == 1
    assert cyc.calls == ["recertify", "promoter", "markout"]
    rec = _stamp(cyc)
    assert rec["stuck"]["stalled"] is True and "STALLED" in rec["stuck"]["error"]
    assert all(rec[n]["ok"] for n in ("recertify", "promoter", "markout"))


def test_one_interrupted_attempt_is_retried_not_skipped(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS", (("slow", cyc.step("slow")),))
    today = daily_cycle._utc_today()
    daily_cycle._inflight_start(today, "slow")
    assert daily_cycle._run_chain(False) == 0
    assert cyc.calls == ["slow"] and daily_cycle.stall_attempts(today, "slow") == 0


def test_a_finished_step_clears_its_mark_and_is_never_rerun(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS", (("a", cyc.step("a")),))
    daily_cycle._run_chain(False)
    daily_cycle._run_chain(False)
    assert cyc.calls == ["a"]
    assert daily_cycle._inflight(daily_cycle._utc_today()) == {}


def test_force_clears_the_stall_count(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS", (("stuck", cyc.step("stuck")),))
    today = daily_cycle._utc_today()
    for _ in range(daily_cycle.STALL_ATTEMPTS):
        daily_cycle._inflight_start(today, "stuck")
    assert daily_cycle._run_chain(True) == 0 and cyc.calls == ["stuck"]


def test_yesterdays_marks_do_not_count_today(cyc):
    daily_cycle._inflight_write("2000-01-01", {"x": {"attempts": 9}})
    assert daily_cycle.stall_attempts(daily_cycle._utc_today(), "x") == 0


def test_a_shipped_step_runs_in_a_child_under_its_limit(cyc, monkeypatch):
    seen = {}

    def fake_run(argv, *, timeout, cwd, check):
        seen.update(argv=argv, timeout=timeout)
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr("libs.ops.proctree.run", fake_run)
    name, fn = daily_cycle.STEPS[0]
    out = daily_cycle.run_chain_step(daily_cycle._utc_today(), name, fn)
    assert out["ok"] and seen["argv"][-2:] == ["--step", name]
    assert seen["timeout"] == daily_cycle.step_timeout_s(name)


def test_a_step_past_its_limit_is_recorded_as_timeout(cyc, monkeypatch):
    def fake_run(argv, *, timeout, cwd, check):
        raise subprocess.TimeoutExpired(argv, timeout)
    monkeypatch.setattr("libs.ops.proctree.run", fake_run)
    name, fn = daily_cycle.STEPS[0]
    today = daily_cycle._utc_today()
    out = daily_cycle.run_chain_step(today, name, fn)
    assert not out["ok"] and out["timed_out"] and "TIMEOUT" in out["error"]
    assert daily_cycle.stall_attempts(today, name) == 0


def test_the_default_limit_stops_a_hang_never_a_measured_slow_step():
    assert daily_cycle.DEFAULT_STEP_TIMEOUT_S > 9056
    assert daily_cycle.STALL_ATTEMPTS >= 2
