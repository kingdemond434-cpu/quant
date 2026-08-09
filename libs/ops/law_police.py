"""THE LAW POLICE -- who watches the watchmen, and notices when one stops watching.

WHY THIS EXISTS, and what it catches that sixty existing checks do not.

The desk has a large audit (`scripts/max_audit.py`, ~60 registered checks), a law-coverage fence,
an enforcement matrix and several ratchets. Every one of them answers the same question: *are the
laws being broken today?* None answers the question one level up, which is the one that actually
decides whether the others mean anything:

    IS THE AUDIT STILL LOOKING?

That gap is not theoretical. Three ways a law silently stops being enforced, none of which raises
a single defect today:

  1. A CHECK IS DELETED OR UNREGISTERED. Remove it from CHECKS and the defects it used to raise
     simply stop appearing. The report gets BETTER. Nothing anywhere records the roster, so
     nothing can tell a fixed defect from a deleted detector. Verified 2026-08-05: no file in this
     repo references `len(CHECKS)` or tracks registered check names over time.

  2. A CHECK PASSES VACUOUSLY. Almost every check begins by reading an artifact and returns early
     when it is absent or unreadable. That early return is INDISTINGUISHABLE from a clean pass:
     both raise zero defects. So an artifact that stops being produced silently converts its
     check into a no-op, and the audit reports green forever. `max_audit` already records every
     path each check reads -- the read-probe has existed for weeks -- and NOTHING has ever used it
     to ask whether a check that raised nothing actually evaluated anything (L1.50: an unexploited
     asset is a defect).

  3. A DEFECT DISAPPEARS FOR THE WRONG REASON. "Absent from today's report" is read as fixed. It
     is equally consistent with the detector having gone blind between yesterday and today, which
     is exactly the failure the first two describe.

THE RULE THIS ENFORCES, and it is the desk's own ratchet law turned on its own police:
DELETION IS WEAKENING. A check may be added freely. A check that DISAPPEARS, or that stops
evaluating, is a FALL, and a fall needs a NAMED CAUSE. Unexplained falls page.

THREE STATES PER CHECK, never two (L1.41, the rule this desk keeps re-learning):

    CLEAN            ran, read real evidence, found nothing      -- a genuine all-clear
    DEFECTIVE        ran, found something                        -- the normal working state
    CANNOT-EVALUATE  ran, raised nothing, READ NOTHING           -- NOT a pass; a blind spot
    BROKEN           raised an exception                         -- already caught by max_audit
    VANISHED         was in the roster yesterday, absent today   -- the silent regression

`CANNOT-EVALUATE` is the whole point. It is the state that has been counted as success.

AUTO-CORRECTION IS DELIBERATELY NARROW. The police repairs by RE-RUNNING idempotent measurement
organs -- the ones whose only effect is to rewrite an artifact from current inputs. It never edits
a threshold, never touches a statistical gate, never changes a size or leverage, never deletes
data, and never touches the Tier-3 never-touch list. A police force that can rewrite the law is
not enforcing it. Everything outside the allowlist is REPORTED for a human, which is the correct
authority boundary for a machine that noticed a problem it does not understand.

Pure logic: no I/O, no imports beyond stdlib. The organ is scripts/run_law_police.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AUTO_CORRECTABLE",
    "EVALUATES_IN_MEMORY",
    "NEVER_AUTO_CORRECT",
    "CheckState",
    "diff_roster",
    "grade_check",
    "police",
    "unexplained_falls",
]

# ---------------------------------------------------------------------------------- the states
CLEAN = "CLEAN"
DEFECTIVE = "DEFECTIVE"
CANNOT_EVALUATE = "CANNOT-EVALUATE"
BROKEN = "BROKEN"
VANISHED = "VANISHED"

#: A check reading fewer than this many real paths while raising nothing has not evaluated the
#: desk -- it has evaluated its own absence. One is enough: a check that opened a single artifact
#: and found it healthy is a genuine pass.
_MIN_EVIDENCE_PATHS = 1

#: Checks that legitimately evaluate WITHOUT consulting anything external -- they read the running
#: program itself. `check-registry` enumerates module-level `check_*` callables and compares them
#: against CHECKS; its whole subject is in memory, so it opens no file, shells to nothing and
#: touches no socket. Grading it CANNOT-EVALUATE would be a false alarm on the one check that
#: guarantees every other check is registered, which is exactly the alarm nobody can afford to
#: start ignoring.
#:
#: EVERY ENTRY NEEDS A REASON, and the reason must name WHAT the check evaluates instead. This is a
#: narrow exemption for a measurement artifact, never a way to excuse a genuinely blind check --
#: the two that prompted this list (`bnb-funded`, `fee-carry-ratio`) were NOT added here, they
#: were FIXED to report UNKNOWN, because they really were blind.
EVALUATES_IN_MEMORY: dict[str, str] = {
    "check-registry": ("enumerates module-level check_* callables and compares them to CHECKS -- "
                       "its subject is the running program, so consulting nothing external is "
                       "correct rather than blind"),
}

#: Organs the police may RE-RUN to repair a stale or missing artifact. Every entry must be
#: idempotent, measurement-only, and change no gate, threshold, size or verdict -- re-running it
#: twice must leave the desk exactly as running it once did. The `why` is the audit trail for a
#: machine acting without being asked, and it is required, not decorative.
AUTO_CORRECTABLE: dict[str, dict[str, str]] = {
    "survivor-cells-unconverted": {
        "organ": "scripts/finalize_axis_screens.py",
        "why": ("re-derives verdict_adjusted for every scored cell from the screens on disk. "
                "Pure recomputation: it reads screens and rewrites reports, moves no threshold "
                "and promotes nothing (Stage A has zero promotion authority)."),
    },
    "survivor-clocks-unrun": {
        "organ": "scripts/run_paper_sleeve_forward.py",
        "why": ("publishes each standing paper sleeve's accrual from its own source artifact. "
                "Writes evidence only -- it cannot start, stop or promote a clock."),
    },
    "survivor-accrual-stale": {
        "organ": "scripts/run_paper_sleeve_forward.py",
        "why": ("same organ; a stale accrual artifact is repaired by RECOMPUTING it from its "
                "sources, never by editing the artifact in place."),
    },
}

#: Never auto-corrected, at any severity, for any reason. Matched as substrings against the defect
#: id AND against any organ a repair would run. The first three are the desk's standing security
#: constraints; the rest are decisions that belong to a person.
NEVER_AUTO_CORRECT: tuple[str, ...] = (
    "run_deadman_switch",     # Tier-3 NEVER-TOUCH
    "threshold", "alpha", "gate", "bar",          # never loosen a statistical gate
    "leverage", "size", "sizing", "capital", "allocation",   # R0143 size fence
    "promote", "promotion",   # promotion is Stage B's authority, never a repair
    "delete", "prune", "retire",                  # destruction is never automatic
)


@dataclass(frozen=True)
class CheckState:
    """One check's verdict for one run, with the evidence it actually touched."""

    name: str
    n_defects: int
    n_evidence: int
    raised: bool = False
    state: str = CLEAN
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "n_defects": self.n_defects,
                "n_evidence": self.n_evidence, "raised": self.raised, "why": self.why}


