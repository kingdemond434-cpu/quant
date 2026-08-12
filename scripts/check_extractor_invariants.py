#!/usr/bin/env python3
"""EXTRACTOR INVARIANTS (R0318, OP-024) -- which parses can prove themselves, and which only look right.

THE DISCIPLINE EXISTED AND THE MECHANISM DID NOT. OP-024 has been marked `[active]` in the search
operator library since the RFB run, and the improvement inbox carries the proposal verbatim, but
grep over max_audit, check_build_standard and data_sanity found no enforcement of any kind. A duty
with no instrument is a wish (L1.46), so this is the instrument.

WHAT IT MEASURES. Every module under `libs/` and `scripts/` that tears a foreign format apart by
hand -- markup by regex, delimited fields sliced out of lines, bytes decoded from a spec -- and
whether it declares an invariant its own output must satisfy. The population is DISCOVERED from
source on every run, never listed: a fence about unvalidated extractors carrying a hardcoded list
of extractors would be the defect it detects (L1.57).

IT REPORTS, IT DOES NOT BLOCK. Coverage is a ratchet whose gap is the work queue (L1.0), so below
100% this is PARTIAL and exits 0. Going red on day one over a population nobody has annotated yet
is how a fence gets switched off in its first week, and a switched-off fence enforces nothing
(L1.43). Zero discovered is UNMEASURED and DOES fail: this repo is full of scrapers, so an empty
population means the detector broke, not that the defect was solved (L1.28a).

CALIBRATED AGAINST AN INDEPENDENT CENSUS, because a detector nobody checked is exactly the
unvalidated extractor this fence is about. A hand census of the repo found 15 hand-rolled
foreign-format modules; this recovers 14 of them, and the two false-positive classes the first run
produced -- regex named groups `(?P<file>` reading as XML tags, and `args.symbols.split(",")`
reading as CSV -- were fixed rather than tolerated.

    python scripts/check_extractor_invariants.py [--report-only] [--json]
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
from libs.research.extractor_invariants import discover, summarise  # noqa: E402

_OUT = _ROOT / "data" / "extractor_invariants.json"
_PASSING = frozenset({"OK", "PARTIAL"})


def build(root: Path | None = None) -> dict[str, Any]:
    report = summarise(root or _ROOT)
    report["generated"] = datetime.now(UTC).isoformat()
    report["next_action"] = _next_action(report)
    return report


def _next_action(report: dict[str, Any]) -> str:
    if report["status"] == "UNMEASURED":
        return ("repair the detector in libs/research/extractor_invariants.py -- it found no "
                "hand-rolled extractors, which cannot be true in this repo")
    undeclared = [e for e in report["extractors"] if e["status"] == "UNDECLARED"]
    if not undeclared:
        return "every discovered extractor declares an invariant -- hold the floor"
    first = undeclared[0]["path"]
    return (f"declare an invariant on {first} (set EXTRACTOR_INVARIANT, or check the parse with "
            f"libs.research.conservation); {len(undeclared)} extractors carry none")


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0")
    ap.add_argument("--json", action="store_true", help="print the artifact")
    args = ap.parse_args()

    report = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(report, indent=2), "utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        coverage = "n/a" if report["coverage"] is None else f"{report['coverage']:.0%}"
        print(f"extractor invariants (R0318/OP-024): {report['status']} -- "
              f"{report['n_declared']}/{report['n_extractors']} hand-rolled extractors declare an "
              f"in-data invariant (coverage {coverage})")
        for entry in report["extractors"]:
            if entry["status"] == "UNDECLARED":
                print(f"  UNDECLARED {entry['path']} ({', '.join(entry['techniques'])})")
        for entry in report["extractors"]:
            if entry["status"] == "DECLARED":
                print(f"  DECLARED   {entry['path']}: {entry['declaration'][:70]}")
        print(f"  next: {report['next_action']}")

    if args.report_only:
        return 0
    # Subject to its own law (L1.57): the discovered population IS this fence's denominator, so a
    # scope discovery that returns nothing refuses its own pass rather than reporting a clean board.
    return fence_exit(report["status"], _PASSING, scanned=len(discover(_ROOT)),
                      of="hand-rolled extractors in libs/ and scripts/",
                      fence="check_extractor_invariants.py")


if __name__ == "__main__":
    raise SystemExit(main())
