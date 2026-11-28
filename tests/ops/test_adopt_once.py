"""ops/box/adopt_once.ps1 and Adopt-And-Seal.ps1 -GuardRoot: the one manual adoption that lets a
release's own guard decide, with nothing switched off (2026-11-17, the 11-14 multi-line row)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADOPT = (ROOT / "desks/mt5/scripts/Adopt-And-Seal.ps1").read_text(encoding="utf-8")
ONCE = (ROOT / "ops/box/adopt_once.ps1").read_text(encoding="utf-8")
CMD = (ROOT / "ops/box/adopt_once.cmd").read_text(encoding="utf-8")


def test_every_guard_call_runs_against_the_box_root() -> None:
    calls = re.findall(r"& \$py @pyArgs \$script:GuardScript (\S+)", ADOPT)
    assert len(calls) == 3
    assert all(c == "@script:GuardRootArgs" for c in calls), calls
    assert '$script:GuardRootArgs = @("--root", $RepoRoot)' in ADOPT


def test_the_release_gate_runs_from_the_same_decider_root() -> None:
    assert '$gateScript = Join-Path $script:DeciderRoot "scripts\\release_promotion.py"' in ADOPT
    assert '"--root", $RepoRoot)' in ADOPT[ADOPT.index("$gateArgs = @(") :]


def test_a_guard_root_is_clean_and_inside_the_target_before_pre() -> None:
    assert "status --porcelain --untracked-files=no" in ADOPT
    assert 'Done 8 "guard-root-unclean"' in ADOPT and 'Done 8 "guard-root-missing"' in ADOPT
    anc = ADOPT.index("merge-base --is-ancestor $script:GuardHead $gateTarget")
    assert ADOPT.index("$gateTarget = [string]$gate.target") < anc
    assert anc < ADOPT.index('Invoke-AdoptGuard @("pre"') < ADOPT.index("\n$script:Adopted = $true")
    assert 'Done 8 "guard-root-not-in-target"' in ADOPT


def test_the_scheduled_task_never_passes_a_guard_root() -> None:
    for rel in ("desks/mt5/scripts/install_adopt_release_task.ps1",):
        assert "GuardRoot" not in (ROOT / rel).read_text(encoding="utf-8")
    block = ADOPT[ADOPT.index("if ($GuardRoot) {") :]
    assert "$env:" not in block[: block.index("$script:GuardScript = Join-Path $guardDir")]


def test_adopt_once_verifies_the_tag_and_skips_nothing() -> None:
    for must in (
        "IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)",
        "$TagShape = '^release/\\d{8}T\\d{6}Z-([0-9a-f]{12})$'",
        "$sha.StartsWith($short)",
        'merge-base --is-ancestor $sha "refs/remotes/origin/$Live"',
        "merge-base --is-ancestor $GuardFix $sha",
        "-RepoRoot $QuantRoot -GuardRoot $stage",
        "Start-Transcript",
    ):
        assert must in ONCE, must
    assert "ccc2fbb396db3a677906586d8a4c0f5c29ab2cc2" in ONCE
    after_help = ONCE[ONCE.index("#>") :]
    body = "\n".join(ln for ln in after_help.splitlines() if not ln.lstrip().startswith("#"))
    for never in (
        "AllowUnreleased",
        "ADOPT_UNRELEASED",
        "Register-ScheduledTask",
        "Set-ScheduledTask",
        "gh.exe",
        "gh auth",
    ):
        assert never not in body, never
    assert '"%~dp0adopt_once.ps1" -Tag "%~1"' in CMD and "pause" in CMD


def test_the_stage_is_never_the_live_tree() -> None:
    assert '$stage = Join-Path (Join-Path $Root "adopt-once")' in ONCE
    assert '[string] $Root = "C:\\ProgramData\\QuantBox"' in ONCE


def test_the_adopt_log_lands_in_the_box_tree() -> None:
    """Audit MF1: a run from a release checkout logs where the box's watchers read."""
    assert '$script:AdoptLog = Join-Path $RepoRoot "desks\\mt5\\logs\\adopt_and_seal.log"' in ADOPT
    assert 'Join-Path $PSScriptRoot "..\\logs' not in ADOPT
    assert ADOPT.index("if (-not $RepoRoot) {") < ADOPT.index("$script:AdoptLog = Join-Path")


def test_a_guard_root_must_be_released_before_it_runs_anything() -> None:
    """Audit SF1: inside production before heal; adopt_once checks the same."""
    rel = ADOPT.index('merge-base --is-ancestor $script:GuardHead "refs/remotes/origin/production"')
    assert (
        rel < ADOPT.index('Invoke-AdoptGuard @("heal"')
        and 'Done 8 "guard-root-not-released"' in ADOPT
    )
    assert "+refs/heads/production:refs/remotes/origin/production" in ONCE
    assert 'merge-base --is-ancestor $sha "refs/remotes/origin/production"' in ONCE


def test_adopt_once_arms_the_gate_registry_notices_without_secrets_or_tasks() -> None:
    """Step 7 (2026-11-18): the box gate sends its veto notice with QUANT_REGISTRY_NOTIFY and
    counts it only on exit 0, so unset means no registry CLEAR can merge. adopt_once sets it at
    user scope for the gate task's account, then sends one test notice, whatever step 5 decided."""
    fn = ONCE[ONCE.index("function Arm-RegistryNotify {") : ONCE.index("\nArm-RegistryNotify\n")]
    assert '$name = "QUANT_REGISTRY_NOTIFY"' in fn
    assert 'Join-Path $QuantRoot "libs\\ops\\send_alert.py"' in fn
    assert 'Get-ScheduledTask -TaskName "Quant-WorkflowGate"' in fn and "Principal.UserId" in fn
    assert '[Environment]::SetEnvironmentVariable($name, $cmd, "User")' in fn
    assert '"Machine"' not in fn  # never machine-wide
    assert "ShortPath" in fn  # the gate splits the command with shlex: no spaces in it
    assert "catch {" in fn  # never fatal to the adoption
    # armed after the adopter ran and before any final verdict
    call = ONCE.index("\nArm-RegistryNotify\n")
    assert ONCE.index("$rc = $LASTEXITCODE") < call < ONCE.index('Finish 0 "DONE: the box adopted')
    for never in ("Register-ScheduledTask", "Set-ScheduledTask", "secrets", "Get-Content"):
        assert never not in fn, never