def grade_check(name: str, *, n_defects: int, n_evidence: int, raised: bool = False) -> CheckState:
    """The three-state grade. A check that raised nothing AND read nothing is NOT clean.

    This is the whole instrument. Every check on this desk begins by reading an artifact and
    returns early when it is missing -- so an artifact that quietly stops being produced turns its
    check into a no-op that reports success forever. Counting that as a pass is a fail-OPEN in the
    one place the desk cannot afford one: the layer that decides whether every other layer works.
    """
    if raised:
        return CheckState(name, n_defects, n_evidence, True, BROKEN,
                          "the check itself threw -- a blind checker is a defect")
    if n_defects > 0:
        return CheckState(name, n_defects, n_evidence, False, DEFECTIVE,
                          f"{n_defects} defect(s) found -- the audit working as designed")
    if n_evidence < _MIN_EVIDENCE_PATHS and name in EVALUATES_IN_MEMORY:
        return CheckState(name, n_defects, n_evidence, False, CLEAN,
                          f"evaluates in memory, exempt with reason: {EVALUATES_IN_MEMORY[name]}")
    if n_evidence < _MIN_EVIDENCE_PATHS:
        return CheckState(name, n_defects, n_evidence, False, CANNOT_EVALUATE,
                          "raised nothing AND read nothing -- it evaluated its own absence, not "
                          "the desk. This is a BLIND SPOT reported as an all-clear, and it is the "
                          "state that silently converts a deleted artifact into a passing law.")
    return CheckState(name, n_defects, n_evidence, False, CLEAN,
                      f"read {n_evidence} path(s) and found nothing -- a genuine all-clear")


