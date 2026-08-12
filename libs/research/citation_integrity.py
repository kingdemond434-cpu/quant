#!/usr/bin/env python3
"""LEDGER CITATION INTEGRITY (L2.3/§42, R0369) -- does the proof-of-work resolve?

WHY THIS EXISTS. `recommendations.py dispose --status implemented` REQUIRES `--commit`, on the
desk's standing rule that an artifact proves the work and never a claim. That makes the commit
field the ledger's entire proof mechanism: it is the one place a reader can go from "this row
says it was implemented" to the diff that implemented it. Nothing had ever checked that the
pointer resolves, so the guarantee was enforced at WRITE time (the CLI refuses an empty
--commit) and never at READ time, which is where it is spent.

THE FAILURE R0369 REPORTED, and it is real: a rebase rewrites SHAs. Three rows were disposed
citing a4054a8/5b0cb81/3abe48b, the branch was rebased onto origin because a sibling had pushed
to it, and all three citations became orphaned local objects that no other clone can resolve and
that `git gc` will eventually delete. The failure is silent and gets WORSE with time.

THE MEASUREMENT FOUND SOMETHING BIGGER, which is why the row asked for the fence before the fix.
Over 225 citing rows: 10 cite the literal string `HEAD` and 4 cite `pending`/`pending-this-commit`.
Those were never valid. `HEAD` is not a citation at all -- it resolves in every clone to whatever
that clone happens to be sitting on, so it reads as a working pointer in the one place it is
checked (`git cat-file -e HEAD` always succeeds) while naming a different commit for every reader.
A citation that resolves to the wrong thing beats one that fails to resolve, in the only direction
that matters: the reader believes they have seen the proof.

THE FIVE STATES, and they are decided on EVIDENCE, never on elapsed time (L1.48):

  OK           reachable from a remote-tracking ref -- every clone can resolve it.
  PENDING-PUSH reachable from a local ref but no remote one. The normal state of a disposition
               made minutes ago; it becomes OK on push. Reported, never counted against.
  ORPHANED     the object exists but NO ref reaches it. Rebase debris, alive only until gc.
               This is R0369's exact case, caught while the commit can still be recovered.
  MISSING      SHA-shaped, no such object here. Either already gc'd or written on another box.
  INVALID      not a fixed object name at all -- a placeholder (`pending`) or a symbolic ref
               (`HEAD`, `master`), which names a different commit for every reader.

WHY SYMBOLIC REFS ARE REFUSED RATHER THAN RESOLVED. Resolving `HEAD` would make this fence report
OK on all ten of them, because they do resolve -- here, today, on this branch. The check must ask
whether the citation names ONE commit for ALL readers, and only a fixed object name does.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, NamedTuple

_ROOT = Path(__file__).resolve().parent.parent.parent

#: A fixed object name. Deliberately NOT `^[0-9a-f]+$` without a length floor: `abc` is valid hex
#: and is far more likely to be a typo than a real short SHA, and git would resolve it ambiguously.
_HEX = re.compile(r"^[0-9a-fA-F]{7,40}$")

#: The states that mean the proof cannot be cashed by another clone. PENDING-PUSH is deliberately
#: absent: it is the correct state for a row disposed this session and would make the fence red on
#: every honest cycle, which is how a fence gets switched off (L1.43).
BAD_STATES = frozenset({"ORPHANED", "MISSING", "INVALID"})


class Citation(NamedTuple):
    """One row's proof-of-work pointer, classified."""

    row_id: str
    raw: str
    state: str
    detail: str

    @property
    def is_bad(self) -> bool:
        return self.state in BAD_STATES


def _git(args: list[str], root: Path) -> tuple[int, str]:
    """Run git, returning (returncode, stdout). Never raises on a git-level failure.

    A failure is returned as a non-zero code with its stderr in the payload rather than swallowed
    (L2.4): the caller turns an unusable git into UNMEASURED, and an unmeasured quantity must not
    be able to read as a clean board (L1.28a).
    """
    try:
        p = subprocess.run(["git", *args], capture_output=True, text=True,
                           timeout=60, cwd=root)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"{type(e).__name__}: {e}"
    return p.returncode, (p.stdout if p.returncode == 0 else p.stderr)


