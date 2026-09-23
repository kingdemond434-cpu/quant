"""A DISPOSITION THAT A MERGE CAN REVERT IS NOT A DECISION, IT IS A DRAFT.

``scripts/recommendations.py`` defends the recommendation ledger against exactly two writers and
believes that is all of them:

* ``dispose()`` refuses a row already terminal -- *"dispositions do not revert. If it was
  MISFILED, use `correct`"* -- so no CLI call can un-decide a row without leaving history;
* ``_locked()`` takes an flock around every read-modify-write, added after two live sessions'
  interleaved calls *"destroyed three rows and reverted two dispositions FIVE separate times in
  one day"* (R0623).

**Neither one reaches ``git merge``.** A merge writes this file without taking the flock, without
calling ``dispose()``, and without consulting ``_TERMINAL`` -- and when a stale side wins, every
disposition on the other side silently becomes ``open`` again. The guard is real, the lock is
real, and the busiest writer on this desk walks straight past both.

WHY NO EXISTING INSTRUMENT COULD SEE IT, WHICH IS THE WHOLE POINT. Every ledger gauge here is a
COUNT -- ``report`` prints totals, ``drain`` measures raised-vs-dispositioned, ``check_conversion``
reads the backlog depth, and the ledger law's loudest rule is that rows must never be MASS
DELETED. A reverting merge deletes nothing. Measured on merge ``a9c13de1`` (2026-08-20): it
reverted **51 dispositions in one commit** while the row count went **714 -> 719**, i.e. UP. Every
count-based check read healthy, the corrupted rows re-entered the owed-work queue as fresh
backlog, and the very next worker session (``72cd67bb``) re-did three of them -- R0495, R0496,
R0497 -- work that was already finished and cited. That is the cost this module exists to stop:
not lost rows, lost DECISIONS, which look exactly like new work to everyone downstream.

THE ASYMMETRY THAT MAKES IT EXPENSIVE. A reverted disposition does not fail loudly and does not
even look wrong: it looks like an open row, which is the single most normal thing in this ledger.
It then consumes a worker's whole session, and the second worker's conclusions are usually
IDENTICAL to the first's, so nothing in the output ever reveals the duplication. Compare that to
the mass-deletion the ledger law does guard: a row that vanishes is visible the moment anyone
counts. **The desk fenced the failure mode that announces itself and left the silent one open.**

WHAT IS MEASURED, AND WHY IT IS EXACT RATHER THAN A HEURISTIC. Two invariants, because the merge
broke the ledger in two different places and the first check alone misses half of it.

**STATUS.** Rows are APPEND-ONLY and dispositions are one-way, so for a row that is ``open`` at
HEAD, finding it terminal-or-scheduled anywhere in the file's history is a contradiction with
exactly one innocent explanation -- ``correct()``, which re-opens a MIS-ENTERED disposition and
records why in the row's own ``corrections`` list::

    open at HEAD  AND  disposed in history  AND  no ``corrections`` entry  =  REVERTED

Thirteen rows carry real ``corrections`` history, so that exclusion is load-bearing rather than
decorative: without it the fence would flag legitimate corrections and be acked into silence
inside a day (L1.43).

**HISTORY.** The status check only looks at rows that are open NOW, and the same merge also
reverted rows that stayed disposed -- so they never enter the first test. ``correct()``,
``repoint()`` and this module's own repair all APPEND to a per-row list and never rewrite one, so
those lists can only grow, and a list that is SHORTER at HEAD than some ancestor published is a
reverted edit however healthy the status looks::

    len(row[list]) at HEAD  <  len(row[list]) in history      =  REVERTED

Measured desk-wide over all 423 versions: exactly THREE hits, all real, all from the same merge,
zero false positives -- R0042 lost a ``repoint`` (so its citation silently points at the
superseded commit again) and R0050 lost a ``correction`` (so it reverted from ``done`` back to
``implemented`` citing the literal string ``'HEAD'``). That second one is not cosmetic: it is why
``check_citation_integrity`` sits at exit 2 desk-wide right now, its ``_FLOOR = 0`` having been
earned by ledger edits a merge then destroyed. **A fence left permanently red by a silent data
loss is how a real gate becomes one everybody has learned to ignore.**

FULL HISTORY, NOT A WINDOW, AND THE COST WAS MEASURED BEFORE CHOOSING. 423 ledger versions, 245 MB
of blobs, **2.19 s CPU** (best of three; wall clock runs 3-7 s on this box, which hosts 40+
worktrees and a cron fleet) through a single ``git cat-file --batch``. A bounded window would have
been faster and would have re-created the defect one level up: a reversion older than the window
falls out of the denominator and the fence reports OK -- the shrinking-denominator failure
(L1.60/L1.65) inside the instrument built to catch a shrinking record. The window exists as a flag
so a future slow clone can bound it, and when it bites it is PUBLISHED (``truncated``) rather than
quietly applied.

UNREADABLE VERSIONS ARE COUNTED, NEVER SKIPPED (L1.60). Four of the 423 versions do not parse --
they are the torn-tail and merge-conflict states this ledger has actually been committed in. A
version that cannot be read is not evidence of absence, so it is counted into ``n_unreadable`` and
published beside the verdict; a run that reads NOTHING is UNMEASURED, never OK (L1.28a).

WHAT THIS DOES NOT DO. It never disposes a row, never changes a status the ledger has not already
recorded in its own history, and has no vocabulary for deciding anything. ``repair_plan`` restores
the exact bytes a prior commit already published -- status, reason, commit, due -- and stamps the
restoration into the row so a reader can always see that it happened. Re-deriving a disposition
would be manufacturing one; this only puts back what the desk already decided and a merge dropped.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: The ledger path, relative to the repo root. One constant so the fence, the repair and the
#: history walk can never disagree about which file they are talking about.
LEDGER_REL = "docs/research/recommendation_ledger.json"

#: Every status that means "this row has been decided". ``scheduled`` is included deliberately:
#: `dispose --status scheduled --due` is a disposition under L1.28b(b), it clears the owed-work
#: queue, and a merge that reverts it costs a worker exactly as much as reverting `implemented`.
#: (`check_row_atomicity` excludes `scheduled` for a DIFFERENT question -- whether a row ever
#: CONVERTED -- and both are right for what they ask.)
DISPOSED: frozenset[str] = frozenset(
    {"implemented", "rejected", "scheduled", "done", "screened"})

#: Fields `dispose()` writes. These and only these are restored by a repair -- never the summary,
#: never the source, never anything a later commit may legitimately have edited.
_DISPOSITION_FIELDS = ("status", "reason", "commit", "due", "disposed")

#: Per-row lists that the CLI only ever APPENDS to -- `correct()` -> corrections, `repoint()` ->
#: repoints, `repair_plan()` -> restorations. Because no verb rewrites one, "shorter than an
#: ancestor published" is a reverted edit and not a judgement call.
_APPEND_ONLY = ("corrections", "repoints", "restorations")


@dataclass(frozen=True)
class Reversion:
    """One row whose decision history HEAD has less of than an ancestor published."""

    id: str
    kind: str
    """STATUS (disposed in history, open at HEAD) or HISTORY (an append-only list shrank)."""
    was: str
    """The disposition that was reverted -- the most recent one history recorded."""
    at: str
    """The newest commit sha that still carried it."""
    detail: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    """The row's fields as that commit published them, for the repair."""

    def as_row(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "was": self.was, "at": self.at,
                "detail": self.detail, "commit": self.fields.get("commit"),
                "reason": (self.fields.get("reason") or "")[:160]}


