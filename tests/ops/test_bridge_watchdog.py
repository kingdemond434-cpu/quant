"""The box bridge's watchdog (ops/bridge/): source-level pins for the properties that keep the
bridge alive without zuck and keep it from doing anything the hand-started bridge did not."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "ops" / "bridge"
WATCHDOG = (BRIDGE / "bridge_watchdog.ps1").read_text(encoding="utf-8")
INSTALL = (BRIDGE / "install_bridge_watchdog.ps1").read_text(encoding="utf-8")
STATUS = (BRIDGE / "bridge_status.ps1").read_text(encoding="utf-8")


def _code(src: str) -> str:
    """The script without its comments and help block: what it DOES, not what it says."""
    src = re.sub(r"<#.*?#>", "", src, flags=re.S)
    return "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))


SCRIPTS = {"watchdog": _code(WATCHDOG), "installer": _code(INSTALL), "status": _code(STATUS)}

#: What none of the three may do. Each pattern is a way to widen the sessions' permissions, store
#: or set a secret, change machine state outside the bridge's own folders, or kill a process.
BANNED = {
    "permission flag": (
        r"--permission-mode|--allowedTools|--allowed-tools|--dangerously|bypassPermissions"
    ),
    "settings override": r"--settings|settings\.json|managed-settings",
    "environment write": r"\$env:\w+\s*=|SetEnvironmentVariable|Set-Item\s+-Path\s+env:|setx",
    "registry write": r"Set-ItemProperty|New-ItemProperty|reg(\.exe)?\s+add|HKLM:|HKCU:",
    "auto-logon": r"Winlogon|AutoAdminLogon|Autologon|DefaultPassword",
    "stored password": r"-Password\b|ConvertTo-SecureString|-LogonType\s+(Password|S4U)",
    "process kill": r"Stop-Process|taskkill|\.Kill\(",
    "sign-in": r"auth\s+login|setup-token|ANTHROPIC_API_KEY|credentials",
    "live tree": r"C:\\opt\\quant(?!\w)",
}


@pytest.mark.parametrize("script", sorted(SCRIPTS))
@pytest.mark.parametrize("what", sorted(BANNED))
def test_no_script_does_what_the_bridge_must_not(script: str, what: str) -> None:
    m = re.search(BANNED[what], SCRIPTS[script], flags=re.I)
    assert m is None, f"{script}: {what}: {m.group(0) if m else ''}"


def test_the_banned_patterns_catch_what_they_name() -> None:
    probes = {
        "permission flag": '"--permission-mode", "acceptEdits"',
        "settings override": "Set-Content $HOME\\.claude\\settings.json",
        "environment write": "$env:CLAUDE_X = 1",
        "registry write": "Set-ItemProperty -Path HKLM:\\SOFTWARE\\X",
        "auto-logon": "Winlogon",
        "stored password": "New-ScheduledTaskPrincipal -LogonType Password",
        "process kill": "Stop-Process -Id 1",
        "sign-in": "claude auth login",
        "live tree": "cd C:\\opt\\quant",
    }
    for what, probe in probes.items():
        assert re.search(BANNED[what], probe, flags=re.I), what


def test_one_watchdog_per_user() -> None:
    assert 'Mutex($false, "Local\\Claude-Bridge-Watchdog")' in WATCHDOG
    assert "WaitOne(0)" in WATCHDOG and "if (-not $owned) { exit 0 }" in WATCHDOG


def test_it_refuses_bytes_the_installer_did_not_pin() -> None:
    code = SCRIPTS["watchdog"]
    assert code.index("watchdog.sha256") < code.index("Start-Process -FilePath $claude")
    assert 'state = "TAMPERED"' in code


def test_adoption_is_narrow_and_cannot_hang_the_bridge() -> None:
    code = SCRIPTS["watchdog"]
    assert "Start-Job" in code and "Wait-Job -Job $job -Timeout 20" in code
    cim = code[code.index("function Find-NamedServer") : code.index("function Wait-Server")]
    assert "--name" in cim and "GetOwner" in cim
    assert code.count("Get-CimInstance") == 1  # only inside the timed job


def test_it_restarts_on_exit_with_backoff_and_a_live_heartbeat() -> None:
    code = SCRIPTS["watchdog"]
    assert "while ($true)" in code and "WaitForExit(60000)" in code
    assert "$null = $p.Handle" in code and "$null = $proc.Handle" in code
    assert "[Math]::Min(" in code and "900" in code
    assert "Start-Sleep -Seconds 1800" in code  # sign-in failures back off, never spin


def test_sign_in_is_judged_from_this_run_only() -> None:
    code = SCRIPTS["watchdog"]
    assert 'rc_debug_{0}.log" -f (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")' in code
    assert "auth status" in code


def test_rc_args_are_the_bridge_and_nothing_more() -> None:
    m = re.search(r"\$rcArgs = @\((.*?)\)", WATCHDOG, re.S)
    assert m is not None
    args = re.findall(r'"([^"]+)"|\$(\w+)', m.group(1))
    flat = [a or f"${b}" for a, b in args]
    assert flat == [
        "remote-control",
        "--spawn",
        "worktree",
        "--no-create-session-in-dir",
        "--name",
        "$Name",
        "--debug-file",
        "$debug",
    ]


def test_installer_locks_the_folder_it_runs_from_and_pins_the_copy() -> None:
    code = SCRIPTS["installer"]
    assert "/inheritance:r" in code and "S-1-5-32-544" in code and "S-1-5-18" in code
    assert code.index("icacls") < code.index("Copy-Item -Path $src -Destination $dst")
    assert "watchdog.sha256" in code
    assert '$RunLevel = "Highest"' in code


def test_installer_rearms_and_registers_one_interactive_task() -> None:
    code = SCRIPTS["installer"]
    assert "-AtLogOn" in code and "-RepetitionInterval (New-TimeSpan -Minutes 5)" in code
    assert "-MultipleInstances IgnoreNew" in code
    assert "-ExecutionTimeLimit (New-TimeSpan -Seconds 0)" in code
    assert code.count("Register-ScheduledTask ") == 1
    assert "-LogonType Interactive" in code


def test_the_heartbeat_has_a_reader_and_the_task_is_in_the_manifest() -> None:
    assert "bridge_watchdog.json" in STATUS and "exit 0" in STATUS
    for verdict in ("LIVE", "STALE", "TAMPERED", "ABSENT", "QUIET", "DEAD_SERVER"):
        assert f'"{verdict}:' in STATUS, verdict
    manifest = (ROOT / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    assert 'name="Claude-Bridge-Watchdog"' in manifest
    assert 'installer="ops/bridge/install_bridge_watchdog.ps1"' in manifest
