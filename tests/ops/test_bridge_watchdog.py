"""The box bridge's watchdog (ops/bridge/): source-level pins for the properties that keep the
bridge alive without zuck and keep it from doing anything the hand-started bridge did not."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHDOG = (ROOT / "ops/bridge/bridge_watchdog.ps1").read_text(encoding="utf-8")
INSTALL = (ROOT / "ops/bridge/install_bridge_watchdog.ps1").read_text(encoding="utf-8")


def test_one_watchdog_per_user() -> None:
    assert 'Mutex($false, "Local\\Claude-Bridge-Watchdog")' in WATCHDOG
    assert "WaitOne(0)" in WATCHDOG and "if (-not $owned) { exit 0 }" in WATCHDOG


def test_a_running_server_is_adopted_not_doubled() -> None:
    assert WATCHDOG.index("Get-RunningServer\n") < WATCHDOG.index("Start-Process -FilePath $claude")
    assert "Wait-Process -Id $p.ProcessId" in WATCHDOG


def test_it_restarts_on_exit_with_backoff() -> None:
    assert "while ($true)" in WATCHDOG and "$proc.WaitForExit()" in WATCHDOG
    assert "[Math]::Min(" in WATCHDOG and "900" in WATCHDOG
    assert "Start-Sleep -Seconds 1800" in WATCHDOG  # sign-in failures back off, never spin


def test_it_adds_no_flag_that_widens_what_sessions_may_do() -> None:
    args = re.search(r"\$rcArgs = @\((.*?)\)", WATCHDOG, re.S).group(1)
    for banned in ("--permission-mode", "--dangerously", "--settings", "bypass"):
        assert banned not in args, banned
    assert '"remote-control"' in args and '"worktree"' in args


def test_it_never_touches_the_live_tree_or_credentials() -> None:
    body = WATCHDOG.split("#>", 1)[1]
    assert "C:\\opt\\quant" not in body
    for banned in ("auth login", "setup-token", "credentials", "ANTHROPIC_API_KEY"):
        assert banned not in body, banned


def test_installer_runs_a_copy_outside_the_checkout_and_rearms() -> None:
    assert "Copy-Item -Path $src -Destination $dst" in INSTALL
    assert '$BinDir = "C:\\opt\\bridge\\bin"' in INSTALL
    assert "-AtLogOn" in INSTALL and "-RepetitionInterval (New-TimeSpan -Minutes 5)" in INSTALL
    assert "-MultipleInstances IgnoreNew" in INSTALL
    assert "-ExecutionTimeLimit (New-TimeSpan -Seconds 0)" in INSTALL


def test_installer_registers_one_task_and_stores_no_password() -> None:
    assert INSTALL.count("Register-ScheduledTask ") == 1
    assert "-Password" not in INSTALL and "AutoAdminLogon" not in INSTALL
    assert "-LogonType Interactive" in INSTALL
