"""The merge gate's jammed clone is rebuilt by SYSTEM on its own clock (2026-11-11).

zuck had to paste an administrator block to delete C:\\ProgramData\\QuantBox\\gate-repo after a
stale maintenance.lock froze every sweep. #901 heals it inside Adopt-And-Seal, which itself was
blocked that night; this task does the same heal every 15 minutes whatever adoption is doing.
Pinned at source level, like the other box scripts (no PowerShell on the CI runner).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "desks" / "mt5" / "scripts"
WD = (SCRIPTS / "gate_clone_watchdog.ps1").read_bytes().decode("ascii")
INST = (SCRIPTS / "install_gate_clone_watchdog_task.ps1").read_bytes().decode("ascii")
ADOPT = (SCRIPTS / "Adopt-And-Seal.ps1").read_bytes().decode("ascii")
MANIFEST = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text(encoding="utf-8")


def _code(text: str) -> str:
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def test_box_scripts_keep_crlf() -> None:
    for text in (WD, INST):
        assert "\r\n" in text and "\n" not in text.replace("\r\n", "")


def test_heals_only_a_jammed_clone_under_all_of_901s_conditions() -> None:
    code = _code(WD)
    assert "[int]$beat.rc -eq 1" in code
    assert "-match $cloneFail" in code
    assert "$fails.Count -eq 3" in code
    assert "Where-Object { $_ -match $cloneFail }).Count -eq 3" in code
    assert "'Global\\QuantBox-WorkflowGate'" in code and "$gm.WaitOne(0)" in code
    assert "ReparsePoint" in code and "$rc = 3" in code  # a junction is refused
    # the removal sits after every check and inside the mutex
    rm = code.index("Remove-Item -LiteralPath $gateRepo")
    assert code.index("if (-not $jammed)") < rm and code.index("$gm.WaitOne(0)") < rm
    assert code.index("ReparsePoint") < rm


def test_removes_nothing_but_the_clone_and_restarts_the_gate() -> None:
    code = _code(WD)
    assert re.findall(r"Remove-Item\s+-LiteralPath\s+(\$\w+)", code) == ["$gateRepo"]
    assert "$gateRepo = Join-Path $qb 'gate-repo'" in code
    for never in ("authority", "ROOT_PIN", "secrets", "bin\\", "ledger"):
        assert never.lower() not in code.lower().replace("logs\\", ""), never
    assert "schtasks.exe /Run /TN 'Quant-WorkflowGate'" in code


def test_every_pass_leaves_a_beat_for_the_pagers() -> None:
    code = _code(WD)
    assert "logs\\gate_clone_watchdog.json" in code
    for verdict in ("'OK'", "'UNMEASURED'", "'JAMMED'", "'REFUSED'", "'HEALED'", "'FAILED'"):
        assert verdict in code


def test_registered_as_system_every_15_minutes_idempotently() -> None:
    code = _code(INST)
    assert "$TaskName = 'MT5-GateCloneWatchdog'" in code
    assert "-UserId 'SYSTEM' -LogonType ServiceAccount" in code
    assert "-RepetitionInterval (New-TimeSpan -Minutes 15)" in code
    assert "$IfMissing -and (Get-ScheduledTask" in code
    assert "-MultipleInstances IgnoreNew" in code


def test_adoption_registers_it_so_no_person_ever_runs_the_installer() -> None:
    assert (
        '@{ Task = "MT5-GateCloneWatchdog"; Installer = "install_gate_clone_watchdog_task.ps1" }'
        in ADOPT
    )


def test_declared_in_the_box_task_manifest() -> None:
    row = [ln for ln in MANIFEST.splitlines() if 'name="MT5-GateCloneWatchdog"' in ln]
    assert len(row) == 1
    assert 'installer="desks/mt5/scripts/install_gate_clone_watchdog_task.ps1"' in row[0]


def test_a_hung_merge_docket_is_ended_only_when_old_and_stalled() -> None:
    code = _code(WD)
    assert "merge_hypotheses\\.py" in code
    assert "$reapAgeH = 13" in code  # #882's 12 h wall plus an hour: never pre-empts the wall
    cond = re.search(r"if \(\$ageH -gt \$reapAgeH -and \$still -ge 2 -and -not \$DryRun\)", code)
    assert cond, "the kill needs age, two stalled passes, and no dry run"
    assert code.index("$still = if ($stalled) { [int]$was.flat + 1 } else { 0 }") < cond.start()


def test_stalled_is_no_io_and_user_cpu_under_one_percent_and_kernel_is_ignored() -> None:
    """D-20261111-REAPIO: pid 36280 over 616 s, kernel +16.6 s (paging), user +1.9 s, zero I/O.
    Kernel + user exactly unchanged never fired on it; I/O unchanged and user < 1% does."""
    code = _code(WD)
    assert "$reapUserShare = 0.01" in code
    assert "User = [double]$_.UserModeTime" in code
    assert "Io = [double]($_.ReadTransferCount + $_.WriteTransferCount)" in code
    assert "KernelModeTime" not in code  # paging inflates it: never part of the test
    assert (
        "$stalled = ($gapS -gt 0 -and [double]$was.io -eq $io -and "
        "$userS -lt ($reapUserShare * $gapS))"
    ) in code
    assert "$userS = ($user - [double]$was.user) / 1e7" in code  # 100 ns units to seconds
    # the measured case: 1.9 s of user CPU over 616 s is 0.31%, under the 1% share
    assert 1.9 < 0.01 * 616
    assert "taskkill.exe /PID $p.Id /T /F" in code
    assert code.count("taskkill.exe") == 1  # nothing else is ever killed
    assert "merge_docket = ($reaped -join '; ')" in code


def test_the_heal_runs_first_and_the_cim_query_is_bounded() -> None:
    """#984 audit M1: CIM has hung on this box; it must never stand in front of the heal."""
    code = _code(WD)
    assert code.index("Remove-Item -LiteralPath $gateRepo") < code.index("Get-CimInstance")
    assert code.count("Get-CimInstance") == 1
    job = code.index("$job = Start-Job -ScriptBlock {")
    assert job < code.index("Get-CimInstance") < code.index("Wait-Job -Job $job -Timeout 60")
    assert "merge-docket check UNMEASURED: CIM timed out" in code
    assert code.count("exit ") == 1 and code.rstrip().endswith("exit $rc")  # no early exit


def test_state_and_beat_are_written_atomically() -> None:
    code = _code(WD)
    assert "Write-Atomic $reapState" in code and "Write-Atomic $outPath" in code
    assert "Move-Item -LiteralPath $tmp -Destination $path -Force" in code
