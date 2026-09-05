"""SUBJECT-CHANGE FRESHNESS (L1.44, one level below age) -- an input can be YOUNG AND WRONG.

THE CLASS THIS CLOSES, AND IT IS THE HALF L1.44 COULD NOT SEE. `read_fresh` asks ONE question of
an input: how old is it? That is the right question when the subject changes at roughly the rate
the producer runs. It is the WRONG question when the subject changes FASTER than the producer --
because then the artifact is honestly young, honestly well-formed, passes its contract, and is
still describing a world that no longer exists. Age and correctness come apart, and every
instrument on this desk was watching age.

THE PROVING INSTANCE IS THE CONTRACT R0495 INSTALLED, ON ITS OWN PATH. max_audit stamps
data/max_audit_report.json and the owed-work payload reads it under max_age_h=24.0 -- one
producer regeneration interval, which is the correct calibration for the PRODUCER. Measured
2026-08-20:

  * the audit ran 02:55:33Z and handed over exactly one non-`rec-` defect,
    `dig-output-uncommitted`;
  * commit 35dd2282 landed 03:03:19Z -- EIGHT MINUTES LATER -- and resolved it;
  * SEVEN commits landed in the 58 minutes between the audit and the worker's spawn;
  * the payload rendered the list as "1.1h old", `fresh=True`, with no re-measure banner. The
    instrument built to stop the worker trusting a stale list reported FRESH about a list that
    had been wrong for 63 of its 66 minutes.

Nothing there is a bug in read_fresh: 1.1h really is inside 24h. The contract is keyed to the
producer's cadence while the defect's subject is the GIT WORKING TREE, which this desk moves
~10 times a day. R0495 measured three of four handed defects already dead on arrival; today it
was one of one. That is not bad luck, it is a cadence ratio, and labelling it is not enough.

THE FIX IS TO RE-MEASURE, NOT TO WARN. A warning hands the worker a list it still cannot trust
and spends its judgement on deciding which half to believe. The commit-volatile checks are a
`git status --porcelain` call -- measured at 0.10s to import max_audit and 0.032s to run the
check, against a worker that fires every 20 minutes. At that price there is no argument for
handing over a snapshot: re-run the check and hand over the TRUTH.

  from libs.ops.audit_recheck import recheck
  rc = recheck(live_ids, ran=report.get("ran"))
  # rc.cleared / rc.standing / rc.appeared / rc.unverified

IT REPORTS IN BOTH DIRECTIONS, WHICH IS WHY IT ALWAYS RE-RUNS RATHER THAN SHORT-CIRCUITING ON
"HEAD HAS NOT MOVED". A tree can be dirtied without a commit, so a volatile defect can APPEAR
between the audit and the read as easily as it can clear. Short-circuiting would have caught only
the direction that makes the list shorter -- and a defect that arrived since the audit is exactly
the one no other organ is going to mention (L1.28b(f): this shows more, never less).

UNVERIFIED IS A REAL ANSWER (L1.28a). If the re-measure cannot run -- max_audit unimportable, git
unavailable, the check raising -- the ids go to `unverified` and are handed over WITH the snapshot
verdict and the reason. They are NEVER silently cleared: absence of a fresh measurement resolving
to a clean verdict is WS-005, the defect class this desk repeats most, and it would be
particularly expensive here because a falsely-cleared defect is one nobody looks at again.

THE REGISTRY IS VERIFIED BY A TEST, NOT ASSERTED (L1.57). A hardcoded list of volatile ids that
the run never checks is precisely the hardcoded denominator L1.57 forbids: it cannot fall when the
thing it counts disappears, and it cannot grow when a new volatile check is written. So
tests/ops/test_audit_recheck.py AST-parses max_audit for the functions that read
`git status --porcelain` AND emit a defect id, and asserts that set equals VOLATILE's keys. A new
commit-volatile check joins the registry on the day it is written, or the test fails.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

#: defect id -> the max_audit function that measures it LIVE.
#:
#: MEMBERSHIP IS NOT A JUDGEMENT CALL: an id belongs here iff its check reads the git working tree
#: (`git status --porcelain`), which is what makes its verdict flip the instant any session
#: commits. Verified against max_audit by AST in tests/ops/test_audit_recheck.py -- do not add or
#: remove a key by hand without that test agreeing, because the whole value of this module is that
#: its scope is measured rather than remembered.
VOLATILE: dict[str, str] = {
    "dig-output-uncommitted": "check_dig_uncommitted",
}

_AUDIT = "scripts.max_audit"


@dataclass(frozen=True)
class Recheck:
    """What a live re-measurement says about the volatile ids in a handed defect list."""

    cleared: list[str] = field(default_factory=list)     # in the snapshot, gone on re-measure
    standing: list[str] = field(default_factory=list)    # in the snapshot, confirmed live
    appeared: list[str] = field(default_factory=list)    # NOT in the snapshot, live now
    unverified: list[str] = field(default_factory=list)  # could not be re-measured -- see why
    why: str = ""
    commits_since: int | None = None                     # None = unmeasurable, never 0

    @property
    def ran(self) -> bool:
        """Did a live measurement actually happen? False means every verdict here is the
        snapshot's, unchanged -- report it as UNVERIFIED, never as agreement."""
        return not self.unverified


