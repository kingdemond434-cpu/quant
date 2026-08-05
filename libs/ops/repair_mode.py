"""THE ACTUATOR FOR L1.28b(d) -- the queue's drain mechanism, which was legislated and never wired.

L1.28b(d) is precise about the remedy: "backlog above the repair-mode line (25 open rows) FLIPS
the next audit/brain window from finding to fixing -- when data/conversion_status.json says
repair_mode". ``scripts/check_conversion.py`` computes that flag every run and publishes it. On
2026-08-05 a grep for its consumers across ``*.py``, ``*.sh``, ``prompts/`` and ``ops/`` returned
exactly ONE::

    run_max_push.py:249   action = ("repair-mode: flip the next audit/brain window from finding
                                    to fixing; ..." if d.get("repair_mode") else ...)

which selects a different ADVICE STRING. Nothing flips. No organ's behaviour changes. ``ops/
brain_env.sh`` -- the file every organ sources, and the one place a duty can reach every present
and future organ (L1.36 REACHING) -- never reads it. The law's own remedy had no actuator.

THIS IS WHY ``rec-ledger-backlog`` RECURS, AND WHY CLOSING IT PER-INSTANCE BUYS ONE CYCLE. The
§37 brief on 2026-08-05 recorded it as RECURRED 3x over 5.2d across 13 sightings, each cycle
disposing the specific named rows. Measured that day: arrivals 54.4/day against dispositions
30.0/day, debt +171 rows in 7d, backlog 204. A queue with λ > μ cannot be drained by servicing
the items it names; it is drained by capacity or by admission control, and L1.28b(f) forbids the
second (acquisition is never cut to meet extraction). So capacity it is -- and the mechanism the
law wrote to redirect capacity was inert.

THE DUPLICATE HYPOTHESIS WAS TESTED FIRST AND REFUTED, which is what makes "raise capacity" the
honest reading rather than the convenient one. If the 203 backlog rows were the same finding
carded repeatedly, de-duplication would be the fix and it would not be "finding less". Measured
over the live backlog at token-set Jaccard >= 0.5: **zero near-duplicate pairs**. The arrivals are
genuinely distinct findings from many organs (07-31: principal 37, deep_sweep 36, cycle 23,
max_audit 19, capability_hunt 18). Detection is working. Conversion is not keeping up.

THE INVERSION THIS MODULE REFUSES TO INHERIT, and it is live in the field it reads. In
``check_conversion.py`` the flag is derived as ``"repair_mode": status != "OK"``, so it is TRUE
for ``ARRIVALS-COLLAPSED`` -- a status whose entire meaning is that the desk is finding too
LITTLE. Forty-two lines above, the same file says so in its own words: "ARRIVALS-COLLAPSED means
find harder." Wiring the actuator to that flag unchanged would have installed a mechanism that
redirects the brain away from finding at the exact moment the fence has determined finding has
collapsed -- L1.25a's fatigue-by-null defect, automated. The status is therefore mapped to a
three-way DIRECTION here and at the source, and ARRIVALS-COLLAPSED maps to FIND-HARDER.

STRUCTURALLY INCAPABLE OF THROTTLING, by the ``libs/execution/excitation.py`` precedent (L1.45),
which has no vocabulary for size so no bug in it can change position sizing. This module has no
vocabulary for STOPPING. Every duty it emits ADDS work; none removes any. That is not a promise
in a docstring -- ``_BANNED_VERBS`` is asserted against every emitted string by
``tests/governance/test_repair_actuator.py``, so a future edit that teaches it to say "pause the
miners" fails a test rather than reaching an organ. It is also what makes the L1.28b(f) exemption
low-stakes rather than load-bearing: the worst case of handing this block to a protected organ is
that a miner spends its first effort disposing rows, which §33 already requires of it.

UNMEASURED OWES WORK (L1.28a). A missing, unreadable or stale artifact yields UNMEASURED, and
UNMEASURED emits a duty -- never silence. The precedent is ``brain_env.sh``'s own ``mine_priority``
fallback: its ``2>/dev/null || true`` once made a broken venv indistinguishable from "nothing owes
a disposition", fail-open, on the gate whose whole job is to stop the desk mining faster than it
converts. "The conversion state could not be read" and "nothing is owed" are different claims and
only one of them is evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.ops.input_provenance import Inputs

_ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT = "data/conversion_status.json"

# The artifact is rewritten by check_conversion.py on the queue-refresh cadence. Older than this
# and the counts describe a desk that no longer exists, so the honest verdict is UNMEASURED
# rather than a confident duty built on yesterday's queue (L1.44: freshness at the READ site).
MAX_AGE_H = 24.0

#: status -> direction. The whole point of the module: these are NOT interchangeable.
#:
#: PUBLIC AND SHARED ON PURPOSE. ``check_conversion.py`` derives its published ``repair_mode`` and
#: ``direction`` fields from this same dict rather than re-deriving the mapping, because the bug
#: this module exists to stop was exactly a second, divergent derivation of it living 42 lines
#: from a comment that stated the correct one.
DIRECTION_FOR_STATUS: dict[str, str] = {
    "FLATLINE": "DRAIN",            # nothing converted at all while a backlog exists
    "REPAIR-MODE": "DRAIN",         # backlog over the line
    "DEBT-GROWING": "DRAIN",        # arrivals outran dispositions this week
    "ARRIVALS-COLLAPSED": "FIND-HARDER",   # the desk is finding too little -- the OPPOSITE defect
    "OK": "STEADY",
}

# L1.28b(f), verbatim in scope: these run at FULL CADENCE UNCONDITIONALLY. Naming them is not a
# switch this module can flip -- it emits no instruction that could reduce them -- it is the
# clause carried INTO the prompt so an organ reading the duty cannot mistake it for a throttle.
_PROTECTED = ("collectors", "recorders", "miners", "diggers", "screens-on-discovery",
              "forward clocks", "fences")

# Asserted against every emitted string by the test suite. A duty that can only ADD work cannot
# become the throttle L1.28b(f) forbids, whatever a later edit intends.
_BANNED_VERBS = ("pause ", "stop ", "throttle", "suspend", "reduce ", "cut ", "slow ",
                 "disable", "skip the", "fewer", "defer mining", "less exploration")


@dataclass(frozen=True)
class RepairDuty:
    """What this brain window owes the conversion queue, and the evidence for it."""

    direction: str          # DRAIN | FIND-HARDER | STEADY | UNMEASURED
    measured: bool
    backlog: int | None
    past_due: list[str]     # NAMES only, and the artifact truncates them to 20
    n_past_due: int | None  # the un-truncated COUNT; never derive this from len(past_due)
    arrivals_7d: int | None
    dispositions_7d: int | None
    oldest_age_days: float | None
    status: str | None
    text: str               # the block injected at organ spawn; "" only when STEADY

    @property
    def owed(self) -> bool:
        """True when this window owes the queue time. STEADY is the only state that owes none."""
        return self.direction != "STEADY"


def _fmt_rows(ids: list[str], total: int | None, limit: int = 12) -> str:
    """Name the rows, and count them from the COUNT -- never from the naming list.

    ``past_due_ids`` in the artifact is ``[r.get("id") for r in past_due][:20]``. Reporting
    ``len()`` of that truncated list as the number of past-due rows would publish 20 for a live
    queue of 67, which is L1.57's own defect -- a count of what the writer wrote down rather than
    of what the run found -- emitted by the actuator built to enforce it. The un-truncated total
    is ``past_due``; the ids are for NAMING, and the "+N more" is derived from the total so it
    cannot understate the queue when the list is capped.
    """
    if not ids:
        return "(none named -- read the ledger for the oldest open rows)"
    shown = ", ".join(ids[:limit])
    n = total if isinstance(total, int) and total >= len(ids) else len(ids)
    return shown if n <= limit else f"{shown} (+{n - limit} more)"


def _drain_text(d: dict[str, Any], past_due: list[str]) -> str:
    n_past_due = d.get("past_due")
    if not isinstance(n_past_due, int):
        n_past_due = len(past_due)
    return (
        f"[L1.28b(d)] REPAIR WINDOW -- THIS WINDOW OWES CONVERSION BEFORE NEW FINDINGS.\n"
        f"  Queue: {d.get('backlog')} rows in backlog, {n_past_due} past grace, oldest "
        f"{d.get('oldest_backlog_age_days')}d. Last 7d: {d.get('arrivals_7d')} raised vs "
        f"{d.get('dispositions_7d')} dispositioned (status {d.get('status')}).\n"
        f"  DRAIN THESE FIRST, each names its own fix: {_fmt_rows(past_due, n_past_due)}\n"
        f"  A REASONED REJECTION IS A CONVERSION (L1.28b(b)) -- implemented with --commit, "
        f"rejected with a real --reason, or scheduled with an enforced --due, via "
        f"scripts/recommendations.py dispose. Silence is the only failure state.\n"
        # WORDED TO CONTAIN NO THROTTLING VERB AT ALL, including negated ones. L1.8's own phrasing
        # ("acquisition is never CUT to meet extraction") would trip `_BANNED_VERBS` -- and that is
        # the guard working, not a false positive: an organ skimming a prompt can read "cut" and
        # miss "never". The check stays dumb and strict; the clause carries the meaning positively.
        f"  THIS ADDS A DUTY AND REMOVES NONE (L1.28b(f)): {', '.join(_PROTECTED)} run at FULL "
        f"CADENCE regardless of this block. Extraction scales UP to meet acquisition, always.")


def _find_harder_text(d: dict[str, Any]) -> str:
    return (
        f"[L1.28b(d)] ARRIVALS COLLAPSED -- THE DEFECT IS FINDING TOO LITTLE, NOT CONVERTING TOO "
        f"LITTLE.\n"
        f"  Last 7d: {d.get('arrivals_7d')} raised against a baseline of "
        f"{d.get('arrivals_baseline_7d')}/week.\n"
        f"  HUNT HARDER THIS WINDOW. Do NOT redirect it to the backlog: a thin week of findings "
        f"is not evidence the ground is picked clean (L1.25a -- a null streak triggers "
        f"ESCALATION, never rest), and raising the conversion ratio by finding less is the "
        f"denominator trick L1.28b(f) forbids.")


def _unmeasured_text(why: str) -> str:
    return (
        f"[L1.28b(d)] CONVERSION STATE UNREADABLE -- {why}\n"
        f"  TREAT THIS AS OWING WORK, NOT AS NOTHING OWING (L1.28a: unmeasured counts as zero). "
        f"Run scripts/check_conversion.py, then work the past-due rows in "
        f"docs/research/recommendation_ledger.json oldest-first before opening new ground.")


def duty(root: Path | None = None, *, now_h: float | None = None) -> RepairDuty:
    """Read the conversion state and return the duty this brain window owes.

    ``now_h`` is unused by callers and exists only so the age check is testable without patching
    the clock; the freshness read itself is done by :class:`Inputs`, which records ABSENT,
    UNREADABLE, STALE and DEFAULTED as DISTINCT states (L1.55) -- collapsing them is how a desk
    debugs the wrong organ.
    """
    ins = Inputs(caller="libs.ops.repair_mode.duty")
    d = ins.read_json((root or _ROOT) / _ARTIFACT, default=None, max_age_h=MAX_AGE_H,
                      required=True)
    # THE CALLER NAMES ITS DEGRADE DIRECTION (L1.44), AND `Inputs` DELIBERATELY DOES NOT DECIDE
    # FOR IT. read_json RECORDS staleness and still RETURNS the parsed data -- correct, because
    # "a stale denylist STILL DENIES" and only the caller knows which way its own artifact should
    # fail. Relying on the default to withhold a stale read is therefore a bug, and it was one
    # here until a test caught a 30-day-old artifact producing a confident DRAIN duty.
    #
    # A conversion artifact fails to UNMEASURED: a month-old queue census is not evidence about
    # today's queue, and naming rows that may already be disposed sends the window to work that
    # does not exist. UNMEASURED still OWES work (L1.28a) and says why -- it is not silence.
    rec = ins.records[-1] if ins.records else None
    if not isinstance(d, dict) or rec is None or rec.status != "READ":
        why = (rec.detail or rec.status) if rec is not None else "no record"
        if rec is not None and rec.status == "STALE":
            why = (f"last written {rec.age_h:.1f}h ago against a {MAX_AGE_H:.0f}h contract -- "
                   f"it describes a queue that may no longer exist")
        return RepairDuty(direction="UNMEASURED", measured=False, backlog=None, past_due=[],
                          n_past_due=None,
                          arrivals_7d=None, dispositions_7d=None, oldest_age_days=None,
                          status=None, text=_unmeasured_text(f"{_ARTIFACT}: {why}."))

    status = str(d.get("status") or "")
    # An UNKNOWN status is not a pass. A future member of the enum reaches here as UNMEASURED and
    # therefore still emits a duty, rather than falling down a `.get(status, "STEADY")` branch
    # into silence -- the `else 0` class R0237 closed for exit codes, closed here for directions.
    direction = DIRECTION_FOR_STATUS.get(status, "UNMEASURED")
    past_due = [str(x) for x in (d.get("past_due_ids") or [])]

    if direction == "DRAIN":
        text = _drain_text(d, past_due)
    elif direction == "FIND-HARDER":
        text = _find_harder_text(d)
    elif direction == "STEADY":
        text = ""
    else:
        text = _unmeasured_text(f"{_ARTIFACT} carries status {status!r}, which this actuator "
                               f"does not recognise.")

    return RepairDuty(
        direction=direction, measured=direction != "UNMEASURED",
        backlog=d.get("backlog"), past_due=past_due,
        n_past_due=d.get("past_due") if isinstance(d.get("past_due"), int) else len(past_due),
        arrivals_7d=d.get("arrivals_7d"), dispositions_7d=d.get("dispositions_7d"),
        oldest_age_days=d.get("oldest_backlog_age_days"), status=status or None, text=text)


def report(root: Path | None = None) -> dict[str, Any]:
    """Machine-readable form, for the fence and for tests."""
    r = duty(root)
    return {"direction": r.direction, "owed": r.owed, "measured": r.measured,
            "status": r.status, "backlog": r.backlog, "past_due": r.n_past_due,
            "past_due_named": len(r.past_due),
            "arrivals_7d": r.arrivals_7d, "dispositions_7d": r.dispositions_7d,
            "oldest_age_days": r.oldest_age_days, "text_chars": len(r.text)}


def main() -> int:
    """Print the injectable duty block. Exit 0 always -- this is a PROMPT PRODUCER, not a gate.

    An organ spawn must never be blocked by the conversion queue's state: L1.37's spawn gate
    "PAGES, IT DOES NOT KILL", because a governance fault that stops the desk is the larger loss
    (L1.2). Whether the desk is BEHIND is judged by ``scripts/check_conversion.py``, which is the
    fence and does exit non-zero. This only decides what the next window is TOLD.
    """
    from libs.ops.lawful import guard as _law_guard  # L1.42: no act exempt

    _law_guard()
    print(duty().text, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
