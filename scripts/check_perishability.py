#!/usr/bin/env python3
"""PERISHABILITY FENCE -- for what the desk does NOT record, does delay cost DELAY or THE DATA?

THE GAP. `check_unwired_capability.py` scores 256 uncalled capabilities as one class: latent
value, cost = delay. That is true of a dormant report and FALSE of a recorder. A recorder of a
point-in-time stream is a CLOCK: the broker publishes `swap_long` for today and will never tell
you what it was last Tuesday, so each night it does not run is a night no amount of later effort
buys back. Nothing on this desk carried a column for that distinction, so the two ranked the same
and the clock queued behind the report.

`libs/research/recoverability.py` (L1.65) cannot close it either: that gauge is denominated in
streams that EXIST, so a stream never opened has zero span, zero loss and no alarm -- WS-005 one
level up. `scripts/asymmetry_ledger.py` has a PERISHABLE class whose only two rows are
crypto-exchange observables banned by the 2026-08-18 mandate, so it reads green while containing
nothing the desk may act on.

THE VERDICTS (full argument in libs/research/perishability.py):
  RECORDING        (exit 0) -- fresh and interpretable.
  BACKFILLABLE     (exit 0) -- a NAMED route reconstructs it. Delay costs delay; waiting is cheap.
  UNINTERPRETABLE  (exit 2) -- rows exist without the field that makes them readable. Recorded and
                              useless, and it looks healthy to every gauge that counts rows.
  PERISHING        (exit 2) -- in-mandate, no backfill route, recorder exists and is not producing.
  NO-RECORDER      (exit 2) -- the same, and nothing in the repo even attempts it.
  UNMEASURED       (exit 2) -- this host cannot see the store. Never folded into a real verdict
                              (L1.28a): a verdict about the HOST is not a verdict about the DESK.

THE REPAIR IS ALWAYS TO START RECORDING, never to widen the staleness bound. A perishable row
cannot be fixed later by definition, which is the entire reason this fence outranks its cost.

    python scripts/check_perishability.py [--json] [--report-only]
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
from libs.research.perishability import (  # noqa: E402
    PASSING,
    REGISTER,
    build_report,
    to_dict,
)

_OUT = _ROOT / "data/perishability.json"


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact")
    ap.add_argument("--report-only", action="store_true", help="write the artifact, exit 0")
    args = ap.parse_args()

    rep = build_report()
    payload = to_dict(rep)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=1))
    else:
        print(f"perishability: {rep.status} -- {rep.n_recording} RECORDING, "
              f"{rep.n_perishing} PERISHING/NO-RECORDER, "
              f"{rep.n_uninterpretable} UNINTERPRETABLE, {rep.n_unmeasured} UNMEASURED")
        for r in rep.rows:
            print(f"  {r.status:<16} {r.key:<24} {r.store}")
            print(f"       {r.what}")
            print(f"       {r.detail}")
            if r.recorder:
                print(f"       RECORDER: {r.recorder}")
        for n in rep.notes:
            print(f"  NOTE  {n}")
        print(f"\n  -> {_OUT.relative_to(_ROOT)}")

    if args.report_only:
        return 0
    # `scanned` is what THIS RUN graded, never a hardcoded roster (L1.57). `fence=` must carry the
    # .py suffix or denominator.summarise() cannot join this row against governed_fences().
    return fence_exit(rep.status, PASSING, scanned=len(rep.rows),
                      of=f"in-mandate observables in the register (of {len(REGISTER)} declared)",
                      fence="check_perishability.py")


if __name__ == "__main__":
    raise SystemExit(main())
