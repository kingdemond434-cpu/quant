#!/usr/bin/env python3
"""DATA-38 FENCE: no dataset without a production permission feeds a LIVE or STANDBY sleeve.

Walks `desks/mt5/data/sleeves.json` (LIVE and STANDBY rows), each row's certificate into its
`UNIVERSAL_SURVIVORS` spec and that spec's conditioner lineage, and resolves every dataset it
consumes to its DatasetContract (`libs/research/data_contract.py`). A dataset whose contract does
not permit `live_signal`, whose legality gate is shut, whose acquired series carries no PIT
authority, or which has no contract at all, is a VIOLATION. The organ that measures it is
`desks/mt5/research/research_only_fence.py` (hourly leg `research_only_fence`); this script
re-measures, rewrites `desks/mt5/reports/RESEARCH_ONLY_DATA.json` and exits 1 on any violation.

A sleeve whose lineage is not on this host is UNMEASURED by name and does not pass silently: it
is printed. With --require-state an unreadable roster exits 2 (L1.28a: absence is not a pass).

    python scripts/check_research_only_data.py [--require-state] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_RESEARCH = ROOT / "desks" / "mt5" / "research"
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(_RESEARCH)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_only_fence as F  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--require-state", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = F.build()
    try:
        F.write(doc)
    except OSError as exc:
        print(f"research-only data: could not write {F.REPORT}: {exc}")
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    if doc["status"] == F.UNMEASURED:
        print(f"research-only data: UNMEASURED -- {doc.get('why')}")
        return 2 if a.require_state else 0
    print(f"research-only data: {doc['n_guarded_sleeves']} LIVE/STANDBY sleeve(s), "
          f"{doc['n_violations']} violation(s) {doc['by_kind']}, "
          f"{doc['n_lineage_unmeasured']} lineage UNMEASURED")
    for v in doc["violations"]:
        print(f"  VIOLATION {v['kind']} {v['sleeve']} ({v['status']}) <- {v['dataset']}: "
              f"{v['why']}")
    for name in doc["lineage_unmeasured"][:20]:
        print(f"  UNMEASURED lineage: {name} (its certificate's spec is not on this host)")
    return 1 if doc["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
