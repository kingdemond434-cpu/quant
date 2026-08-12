"""WHY IS THIS FORWARD CLOCK NOT ACCRUING? -- the question nothing on the desk was asking.

MEASURED 2026-08-12. All 12 forward slots are occupied. `accruing` is ZERO. Every sleeve on the
roster reads NO-EVIDENCE at 162.7 hours old, against a 36h staleness threshold. Behind them, the
paper-sleeve spawner holds 26 QUEUED Stage-A survivors it cannot start, because the cohort is at
the Holm cap of 12 and spawning over cap would understate nothing but would break the
fixed-for-life forward bar those 12 were admitted under.

So the desk's only path from research to capital is fully subscribed by clocks that are producing
no evidence, and 26 candidates are waiting behind them. That is L1.50 -- an unexploited asset is a
defect -- landing on the single most load-bearing pipeline there is.

WHAT WAS MISSING IS NOT A RETIREMENT BUTTON. `run_paper_sleeve_forward` already says, per sleeve,
"no rows added since the baseline -- the source artifact has not been regenerated". What nothing
asked is the NEXT question, and it is the one that separates four completely different situations
that all look identical in that sentence:

    PRODUCER_UNSCHEDULED  nothing in the scheduler regenerates this clock's origin artifact. The
                          clock is BORN DEAD: its inputs may accumulate forever and its `n` will
                          never move, on this box or any other. This is a BUILD defect and the
                          repair is to schedule the producer -- never to retire the clock, which
                          would throw away a real candidate to hide a missing cron line.
    SOURCE_STALE_HERE     a producer IS scheduled; this box simply has not run it. On an ephemeral
                          container that is the NORMAL state and says nothing about the desk. This
                          distinction is the whole reason this module exists rather than a grep:
                          without it, every container run would diagnose the desk as dead.
    SOURCE_FROZEN         the producer is scheduled AND has run recently, and `n` still has not
                          moved. Then the screen's window is fixed rather than expanding, and the
                          clock is STRUCTURALLY incapable of accruing however long it waits.
    ACCRUING              rows are being added. Nothing to do.

WHY THIS MODULE HAS NO AUTHORITY TO RETIRE ANYTHING, stated because the temptation is obvious and
the direction is forbidden. `slot_registry` is explicit: "a dormant clock is counted until it is
RETIRED by an explicit ledgered decision -- over-counting only tightens the bar (the safe error),
under-counting admits noise as edge." Retirement SHRINKS m and LOOSENS every standing clock's Holm
bar. An organ that auto-retired dead clocks to free slots would be an organ that automatically
loosens statistical gates whenever the desk gets impatient, which is precisely how a queue of 26
candidates becomes a machine for manufacturing survivors.

So this REPORTS, with enough evidence attached that the ledgered decision has something to decide
on. The bottleneck was never that the decision was hard -- it is that nothing ever triggered it.
"""
from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["ClockHealth", "assess", "producer_for", "report"]

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = "ops/crontab.manifest"

#: A producer that has not run in this long, on a box that schedules it daily, has missed a cycle.
#: Deliberately generous: the point is to catch a DEAD producer, not to page on one late run.
PRODUCER_STALE_H = 48.0

#: How long a clock may sit at zero rows added, with a producer that IS running, before the
#: honest reading flips from "early" to "this window does not expand". Three producer cycles.
FROZEN_AFTER_H = 72.0


@dataclass
class ClockHealth:
    """One forward clock, and the reason it is or is not accruing."""

    name: str
    origin_artifact: str
    state: str = "UNKNOWN"
    rows_added: float | None = None
    age_h: float | None = None
    producer: str = ""
    producer_scheduled: bool = False
    producer_ran_h_ago: float | None = None
    why: str = ""
    repair: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def can_ever_accrue(self) -> bool:
        """False ONLY when the defect is structural. UNKNOWN is never False -- an unmeasured clock
        is not a dead one, and treating it as dead is how a real candidate gets retired to tidy a
        report."""
        return self.state not in ("PRODUCER_UNSCHEDULED", "SOURCE_FROZEN")

    @property
    def blocks_a_slot(self) -> bool:
        """It occupies a slot AND cannot use it. This is the set the ledgered decision is about."""
        return not self.can_ever_accrue