@dataclass(frozen=True)
class Census:
    """The verdict plus every number needed to judge whether it was earned."""

    status: str
    reversions: list[Reversion]
    n_rows: int
    """DENOMINATOR (L1.57): rows at HEAD actually compared against history.

    ROWS, not OPEN ROWS, and the difference is not pedantic. ``n_open`` was the first choice and
    the fence's own test caught it: dispose every row and the open count reaches zero, the
    denominator is vacuous, and the fence goes RED for having achieved exactly what it exists to
    encourage. That is L1.53(4) -- "whenever a gauge can be improved by doing less of the thing it
    exists to encourage, its denominator is a first-class measurement" -- pointed the other way,
    and it would have shipped. Every row is compared (the HISTORY invariant reads all of them), so
    every row is the denominator; only a ledger with NO rows is genuinely vacuous.
    """
    n_open: int
    n_versions_read: int
    n_versions_attempted: int
    """ATTRITION (L1.60): a version that could not be read is counted, never dropped."""
    n_unreadable: int
    oldest_examined: str
    truncated: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "n_reverted": len(self.reversions),
            "reverted": [r.as_row() for r in self.reversions],
            "n_rows": self.n_rows,
            "n_open": self.n_open,
            "n_versions_read": self.n_versions_read,
            "n_versions_attempted": self.n_versions_attempted,
            "n_unreadable": self.n_unreadable,
            "oldest_examined": self.oldest_examined,
            "truncated": self.truncated,
        }


