"""The research bandit runs in its own process under a wall budget, so one slow run cannot hold
the daily chain hostage (11-10/11: 6 h 20 min inside it, then MT5-Daily's PT10H kill took the
33 steps behind it with it)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402


def _isolate(tmp_path, monkeypatch, script: str) -> Path:
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    child = tmp_path / "fake_bandit.py"
    child.write_text(script, encoding="utf-8")
    monkeypatch.setattr(daily_cycle, "_research_bandit_cmd",
                        lambda: [sys.executable, "-u", str(child)])
    return tmp_path / "daily_cycle.log"


def test_a_bandit_past_its_budget_is_ended_and_the_step_returns(tmp_path, monkeypatch) -> None:
    pid_file = tmp_path / "grandchild.pid"
    log = _isolate(tmp_path, monkeypatch, (
        "import subprocess, sys, time\n"
        "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"open(r'{pid_file}', 'w').write(str(g.pid))\n"
        "time.sleep(120)\n"))
    monkeypatch.setenv("RESEARCH_BANDIT_BUDGET_S", "60")
    monkeypatch.setattr(daily_cycle, "_research_bandit_budget_s", lambda: 3.0)
    t0 = time.monotonic()
    daily_cycle._research_bandit()          # must not raise
    assert time.monotonic() - t0 < 60
    text = log.read_text(encoding="utf-8")
    assert "research_bandit TIMEOUT" in text and "chain continues" in text
    # the pool it opened went with it
    import psutil
    gpid = int(pid_file.read_text())
    time.sleep(0.5)
    assert not psutil.pid_exists(gpid) or psutil.Process(gpid).status() == psutil.STATUS_ZOMBIE


def test_a_bandit_inside_its_budget_logs_its_shares(tmp_path, monkeypatch) -> None:
    log = _isolate(tmp_path, monkeypatch, (
        "print('RESEARCH BANDIT  10 graph rows')\n"
        "print('  cross_asset_signal       share=16.0%  born=1')\n"
        "print('  failure_derived          share=11.0%  born=1')\n"
        "print('written: x')\n"))
    daily_cycle._research_bandit()
    text = log.read_text(encoding="utf-8")
    assert "research bandit:" in text and "cross_asset_signal share=16.0%" in text
    assert "TIMEOUT" not in text and "FAILED" not in text


def test_a_bandit_that_fails_is_logged_not_raised(tmp_path, monkeypatch) -> None:
    log = _isolate(tmp_path, monkeypatch, "import sys\nprint('boom')\nsys.exit(3)\n")
    daily_cycle._research_bandit()
    text = log.read_text(encoding="utf-8")
    assert "research_bandit FAILED (non-fatal): rc=3" in text and "boom" in text


def test_the_budget_reads_the_env_and_floors_at_a_minute(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_BANDIT_BUDGET_S", "5")
    assert daily_cycle._research_bandit_budget_s() == 60.0
    monkeypatch.setenv("RESEARCH_BANDIT_BUDGET_S", "7200")
    assert daily_cycle._research_bandit_budget_s() == 7200.0
    monkeypatch.setenv("RESEARCH_BANDIT_BUDGET_S", "junk")
    assert daily_cycle._research_bandit_budget_s() == daily_cycle.RESEARCH_BANDIT_BUDGET_S_DEFAULT
    monkeypatch.delenv("RESEARCH_BANDIT_BUDGET_S")
    assert daily_cycle._research_bandit_budget_s() == 3 * 3600.0