def producer_for(artifact: str, root: Path | None = None) -> tuple[str, bool]:
    """(script that writes `artifact`, is it scheduled). ("", False) when nothing writes it.

    SCORED, NOT FIRST-MATCH, and the first draft of this got it wrong in the silent direction. It
    matched on the artifact path appearing anywhere in a script and took the first hit, so the
    liquidation-reversion screen's artifact resolved to `finalize_axis_screens.py` -- which walks
    that directory and rewrites `verdict_adjusted` into files that already exist. A REWRITER, not
    a row producer. It is scheduled, so the clock came back healthy while
    its real producer (`screen_liquidation_reversion.py`) was on no cron line at all. The detector
    said "fine" about the one genuinely dead clock in the set.

    Two things fix it. The artifact's own STEM TOKENS must appear in the candidate's name, so a
    directory-walker cannot claim a file it never names; and candidates are SCORED, so the script
    that echoes the artifact wins over one that merely touches its folder. A literal path match is
    not required, because a producer that composes its filename in an f-string -- which is exactly
    what the missing one does -- contains no literal to find.
    """
    base = root or _ROOT
    stem = artifact.split("/")[-1].replace(".json", "").replace(".jsonl", "")
    toks = [t.lower() for t in re.split(r"[_\-.]", stem) if len(t) > 3]
    manifest = ""
    with contextlib.suppress(OSError):
        manifest = (base / _MANIFEST).read_text("utf-8", errors="ignore")

    best, best_score = "", 0
    for p in sorted((base / "scripts").glob("*.py")):
        try:
            body = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if not re.search(r"(write_text|json\.dump|to_json|to_parquet)", body):
            continue        # it never writes anything; it cannot be a producer
        name = p.stem.lower()
        # THE NAME IS THE EVIDENCE. A script that does not name what the artifact is called is a
        # walker of its directory, not its author.
        overlap = sum(1 for t in toks if t in name)
        if not overlap:
            continue
        score = overlap * 10
        if artifact in body or stem in body:
            score += 5                       # a literal path is corroboration, never the test
        if name.startswith(("screen_", "run_", "build_", "fit_", "collect_")):
            score += 2
        if name.startswith(("finalize_", "check_", "audit_", "report_")):
            score -= 6                       # annotators rewrite rows; they do not add any
        if score > best_score:
            best, best_score = p.name, score
    if not best:
        return "", False
    scheduled = any(best in ln and (ln[:1].isdigit() or ln.startswith("SYSTEMD"))
                    for ln in manifest.splitlines())
    return best, scheduled


