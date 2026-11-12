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


def _age(today: str, name: str, seconds: float) -> None:
    """Credit a step with `seconds` of RUN time across its interrupted attempts."""
    steps = daily_cycle._inflight(today)
    steps[name]["ran_s"] = float(seconds)
    daily_cycle._inflight_write(today, steps)


def _back(today: str, name: str, seconds: float) -> None:
    """Back-date the last start, as if that attempt began `seconds` ago."""
    from datetime import UTC, datetime, timedelta
    steps = daily_cycle._inflight(today)
    steps[name]["last_start"] = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()
    daily_cycle._inflight_write(today, steps)


def test_four_hourly_kills_of_a_two_hour_step_credit_run_time_not_wall_time(cyc, monkeypatch):
    """Started at 00:00, 01:00, 02:00, 03:00, killed at 900 s each time: ~45 min run, not 3 h."""
    monkeypatch.delenv("DAILY_CYCLE_HOURLY_BUDGET_SEC", raising=False)
    today = daily_cycle._utc_today()
    for _ in range(4):
        daily_cycle._inflight_start(today, "research")
        _back(today, "research", 3600)
    daily_cycle._inflight_start(today, "research")
    assert daily_cycle.in_flight_s(today, "research") == 4 * 900
    assert not daily_cycle.is_stalled(today, "research")


def test_a_step_killed_twice_today_is_skipped_by_name_and_the_rest_run(cyc, monkeypatch):
    steps = tuple((n, cyc.step(n)) for n in ("stuck", "recertify", "promoter", "markout"))
    monkeypatch.setattr(daily_cycle, "STEPS", steps)
    today = daily_cycle._utc_today()
    # two earlier passes started `stuck` and were killed around it (no end mark), and it has
    # been in flight longer than its own limit
    daily_cycle._inflight_start(today, "stuck")
    daily_cycle._inflight_start(today, "stuck")
    _age(today, "stuck", daily_cycle.step_timeout_s("stuck") + 1)
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


def test_a_healthy_slow_step_killed_by_the_hourly_caller_is_never_stalled(cyc, monkeypatch):
    """Killed at 900 s on two hourly passes: the caller's budget, not the step's. It runs again."""
    monkeypatch.setattr(daily_cycle, "STEPS", (("research", cyc.step("research")),))
    today = daily_cycle._utc_today()
    for _ in range(daily_cycle.STALL_ATTEMPTS + 1):
        daily_cycle._inflight_start(today, "research")
    _age(today, "research", 3 * 900)               # three hourly kills: 45 min run
    assert not daily_cycle.is_stalled(today, "research")
    assert daily_cycle._run_chain(False) == 0 and cyc.calls == ["research"]


def test_a_step_in_flight_past_its_limit_but_started_once_is_retried(cyc):
    today = daily_cycle._utc_today()
    daily_cycle._inflight_start(today, "x")
    _age(today, "x", daily_cycle.step_timeout_s("x") + 1)
    assert not daily_cycle.is_stalled(today, "x")


def test_force_clears_the_stall_count(cyc, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STEPS", (("stuck", cyc.step("stuck")),))
    today = daily_cycle._utc_today()
    for _ in range(daily_cycle.STALL_ATTEMPTS):
        daily_cycle._inflight_start(today, "stuck")
    _age(today, "stuck", daily_cycle.step_timeout_s("stuck") + 1)
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
