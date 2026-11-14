"""The research bandit runs under a wall-clock cap inside the daily chain (2026-11-14).

On 11-13 the bandit's whole-graph read ran ~6.5 h until the scheduler killed MT5-Daily, so every
step behind it did not run. A capped child process is killed at the cap and the chain goes on.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


@pytest.fixture
def logged(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    lines: list[str] = []
    monkeypatch.setattr(daily_cycle, "dlog", lines.append)
    return lines


def test_a_bandit_past_its_cap_is_killed_and_the_step_fails(
        monkeypatch: pytest.MonkeyPatch, logged: list[str]) -> None:
    seen: dict[str, object] = {}

    def slow(cmd, **kw):
        seen.update(kw)
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(RuntimeError, match="wall-clock cap"):
        daily_cycle._research_bandit()
    assert seen["timeout"] == daily_cycle.BANDIT_WALL_S


def test_the_chain_goes_on_after_a_capped_bandit(
        monkeypatch: pytest.MonkeyPatch, logged: list[str]) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (_ for _ in ()).throw(
        subprocess.TimeoutExpired(cmd, kw["timeout"])))
    monkeypatch.setattr(daily_cycle, "_woe_before", lambda name: {})
    monkeypatch.setattr(daily_cycle, "_woe_after", lambda *a, **k: None)
    out = daily_cycle.run_step("research_bandit", daily_cycle._research_bandit)
    assert out["ok"] is False and "wall-clock cap" in out["error"]


def test_the_cap_never_cuts_a_run_the_desk_measured_finishing() -> None:
    assert daily_cycle.BANDIT_WALL_S >= 1.5 * 3600      # 11-12 took 1.5 h


def test_a_finished_bandit_logs_its_top_three_shares(
        monkeypatch: pytest.MonkeyPatch, logged: list[str]) -> None:
    out = ("RESEARCH BANDIT  10 graph rows, pooled certify rate 0.1\n"
           "  alpha                    share=50.0%  born=1\n"
           "  beta                     share=30.0%  born=1\n"
           "  gamma                    share=15.0%  born=1\n"
           "  delta                    share= 5.0%  born=1\n")
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=out, stderr=""))
    daily_cycle._research_bandit()
    assert logged == ["research bandit: alpha=50.0%, beta=30.0%, gamma=15.0%"]


def test_a_failed_bandit_stays_non_fatal(
        monkeypatch: pytest.MonkeyPatch, logged: list[str]) -> None:
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: SimpleNamespace(
        returncode=1, stdout="", stderr="Traceback\nValueError: bad"))
    daily_cycle._research_bandit()
    assert logged and "rc 1" in logged[0] and "ValueError: bad" in logged[0]