def _mtime_h(path: Path) -> float | None:
    try:
        return (datetime.now(tz=UTC).timestamp() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


def assess(name: str, row: dict[str, Any], *, root: Path | None = None) -> ClockHealth:
    """Classify one sleeve row as produced by `run_paper_sleeve_forward.run()["sleeves"]`."""
    base = root or _ROOT
    artifact = str(row.get("origin_artifact") or "")
    rows_added = row.get("rows_added")
    age_h = None
    try:
        start = datetime.fromisoformat(str(row["shadow_start"]))
        age_h = (datetime.now(tz=UTC) - start).total_seconds() / 3600.0
    except (KeyError, TypeError, ValueError):
        age_h = None

    h = ClockHealth(name=name, origin_artifact=artifact, rows_added=rows_added, age_h=age_h)
    if not artifact:
        h.state = "UNKNOWN"
        h.why = "the sleeve declares no origin artifact, so nothing can say whether it could accrue"
        h.repair = "give the state file an origin_artifact -- an unattributable clock is unaudita"\
                   "ble in both directions"
        return h

    h.producer, h.producer_scheduled = producer_for(artifact, base)
    h.producer_ran_h_ago = _mtime_h(base / artifact)

    if rows_added is not None and float(rows_added) > 0:
        h.state = "ACCRUING"
        h.why = f"{float(rows_added):g} out-of-sample row(s) added since baseline"
        return h

    if not h.producer:
        h.state = "PRODUCER_UNSCHEDULED"
        h.why = (f"NOTHING on this desk writes {artifact}. The clock's `n` cannot move, on this "
                 "box or any other -- it was born unable to finish")
        h.repair = (f"find or write the producer for {artifact} and schedule it; retiring the "
                    "clock would discard a real candidate to hide a missing organ")
        return h

    if not h.producer_scheduled:
        h.state = "PRODUCER_UNSCHEDULED"
        h.why = (f"{h.producer} writes {artifact} but appears on NO cron or systemd line, so the "
                 "artifact is never regenerated and this clock's `n` is frozen for life. Its "
                 "inputs may be accumulating perfectly -- nothing turns them into rows")
        h.repair = (f"schedule {h.producer} in {_MANIFEST}. This is a BUILD defect and costs one "
                    "cron line; it is never a reason to retire the clock")
        return h

    # Producer exists and is scheduled. Now: has it actually RUN, and did `n` still not move?
    ran = h.producer_ran_h_ago
    if ran is None:
        h.state = "SOURCE_STALE_HERE"
        h.why = (f"{artifact} is absent on THIS box while {h.producer} is scheduled -- this "
                 "describes the container, not the desk")
        h.repair = "read the VPS mirror (scripts/sync_desk_state.py) before drawing any conclusion"
        return h
    if ran > PRODUCER_STALE_H:
        h.state = "SOURCE_STALE_HERE"
        h.why = (f"{h.producer} is scheduled but {artifact} is {ran / 24:.1f} days old here. On an "
                 "ephemeral container that is the NORMAL state -- a reset reverts tracked files "
                 "and leaves data/ as a fossil layer -- and says nothing about the VPS")
        h.repair = ("confirm against the VPS before acting; if the VPS shows the same age, the "
                    f"scheduled {h.producer} is failing and THAT is the defect")
        return h
    if age_h is not None and age_h > FROZEN_AFTER_H:
        h.state = "SOURCE_FROZEN"
        h.why = (f"{h.producer} ran {ran:.1f}h ago and this clock is {age_h / 24:.1f} days old, "
                 "and `n` has still not moved. The screen's window is FIXED rather than expanding, "
                 "so waiting longer cannot help -- the clock is structurally unable to resolve")
        h.repair = (f"make {h.producer} write an expanding window, or record a ledgered retirement "
                    "for this clock -- and note that retirement SHRINKS m and loosens every "
                    "standing bar, so it is a decision with an owner, never an automatic sweep")
        return h

    h.state = "TOO_EARLY"
    h.why = (f"{h.producer} ran {ran:.1f}h ago and no rows have been added yet; the clock is "
             f"{(age_h or 0) / 24:.1f} days old, inside the {FROZEN_AFTER_H / 24:.0f}-day window "
             "where zero rows is still ordinary")
    return h


def report(sleeves: dict[str, dict[str, Any]] | None = None, *,
           root: Path | None = None) -> dict[str, Any]:
    """Every standing clock, why it is idle, and what would actually repair it.

    Returns ONLY a reading. No slot is freed, no clock is retired, no bar moves.
    """
    base = root or _ROOT
    if sleeves is None:
        sleeves = _live_sleeves(base)

    rows = [assess(name, row, root=base) for name, row in sorted(sleeves.items())]
    by_state: dict[str, list[str]] = {}
    for r in rows:
        by_state.setdefault(r.state, []).append(r.name)

    blocked = [r for r in rows if r.blocks_a_slot]
    fixable = [r for r in blocked if r.state == "PRODUCER_UNSCHEDULED"]
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "n_clocks": len(rows),
        "accruing": len(by_state.get("ACCRUING", [])),
        "by_state": {k: sorted(v) for k, v in sorted(by_state.items())},
        "slots_blocked_by_a_clock_that_cannot_accrue": len(blocked),
        "repairable_by_scheduling_a_producer": [
            {"clock": r.name, "artifact": r.origin_artifact, "producer": r.producer,
             "repair": r.repair} for r in fixable],
        "clocks": [{"name": r.name, "state": r.state, "origin_artifact": r.origin_artifact,
                    "producer": r.producer, "producer_scheduled": r.producer_scheduled,
                    "rows_added": r.rows_added, "age_h": None if r.age_h is None
                    else round(r.age_h, 1), "why": r.why, "repair": r.repair} for r in rows],
        "authority": "MEASUREMENT ONLY. This organ frees no slot and retires no clock. Retirement "
                     "shrinks the Holm m and LOOSENS every standing clock's bar, so it stays an "
                     "explicit ledgered decision with an owner (slot_registry). What was missing "
                     "was never the decision -- it was anything that triggered it.",
        "why_it_matters": "a clock that cannot accrue still occupies one of 12 forward slots, and "
                          "the spawner is holding queued Stage-A survivors behind it",
    }


def _live_sleeves(root: Path) -> dict[str, dict[str, Any]]:
    """The forward runner's own view, so there is ONE definition of what a clock is doing."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "_psf", root / "scripts/run_paper_sleeve_forward.py")
        if not (spec and spec.loader):
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return dict(mod.run(root=root).get("sleeves") or {})
    except (OSError, ValueError, ImportError, AttributeError, KeyError, json.JSONDecodeError):
        return {}