def rows_of(payload: object) -> list[dict[str, Any]]:
    """Rows out of either ledger shape, and [] for anything that is not one.

    The ledger is ``{"recommendations": [...]}`` today and was a bare list earlier in its life;
    both appear in the history this walks, so both are read rather than one being assumed.
    """
    rows = payload.get("recommendations") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)]


def _batch(root: Path, revs: list[str]) -> list[tuple[str, bytes]]:
    """Stream every version's blob through ONE ``git cat-file --batch``.

    One process for 423 blobs rather than 423 processes: measured 3.06 s against 1.9 s for just
    60 versions spawned individually, which is what made a full-history walk affordable at all.
    A rev whose blob git declines to emit is simply absent from the result and is accounted for
    by the caller against ``n_versions_attempted`` -- it is never silently equated to an empty
    ledger, which would resolve absence into a clean verdict (L1.28a).
    """
    if not revs:
        return []
    spec = "".join(f"{r}:{LEDGER_REL}\n" for r in revs)
    try:
        proc = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
                              input=spec.encode(), capture_output=True, timeout=180, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    out, blobs, i = proc.stdout, [], 0
    for rev in revs:
        nl = out.find(b"\n", i)
        if nl < 0:
            break
        header = out[i:nl].split()
        # "<sha> missing" -- a real answer, and a different one from "empty". Stop rather than
        # mis-align every remaining blob against the wrong rev.
        if len(header) < 3 or not header[2].isdigit():
            break
        size = int(header[2])
        blobs.append((rev, out[nl + 1:nl + 1 + size]))
        i = nl + 1 + size + 1
    return blobs


def ledger_versions(root: Path, max_commits: int = 0) -> tuple[list[tuple[str, bytes]], int]:
    """Every committed version of the ledger, newest first, with the count ATTEMPTED.

    Returns ``(versions, n_attempted)``. The two numbers are returned separately on purpose: a
    walk that asked for 423 versions and got 419 has lost four, and reporting only ``len()``
    would publish a denominator that shrank in silence (L1.60).
    """
    cmd = ["git", "log", "--format=%H"]
    if max_commits > 0:
        cmd.append(f"--max-count={max_commits}")
    cmd += ["--", LEDGER_REL]
    try:
        revs = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              timeout=60, check=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return [], 0
    return _batch(root, revs), len(revs)


