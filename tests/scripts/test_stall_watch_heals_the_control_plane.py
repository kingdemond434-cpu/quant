"""MT5-StallWatch re-enables the control plane and kicks a stale feed, never a held task.

Principal 2026-11-17: routine recovery (a task Windows flipped Disabled, a stale desk feed) never
waits on a person. The heals are the narrowest ones that work: enable a task or start it once on
its own registered action; the order paths are not in the set; a TASK_HOLD_<name> marker wins.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "desks" / "mt5" / "scripts" / "stall_watch.ps1").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    i = SRC.index(start)
    return SRC[i:SRC.index(end, i)]


def test_control_tasks_are_reenabled_unless_held() -> None:
    names = _block("$controlTasks = @(", ")")
    for t in ("MT5-TerminalBoot", "MT5-AdoptRelease", "MT5-DeskState", "MT5-ShadowSync",
              "MT5-Universe", "MT5-ClockFixer", "MT5-NeverStale"):
        assert f"'{t}'" in names, t
    # the order paths are never in the set
    for money in ("MT5-GatewayResident", "MT5-Gateway'", "MT5-E8WindowGuard", "Deadman"):
        assert money not in names, money
    loop = _block("foreach ($tn in $controlTasks)", "# A STALE DESK FEED")
    assert loop.index("Test-TaskHeld $tn") < loop.index("Enable-ScheduledTask")
    assert "TASK_AUTO_REENABLED" in loop and "JOURNAL DISABLED" in loop
    assert "Stop-Process" not in loop and "schtasks /Run" not in loop


def test_research_reenable_honours_the_hold_marker_too() -> None:
    loop = _block("foreach ($tn in $researchTasks)", "# THE CONTROL PLANE COMES BACK ON")
    assert loop.index("Test-TaskHeld $tn") < loop.index("Enable-ScheduledTask")
    assert "TASK_HOLD_" in SRC and "function Test-TaskHeld" in SRC


def test_a_stale_feed_starts_the_desk_state_task_once() -> None:
    feed = _block("$feedStaleMin = 45", "# RAM FLOOR")
    assert "web\\desk_state.json" in feed
    assert "$q.Status -eq 'Ready'" in feed            # never stacked on a running build
    assert "Test-TaskHeld 'MT5-DeskState'" in feed
    assert feed.count("schtasks /Run") == 1 and "/Run /TN 'MT5-DeskState'" in feed
    assert "FEED_AUTO_KICKED" in feed and "JOURNAL STALE FEED" in feed


def test_a_retired_box_still_heals_nothing() -> None:
    assert SRC.index("BOX_RETIRED") < SRC.index("$controlTasks = @(")
    retired = _block("if (Test-Path (Join-Path $base 'data\\BOX_RETIRED'))", "}")
    assert "exit 0" in SRC[SRC.index(retired):SRC.index(retired) + len(retired) + 5]


def test_the_event_kinds_are_registered() -> None:
    from libs.ops.events import KINDS
    for k in ("TASK_AUTO_REENABLED", "FEED_AUTO_KICKED", "GATEWAY_AUTO_REARMED"):
        assert k in KINDS, k


def test_a_deliberate_adopter_disable_writes_its_hold_marker() -> None:
    """Auditor MF1 on #1226: migrate_to_new_box disables MT5-AdoptRelease on purpose; without the
    marker StallWatch would re-enable it within ten minutes."""
    src = (ROOT / "ops" / "migrate_to_new_box.ps1").read_text(encoding="utf-8-sig")
    off = src.index("Disable-ScheduledTask -TaskName MT5-AdoptRelease")
    hold = src.index("TASK_HOLD_MT5-AdoptRelease")
    assert off < hold < off + 800
    assert "Set-Content -LiteralPath $adoptHold" in src
    # every other deliberate Disable of a control task in ops/ and the desk scripts carries one
    names = _block("$controlTasks = @(", ")")
    for p in list((ROOT / "ops").rglob("*.ps1")) + list((ROOT / "desks" / "mt5").rglob("*.ps1")):
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        for t in ("MT5-TerminalBoot", "MT5-AdoptRelease", "MT5-DeskState", "MT5-ShadowSync",
                  "MT5-Universe", "MT5-ClockFixer", "MT5-NeverStale"):
            if f"Disable-ScheduledTask -TaskName {t}" in text:
                assert f"TASK_HOLD_{t}" in text, (p, t)
        assert names
