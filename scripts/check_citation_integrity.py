#!/usr/bin/env python3
"""CITATION INTEGRITY FENCE (L2.3/§42, R0369) -- can the ledger's proof-of-work be cashed?

`dispose --status implemented` refuses an empty `--commit`, on the desk's standing rule that an
artifact proves the work and never a claim. That check runs at WRITE time. Nothing ran at READ
time, where the proof is actually spent -- so the ledger could hold a citation that resolves to
nothing, or worse to something different for every reader, and report itself fully disposed.

WHAT THE FIRST RUN MEASURED over 227 citing rows: 208 OK, 14 INVALID, 1 ORPHANED. Ten of the
fourteen cite the literal string `HEAD` and four cite `pending`. None was ever a valid citation,
and none could have been caught by the existing write-time check, which only asks whether the
field is non-empty. The single ORPHANED row is R0369's own reported case -- a SHA left behind by
a rebase, still recoverable today and gone at the next gc.

THE VERDICTS, and the floor is why this fence can be scheduled at all:
  OK         (exit 0) -- every citation resolves for every clone.
  BACKLOG    (exit 0) -- bad citations at or below the recorded floor: the historical stock,
                         a work queue rather than a cliff (L1.0/L1.43). A fence red from day one
                         gets switched off, and then it enforces nothing.
  DEGRADED   (exit 2) -- the count ROSE above the floor. A NEW unresolvable citation was written,
                         which is the thing this exists to stop.
  UNMEASURED (exit 2) -- git unreadable, or no citation found at all. An unmeasured quantity
                         counts as zero, never as fine (L1.28a).

THE FLOOR ONLY EVER MOVES DOWN (L1.0). It is a constant in this file rather than a value read
back from the artifact: a floor that re-derives itself from the last run ratifies whatever drift
has landed, which is the denominator trick in ratchet clothing. Lowering it is a one-line edit
here, in a diff, paired with the repointing that earned it.

ANTI-TIMIDITY READING (L1.28). A MEASUREMENT duty. It promotes nothing, sizes nothing, loosens no
bar, and cannot turn a failing disposition into a passing one -- it can only make a citation that
never resolved distinguishable from one that does. Repair is UPWARD: `recommendations.py repoint`
re-points a citation at the commit that really carries the work; nothing here deletes a row or
downgrades a disposition.

    python scripts/check_citation_integrity.py [--report-only] [--json]
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
from libs.research.citation_integrity import classify  # noqa: E402

_LEDGER = _ROOT / "docs/research/recommendation_ledger.json"
_OUT = _ROOT / "data" / "citation_integrity.json"
_PASSING = frozenset({"OK", "BACKLOG"})

#: Measured 2026-08-12 on the live ledger: 14 INVALID (10 `HEAD`, 4 `pending`) + 1 ORPHANED.
#: RATCHET (L1.0): this number only ever moves DOWN, and only in a commit that repoints the rows
#: it accounts for. Raising it to clear a red board is the failure the desk has paid for.
_FLOOR = 15


def build_report(root: Path | None = None) -> dict[str, Any]:
    root = root or _ROOT
    ledger = root / "docs/research/recommendation_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8"))["recommendations"]
    except (OSError, ValueError, KeyError) as e:
        # Printed, never swallowed: an unreadable ledger must not read as a clean board.
        return {"generated": datetime.now(tz=UTC).isoformat(), "status": "UNMEASURED",
                "why": f"ledger unreadable: {type(e).__name__}: {e}", "floor": _FLOOR,
                "n_citations": 0, "n_bad": 0, "attempted": 0, "no_citation": 0,
                "by_state": {}, "bad": []}

    rep = classify(rows, root)
    if not rep["measured"]:
        return {"generated": datetime.now(tz=UTC).isoformat(), "status": "UNMEASURED",
                "why": rep["why"], "floor": _FLOOR, "n_citations": 0, "n_bad": 0,
                "attempted": rep["attempted"], "no_citation": rep["no_citation"],
                "by_state": {}, "bad": []}

    cits = rep["citations"]
    by_state: dict[str, int] = {}
    for c in cits:
        by_state[c.state] = by_state.get(c.state, 0) + 1
    n_bad = rep["n_bad"]

    if not cits:
        status, why = "UNMEASURED", "no row carries a citation -- nothing was checked (L1.28a)"
    elif n_bad == 0:
        status, why = "OK", "every citation resolves for every clone"
    elif n_bad <= _FLOOR:
        status = "BACKLOG"
        why = (f"{n_bad} unresolvable citation(s) at or below the floor of {_FLOOR} -- "
               "the historical stock, and the gap is the work queue")
    else:
        status = "DEGRADED"
        why = (f"{n_bad} unresolvable citation(s) ABOVE the floor of {_FLOOR}: a NEW citation "
               "was written that no other clone can resolve")

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L2.3/§42 (R0369) -- an implemented row's --commit is its proof of work; a "
               "pointer that resolves for nobody is a false citation in the one dimension the "
               "field exists to make true.",
        "status": status, "why": why, "floor": _FLOOR,
        # L1.60: `attempted` counts every row handed to the classifier, `no_citation` those with
        # nothing to check, so the shrinkage from 512 rows to 227 citations is visible rather
        # than implied by a surviving count.
        "attempted": rep["attempted"], "no_citation": rep["no_citation"],
        "n_citations": len(cits), "n_bad": n_bad, "by_state": by_state,
        "bad": [{"id": c.row_id, "commit": c.raw, "state": c.state, "detail": c.detail}
                for c in cits if c.is_bad],
        "next_action": (
            "python scripts/recommendations.py repoint --id <R####> --commit <sha> --reason ..."
            if n_bad else "none -- every citation resolves"),
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build_report()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"citation integrity (L2.3/§42): {rep['status']} -- {rep['n_bad']} unresolvable "
              f"of {rep['n_citations']} citation(s) over {rep['attempted']} row(s) "
              f"({rep['no_citation']} carry none), floor {rep['floor']}")
        for k in sorted(rep["by_state"]):
            print(f"    {k:<13} {rep['by_state'][k]}")
        for b in rep["bad"]:
            print(f"  {b['state']:<9} {b['id']} {b['commit']!r} -- {b['detail']}")
        print(f"  {rep['why']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to L1.57: the denominator is the citations actually examined, so an empty ledger
    # or a scope that discovers nothing cannot exit clean.
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_citations"],
                      of="ledger rows citing a commit", fence="check_citation_integrity.py")


if __name__ == "__main__":
    raise SystemExit(main())
