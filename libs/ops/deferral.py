"""A DEFERRAL THAT LEAVES NO TRACE IS A SKIP WEARING A DISPOSITION'S CLOTHES (L1.60).

``scripts/recommendations.py`` states its own anti-gaming guarantee in its module docstring::

    a SCHEDULED row that passes its due date fires exactly like an orphan, so "scheduled"
    cannot become a place recommendations go to die

That is true, and it has a hole exactly the size of the verb the same file provides: **unless the
due date moves first**. ``dispose`` overwrote ``due`` in place, with no history and no counter, so
a row scheduled once honestly and a row snoozed for the fourth time were BYTE-IDENTICAL in the
artifact -- and re-snoozing a row the day before it came due removed it from ``owed`` entirely,
with no work done and no trace left. The one escape the docstring says is closed was the only one
that was open.

MEASURED 2026-08-13, reconstructed from the ledger's own first-parent git history (74 commits
touching ``docs/research/recommendation_ledger.json``): **39 of 152 ever-scheduled rows (26%) were
given more than one distinct due date, and 38 of those 39 are STILL scheduled today** -- they never
converted, they only moved. Worst observed: 3 distinct due dates (R0005, R0011, R0020, R0046);
longest single push 2026-11-15 -> 2027-06-01 (R0012, +7 months) with nothing anywhere recording
that it happened. The proximate symptom is in the §37 carry-over brief the same morning: seven of
its twelve listed items were ``rec-owed-R00xx`` marked RECURRING, all sharing one due date of
2026-08-12 -- a batch snooze that expired together, one day after it was applied.

WHY THE COUNT HAD TO BE RECONSTRUCTED FROM GIT, AND WHAT THAT COSTS. The history did not exist to
read; it had been overwritten one ``dispose`` at a time. First-parent is not a stylistic choice --
plain ``git log`` interleaves the branch lineages this ledger is edited on, and counting the
resulting oscillation (``08-04, 08-12, 08-04, 08-12 ...``) as re-schedules reports 15 episodes for
a row that had 2. Distinct due dates over first-parent history is invariant to that interleaving;
episode counts are not. The pre-instrumentation snoozes are UNRECOVERABLE per row and this module
says so rather than back-filling a guess: ``schedule_history`` is born empty on 2026-08-13 and
counts FORWARD only (L1.28a -- unmeasured is a real answer, and a limitation must never read as
health).

THE RULE FORBIDS NO DEFERRAL, and that is load-bearing rather than a hedge. Re-scheduling is
frequently the correct disposition -- a row genuinely blocked on Gate 0, on a forward clock, or on
a principal act is not repair debt, and forcing it to terminal would manufacture a FALSE rejection,
which corrupts the ledger far more expensively than a slow row. What is never correct is deferring
INVISIBLY. So the teeth here are not a refusal to defer: a chronically re-scheduled row simply
stops being able to buy its way OUT of the ``owed`` population by moving its date. It keeps owing a
decision every cycle until it genuinely converts. The desk keeps looking at it; nobody is forced to
lie about it.

ANTI-TIMIDITY READING, THE ENTIRE PURPOSE: this is a MEASUREMENT duty. It lifts nothing, sizes
nothing, promotes nothing, opens no gate, loosens no statistical bar, and has no vocabulary for
turning a failing verdict into a passing one -- ``is_chronic`` can only ever ADD rows to the
population that owes work. Its whole effect is to make "scheduled once, with a reason" and "snoozed
for the fourth time" distinguishable, which they were not until now, and only one of them is a
disposition.

ON THE DAY IT LANDS IT ADDS EXACTLY ZERO ROWS, which is the property that keeps it alive: every
row's ``schedule_history`` is empty at install, so today's verdict is bit-identical before and
after. A fence red from day one gets switched off (L1.43), taking the real signal with it. This one
bites only on the next snooze of the next row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

#: Recorded re-schedules after which a row can no longer leave ``owed`` by moving its due date.
#: Set at the WORST BEHAVIOUR ACTUALLY MEASURED rather than at a round number: the four worst rows
#: in the 2026-08-13 census had 3 distinct due dates, i.e. two moves after the original schedule.
#: A row reaching this has been deferred twice and is still not done; it does not lose the right to
#: be deferred again, only the ability to do so unseen.
CHRONIC_RESCHEDULES = 2


def reschedule_count(row: dict[str, Any]) -> int:
    """How many times this row's schedule has been MOVED (0 for a first, honest schedule).

    Absent history reads 0, which is correct for a row scheduled once and also for every row that
    predates this instrument -- the two are indistinguishable per row BY CONSTRUCTION and the
    module docstring says so rather than guessing a backfill.
    """
    return len(row.get("schedule_history") or [])


def is_chronic(row: dict[str, Any]) -> bool:
    """True when a SCHEDULED row has been moved often enough to stop escaping ``owed``.

    Only ever adds to the owed population; it can never remove a row from it, so no bug in this
    predicate can make the desk look more converted than it is.
    """
    return row.get("status") == "scheduled" and reschedule_count(row) >= CHRONIC_RESCHEDULES


def record_reschedule(row: dict[str, Any], why: str, now: datetime | None = None) -> None:
    """Append the schedule being REPLACED to the row's history, before the new one overwrites it.

    Called only when a row that is ALREADY ``scheduled`` is scheduled again. Nothing is deleted:
    the prior due date, the prior reason and the prior disposition stamp are all preserved, so the
    record reads as "deferred, three times, for these stated reasons" rather than as a single
    tidy schedule that was always going to be met.
    """
    row.setdefault("schedule_history", []).append({
        "was_due": row.get("due"),
        "was_reason": row.get("reason"),
        "was_disposed": row.get("disposed"),
        "rescheduled": (now or datetime.now(tz=UTC)).isoformat(),
        "why": why,
    })
