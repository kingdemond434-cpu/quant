#!/usr/bin/env python3
"""FROZEN-VALUE FENCE (L1.66) -- is a running daemon's config the config on disk?

``check_stale_daemons`` asks whether a long-lived process is running the committed CODE. This
asks the other half of the same question, which nothing on this desk has ever asked: whether it
is running the committed VALUES. A module-scope read executes once, at import; edit the artifact
and disk and memory disagree for the life of the process, silently, with every producer-side and
artifact-side gauge green.

See ``libs/ops/value_staleness.py`` for the full argument, including why L1.44's self-building
freshness registry, L1.55's provenance and L1.49's reachability are each blind to this by
construction.

IT MEASURES EXPOSURE, NOT DAMAGE, AND THE DISTINCTION IS LOAD-BEARING. FROZEN-STALE means the
in-memory value CANNOT BE PROVEN to match disk -- never that it provably differs. Overstating
that would make this a detector that cries wolf, and a detector that cries wolf gets acked into
silence (L1.43/L1.37).

THE VERDICTS:
  OK                (exit 0) -- every frozen read examined is over an artifact unchanged since
                               its process started.
  UNVERIFIABLE      (exit 2) -- >=1 running daemon holds a value whose input changed after start.
  UNRESOLVED        (exit 2) -- >=1 read is real but its artifact could not be resolved. Counted,
                               never silently dropped -- the prototype dropped exactly these and
                               reported a clean zero.
  NO-DAEMONS-HERE   (exit 0) -- nothing of ours is running from this vantage point. An honest
                               declared refusal about the VANTAGE POINT, never about the desk.
  UNMEASURED        (exit 2) -- daemons running, nothing examined. Never OK (L1.28a).

THE REPAIR IS UPWARD (L1.49): move the read inside the function that consumes it -- the
``run_cashcarry_executor._live_params`` shape, which is the desk's own positive control. A
restart is NOT a repair; it re-freezes the same value one tick later.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402
from libs.ops.value_staleness import (  # noqa: E402
    FROZEN_STALE,
    FROZEN_UNRESOLVED,
    NO_DAEMONS_HERE,
    PASSING,
    SOURCE_DRIFTED,
    build_report,
)

_OUT = "data/value_staleness.json"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--root", default=None,
                    help="EXPLICIT override of the tree to measure. Not normally needed: the "
                         "vantage point is resolved by libs.ops.box_state.data_root, so a "
                         "worktree run measures the box's real checkout -- the one the running "
                         "daemons actually imported -- rather than its own gitignored copy.")
    args = ap.parse_args()

    rep = build_report(Path(args.root).resolve() if args.root else None)
    doc = rep.as_dict()

    # The artifact lands beside the tree that was MEASURED, never beside the tree that ran the
    # fence. Writing a box-wide verdict into a worktree's gitignored data/ would publish a
    # measurement nothing can read (R0521).
    out = Path(rep.root) / _OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        # EVERY NON-CLEAN STATUS APPEARS IN BOTH THE COUNTS AND THE DETAIL. The first run of this
        # fence printed 6 pairs and listed 5: SOURCE-DRIFTED was computed, counted in the artifact
        # and invisible in the only output a human reads. A status that fires silently is the
        # defect class this whole law exists to end, committed by its own reporting line.
        print(f"frozen values (L1.66): {rep.status} -- {len(rep.daemons)} daemon(s), "
              f"{rep.n_pairs} frozen read(s): {rep.n_stale} FROZEN-STALE, "
              f"{rep.n_current} FROZEN-CURRENT, {rep.n_refreshed} REFRESHED, "
              f"{rep.n_source_drifted} SOURCE-DRIFTED, {rep.n_unresolved} UNRESOLVED, "
              f"{rep.n_exempt} EXEMPT")
        for p in rep.pairs:
            if p.status not in {FROZEN_STALE, FROZEN_UNRESOLVED, SOURCE_DRIFTED}:
                continue
            print(f"  {p.status:<18} {p.daemon}")
            print(f"       {p.read.module}:{p.read.lineno} {p.read.name} [{p.read.kind}]")
            print(f"       {p.why}")
        for n in rep.notes:
            print(f"  NOTE  {n}")

    if args.report_only:
        return 0
    if rep.status == NO_DAEMONS_HERE:
        # An HONEST DECLARED REFUSAL, not a vacuous pass (the L1.65 NOT-READABLE-HERE precedent).
        # L1.57 refuses a passing status over a zero denominator because the fence believed it had
        # checked something; here the status IS the statement that nothing was running and why.
        # Failing on it would paint every CI run and fresh clone red, and a fence red from day one
        # gets switched off (L1.43) -- costing exactly the measurement this law exists to take.
        return 0
    # `scanned` is the number of (daemon, frozen-read) pairs THIS RUN discovered, never a
    # hardcoded roster (L1.57).
    return fence_exit(rep.status, PASSING, scanned=rep.n_pairs,
                      of="(live daemon, frozen read) pairs", fence="check_frozen_values.py")


if __name__ == "__main__":
    raise SystemExit(main())
