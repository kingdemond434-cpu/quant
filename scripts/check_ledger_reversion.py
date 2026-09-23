#!/usr/bin/env python3
"""FENCE: no merge may un-decide a recommendation (L2.3/L1.28b).

``recommendations.py`` guards the ledger against two writers -- ``dispose()`` refuses to revert a
terminal row, ``_locked()`` serialises concurrent CLI calls -- and **neither reaches git**. A
merge writes the ledger without the flock, without ``dispose()`` and without ``_TERMINAL``, so a
stale side silently un-decides every row the other side had decided.

MEASURED, ON MERGE ``a9c13de1`` (2026-08-20): **51 dispositions reverted in one commit** while
the row count went 714 -> 719, i.e. UP. Every count-based ledger gauge read healthy, the rows
re-entered the owed-work queue as ordinary backlog, and the next worker session re-did three of
them (R0495/R0496/R0497 in ``72cd67bb``) -- finished, cited work, done twice. Nothing in either
session's output could have revealed the duplication, because a reverted disposition does not
look damaged: it looks like an open row, the most ordinary thing in this file.

WHY THIS BELONGS IN ``ops/gates.sh`` AND NOT ONLY IN CRON. The damage is done by a merge and lands
in a push, so the push is where it must be caught -- ``ops/githooks/pre-push`` execs ``gates.sh``
(``core.hooksPath`` is set in this clone and the main checkout) and ``ops/sync_from_repo.sh:73``
runs the same script on the box. A nightly cron would report the loss after every downstream
reader had already treated the rows as open work (L1.37: every law at every boundary).

DETECT IMPLIES REPAIR, SO THE REPAIR IS IN THE TOOL::

    python scripts/check_ledger_reversion.py            # census, exit 2 if anything reverted
    python scripts/check_ledger_reversion.py --repair   # put the lost decisions back

``--repair`` restores only what a prior commit already published, and stamps every restoration
into the row's own ``restorations`` list. It never derives a disposition, never decides a row and
never touches a summary; a row whose decision is genuinely owed stays owed.

A MERGE DRIVER WAS CONSIDERED AND NOT BUILT, WHICH IS A DECISION AND SO IS RECORDED. A
``.gitattributes`` driver could union the two sides and make the loss impossible rather than
merely loud. It was rejected as the DOMINATED option: a custom driver is per-clone
``git config`` that no commit can install, so on 40+ worktrees and the VPS it would be exactly the
unwired capability III.16 forbids -- while this fence is a tracked script on a path that already
runs. If the loss recurs after this lands, the driver is the next step and this note is its brief.
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
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.ops.ledger_reversion import (  # noqa: E402
    LEDGER_REL,
    census,
    repair_plan,
    rows_of,
)

#: UNMEASURED is deliberately NOT here. A run that could read no history has not cleared the
#: ledger, and absence must never resolve into a clean verdict (L1.28a).
_PASSING = frozenset({"OK"})


def build(root: Path, max_commits: int = 0) -> dict[str, Any]:
    cen = census(root, max_commits)
    rep = cen.as_dict()
    rep["at"] = datetime.now(tz=UTC).isoformat()
    rep["next_action"] = (
        "python scripts/check_ledger_reversion.py --repair"
        if cen.reversions else
        "none -- every decision in this ledger's history is still in it")
    return rep


def _repair(root: Path, max_commits: int) -> int:
    ledger = root / LEDGER_REL
    payload = json.loads(ledger.read_text("utf-8"))
    rows = rows_of(payload)
    cen = census(root, max_commits, head_rows=rows)
    if cen.status == "UNMEASURED":
        print("REFUSING to repair: no ledger history could be read, so nothing is known to be "
              "lost. Repairing on an unmeasured census would write fabricated dispositions.")
        return fence_exit(cen.status, _PASSING)
    touched = repair_plan(cen, rows, datetime.now(tz=UTC).isoformat())
    if not touched:
        print("nothing to repair")
        return 0
    ledger.write_text(json.dumps(payload, indent=1, ensure_ascii=False), "utf-8")
    print(f"restored {len(touched)} reverted decision(s) from this ledger's own git history:")
    for row in touched:
        print(f"  {row['id']} -> {str(row.get('status')).upper()}")
    print("  review with `git diff` and commit -- the restorations are stamped into each row")
    return 0


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repair", action="store_true",
                    help="restore every reverted decision from git history")
    ap.add_argument("--max-commits", type=int, default=0,
                    help="bound the history walk (0 = all of it, ~3s over 423 versions); "
                         "when it bites, the report says so rather than silently narrowing")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    # A WORKTREE-BLIND FENCE FABRICATES BOTH REDS AND GREENS, and this desk has shipped four of
    # them. `data/` is gitignored so it does not exist in a worktree at all, and a worktree's git
    # history is its BRANCH's -- so a fence measuring "the repo" from a side branch reports on a
    # tree nobody has merged. --root makes the subject explicit and is what lets the tests below
    # drive this against a planted repo rather than the live one.
    ap.add_argument("--root", type=Path, default=_ROOT,
                    help="repo to measure (default: this script's own checkout)")
    args = ap.parse_args()
    root = args.root.resolve()

    if args.repair:
        return _repair(root, args.max_commits)

    rep = build(root, args.max_commits)
    out = root / "data" / "ledger_reversion.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"ledger reversion (L2.3): {rep['status']} -- {rep['n_reverted']} decision(s) "
              f"reverted, over {rep['n_rows']} row(s) ({rep['n_open']} open) and "
              f"{rep['n_versions_read']}/{rep['n_versions_attempted']} readable ledger versions"
              + (f" ({rep['n_unreadable']} unreadable)" if rep["n_unreadable"] else ""))
        for r in rep["reverted"]:
            print(f"  {r['kind']:7} {r['id']}: was {r['was'].upper()} in {r['at'][:8]} -- "
                  f"{r['detail']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to its own law (L1.57): the denominator is the rows actually compared against
    # history. A ledger that yielded no rows refuses its own pass rather than reporting a clean
    # board -- "nothing was reverted" and "nothing was examined" are not the same claim.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_rows"],
                      of=f"rows in {LEDGER_REL}", fence="check_ledger_reversion.py")


if __name__ == "__main__":
    raise SystemExit(main())
