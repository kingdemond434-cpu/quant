#!/usr/bin/env python3
"""THE SEVEN PRINCIPLES, HOURLY (ARCH-32): each principle's enforcing organs proved present and
its state measured from live artifacts.

    python desks/mt5/research/principles_enforcement.py            # write the report
    python desks/mt5/research/principles_enforcement.py --dry-run  # print, write nothing

The map is `docs/research/principles_map.json`; the organ checks and the seven measurements are
`libs/tiers/principles.py`; the committed ratchet floor is `docs/research/principles_floor.json`
and its fence is `scripts/check_principles.py` (law gate, portable half; box gate,
`--require-state`).

Writes ONE report, `reports/PRINCIPLES.json`: per principle MET | VIOLATED | UNMEASURED |
UNENFORCED, the organs that enforce it (each resolved against the tree), the named findings, and
the ratchet verdict against the floor (which findings are pre-existing debt and which arrived).
Its reader is `scripts/check_principles.py --require-state` (the box's hourly law gate), which
refuses a report older than 3h -- so the leg's clock is itself fenced -- and re-derives the pass
rather than trusting the file's verdicts.

READ-ONLY, CAPS NOTHING. It changes no sleeve, no fraction, no heat and no gate. The one action
the principles programme takes -- queueing a re-judge for a structural change -- belongs to the
`queue_cycle` leg (`libs/ops/queue_cycle._structural_change`), not to this report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.tiers import principles as P  # noqa: E402

REPORT = BASE / "reports" / "PRINCIPLES.json"
FLOOR = ROOT / "docs" / "research" / "principles_floor.json"


def build(root: Path = ROOT) -> dict:
    doc = P.evaluate(root)
    floor = None
    try:
        floor = json.loads(FLOOR.read_text("utf-8")) if FLOOR.is_file() else None
    except (OSError, ValueError):
        floor = None
    doc["ratchet"] = P.ratchet(doc, floor)
    doc["floor"] = FLOOR.relative_to(ROOT).as_posix() if floor is not None else P.UNMEASURED
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ARCH-32: the seven principles, measured")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    a = ap.parse_args(argv)
    doc = build()
    for r in doc["principles"]:
        print(f"{r['verdict']:<11} {r['id']:<32} organs {r['organs_enforcing']}/"
              f"{r['organs_declared']}  findings {len(r['findings'])}")
    rat = doc["ratchet"]
    print(f"ratchet: {'OK' if rat['ok'] else 'BREACH'}  arrived={len(rat['arrived'])} "
          f"pre-existing={len(rat['pre_existing'])} unenforced={rat['unenforced']}")
    if a.dry_run:
        return 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(REPORT)
    print(f"-> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
