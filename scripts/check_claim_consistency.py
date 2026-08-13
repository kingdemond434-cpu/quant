#!/usr/bin/env python3
"""INTERNAL CLAIM CONSISTENCY FENCE (L1.61) -- does this desk contradict itself?

The desk reconciles its book against the VENUE every cycle and has never once reconciled its own
published artifacts against EACH OTHER. Every existing instrument is single-artifact by
construction, so an organ that reads its inputs successfully, computes honestly and publishes a
fresh well-formed artifact passes all of them while asserting the opposite of the organ beside
it. This fence holds two artifacts at once, which is the only position from which a
contradiction is visible at all.

THE VERDICTS:
  OK           (exit 0) -- every compared claim agreed, and at least one claim was compared.
  PARTIAL      (exit 0) -- no contradiction among the claims that resolved, but some claim could
                           not be compared. Reported, never hidden: the gap is a work queue
                           rather than a cliff (L1.0/L1.43), because a fence red from day one
                           gets switched off.
  CONTRADICTED (exit 2) -- two organs published incompatible answers to the same question.
  UNMEASURED   (exit 2) -- not one claim could be compared. This fence is SUBJECT TO ITS OWN LAW
                           (L1.57): it declares scanned=n_compared, so a run that compared
                           nothing refuses its own pass rather than printing a clean board
                           (L1.28a). An empty comparison set is the one result that must never
                           read as agreement.

ANTI-TIMIDITY READING (L1.28): a MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes
nothing, promotes nothing, opens no gate, loosens no statistical bar and cannot change any value
it reads. Its whole effect is to make "these two boards agree" distinguishable from "these two
boards have never been compared" -- byte-identical on this desk until now, and only one of them
is evidence.

    python scripts/check_claim_consistency.py [--json]
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
from libs.ops.claim_registry import reconcile, summarise  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data" / "claim_consistency.json"
_PASSING = frozenset({"OK", "PARTIAL"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args()
    _law_guard()

    report: dict[str, Any] = reconcile(_ROOT)
    report["generated"] = datetime.now(tz=UTC).isoformat()
    report["law"] = "L1.61"
    _OUT.write_text(json.dumps(report, indent=2) + "\n")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        st = report["status"]
        print(f"internal claim consistency (L1.61): {st} -- "
              f"{report['n_compared']}/{report['n_claims_registered']} claims compared, "
              f"{report['n_contradicted']} contradicted, "
              f"{report['n_unresolved']} unresolved")
        for line in summarise(report):
            print(line)
        for art, why in report["unreadable_artifacts"].items():
            print(f"  attrition: {art} -- {why}")
        if st == "UNMEASURED":
            print("  UNMEASURED: not one claim could be compared -- this is a refusal, not a "
                  "pass (L1.28a)")

    # scanned is the number of claims ACTUALLY COMPARED, never len(CLAIMS): a count of what the
    # author wrote down is not a denominator (L1.57).
    # `fence=` is deliberately NOT passed: the denominator registry joins on the value
    # `governed_fences()` yields, which is the FILENAME WITH ITS SUFFIX. Passing a bare
    # "check_claim_consistency" here recorded a row nothing could join to, so this fence read as
    # UNDECLARED while declaring correctly -- the very producer/consumer name mismatch it exists
    # to catch, in its own exit line. `caller_name()` derives the joinable name.
    return fence_exit(report["status"], _PASSING, scanned=report["n_compared"],
                      of="claims compared across >=2 publishers")


if __name__ == "__main__":
    raise SystemExit(main())
