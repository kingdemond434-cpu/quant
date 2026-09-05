#!/usr/bin/env python3
"""FENCE: a row closed as `implemented` must cite a commit that is actually in the branch (R0742).

`git commit` and `git merge` are different claims and only the second one counts. The ledger
records the first. Measured 2026-08-20: 4 of 350 implemented rows -- R0560, R0561, R0569, R0573 --
cite commits that exist, print a real diff, and are not in the live branch, so the desk believed it
held four fixes it did not hold. A closed row is out of the owed-work queue permanently, which is
what makes this more expensive than an open one and why nothing was going to re-hand it.

    python scripts/check_disposition_landed.py            # census, exit 2 if anything is stranded
    python scripts/check_disposition_landed.py --json     # the artifact

DETECT IMPLIES REPAIR, and the repair is NAMED rather than taken: for each stranded row the report
prints the branch that contains the commit and the exact `git merge --ff-only` that lands it. It is
not applied automatically, because two different states produce this reading -- work sitting on an
unmerged branch (land it) and work that is genuinely gone (re-open the row) -- and only a reader
can tell them apart. Guessing wrong in the second direction would re-close a row on a commit that
no longer does anything.

See libs/ops/disposition_landed.py for the mechanism and why the ledger lands when the code does
not. The short version: the ledger is one file every session touches, so it merges through ordinary
conflict resolution; the code commits merge only if the worker completes its own final step.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.disposition_landed import LEDGER_REL, census  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

#: UNMEASURED is deliberately absent. A run that could resolve no commit has verified nothing, and
#: absence must never resolve into a clean verdict (L1.28a).
_PASSING = frozenset({"OK"})


def build(root: Path, ref: str) -> dict[str, Any]:
    cen = census(root, ref=ref)
    rep = cen.as_dict()
    rep["at"] = datetime.now(tz=UTC).isoformat()
    if cen.stranded:
        rep["next_action"] = ("land the named branch(es), or re-open the row if the work is gone "
                              "-- a disposition and its evidence must agree")
    elif cen.status == "UNMEASURED":
        rep["next_action"] = "run on a full clone -- no cited commit could be resolved here"
    else:
        rep["next_action"] = "none -- every implemented row's commit is in this branch"
    return rep


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--ref", default="HEAD",
                    help="branch the dispositions are checked against (default: HEAD, i.e. the "
                         "tree being measured -- at pre-push time that is the tree being pushed)")
    # A WORKTREE-BLIND FENCE FABRICATES BOTH REDS AND GREENS. --root makes the subject explicit
    # and is what lets the tests drive this against a planted repo rather than the live one.
    ap.add_argument("--root", type=Path, default=_ROOT, help="repo to measure")
    args = ap.parse_args()
    root = args.root.resolve()

    rep = build(root, args.ref)
    out = root / "data" / "disposition_landed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"disposition landed (L2.3): {rep['status']} -- {rep['n_stranded']} implemented "
              f"row(s) cite a commit that is not in {rep['ref']}, over {rep['n_resolved']} "
              f"resolved of {rep['n_implemented_with_sha']} implemented row(s) citing a sha"
              + (f", {rep['n_unresolvable']} unresolvable" if rep["n_unresolvable"] else ""))
        for s in rep["stranded"]:
            print(f"  {s['id']}: {s['sha'][:8]} {s['subject']}")
            print(f"      REPAIR: {s['repair']}")
        for n in rep["notes"]:
            print(f"  note: {n}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to its own law (L1.57): the denominator is the commits actually RESOLVED, never the
    # implemented rows found. A run that resolved nothing refuses its own pass -- "no disposition
    # is stranded" and "no disposition could be checked" are different claims.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_resolved"],
                      of=f"resolved commits cited by implemented rows in {LEDGER_REL}",
                      fence="check_disposition_landed.py")


if __name__ == "__main__":
    raise SystemExit(main())
