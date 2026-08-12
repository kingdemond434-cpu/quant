"""The event guard must block on ambiguity, and must distinguish 'no event' from 'no calendar'."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.execution.event_guard import check


def _cal(tmp_path, events, valid_through="2099-12-31"):
    p = tmp_path / "event_calendar.json"
    p.write_text(json.dumps({"valid_through": valid_through,
                             "source": "test fixture", "events": events}), "utf-8")
    return p


_T = datetime(2026, 9, 17, 18, 0, tzinfo=UTC)


def test_inside_the_window_defers_the_entry(tmp_path):
    cal = _cal(tmp_path, [{"utc": "2026-09-17T18:00:00Z", "name": "FOMC decision",
                           "impact": "high"}])
    for offset in (-29, -1, 0, 5, 14):
        v = check(_T + timedelta(minutes=offset), calendar=cal)
        assert not v.allowed and v.state == "BLACKOUT", f"allowed at {offset} min"
    assert "DEFERRED, not cancelled" in check(_T, calendar=cal).why


def test_outside_the_window_is_clear(tmp_path):
    cal = _cal(tmp_path, [{"utc": "2026-09-17T18:00:00Z", "name": "FOMC decision",
                           "impact": "high"}])
    for offset in (-31, -120, 16, 600):
        v = check(_T + timedelta(minutes=offset), calendar=cal)
        assert v.allowed and v.state == "CLEAR", f"blocked at {offset} min"


def test_a_missing_calendar_blocks_rather_than_waving_through(tmp_path):
    """THE LOAD-BEARING PROPERTY. An unreadable calendar cannot tell a quiet day from an FOMC
    day, and the permissive reading of that ambiguity is the one that costs money -- a position
    opened into a gap that jumps straight through its stop."""
    v = check(_T, calendar=tmp_path / "does_not_exist.json")
    assert not v.allowed and v.state == "EMPTY"
    assert "federalreserve.gov" in v.why          # names the fix, not just the failure


def test_an_expired_calendar_blocks_and_says_so(tmp_path):
    cal = _cal(tmp_path, [{"utc": "2026-01-01T18:00:00Z", "name": "old", "impact": "high"}],
               valid_through="2026-01-31")
    v = check(_T, calendar=cal)
    assert not v.allowed and v.state == "STALE"
    assert "2026-01-31" in v.why


def test_an_empty_event_list_is_not_evidence_of_a_clear_window(tmp_path):
    """An empty list is indistinguishable from an unpopulated file. Reading it as 'nothing
    scheduled' is exactly how a guard becomes decorative."""
    v = check(_T, calendar=_cal(tmp_path, []))
    assert not v.allowed and v.state == "EMPTY"


def test_low_impact_events_do_not_block(tmp_path):
    cal = _cal(tmp_path, [{"utc": "2026-09-17T18:00:00Z", "name": "minor", "impact": "low"},
                          {"utc": "2026-12-01T18:00:00Z", "name": "FOMC", "impact": "high"}])
    assert check(_T, calendar=cal).allowed


def test_the_next_event_is_reported_so_a_human_can_plan(tmp_path):
    cal = _cal(tmp_path, [{"utc": "2026-12-01T18:00:00Z", "name": "FOMC", "impact": "high"}])
    v = check(_T, calendar=cal)
    assert v.allowed and "next is 2026-12-01" in v.why


def test_a_malformed_timestamp_is_skipped_not_crashed(tmp_path):
    cal = _cal(tmp_path, [{"utc": "not-a-date", "name": "junk", "impact": "high"},
                          {"utc": "2026-09-17T18:00:00Z", "name": "FOMC", "impact": "high"}])
    assert not check(_T, calendar=cal).allowed        # the good row still fires


# ----------------------------------------------------------------- L0088 graduation
def test_the_calendar_this_guard_fails_closed_on_is_tracked_in_git():
    """GRADUATES L0088. This guard BLOCKS on a missing or expired calendar, which is the correct
    design -- an unknown event window must never wave an entry through. But `data/` is gitignored
    wholesale here, so on a fresh checkout a fail-closed guard reading an untracked file finds
    nothing and refuses EVERY entry. The sleeve then looks exactly like a sleeve finding no
    setups: no error, no alarm, no trades. R0276 caught this before it shipped; nothing stopped
    it coming back.

    The pairing is the invariant, not the file: fail-closed + gitignored input = a guard that
    silently owns the whole strategy on any clone. Either the file travels with the repo or the
    guard must not fail closed, and the first is what the desk chose (a `!data/event_calendar.json`
    exception plus a monthly idempotent rebuild).
    """
    import subprocess

    from libs.execution.event_guard import CALENDAR

    root = Path(__file__).resolve().parents[2]
    r = subprocess.run(["git", "ls-files", "--error-unmatch", str(CALENDAR)],
                       cwd=root, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (
        f"{CALENDAR} is NOT tracked, and event_guard.check() blocks when it cannot read it. A "
        "fresh clone would refuse every conviction entry and look like a quiet market. Add a "
        f"`!{CALENDAR}` exception to .gitignore and commit the file.")

    # And the exception has to be in .gitignore rather than resting on the file happening to be
    # in the index -- a future `git rm --cached` or a re-clone off a rewritten history would
    # otherwise put it back in the ignored set with nothing complaining.
    assert f"!{CALENDAR}" in (root / ".gitignore").read_text("utf-8"), (
        "the file is tracked today but nothing keeps it tracked -- .gitignore must carry the "
        "explicit negation")
    # The other half of the pairing lives above in
    # `test_a_missing_calendar_blocks_rather_than_waving_through`: if the guard ever stops
    # refusing on an unreadable calendar, this requirement stops being load-bearing. Both have to
    # hold, and they are in one file so a future edit cannot drop one without seeing the other.
