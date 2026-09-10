#!/usr/bin/env python3
"""THE RATCHET ON UNDECLARED WORK: a leg may not join the cycles without saying what it produces.

`libs.ops.completion` measures whether a leg that RAN actually COMPLETED -- artifact on disk,
inside its freshness SLA, read by something. It can only ask that of a leg whose output is
DECLARED, and measured 2026-09-10 the two cycles carry 88 legs of which 78 declare nothing in
`libs/ops/capability_graph`. Eighty-nine percent of the desk's hourly compute is invisible to
every completion check the desk owns, and that is how `pf_allocator` spent six days returning
exit 1 while every panel read healthy.

FAILING ON 78 WOULD BE A GATE NOBODY CAN GO GREEN ON, which is the failure this whole line of
work exists to end rather than repeat. So the debt is RATCHETED, exactly as the coverage floors
are (L1.50): the current count is recorded, it may fall freely, and it may never rise. A new leg
declares its artifacts or this gate is red -- and paying down the existing 78 is ordinary work
that shows up as a number going down.

    ONE-WAY, DELIBERATELY. `--accept` lowers the ceiling to what is measured now and refuses to
    raise it. There is no flag that raises it, because the only reason to want one is to land a
    leg that declares nothing, and that is the thing being fenced.

The AUTHORITY check is not ratcheted and never will be. A node that can change a position, a
size or a certificate, whose declared artifact has NEVER BEEN PRODUCED on any machine, is
capital sizing off a file that does not exist. That is a breach on the first occurrence.

    python scripts/check_completion.py
    python scripts/check_completion.py --accept     # lower the ceiling to what is measured now
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import completion  # noqa: E402

CEILING = ROOT / "desks" / "mt5" / "data" / "completion_ceiling.json"


def ceiling(path: Path | None = None) -> int:
    """The most UNDECLARED legs the cycles are allowed to carry. Absent means "not yet set",
    which is NOT permission: `main` refuses rather than passing an unset gate."""
    try:
        doc = json.loads((path or CEILING).read_text("utf-8"))
    except (OSError, ValueError):
        return -1
    try:
        return int(doc["undeclared_max"])
    except (KeyError, TypeError, ValueError):
        return -1


def write_ceiling(n: int, measured: int, path: Path | None = None) -> None:
    p = path or CEILING
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "undeclared_max": int(n),
        "measured_when_set": int(measured),
        "rule": ("the number of cycle legs that declare no artifact in capability_graph. It "
                 "RATCHETS DOWN ONLY (L1.50). A leg that declares nothing cannot be checked for "
                 "completion by anything, which is how a leg returning exit 1 every hour went "
                 "six days unnoticed. There is no flag that raises this."),
    }, indent=1) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--accept", action="store_true",
                    help="lower the ceiling to the measured count (never raises it)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root)
    doc = completion.report(root)
    undeclared = doc["by_verdict"].get(completion.UNDECLARED, 0)
    cap = ceiling()
    fails: list[str] = []

    if not doc["graph_available"]:
        fails.append("libs/ops/capability_graph is unimportable, so NOTHING was checked. An "
                     "unrunnable checker is not a passing one")

    if cap < 0:
        fails.append(f"no ceiling recorded in {CEILING.relative_to(root)}: an unset gate is not "
                     f"a passing gate. Run --accept once to record the current {undeclared}")
    elif undeclared > cap:
        fails.append(f"{undeclared} cycle legs declare no artifact, against a ceiling of {cap}. "
                     f"A leg that declares nothing is invisible to every completion check the "
                     f"desk owns -- declare its writes in libs/ops/capability_graph.NODES")

    # NOT RATCHETED, EVER. An authority node whose artifact has never been produced is capital
    # sizing off a file that does not exist.
    for row in doc["authority_breaches"]:
        if row["verdict"] == completion.NO_OUTPUT:
            fails.append(f"AUTHORITY {row['name']}: {row['why']}")

    if args.accept:
        new = min(undeclared, cap) if cap >= 0 else undeclared
        write_ceiling(new, undeclared)
        print(f"ceiling set to {new} (measured {undeclared})")
        return 0

    print(json.dumps(doc, indent=1, default=str) if args.json else completion.render(doc))
    if cap >= 0:
        print(f"  undeclared {undeclared} / ceiling {cap}"
              f"{'  <-- BREACH' if undeclared > cap else ''}")
    for f in fails:
        print(f"FAIL: {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
