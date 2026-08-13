"""L1.60: a deferral that leaves no trace is a skip wearing a disposition's clothes.

`scripts/recommendations.py` promises in its own docstring that "scheduled" cannot become a place
recommendations go to die, because an overdue schedule fires like an orphan. The hole is the verb
the same file provides: a row whose due date MOVES never becomes overdue. Measured 2026-08-13 over
the ledger's first-parent git history, 39 of 152 ever-scheduled rows (26%) had their due date moved
and 38 of the 39 were still scheduled -- they never converted, they only moved.

These tests pin the three properties that close it, and the fourth that keeps the fix from being
worse than the defect:
  1. a re-schedule is RECORDED, not overwritten;
  2. an UNREASONED re-schedule is refused (the refusal path L1.41 requires);
  3. a chronically deferred row cannot leave `owed` by moving its date;
  4. it ADDS ZERO rows on the day it lands, so the fence is not red from day one (L1.43).
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import scripts.recommendations as rec

from libs.ops.deferral import CHRONIC_RESCHEDULES, is_chronic, reschedule_count


def _args(**kw: Any) -> argparse.Namespace:
    base = {"id": "R0001", "status": "scheduled", "reason": None, "commit": None,
            "due": "2026-12-01", "expect": None}
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def ledger(tmp_path: Any) -> Any:
    """A one-row ledger on disk, already SCHEDULED -- the state a re-schedule starts from."""
    path = tmp_path / "recommendation_ledger.json"
    path.write_text(json.dumps({"recommendations": [{
        "id": "R0001", "source": "cycle", "summary": "a scheduled row", "roi_bps": 1.0,
        "raised": (datetime.now(tz=UTC) - timedelta(days=9)).isoformat(),
        "status": "scheduled", "reason": "blocked on the forward clock, revisit at 40 obs",
        "commit": None, "due": "2026-11-01",
        "disposed": (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()}]}), "utf-8")
    original, rec.LEDGER = rec.LEDGER, path
    yield path
    rec.LEDGER = original


def _rows(path: Any) -> list[dict[str, Any]]:
    return json.loads(path.read_text("utf-8"))["recommendations"]


def test_reschedule_is_recorded_not_overwritten(ledger: Any) -> None:
    """The PRIOR due date survives the move. This is the whole defect: it used to be erased."""
    rec.dispose(_args(reason="the forward clock slipped: venue backfill landed 3 weeks late"))
    row = _rows(ledger)[0]
    assert row["due"] == "2026-12-01"                     # the new schedule applies
    assert reschedule_count(row) == 1                     # and the move is COUNTED
    assert row["schedule_history"][0]["was_due"] == "2026-11-01"
    # nothing about the superseded schedule is lost -- reason and stamp travel with the date
    assert "forward clock" in row["schedule_history"][0]["was_reason"]
    assert row["schedule_history"][0]["was_disposed"] is not None
    assert "backfill landed" in row["schedule_history"][0]["why"]


def test_unreasoned_reschedule_is_refused(ledger: Any) -> None:
    """Deferring again is always allowed; deferring SILENTLY is not (the refusal path)."""
    with pytest.raises(SystemExit) as e:
        rec.dispose(_args(reason=None))
    assert "DEFERRAL" in str(e.value)
    # and the refusal is total -- a rejected re-schedule must not half-apply the new date
    assert _rows(ledger)[0]["due"] == "2026-11-01"
    assert reschedule_count(_rows(ledger)[0]) == 0
    with pytest.raises(SystemExit):                        # a token reason is still silence
        rec.dispose(_args(reason="later"))


def test_first_schedule_of_an_open_row_needs_no_reason(ledger: Any) -> None:
    """The rule targets DEFERRAL, never scheduling. An open row schedules exactly as before."""
    rows = _rows(ledger)
    rows[0].update(status="open", reason=None, due=None, disposed=None)
    ledger.write_text(json.dumps({"recommendations": rows}), "utf-8")
    rec.dispose(_args(reason=None))                        # no reason required, no history made
    assert _rows(ledger)[0]["status"] == "scheduled"
    assert reschedule_count(_rows(ledger)[0]) == 0


def test_chronic_row_stays_owed_despite_a_future_due_date(ledger: Any) -> None:
    """The teeth: a row that keeps moving its date can no longer leave the owed population."""
    for i in range(CHRONIC_RESCHEDULES):
        rec.dispose(_args(reason=f"deferred again, stated reason number {i} of the census"))
    row = _rows(ledger)[0]
    assert row["due"] == "2026-12-01" and is_chronic(row)
    _, overdue = rec.owed({"recommendations": [row]})
    assert [r["id"] for r in overdue] == ["R0001"], "a chronic deferral owes a decision NOW"


def test_no_row_is_chronic_on_the_live_ledger(ledger: Any) -> None:
    """L1.43: a fence red from day one gets switched off, taking the real signal with it.

    THIS ASSERTED A MOMENT AND THE MOMENT PASSED. The original form also required
    `sum(reschedule_count) == 0` across the live ledger -- true on install day, when no row had
    any `schedule_history` at all. Nine genuine reschedules have happened since, so the assertion
    began failing on the fence WORKING rather than on anything being wrong: a test measuring the
    install-day snapshot instead of the invariant it was written to protect.

    The invariant that does not expire is the one kept here -- no row may become CHRONIC, i.e. no
    recommendation may keep moving its own due date out of the owed population. Ordinary
    rescheduling is legitimate and is exactly what the predicate is designed to tolerate; the
    counter is asserted below to be live rather than stuck at zero, which is what the removed
    line accidentally guarded.
    """
    live = json.loads(
        (rec.ROOT / "docs/research/recommendation_ledger.json").read_text("utf-8"))
    rows = live["recommendations"]
    assert rows, "the live ledger is the fixture here; an empty one would prove nothing"
    assert not [r for r in rows if is_chronic(r)], (
        "a row that keeps rescheduling itself has left the owed population without a decision")


def test_the_reschedule_counter_reads_the_live_ledger_at_all(ledger: Any) -> None:
    """GUARD THE GUARD. `reschedule_count` returning 0 for every row is indistinguishable from a
    counter that lost its field name, and that silence is what the old install-day assertion
    would have kept reporting as success forever."""
    live = json.loads(
        (rec.ROOT / "docs/research/recommendation_ledger.json").read_text("utf-8"))
    counts = [reschedule_count(r) for r in live["recommendations"]]
    assert all(c >= 0 for c in counts)
    assert any(c > 0 for c in counts), (
        "not one row on the live ledger records a reschedule -- either nothing has ever been "
        "deferred, or the counter is reading a field the ledger no longer writes. Both are worth "
        "a look; a counter that cannot fire is not a fence")


def test_chronic_never_removes_a_row_from_owed(ledger: Any) -> None:
    """Directional safety: this predicate may only ADD work, never subtract it.

    An overdue row must stay owed whether or not it is chronic, so no bug in the counter can make
    the desk look more converted than it is.
    """
    row = _rows(ledger)[0]
    row["due"] = (datetime.now(tz=UTC) - timedelta(days=5)).date().isoformat()
    assert not is_chronic(row)                             # no history, but long overdue
    _, overdue = rec.owed({"recommendations": [row]})
    assert [r["id"] for r in overdue] == ["R0001"]
