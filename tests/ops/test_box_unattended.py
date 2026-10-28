"""The box's unattended pieces (ops/box/): source-level pins for what keeps a reboot and a
workflow-file PR from needing zuck, and for what they must never do."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BOX = ROOT / "ops" / "box"
RAW = {
    name: (BOX / f"{name}.ps1").read_text(encoding="utf-8")
    for name in ("unattended_boot", "workflow_gate", "install_unattended")
}


def _code(src: str) -> str:
    """The script without its comments: what it DOES, not what it says."""
    src = re.sub(r"<#.*?#>", "", src, flags=re.S)
    return "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("#"))


CODE = {k: _code(v) for k, v in RAW.items()}

#: What none of them may do.
BANNED = {
    "registry write": (
        r"Set-ItemProperty|New-ItemProperty|Remove-ItemProperty|reg(\.exe)?\s+(add|delete)"
    ),
    "password handling": r"ConvertTo-SecureString|-Password\b|GetValue\('DefaultPassword'\)",
    "session-0 task": r"-LogonType\s+(Password|S4U|ServiceAccount)|NT AUTHORITY\\SYSTEM",
    "process kill": r"Stop-Process|taskkill|\.Kill\(",
    "token in the open": r"auth\s+token|--with-token|\$env:GH_TOKEN\s*=|\$env:GITHUB_TOKEN\s*=",
    "permission bypass": r"--no-verify|--dangerously|bypassPermissions",
}


@pytest.mark.parametrize("name", sorted(CODE))
@pytest.mark.parametrize("what", sorted(BANNED))
def test_none_of_them_does_what_is_banned(name: str, what: str) -> None:
    assert not re.search(BANNED[what], CODE[name], flags=re.I), (name, what)


def test_the_tasks_run_interactive_as_this_user_from_admin_only_copies() -> None:
    inst = CODE["install_unattended"]
    assert "-LogonType Interactive -RunLevel Highest" in inst
    assert inst.count("Add-QuantTask '") == 3
    for task in ("Quant-BootSession", "Quant-BootRecord", "Quant-WorkflowGate"):
        assert f"'{task}'" in inst
    assert "C:\\ProgramData\\QuantBox" in inst and "SetAccessRuleProtection($true, $false)" in inst
    assert "is a junction or symlink; not installing" in inst
    assert "-RepetitionDuration (New-TimeSpan -Days 1)" in inst  # never a long -Once


def test_autologon_is_only_reported_and_staged_signed_never_set() -> None:
    inst = CODE["install_unattended"]
    assert "GetValueNames()" in inst and "DefaultPassword" in inst  # presence only
    assert "Get-AuthenticodeSignature" in inst and "O=Microsoft Corporation" in inst
    assert "download.sysinternals.com/files/AutoLogon.zip" in inst
    assert not re.search(r"(&|Start-Process)\s+\S*(\$exe|Autologon)", inst, flags=re.I)  # never run


def test_the_boot_session_starts_only_missing_recorded_terminals_and_never_fusion() -> None:
    boot = CODE["unattended_boot"]
    assert "$session -eq 0" in boot  # no desktop in Session 0
    assert "-ine $Fusion" in boot and "-ieq $Fusion) { continue }" in boot
    assert "already runs in session(s)" in boot  # never a second copy, any session
    assert "TickCount64 -lt 15 * 60 * 1000" in boot  # no half-started desk recorded
    assert "WTSGetActiveConsoleSessionId() -eq [uint32]$session" in boot  # lock the console only
    assert "Get-CimInstance" not in boot and "Get-WmiObject" not in boot


def test_the_workflow_gate_runs_the_trusted_gate_in_box_mode_with_zucks_login_only() -> None:
    wg = CODE["workflow_gate"]
    for v in ("GITHUB_TOKEN", "GH_TOKEN"):
        assert f"'{v}'" in wg
    assert 'Remove-Item -LiteralPath "env:$v"' in wg
    assert "'workflow'" in wg and "exit 3" in wg  # no scope, no merge
    assert 'checkout -q -f --detach "origin/$Live"' in wg  # LIVE, never a PR branch
    assert "--sweep --box" in wg and '".github\\scripts\\audit_gate.py"' in wg
    assert "GIT_CONFIG_KEY_0 = 'safe.directory'" in wg
    assert "Global\\QuantBox-WorkflowGate" in wg


def test_the_gate_script_the_box_runs_has_the_box_mode() -> None:
    gate = (ROOT / ".github" / "scripts" / "audit_gate.py").read_text(encoding="utf-8")
    assert '"--sweep"' in gate and '"--box"' in gate
