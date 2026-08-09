#!/usr/bin/env python3
"""DENOMINATOR FENCE (L1.57) -- how many things did this fence examine to earn its verdict?

WHAT THIS ASKS THAT NOTHING ELSE ON THE DESK DOES. L1.28a/R0237 gave every fence a fail-closed
exit map (`libs/ops/fence_exit.py`): name the passing statuses, fail the rest. L1.43's
`check_fence_yield` asks whether a fence has ever FIRED. Neither can see the case where a fence
runs, scans an EMPTY set, honestly computes `OK` because zero violations were found in zero
files, and exits 0 -- for years. `all([])` is True, `0 < 0/2` is False, and `min(survivors)`
hides every absent sibling. Each renders as health.

L1.53(4) ALREADY REQUIRED THIS AND HAD ONE INSTRUMENT FOR ONE RATIO: "whenever a gauge can be
improved by doing less of the thing it exists to encourage, its denominator is a first-class
measurement and is fenced separately." Written for the conversion ratio, fenced for the
conversion ratio, generalised in its own text to "every ratio the desk reports", and never
carried to a fence's own verdict -- where the same arithmetic decides whether a governance layer
is believed. A DUTY WITH NO INSTRUMENT IS A WISH (L1.46).

MEASURED THE DAY THIS WAS BUILT (2026-08-05, 40 fences read by hand across two sweeps):
18 of 40 pass vacuously; a further 10 publish an `n_*` that is `len()` of a hardcoded literal --
a count of what the author wrote down, never of what the run found. Three published a measured
count of what they actually examined.

THE VERDICTS, per governed fence:
  * DECLARED   -- it passes `scanned=` to `fence_exit`, and its last run counted >= 1 thing.
  * VACUOUS    -- its last run PASSED on a denominator of zero (or on a non-count). THE FAILING
                  STATE: this fence certified something while examining nothing.
  * UNDECLARED -- it never declares a denominator, so a vacuous pass is undetectable in it.
                  Counted against coverage, NOT a failure -- see the ratchet note below.

THIS FENCE'S OWN STATUS, and it may never read OK on an empty measurement set (L1.28a):
  VACUOUS    (exit 2) -- at least one fence passed while scanning nothing.
  UNMEASURED (exit 2) -- zero governed fences discovered, or the registry is empty/unreadable.
                         This fence is SUBJECT TO ITS OWN LAW: it declares `scanned=n_fences`,
                         so if its own scope discovery returns nothing, `fence_exit` refuses its
                         pass. A denominator fence that could itself pass vacuously would be the
                         joke it exists to end.
  PARTIAL    (exit 0) -- coverage below 100%, nothing vacuous. Deliberately NOT a failure:
                         coverage is a RATCHET (L1.0) whose gap is the work queue, and a fence
                         that goes red on its first day gets switched off (L1.43). The 40-fence
                         wiring is a conversion queue, not a cliff.
  OK         (exit 0) -- every governed fence declares a denominator, none vacuous.

ANTI-TIMIDITY READING (L1.28). A MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes
nothing, loosens no statistical bar, and can only ever make a fence fail on MORE inputs than
before. Its whole effect is to make "I checked 900 files and found nothing" distinguishable from
"I checked nothing" -- currently byte-identical on this desk, and only one of them is evidence.

    python scripts/check_denominators.py [--report-only] [--json]
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
from libs.ops.denominator import governed_fences, summarise  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

_OUT = _ROOT / "data" / "denominators.json"
_PASSING = frozenset({"OK", "PARTIAL"})


def build(root: Path | None = None) -> dict[str, Any]:
    r = root or _ROOT
    s = summarise(r)
    n = s["n_fences"]

    if n == 0 or (s["n_declared"] == 0 and n > 0):
        status = "UNMEASURED"
        why = ("no governed fences discovered under scripts/check_*.py" if n == 0 else
               f"{n} fences governed, NONE declares a denominator -- the registry at "
               "data/denominator_contracts.jsonl is empty or unreadable, so no vacuous pass "
               "on this desk is currently detectable")
        nxt = ("repair scope discovery in libs.ops.denominator.governed_fences" if n == 0 else
               "wire scanned= into fence_exit calls, highest-traffic fence first")
    elif s["vacuous"]:
        status = "VACUOUS"
        names = ", ".join(v["fence"] for v in s["vacuous"][:4])
        why = (f"{len(s['vacuous'])} fence(s) passed while examining nothing: {names}"
               f"{' ...' if len(s['vacuous']) > 4 else ''}")
        nxt = "fix the scope discovery in the named fence(s); a zero denominator is not a pass"
    elif s["undeclared"]:
        status = "PARTIAL"
        why = (f"{s['n_declared']}/{n} fences declare a denominator; "
               f"{len(s['undeclared'])} cannot report a vacuous pass")
        nxt = f"wire scanned= into: {', '.join(s['undeclared'][:6])}"
    else:
        status = "OK"
        why = f"all {n} governed fences declare a measured denominator; none vacuous"
        nxt = "none"

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.57 -- a verdict without a denominator is an opinion; a passing status over "
               "an empty scan set is VACUOUS, never OK. Instrument for L1.53(4).",
        "status": status,
        "n_fences": n,
        "n_declared": s["n_declared"],
        "n_vacuous": len(s["vacuous"]),
        "n_undeclared": len(s["undeclared"]),
        "coverage": s["coverage"],
        "vacuous": s["vacuous"],
        "declared": s["declared"],
        "undeclared": s["undeclared"],
        "detail": why,
        "next_action": nxt,
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    rep = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        cov = "n/a" if rep["coverage"] is None else f"{rep['coverage']:.0%}"
        print(f"denominators (L1.57): {rep['status']} -- {rep['n_declared']}/{rep['n_fences']} "
              f"fences declare a denominator (coverage {cov}), {rep['n_vacuous']} vacuous")
        for v in rep["vacuous"]:
            print(f"  VACUOUS    {v['fence']}: passed with n_scanned={v['n_scanned']} "
                  f"over {v['of']}")
        for d in rep["declared"]:
            print(f"  DECLARED   {d['fence']}: {d['n_scanned']} x {d['of']}")
        print(f"  next: {rep['next_action']}")

    if args.report_only:
        return 0
    # Subject to its own law: n_fences is this fence's denominator, so a scope discovery that
    # returns nothing refuses its own pass rather than reporting a clean board.
    return fence_exit(rep["status"], _PASSING, scanned=len(governed_fences(_ROOT)),
                      of="scripts/check_*.py", fence="check_denominators.py")


if __name__ == "__main__":
    raise SystemExit(main())
