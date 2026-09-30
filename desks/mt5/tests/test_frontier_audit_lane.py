"""MT5-FrontierAudit: the runner reports failure honestly and the box can (re)build the task."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "ops" / "run_frontier_audit.cmd"
INSTALLER = ROOT / "desks" / "mt5" / "scripts" / "install_frontier_audit_task.ps1"
ADOPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"
MANIFEST = ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest"


def _code_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.strip().lower().startswith("rem")]


def _main_body(lines: list[str]) -> list[str]:
    return lines[:lines.index(":run")]


def test_every_organ_runs_through_the_failure_counter() -> None:
    lines = _code_lines(RUNNER.read_text("utf-8"))
    body = _main_body(lines)
    organs = [ln for ln in body if ln.startswith("call :run ")]
    assert len(organs) >= 29
    # No organ bypasses :run -- a bare python call would escape the failure count.
    assert not [ln for ln in body if '"%PY%"' in ln]
    # Each organ names a script or module that exists in this repository.
    for ln in organs:
        rest = ln[len("call :run "):]
        if rest.startswith("-m "):
            mod = rest.split()[1]
            assert (ROOT / (mod.replace(".", "/") + ".py")).is_file(), mod
        else:
            script = re.match(r'"([^"]+)"', rest)
            assert script, ln
            assert (ROOT / script.group(1).replace("\\", "/")).is_file(), ln


def test_the_lane_exit_code_is_derived_not_hardcoded() -> None:
    lines = _code_lines(RUNNER.read_text("utf-8"))
    body = _main_body(lines)
    assert "set /a FAILED=0" in body
    # The failure branch comes BEFORE the success exit and exits non-zero.
    fail_at = next(i for i, ln in enumerate(body) if ln.startswith("if %FAILED% neq 0"))
    ok_at = max(i for i, ln in enumerate(body) if ln == "exit /b 0")
    assert fail_at < ok_at
    assert "exit /b 1" in body[fail_at:ok_at]
    # Every organ runs before the verdict: nothing exits early.
    last_organ = max(i for i, ln in enumerate(body) if ln.startswith("call :run "))
    assert last_organ < fail_at
    assert not [ln for ln in body[:fail_at] if ln.startswith("exit")]


def test_the_run_subroutine_counts_negative_crash_codes_and_returns_zero() -> None:
    lines = _code_lines(RUNNER.read_text("utf-8"))
    sub = lines[lines.index(":run"):]
    assert sub[0] == ":run"
    assert '"%PY%" -u %* >>"%LOG%" 2>&1' in sub
    # `if errorlevel 1` is true only for >= 1 and misses Windows crash codes (negative).
    assert not [ln for ln in sub if "errorlevel 1" in ln.lower()]
    assert any('if not "%RC%"=="0"' in ln for ln in sub)
    assert "set /a FAILED+=1" in sub
    assert sub[-1] == "exit /b 0"


def test_installer_is_declared_idempotent_and_hooked_into_adoption() -> None:
    manifest = MANIFEST.read_text("utf-8")
    row = next(ln for ln in manifest.splitlines() if 'name="MT5-FrontierAudit"' in ln)
    assert 'installer="desks/mt5/scripts/install_frontier_audit_task.ps1"' in row
    assert 'trigger="daily 05:10"' in row

    inst = INSTALLER.read_text("utf-8")
    assert "$TaskName = 'MT5-FrontierAudit'" in inst
    assert "param([switch]$IfMissing)" in inst
    assert "run_frontier_audit.cmd" in inst
    assert "AddHours(5).AddMinutes(10)" in inst
    # -IfMissing returns before any Unregister, so a live task is never touched.
    assert inst.index("if ($IfMissing -and") < inst.index("Unregister-ScheduledTask")

    adopt = ADOPT.read_text("utf-8")
    assert "install_frontier_audit_task.ps1" in adopt
    hook = adopt.index("install_frontier_audit_task.ps1")
    # After a SUCCESSFUL adoption (the partial branch exits first) and before the seal.
    assert adopt.index('Done $adoptExit "adopt-release-partial"') < hook
    assert hook < adopt.index("release.seal(by='Adopt-And-Seal')")
    assert "-IfMissing" in adopt[hook:hook + 800]