def reachable_sets(root: Path | None = None) -> tuple[set[str], set[str]] | None:
    """(reachable-from-a-remote, reachable-from-any-ref) as full 40-char SHAs.

    Two git calls regardless of how many rows are checked -- a per-row `git branch --contains`
    would be O(rows) subprocesses and the fence would be too slow to schedule, which is how a
    correct check ends up exempted from cron.

    Returns None when git cannot be read at all, so the caller reports UNMEASURED rather than
    an empty set, which would classify every citation as ORPHANED and manufacture a red board.
    """
    root = root or _ROOT
    rc_r, out_r = _git(["rev-list", "--remotes"], root)
    rc_a, out_a = _git(["rev-list", "--all"], root)
    if rc_r != 0 or rc_a != 0:
        return None
    remote = {ln.strip() for ln in out_r.splitlines() if ln.strip()}
    local = {ln.strip() for ln in out_a.splitlines() if ln.strip()}
    # HEAD may be detached or ahead of every branch ref; `rev-list --all` walks refs/ only.
    rc_h, out_h = _git(["rev-list", "HEAD"], root)
    if rc_h == 0:
        local |= {ln.strip() for ln in out_h.splitlines() if ln.strip()}
    return remote, local


def _resolve(raws: list[str], root: Path) -> dict[str, str]:
    """raw citation -> full SHA, for those that are real commit objects. One git call.

    Only SHA-shaped inputs are passed in, so `HEAD` can never be resolved here by accident --
    that exclusion happens in `classify` and is the point of the whole check.
    """
    if not raws:
        return {}
    payload = "\n".join(f"{r}^{{commit}}" for r in raws)
    try:
        p = subprocess.run(["git", "cat-file", "--batch-check"], input=payload,
                           capture_output=True, text=True, timeout=60, cwd=root)
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {}
    out: dict[str, str] = {}
    for raw, line in zip(raws, p.stdout.splitlines(), strict=False):
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "commit":
            out[raw] = parts[0]
    return out


def classify(rows: list[dict[str, Any]], root: Path | None = None,
             sets: tuple[set[str], set[str]] | None = None) -> dict[str, Any]:
    """Classify every row that carries a commit citation.

    ATTRITION IS COUNTED, NOT IMPLIED (L1.60). `attempted` counts every row handed in;
    `no_citation` counts those with nothing to check. A reader can therefore tell "this row was
    out of scope" from "this fence could not read this row", which are byte-identical to every
    caller that publishes only the surviving count.
    """
    root = root or _ROOT
    if sets is None:
        sets = reachable_sets(root)
    if sets is None:
        return {"measured": False, "why": "git unreadable -- reachability is UNMEASURED",
                "attempted": len(rows), "no_citation": 0, "citations": [], "n_bad": 0}
    remote, local = sets

    attempted = len(rows)
    pairs: list[tuple[str, str]] = []
    no_citation = 0
    for r in rows:
        raw = str(r.get("commit") or "").strip()
        if not raw:
            no_citation += 1
            continue
        pairs.append((str(r.get("id") or "?"), raw.split()[0].strip().rstrip(",")))

    shaped = sorted({raw for _, raw in pairs if _HEX.match(raw)})
    resolved = _resolve(shaped, root)

    cits: list[Citation] = []
    for rid, raw in pairs:
        if not _HEX.match(raw):
            why = ("a symbolic ref -- names a different commit in every clone"
                   if raw.lower() in {"head", "master", "main"} or "/" in raw
                   else "not a fixed object name")
            cits.append(Citation(rid, raw, "INVALID", why))
            continue
        full = resolved.get(raw)
        if full is None:
            cits.append(Citation(rid, raw, "MISSING", "no such commit object in this clone"))
        elif full in remote:
            cits.append(Citation(rid, raw, "OK", "reachable from a remote-tracking ref"))
        elif full in local:
            cits.append(Citation(rid, raw, "PENDING-PUSH",
                                 "reachable locally; becomes OK on push"))
        else:
            cits.append(Citation(rid, raw, "ORPHANED",
                                 "object exists but no ref reaches it -- rebase debris, "
                                 "recoverable only until gc"))
    return {"measured": True, "why": "", "attempted": attempted, "no_citation": no_citation,
            "citations": cits, "n_bad": sum(1 for c in cits if c.is_bad)}
