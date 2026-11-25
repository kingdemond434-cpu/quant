"""Tasks the manifest declares register THEMSELVES on the box (principal 2026-11-25 11:53Z: "I
already told u id paste everything once so next time nth ever needs me").

THE DEFECT THIS PINS. MT5-Guardian -- the SYSTEM task that ends a hung research producer and runs it
again -- was built, manifested and shipped with an installer, and was never registered: the box
Claude's own classifier refuses to register or end tasks, so the last step waited on a person's
paste. MergeDocket then sat hung on one lock for 17.5 h with nothing on the box able to end it.

The rule (scripts/check_box_tasks.ensure_rows, called by Adopt-And-Seal as `--ensure-list`): every
manifest row whose installer OPTS IN by declaring `[switch]$IfMissing` is registered by the adopter
(SYSTEM) the first time the box lacks it, held or not. `-IfMissing` never touches a registered
task. There is no pwsh on the research host, so the PowerShell is read rather than run.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_box_tasks as cbt  # noqa: E402

ADOPT = ROOT / "desks" / "mt5" / "scripts" / "Adopt-And-Seal.ps1"
GUARDIAN = ROOT / "desks" / "mt5" / "scripts" / "install_guardian_task.ps1"


def _manifest(tmp: Path, rows: list[tuple[str, str]]) -> None:
    m = tmp / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text("".join(f'TASK name="{n}" trigger="hourly" runs="x.py" installer="{i}" '
                         f'lane="ops"\n' for n, i in rows), "utf-8")


def _installer(tmp: Path, rel: str, body: str) -> None:
    p = tmp / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")


def test_the_guardian_registers_itself() -> None:
    names = [n for n, _ in cbt.ensure_rows()[0]]
    assert "MT5-Guardian" in names
    src = GUARDIAN.read_text("utf-8")
    assert re.search(r"\[switch\]\s*\$IfMissing", src)
    # -IfMissing on an existing task touches nothing: it exits before Set-/Register-ScheduledTask.
    guard = src.index("if ($IfMissing -and (Get-ScheduledTask -TaskName $TaskName")
    early = src.index("exit 0", guard)
    assert early - guard < 200
    assert early < src.index("Set-ScheduledTask") and early < src.index("Register-ScheduledTask")


def test_the_lane_floor_is_still_covered() -> None:
    names = {n for n, _ in cbt.ensure_rows()[0]}
    assert {"MT5-Compiler", "MT5-TapeRecord", "MT5-TierS", "MT5-Replication"} <= names


def test_opt_in_only(tmp_path: Path) -> None:
    yes = "desks/mt5/scripts/install_a_task.ps1"
    no = "desks/mt5/scripts/install_b_task.ps1"
    _manifest(tmp_path, [("MT5-Alpha", yes), ("MT5-Beta", no)])
    _installer(tmp_path, yes, "param([switch]$IfMissing)\n$TaskName = 'MT5-Alpha'\n")
    _installer(tmp_path, no, "param()\n$TaskName = 'MT5-Beta'\n")
    rows, skipped = cbt.ensure_rows(tmp_path)
    assert rows == [("MT5-Alpha", yes)]
    assert skipped == ["MT5-Beta"]


def test_never_list_and_path_fences(tmp_path: Path) -> None:
    body = "param([switch]$IfMissing)\n$TaskName = '{n}'\n"
    rows = [("MT5-AdoptRelease", "desks/mt5/scripts/install_adopt_release_task.ps1"),
            ("Quant-SignTrain", "ops/box/install_sign.ps1"),
            ("MT5-DashMirror", "desks/mt5/scripts/install_dash.ps1"),
            ("MT5-Escape", "desks/mt5/scripts/../../../evil/install_x.ps1"),
            ("MT5-Elsewhere", "tools/install_y.ps1"),
            ("MT5-NotPs", "desks/mt5/scripts/install_z.cmd"),
            ("MT5-Absent", "desks/mt5/scripts/install_gone.ps1"),
            ("MT5-Unnamed", "desks/mt5/scripts/install_other.ps1")]
    _manifest(tmp_path, rows)
    for n, rel in rows:
        if n in ("MT5-Absent",):
            continue
        _installer(tmp_path, rel, body.format(n="MT5-Someone" if n == "MT5-Unnamed" else n))
    out, skipped = cbt.ensure_rows(tmp_path)
    assert out == []
    assert sorted(skipped) == sorted(n for n, _ in rows)


#: Money- and prop-lane tasks the adopter may register by itself, reviewed one by one (Audit
#: 2026-11-25): the FTMO book and its STANDBY executor (registering arms nothing --
#: data\\FTMO_EXECUTOR_ARMED does), and MT5-AllocatorPulse (CLEARed #1107/#1233; its absence on
#: the box is MISS M3). Any other money/prop-lane task joining the self-registered set must change
#: this list in review. Keyed off the manifest's own lane tag, never a name pattern.
MONEY_LANE_ALLOWED = frozenset({"MT5-FTMO-Allocator", "MT5-FTMO-Executor", "MT5-AllocatorPulse"})


def test_no_money_lane_task_self_registers_unless_reviewed() -> None:
    lanes = {r["name"]: r.get("lane", "") for r in cbt.manifest_rows()}
    names = {n for n, _ in cbt.ensure_rows()[0]}
    money = {n for n in names if lanes.get(n) in ("money", "prop")}
    assert money <= MONEY_LANE_ALLOWED, sorted(money - MONEY_LANE_ALLOWED)


def test_the_money_lane_pin_reads_the_lane_tag(tmp_path: Path) -> None:
    rel = "desks/mt5/scripts/install_q_task.ps1"
    m = tmp_path / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(f'TASK name="MT5-Quiet" trigger="hourly" runs="x.py" installer="{rel}" '
                 f'lane="money"\n', "utf-8")
    _installer(tmp_path, rel, "param([switch]$IfMissing)\n$TaskName = 'MT5-Quiet'\n")
    rows = cbt.manifest_rows(m)
    names = {n for n, _ in cbt.ensure_rows(tmp_path)[0]}
    money = {n for n in names if {r["name"]: r["lane"] for r in rows}.get(n) == "money"}
    # A name no pattern would flag is still caught by its lane, and is not on the reviewed list.
    assert money == {"MT5-Quiet"} and not money <= MONEY_LANE_ALLOWED


def test_the_adopter_calls_it_on_every_path_that_exits_cleanly() -> None:
    src = ADOPT.read_text("utf-8")
    assert "--ensure-list" in src and "check_box_tasks.py" in src
    define = src.index("function Invoke-EnsureManifestTasks")
    calls = [m.start() for m in re.finditer(r"^\s*Invoke-EnsureManifestTasks\s*$", src, re.M)]
    # Defined before its first call (a PowerShell script function must exist when it is called).
    assert calls and define < min(calls)
    # Both HOLD exits (no new release, adopt-guard hold) and the adoption path all call it.
    held_release = src.index('Done 0 "held-awaiting-release"')
    held_guard = src.index("Done 0 $held")
    assert any(c < held_release and held_release - c < 200 for c in calls)
    assert any(c < held_guard and held_guard - c < 200 for c in calls)
    assert len(calls) >= 3
    body = src[define:src.index("\n}", define)]
    # Never re-registers a live task, never runs an installer outside the repo, never throws.
    assert "-IfMissing" in body and 'Contains("..")' in body and "catch" in body
    assert "Unregister-ScheduledTask" not in body and "Stop-ScheduledTask" not in body


def test_cli_prints_tab_separated_pairs(capsys) -> None:
    assert cbt.main(["--ensure-list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines and all(len(x.split("\t")) == 2 for x in lines)
    assert any(x.startswith("MT5-Guardian\t") for x in lines)