def commits_since(ran: str | None, root: Path | None = None) -> int | None:
    """How many commits landed since the audit stamp -- CONTEXT for the reader, never a gate.

    None means unmeasurable (no stamp, no git, unreadable), and unmeasurable must never render as
    zero: "the tree has not moved" and "I could not tell whether the tree moved" are different
    claims and only one of them is evidence (L1.28a).
    """
    if not ran:
        return None
    try:
        out = subprocess.run(
            ["git", "log", "--oneline", f"--since={ran}"],
            cwd=root or Path.cwd(), capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return len([ln for ln in out.stdout.splitlines() if ln.strip()])


def _git_works(root: Path | None = None) -> bool:
    """Can git actually run here?

    THIS PROBE IS LOAD-BEARING AND IT IS NOT PARANOIA. `check_dig_uncommitted` ends its git call
    with `except (OSError, subprocess.SubprocessError): return` and `if out.returncode != 0:
    return` -- i.e. it emits NO DEFECT when git is unavailable, which is the right call for an
    audit ("the check does not apply here") and a fabrication risk for THIS module, because a
    check that returns clean on failure is indistinguishable, to its consumer, from a check that
    returned clean on success. Without this probe a git outage would render as "every volatile
    defect was fixed" -- WS-005 arriving through a helper's own swallow rather than through an
    exception my refusal path can catch. A clean re-measure is only evidence if the instrument
    was working.
    """
    try:
        out = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=root or Path.cwd(),
                             capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def _live_volatile_ids(root: Path | None = None) -> tuple[set[str], str]:
    """Run the volatile checks against the CURRENT tree.

    Returns (ids_found, ""), or (set(), reason) when the measurement could not be made. The
    reason is propagated to the caller verbatim rather than swallowed: a re-measure that failed
    and a re-measure that found nothing are opposite facts (L1.55).
    """
    if not _git_works(root):
        return set(), ("git unavailable -- the volatile checks return CLEAN when git cannot run, "
                       "so a clean re-measure here would be fabricated rather than measured")
    try:
        import importlib
        audit = importlib.import_module(_AUDIT)
    except Exception as exc:                          # broad ON PURPOSE: reported, never swallowed
        return set(), f"{_AUDIT} unimportable: {type(exc).__name__}: {exc}"

    found: set[str] = set()
    for did, fname in sorted(VOLATILE.items()):
        fn = getattr(audit, fname, None)
        if fn is None:
            return set(), (f"{_AUDIT}.{fname} is gone -- the registry names a check "
                           "that no longer exists")
        defects: list[tuple[str, str]] = []
        try:
            fn(defects)
        except Exception as exc:                      # broad ON PURPOSE: reported, not swallowed
            return set(), f"{fname} raised {type(exc).__name__}: {exc}"
        found |= {d[0] for d in defects if d and d[0] == did}
    return found, ""


def recheck(live_ids: Iterable[str], ran: str | None = None,
            root: Path | None = None) -> Recheck:
    """Re-measure the commit-volatile defects in a handed list against the tree as it is NOW.

    `live_ids` is the id list from the audit snapshot; `ran` is that snapshot's stamp, used only
    to report how far the tree has moved since. Ids outside VOLATILE are not this module's
    business and are left alone -- a check whose subject is not the working tree is not made more
    correct by re-running it here.
    """
    snapshot = {i for i in live_ids if i in VOLATILE}
    since = commits_since(ran, root=root)

    found, why = _live_volatile_ids()
    if why:
        # THE REFUSAL PATH. Every volatile id keeps its snapshot verdict and is flagged. Nothing
        # is cleared on a failed measurement -- that is the direction that buries a live defect.
        return Recheck(unverified=sorted(snapshot), why=why, commits_since=since)

    return Recheck(
        cleared=sorted(snapshot - found),
        standing=sorted(snapshot & found),
        appeared=sorted(found - snapshot),
        why=f"re-measured {len(VOLATILE)} commit-volatile check(s) against the live tree",
        commits_since=since)


def render(rc: Recheck) -> list[str]:
    """The lines the payload prints. Kept here so the wording is testable rather than buried in a
    bash heredoc, and so a future reader can see what the worker was actually told."""
    out: list[str] = []
    moved = "" if rc.commits_since is None else f" ({rc.commits_since} commit(s) since it ran)"
    if rc.unverified:
        out.append(f"### VOLATILE DEFECTS UNVERIFIED -- {rc.why}.")
        out.append("### These ids read from the SNAPSHOT and could not be re-measured"
                   f"{moved}: {', '.join(rc.unverified)}. That is UNMEASURED, not clean -- "
                   "re-run the named check yourself before you ack one of them.")
    if rc.cleared:
        out.append(f"### ALREADY FIXED SINCE THE AUDIT RAN{moved}, verified live just now: "
                   f"{', '.join(rc.cleared)}.")
        out.append("### Do NOT ack these and do NOT re-fix them. Cite the commit that resolved "
                   "them and move on -- an ack for an already-fixed defect is a false "
                   "disposition and buries the class (R0495).")
    if rc.appeared:
        out.append(f"### APPEARED SINCE THE AUDIT RAN{moved}, not in the handed list, live now: "
                   f"{', '.join(rc.appeared)}. Take these too.")
    return out
