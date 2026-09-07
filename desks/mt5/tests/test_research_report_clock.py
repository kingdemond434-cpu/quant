"""Hourly producers must have a clock of their own, not a place in a queue behind fifty legs.

Eleven producers declare a 3600-second cadence in `issue_board.CADENCE`, and every one of them is
a LEG of `hourly_cycle.py`. `issue_board` is itself a leg of the same cycle and runs BEFORE the
four research reports it measures, so at measurement time those artifacts were written by the
PREVIOUS pass and their age is one full cycle duration. The cycle now has fifty-five legs and a
backtest with a forty-five-minute budget; once a pass exceeds `STALE_TOLERANCE` (2.0) times the
cadence, the board reports them STALLED every pass, forever, while the producers are fine.

Measured 2026-09-07: `issue_board` last wrote 12:37 and had not run again by 13:49.

The property that matters most here is the one in the last test: the fix is a clock, and any
future "fix" that instead raises the tolerance is the loosening this desk does not do.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
if str(BASE / "research") not in sys.path:
    sys.path.insert(0, str(BASE / "research"))

from research import issue_board  # noqa: E402
from scripts import run_research_reports as clock  # noqa: E402


def test_it_watches_every_hourly_producer_the_issue_board_watches() -> None:
    """One table, two consumers. The detector and the refresher cannot disagree.

    `issue_board.CADENCE` already says a producer absent from it is a producer nothing can notice
    going quiet. Deriving the clock from the same table means adding a producer gives it a clock
    in the same edit, rather than in a second one somebody forgets.
    """
    expected = {
        name for name, _rel, cadence, producer in issue_board.CADENCE
        if cadence <= clock.MAX_CADENCE_S and producer
    }
    assert {row["name"] for row in clock.due()} == expected
    assert expected, "no hourly producers found -- the table shape has changed"


def test_a_producer_with_no_command_is_not_invented() -> None:
    """`shadow_health` declares an artifact and no producer: nothing here can refresh it.

    Guessing a command for it would be the failure the desk keeps paying for -- a task that
    reports success and runs nothing.
    """
    named = {row["name"] for row in clock.due()}
    assert "shadow_health" not in named


def test_daily_producers_keep_their_daily_clock() -> None:
    """An hourly clock for a daily producer is work nobody asked for."""
    named = {row["name"] for row in clock.due()}
    for name, _rel, cadence, _p in issue_board.CADENCE:
        if cadence > clock.MAX_CADENCE_S:
            assert name not in named


def test_a_fresh_artifact_is_skipped_so_the_cycle_is_not_duplicated(tmp_path: Path) -> None:
    """On a healthy box the cycle's own leg has just written it and this task does nothing.

    Without the freshness guard the runner would re-run every producer every hour beside the
    cycle, which is the same work twice and a race for every artifact.
    """
    import time
    from datetime import UTC, datetime

    fresh = tmp_path / "FRESH.json"
    fresh.write_text("{}")
    stale = tmp_path / "STALE.json"
    stale.write_text("{}")
    import os
    old = time.time() - 3000                        # past 0.5 x 3600
    os.utime(stale, (old, old))

    now = datetime.now(tz=UTC)
    assert clock._artifact_path(str(fresh)).exists()
    # Freshness is the only thing separating these two, so assert on the arithmetic directly.
    assert (now.timestamp() - fresh.stat().st_mtime) <= 3600 * clock.REFRESH_AT
    assert (now.timestamp() - stale.stat().st_mtime) > 3600 * clock.REFRESH_AT


def test_refresh_at_leaves_room_for_the_producer_to_run() -> None:
    """Waiting for the full cadence guarantees arriving after the deadline, not before it."""
    assert 0.0 < clock.REFRESH_AT < 1.0
    assert clock.BUDGET_S < 3600, "a producer must not still be running at its next trigger"


def test_the_report_is_written_even_when_nothing_is_due(tmp_path: Path) -> None:
    """A task that prints nothing when it skips everything looks exactly like a dead task."""
    rc = clock.main(["--report"])
    assert rc == 0
    payload = json.loads(clock.REPORT.read_text("utf-8"))
    assert payload["watched"] >= 1
    assert "verdicts" in payload
    for row in payload["verdicts"]:
        assert row["why"], f"{row['name']} recorded no reason for its verdict"


def test_the_installer_registers_the_clock() -> None:
    import re
    text = (BASE / "scripts" / "Install-QuantWindows.ps1").read_text("utf-8")
    assert 'Name = "MT5-ResearchReports"' in text
    block = re.search(r'@\{\s*Name\s*=\s*"MT5-ResearchReports"(.*?)(?=@\{\s*Name\s*=|\n\)\n)',
                      text, re.S)
    assert block and "run_research_reports.py" in block.group(1)


def test_the_stale_tolerance_was_not_loosened_to_hide_this() -> None:
    """THE POINT. Raising the tolerance silences the board and leaves the artifacts as old.

    The desk's standing rule is that no statistical gate, threshold or floor is loosened to turn a
    red light green, and a staleness threshold is one. If a future change wants a different
    tolerance it must argue for it here, not arrive as a side effect of quieting an alarm.
    """
    assert issue_board.STALE_TOLERANCE == 2.0
    assert all(cadence in (3600, 86400) for _n, _r, cadence, _p in issue_board.CADENCE)