def census(root: Path, max_commits: int = 0,
           head_rows: list[dict[str, Any]] | None = None) -> Census:
    """Rows open at HEAD that this ledger's own history says were already decided.

    ``head_rows`` is injectable so the detector can be driven against a constructed ledger in a
    test without a repo -- and so its positive control proves it FINDS a planted reversion rather
    than merely staying quiet (the desk's standing rule: a detector whose only observed behaviour
    is silence has not been validated).
    """
    if head_rows is None:
        try:
            head_rows = rows_of(json.loads((root / LEDGER_REL).read_text("utf-8")))
        except (OSError, ValueError):
            head_rows = []
    head_by_id = {r["id"]: r for r in head_rows}
    open_now = {i: r for i, r in head_by_id.items() if r.get("status") == "open"}

    versions, attempted = ledger_versions(root, max_commits)
    unreadable = 0
    # Newest first, so the FIRST disposition seen for an id is the most recent one history
    # recorded -- which is the one a repair must put back.
    last_disposed: dict[str, tuple[str, dict[str, Any]]] = {}
    # id -> (total append-only entries, rev, that version's row) for the RICHEST history seen.
    richest: dict[str, tuple[int, str, dict[str, Any]]] = {}
    for rev, blob in versions:
        try:
            payload = json.loads(blob)
        except ValueError:
            unreadable += 1        # counted, not skipped: a torn ledger is not an empty one
            continue
        for row in rows_of(payload):
            rid = row["id"]
            if rid in open_now and rid not in last_disposed:
                status = row.get("status")
                if isinstance(status, str) and status in DISPOSED:
                    last_disposed[rid] = (
                        rev, {k: row.get(k) for k in _DISPOSITION_FIELDS})
            # A row absent from HEAD cannot have lost history AT HEAD; that is a deleted row,
            # a different defect with a different repair. (Skipping the ~99% of rows with no
            # history lists at all was tried and measured worth nothing -- 2.22s vs 2.19s CPU
            # over the full walk -- because json.loads of 245 MB dominates everything here. The
            # simpler loop is kept.)
            if rid not in head_by_id:
                continue
            depth = sum(len(row.get(k) or []) for k in _APPEND_ONLY)
            if depth > richest.get(rid, (0, "", {}))[0]:
                richest[rid] = (depth, rev, row)

    reversions = [
        Reversion(id=rid, kind="STATUS", was=str(fields.get("status")), at=rev, fields=fields,
                  detail=f"{fields.get('status')} in {rev[:8]}, open at HEAD")
        for rid, (rev, fields) in sorted(last_disposed.items())
        # `correct()` is the ONE legitimate way a disposition becomes open again, and it always
        # leaves the prior decision in the row's own history. Without this the fence would fire
        # on 13 honest corrections and be acked into silence inside a day (L1.43).
        if not open_now[rid].get("corrections")
    ]
    for rid, (depth, rev, row) in sorted(richest.items()):
        here = sum(len(head_by_id[rid].get(k) or []) for k in _APPEND_ONLY)
        if here >= depth:
            continue
        lost = ", ".join(
            f"{k} {len(row.get(k) or [])}->{len(head_by_id[rid].get(k) or [])}"
            for k in _APPEND_ONLY
            if len(row.get(k) or []) > len(head_by_id[rid].get(k) or []))
        reversions.append(Reversion(
            id=rid, kind="HISTORY", was=str(row.get("status")), at=rev,
            detail=f"{lost} (append-only lists cannot shrink)",
            fields={k: row.get(k) for k in (*_DISPOSITION_FIELDS, *_APPEND_ONLY)}))

    n_read = len(versions) - unreadable
    if n_read == 0:
        # Nothing was compared, so nothing can be cleared. "We could not look" and "there is
        # nothing there" are different claims and only one of them is evidence (L1.28a).
        status = "UNMEASURED"
    elif reversions:
        status = "REVERTED"
    else:
        status = "OK"
    return Census(
        status=status, reversions=reversions, n_rows=len(head_by_id), n_open=len(open_now),
        n_versions_read=n_read, n_versions_attempted=attempted, n_unreadable=unreadable,
        oldest_examined=versions[-1][0] if versions else "",
        truncated=bool(max_commits) and attempted >= max_commits)


def repair_plan(cen: Census, rows: list[dict[str, Any]],
                stamp: str) -> list[dict[str, Any]]:
    """Mutate ``rows`` in place, restoring each reverted disposition exactly as history had it.

    Every restoration is APPENDED to the row's ``restorations`` list before the fields are put
    back, for the same reason ``correct()`` keeps its history and ``repoint()`` keeps its old
    pointer: what stops a ledger being laundered is not immovability but VISIBILITY. A reader
    seeing ``restorations`` learns that this decision was made once, dropped by a merge, and put
    back -- which is the true story and is strictly more than the ledger could say before.

    Returns the rows it touched. A reversion whose row has vanished from HEAD is NOT invented
    back: that is a different defect (a deleted row) with a different repair, and quietly
    re-creating it here would hide it.
    """
    by_id = {r["id"]: r for r in rows if isinstance(r.get("id"), str)}
    touched = []
    for rev in cen.reversions:
        row = by_id.get(rev.id)
        if row is None:
            continue
        # The lost history goes back FIRST, so the stamp below lands on top of it rather than
        # being overwritten by the restore -- the note about the repair is itself part of the
        # record it is repairing.
        for key in _APPEND_ONLY:
            had = rev.fields.get(key)
            if isinstance(had, list) and len(had) > len(row.get(key) or []):
                row[key] = had
        row.update({k: v for k, v in rev.fields.items() if k in _DISPOSITION_FIELDS})
        row.setdefault("restorations", []).append(
            {"was": rev.kind, "restored_to": rev.was, "from_commit": rev.at, "at": stamp,
             "why": f"{rev.detail}; reverted by a merge that bypassed dispose()'s "
                    "one-way guard and the CLI flock, restored from this ledger's own history"})
        touched.append(row)
    return touched
