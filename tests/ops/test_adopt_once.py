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
    """Audit SF1: inside the released line before heal. Under the Audit-CLEAR authority (zuck
    2026-11-25 18:53Z) that line is LIVE; QUANT_ADOPT_AUTHORITY=release keeps production."""
    rel = ADOPT.index("merge-base --is-ancestor $script:GuardHead $guardRef")
    assert (
        rel < ADOPT.index('Invoke-AdoptGuard @("heal"')
        and 'Done 8 "guard-root-not-released"' in ADOPT
    )
    assert '"refs/remotes/origin/production" } else { "refs/remotes/origin/$Branch" }' in ADOPT
    assert ADOPT.index("$script:AdoptAuthority = ") < ADOPT.index("if ($GuardRoot) {")
    assert "+refs/heads/production:refs/remotes/origin/production" in ONCE
    assert 'merge-base --is-ancestor $sha "refs/remotes/origin/production"' in ONCE


def test_the_audit_clear_bootstrap_runs_the_targets_own_adopter_with_every_check() -> None:
    clear = (ROOT / "ops/box/adopt_clear_once.ps1").read_text(encoding="utf-8")
    assert "github.com" not in clear and "remote get-url origin" in clear
    assert "'^[0-9a-f]{40}$'" in clear
    assert 'merge-base --is-ancestor $Sha "refs/remotes/origin/$Live"' in clear
    assert "-RepoRoot $QuantRoot -GuardRoot $stage" in clear
    assert "AllowUnreleased" not in clear.split("#>", 1)[1]
    assert '"ADOPT_CLEAR"' in clear and '[string] $GuardRoot' in clear
