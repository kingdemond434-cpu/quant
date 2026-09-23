"""A ROW CLOSED AS IMPLEMENTED IS A CLAIM THAT CODE IS IN THE TREE (L2.3/L1.28b, R0742).

`dispose --status implemented --commit <sha>` writes a sha into the ledger and nothing has ever
asked whether that sha is IN THE BRANCH THE DESK RUNS. The two failure modes it separates are not
symmetric: an OPEN row is visible and gets re-handed, while a row closed as implemented is out of
the queue permanently. A false `implemented` is therefore the more expensive error -- it is the one
that removes the work from view -- and it is invisible to every gauge that counts dispositions,
because a closed row is the most ordinary thing in the file.

MEASURED 2026-08-20 over the live ledger: 350 implemented rows cite a sha, 346 are ancestors of the
live branch, and **4 are not** -- R0560, R0561, R0569 and R0573, all citing commits made that
morning on `claude/owed-0820-b7st`, a branch whose 4 commits never merged. The dispositions landed
(the ledger is a tracked file, so the ledger commit merged) while the code they cite did not. So
the desk believed it held four fixes it did not hold, and no reader could have told: the rows say
implemented, they cite a real sha, and `git show <sha>` prints a real diff.

WHY THE LEDGER LANDS WHEN THE CODE DOES NOT, which is the mechanism and not bad luck. Every worker
is ordered into its own worktree (R0423) and told to merge back. The ledger is one file that every
session touches, so it merges early and often through ordinary conflict resolution; the code
commits are separate and merge only if the worker completes its own final step. The two halves of
one disposition travel by different routes, and only one of them has a fence.

THIS COUNTS WHAT IT COULD NOT RESOLVE (L1.60). A sha absent from the object database is NOT a
stranded commit -- on the shallow clone `actions/checkout` produces by default, most history is
simply not present, and reporting that as 350 stranded rows would be a fence crying wolf on its
own environment (L1.43). Unresolvable shas are counted, named and reported separately, and a run
that could resolve nothing reads UNMEASURED rather than OK (L1.28a).

THE REPAIR IS UPWARD AND IS NEVER "RE-OPEN THE ROW" BY DEFAULT. Two states can be true: the work
exists on an unmerged branch (land it -- the fence names the branch and the exact merge command),
or the work is genuinely gone (re-open the row). Only a reader can tell those apart, so this
reports and prescribes; it does not silently rewrite dispositions in either direction.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["LEDGER_REL", "Census", "Stranded", "census"]

LEDGER_REL = "docs/research/recommendation_ledger.json"


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args],
                           capture_output=True, text=True, check=False, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return r.returncode, r.stdout.strip()


@dataclass(frozen=True)
class Stranded:
    """One row whose cited commit is real and is NOT in the measured branch."""

    id: str
    sha: str
    subject: str
    branches: tuple[str, ...]      # branches that DO contain it -- the repair, named

    @property
    def repair(self) -> str:
        if not self.branches:
            return (f"no branch contains {self.sha[:8]} -- the work exists only as a dangling "
                    f"commit; recover it or re-open {self.id}")
        return f"git merge --ff-only {self.branches[0]}"


@dataclass
class Census:
    n_rows: int = 0
    n_implemented: int = 0        # implemented rows citing a sha at all
    n_resolved: int = 0           # ...of those, shas this repo can actually see
    n_unresolvable: int = 0       # counted, never silently dropped (L1.60)
    unresolvable_ids: tuple[str, ...] = ()
    stranded: tuple[Stranded, ...] = ()
    ref: str = ""
    shallow: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """OK | STRANDED | UNMEASURED."""
        if not self.n_resolved:
            return "UNMEASURED"
        return "STRANDED" if self.stranded else "OK"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ref": self.ref,
            "shallow": self.shallow,
            "n_rows": self.n_rows,
            "n_implemented_with_sha": self.n_implemented,
            "n_resolved": self.n_resolved,
            "n_unresolvable": self.n_unresolvable,
            "unresolvable_ids": list(self.unresolvable_ids),
            "n_stranded": len(self.stranded),
            "stranded": [{"id": s.id, "sha": s.sha, "subject": s.subject,
                          "branches": list(s.branches), "repair": s.repair}
                         for s in self.stranded],
            "notes": self.notes,
        }


def rows_of(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("recommendations") or payload.get("rows") or []
    return [r for r in payload if isinstance(r, dict)]


def census(root: Path, *, ref: str = "HEAD") -> Census:
    """Which implemented rows cite a commit that is not in `ref`?

    `ref` defaults to HEAD, so the subject is always THE TREE BEING MEASURED. Run from the main
    checkout it asks "does the desk hold what its ledger claims"; run from a worker's branch it
    asks the same question of that branch, which is the right question at pre-push time.
    """
    cen = Census(ref=ref)
    try:
        payload = json.loads((root / LEDGER_REL).read_text("utf-8"))
    except (OSError, ValueError) as exc:
        cen.notes.append(f"ledger unreadable ({type(exc).__name__}) -- nothing could be compared")
        return cen

    rows = rows_of(payload)
    cen.n_rows = len(rows)
    rc, _ = _git(root, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if rc != 0:
        cen.notes.append(f"ref {ref!r} does not resolve -- no branch to measure against")
        return cen
    _, sh = _git(root, "rev-parse", "--is-shallow-repository")
    cen.shallow = sh.strip() == "true"

    stranded: list[Stranded] = []
    unresolvable: list[str] = []
    for r in rows:
        if str(r.get("status", "")).lower() != "implemented":
            continue
        raw = r.get("commit")
        if not raw or not isinstance(raw, str):
            continue
        # A row may cite several shas or trailing prose; the first token is the disposition's sha.
        sha = raw.split()[0].strip().strip(",;")
        if len(sha) < 7:
            continue
        cen.n_implemented += 1
        rc, _ = _git(root, "cat-file", "-e", f"{sha}^{{commit}}")
        if rc != 0:
            # NOT a stranded commit: on a shallow clone the object is simply absent. Counted and
            # named so "I could not look" never renders as "I looked and it was fine".
            cen.n_unresolvable += 1
            unresolvable.append(str(r.get("id", "?")))
            continue
        cen.n_resolved += 1
        rc, _ = _git(root, "merge-base", "--is-ancestor", sha, ref)
        if rc == 0:
            continue
        _, subject = _git(root, "log", "-1", "--format=%s", sha)
        _, br = _git(root, "branch", "--format=%(refname:short)", "--contains", sha)
        branches = tuple(b.strip() for b in br.splitlines() if b.strip())
        stranded.append(Stranded(id=str(r.get("id", "?")), sha=sha,
                                 subject=subject[:120], branches=branches))

    cen.stranded = tuple(stranded)
    cen.unresolvable_ids = tuple(unresolvable)
    if cen.shallow and cen.n_unresolvable:
        cen.notes.append(
            f"shallow clone: {cen.n_unresolvable} sha(s) are not in the object database here, "
            "which is expected and is NOT evidence of anything -- run this on a full clone")
    return cen