def diff_roster(prior: dict[str, Any], current: list[CheckState]) -> dict[str, Any]:
    """What changed in the audit's own coverage since the last run. DELETION IS WEAKENING.

    A check may be ADDED freely -- more watching is never a fall. A check that VANISHES from the
    roster, or that falls from CLEAN/DEFECTIVE to CANNOT-EVALUATE, is a FALL and needs a named
    cause. Without this the roster can be quietly emptied one check at a time and every report
    along the way gets better.
    """
    _pr = prior.get("roster")
    prior_roster: dict[str, Any] = _pr if isinstance(_pr, dict) else {}
    now = {c.name: c for c in current}
    vanished = sorted(set(prior_roster) - set(now))
    added = sorted(set(now) - set(prior_roster))

    went_blind: list[dict[str, str]] = []
    for name, c in sorted(now.items()):
        was = str((prior_roster.get(name) or {}).get("state") or "")
        if c.state == CANNOT_EVALUATE and was in (CLEAN, DEFECTIVE):
            went_blind.append({"check": name, "was": was, "now": c.state,
                               "why": ("this check evaluated real evidence on the previous run "
                                       "and read NOTHING on this one -- its input stopped being "
                                       "produced, or it now returns early. The law it enforces is "
                                       "unenforced as of this run, and no defect anywhere says so "
                                       "except this line.")})
    return {
        "vanished": [{"check": n,
                      "why": ("registered on the previous run and absent now. A check that "
                              "disappears takes its defects with it and the report gets BETTER -- "
                              "deletion is weakening, and a fall needs a NAMED CAUSE.")}
                     for n in vanished],
        "added": added,
        "went_blind": went_blind,
        "n_prior": len(prior_roster),
        "n_now": len(now),
    }


def unexplained_falls(diff: dict[str, Any], causes: dict[str, str] | None = None) -> list[str]:
    """Falls with no recorded cause. These are the ones that page.

    A cause is a DECISION someone recorded -- "removed because the law was repealed", "blind
    because the collector is down, ticket #N". Absence of a cause is the default, so a fall that
    nobody explained cannot quietly become the new baseline.
    """
    named = causes or {}
    out = [f"VANISHED {r['check']}" for r in diff.get("vanished", [])
           if r["check"] not in named]
    out += [f"WENT-BLIND {r['check']} ({r['was']} -> {r['now']})"
            for r in diff.get("went_blind", []) if r["check"] not in named]
    return sorted(out)


def _forbidden(text: str) -> str | None:
    low = str(text).lower()
    for token in NEVER_AUTO_CORRECT:
        if token in low:
            return token
    return None


def repairs_for(defect_ids: list[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """(repairs the police MAY run, defects it must REPORT instead).

    The allowlist is by DEFECT ID, not by pattern: a police force that infers its own powers is
    not bounded by them. Every candidate is additionally screened against NEVER_AUTO_CORRECT, so
    an allowlist entry that ever drifts toward a gate, a size or the deadman switch is refused by
    the second fence rather than trusted to the first.
    """
    allowed: list[dict[str, str]] = []
    report_only: list[dict[str, str]] = []
    for did in sorted(set(defect_ids)):
        entry = AUTO_CORRECTABLE.get(did)
        if entry is None:
            report_only.append({"defect": did,
                                "why": "not on the repair allowlist -- reported for a person. A "
                                       "machine that repairs what it does not understand is worse "
                                       "than one that reports it."})
            continue
        hit = _forbidden(did) or _forbidden(entry["organ"])
        if hit:
            report_only.append({"defect": did,
                                "why": f"REFUSED: matches the never-auto-correct token {hit!r}. "
                                       "This is the second fence -- an allowlist entry that "
                                       "drifts toward a gate, a size or the deadman switch is "
                                       "stopped here rather than trusted upstream."})
            continue
        allowed.append({"defect": did, "organ": entry["organ"], "why": entry["why"]})
    return allowed, report_only


@dataclass
class PoliceReport:
    states: list[CheckState] = field(default_factory=list)
    diff: dict[str, Any] = field(default_factory=dict)
    falls: list[str] = field(default_factory=list)
    repairs: list[dict[str, str]] = field(default_factory=list)
    report_only: list[dict[str, str]] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if self.falls:
            return "REGRESSION"
        if any(c.state == BROKEN for c in self.states):
            return "BROKEN-CHECKS"
        if any(c.state == CANNOT_EVALUATE for c in self.states):
            return "BLIND-SPOTS"
        return "WATCHING"


def police(current: list[CheckState], prior: dict[str, Any],
           defect_ids: list[str], causes: dict[str, str] | None = None) -> PoliceReport:
    """One full pass. Pure -- the organ supplies the measurements and performs the repairs."""
    diff = diff_roster(prior, current)
    repairs, report_only = repairs_for(defect_ids)
    return PoliceReport(states=current, diff=diff,
                        falls=unexplained_falls(diff, causes),
                        repairs=repairs, report_only=report_only)
