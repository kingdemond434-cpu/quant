#!/usr/bin/env python3
"""DATA RECOVERABILITY FENCE (L1.65) -- did the desk lose span, and can it be bought back?

Every data gauge on this desk is denominated in what is ON DISK NOW, so all of them improve when
data is destroyed. ``mine_moat`` printed ``coverage_pct 100.0`` twenty-four seconds after 19.46 GB
of tape was deleted, because ``cells_filled`` and ``cells_total`` collapsed together; it reads
99.75% today on 4.2% of the bytes. Zero alerts have ever carried a data-loss title. L1.0 names
"data span" as a ratchet and it is the only one with no floor artifact -- and the only one whose
fall cannot be re-earned by working harder.

This fence compares span NOW against the deepest span this desk has EVER held, and pairs the
answer with a recovery class READ FROM A PROBE rather than asserted. See
``libs/research/recoverability.py`` for the full argument.

THE VERDICTS:
  OK                 (exit 0) -- every measured stream is at or above its high-water mark.
  NOT-READABLE-HERE  (exit 0) -- data/ is gitignored and VPS-only; this host cannot measure span.
                                 Distinct from 0%, and never OK-by-default.
  LOSS-RECOVERABLE   (exit 2) -- span fell and a verified free path exists. The fix is a FETCH.
  LOSS-PERMANENT     (exit 2) -- span fell with no known path. Unbuyable time; this one pages.
  CONTRADICTED       (exit 2) -- doctrine calls a stream irreplaceable while a probe shows it
                                 reachable. Both artifacts honest, never compared (L1.61 class).
  UNMEASURED         (exit 2) -- no high-water history. Never OK (L1.28a).

THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49): a fall is never fixed by lowering the mark. The
ledger is append-only and a mark moves only when span EXCEEDS it.
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
from libs.research.recoverability import (  # noqa: E402
    NOT_READABLE_HERE,
    PASSING,
    build_report,
    record_marks,
)

_OUT = _ROOT / "data/recoverability.json"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    ap.add_argument("--no-record", action="store_true",
                    help="do not append new high-water marks (inspection only)")
    ap.add_argument("--root", default=None,
                    help="EXPLICIT override of the tree to measure. Not normally needed: the "
                         "vantage point is resolved by libs.ops.box_state.data_root, which walks a "
                         "linked worktree's marker back to the box's main checkout, so a worktree "
                         "run measures the real tape rather than fabricating a verdict about an "
                         "empty gitignored data/. Use this for tests or a foreign tree.")
    args = ap.parse_args()

    root = Path(args.root).resolve() if args.root else _ROOT
    rep = build_report(root if args.root else None)
    doc = rep.as_dict()
    doc["root"] = str(root)

    # --root relocates the ARTIFACTS as well as the measurement. A flag that moved only what is
    # read would write a live tape's high-water into a worktree's data/ -- splitting the ratchet
    # across trees, which is the one thing a ratchet cannot survive.
    out = root / "data/recoverability.json"
    if not args.no_record:
        doc["marks_appended"] = record_marks(rep.streams, root / "data/span_high_water.jsonl")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2), "utf-8")

    if args.json:
        print(json.dumps(doc, indent=2))
    else:
        print(f"data recoverability (L1.65): {rep.status} -- {rep.n_streams} stream(s), "
              f"{rep.n_loss_permanent} LOSS-PERMANENT, {rep.n_loss_recoverable} "
              f"LOSS-RECOVERABLE, {rep.n_unmeasured} UNMEASURED")
        for s in rep.streams:
            print(f"  {s.status:<18} {s.key:<28} span {s.span_now} {s.unit}"
                  f"{'' if s.span_high_water is None else f' / hw {s.span_high_water}'}"
                  f"  [{s.recovery}]")
            if s.why:
                print(f"       {s.why}")
            if s.fetch_command:
                print(f"       FETCH: {s.fetch_command}")
        for n in rep.notes:
            # The label is the report's own status, never a fixed string: a NOT-READABLE-HERE
            # explanation printed as CONTRADICTED would be this module's own defect class.
            print(f"  {'NOTE' if rep.status == NOT_READABLE_HERE else 'CONTRADICTED'}  {n}")

    if args.report_only:
        return 0
    if rep.status == NOT_READABLE_HERE:
        # An HONEST DECLARED REFUSAL, not a vacuous pass. L1.57 refuses a passing status over a
        # zero denominator because the fence believed it had checked something; here the status
        # itself is the statement that nothing was checked and why. Failing on it would paint
        # every fresh checkout and CI run red, and a fence red from day one gets switched off
        # (L1.43) -- which would cost exactly the measurement this law exists to take.
        return 0
    # `scanned` is the number of streams THIS RUN discovered, never a hardcoded roster (L1.57).
    # `fence=` MUST carry the .py suffix: denominator.summarise() joins these rows against
    # governed_fences(), which yields `p.name`. Without it this fence's row could never match and
    # it was scored UNDECLARED against the L1.57 coverage ratchet forever, despite correctly
    # passing scanned=/of=. It was the only one of 22 call sites in scripts/ missing the suffix.
    return fence_exit(rep.status, PASSING, scanned=rep.n_streams,
                      of="recorded streams under data/", fence="check_data_recoverability.py")


if __name__ == "__main__":
    raise SystemExit(main())
