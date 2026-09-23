"""The reboot drill runs on a clock and its verdict reaches the issue board.

MEASURED 2026-09-08: `ops/reboot_drill.ps1` -- the one real fault drill on this desk (terminal64
running, eleven required tasks present and enabled, the account read under 900 s old) -- was
scheduled NOWHERE. grep for reboot_drill found only source comments and
test_installer_covers_the_reboot_drill. A drill that runs when somebody remembers is a drill that
does not run after the reboot nobody noticed.

Three properties:

  1. the installer's `$tasks` table carries a `Kind = "ps1"` row for it on a daily trigger, and
     the script it names exists under the repository root the loop searches;
  2. the drill writes desks/mt5/reports/REBOOT_DRILL.json every run and raises
     data/REBOOT_DRILL_ALARM.txt on FAIL (removing it on PASS) -- the two shapes issue_board
     already reads;
  3. issue_board grades a missing/stale drill record STALLED (the drill stopped) and a present
     alarm STALLED with the drill's own first line (the drill failed) -- executed against a tmp
     root, not pattern-matched.

The drill itself is not executed here: it is PowerShell against the Windows task registry.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
INSTALLER = BASE / "scripts" / "Install-QuantWindows.ps1"
MANIFEST = BASE / "ops" / "box_tasks.manifest"
DRILL = REPO / "ops" / "reboot_drill.ps1"
TASK = "MT5-RebootDrill"

if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from research import issue_board  # noqa: E402


def _installer_block() -> str:
    text = INSTALLER.read_text("utf-8")
    m = re.search(rf'@\{{\s*Name\s*=\s*"{re.escape(TASK)}"(.*?)(?=@\{{\s*Name\s*=|\n\)\n)',
                  text, re.S)
    assert m, f"{TASK} is not in the installer's $tasks table"
    return m.group(0)


def test_the_installer_gives_the_drill_a_daily_powershell_clock() -> None:
    block = _installer_block()
    assert 'Kind = "ps1"' in block, "a .ps1 handed to python reports a SyntaxError as result 1"
    assert 'Script = "ops\\\\reboot_drill.ps1"' in block
    assert "New-ScheduledTaskTrigger -Daily" in block
    assert DRILL.exists(), "the row names a script that is not in the repository"


def test_the_manifest_declares_the_drill_with_its_cadence() -> None:
    rows = [ln for ln in MANIFEST.read_text("utf-8").splitlines()
            if ln.startswith("TASK") and f'name="{TASK}"' in ln]
    assert len(rows) == 1, rows
    (row,) = rows
    assert 'trigger="daily' in row and 'runs="ops/reboot_drill.ps1"' in row
    assert 'installer="desks/mt5/scripts/Install-QuantWindows.ps1"' in row


def test_the_drill_records_its_verdict_where_the_board_reads() -> None:
    """Text pins on the PowerShell: the two paths, the alarm removed on PASS, and the root
    resolved from the script's own location rather than a hardcoded drive."""
    src = DRILL.read_text("utf-8")
    assert "$root = Split-Path -Parent $PSScriptRoot" in src
    assert 'Join-Path $root "desks\\mt5\\reports\\REBOOT_DRILL.json"' in src
    assert 'Join-Path $root "data\\REBOOT_DRILL_ALARM.txt"' in src
    assert "Remove-Item -Path $alarm" in src, "a PASS must clear the previous FAIL's alarm"
    assert "ConvertTo-Json" in src and "verdict = $verdict" in src
    # Still read-only apart from the re-enable: no schtasks /Change, /Create, /Delete or /Run.
    assert not re.search(r"schtasks\s+/(Change|Create|Delete|Run)", src, re.I)
    assert "Enable-ScheduledTask" in src


def test_the_board_grades_a_missing_or_stale_drill_record_stalled(tmp_path: Path) -> None:
    keys = {i.key for i in issue_board.stale_producers(tmp_path)}
    assert "missing:reboot_drill" in keys
    rec = tmp_path / "desks" / "mt5" / "reports" / "REBOOT_DRILL.json"
    rec.parent.mkdir(parents=True)
    rec.write_text('{"verdict": "PASS"}', "utf-8")
    keys = {i.key for i in issue_board.stale_producers(tmp_path)}
    assert "missing:reboot_drill" not in keys and "stale:reboot_drill" not in keys
    old = time.time() - 86400 * issue_board.STALE_TOLERANCE - 60
    os.utime(rec, (old, old))
    (issue,) = [i for i in issue_board.stale_producers(tmp_path) if i.key == "stale:reboot_drill"]
    assert issue.severity == "STALLED" and issue.auto is False and issue.repair is None


def test_the_board_raises_a_failed_drill_with_its_own_first_line(tmp_path: Path) -> None:
    assert not [i for i in issue_board.raised_alarms(tmp_path)
                if i.key == "alarm:REBOOT_DRILL_ALARM.txt"]
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "REBOOT_DRILL_ALARM.txt").write_text(
        "REBOOT DRILL FAIL 2026-09-08T06:30:00Z -- task MISSING: MT5-ShadowSync\n"
        "  - task MISSING: MT5-ShadowSync\n", "utf-8")
    (issue,) = [i for i in issue_board.raised_alarms(tmp_path)
                if i.key == "alarm:REBOOT_DRILL_ALARM.txt"]
    assert issue.severity == "STALLED" and "post-reboot drill FAILED" in issue.what
    assert "task MISSING: MT5-ShadowSync" in issue.detail
    assert issue.auto is False, "a missing task is repaired by the installer, not by a guess"


def test_the_drill_keeps_its_daily_cadence_and_no_invented_producer() -> None:
    (row,) = [r for r in issue_board.CADENCE if r[0] == "reboot_drill"]
    assert row[1:] == ("desks/mt5/reports/REBOOT_DRILL.json", 86400, None)
