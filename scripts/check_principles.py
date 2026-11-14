#!/usr/bin/env python3
"""THE SEVEN PRINCIPLES ARE ENFORCED, AND STAY ENFORCED (ARCH-32, law fence).

    python scripts/check_principles.py                   # portable: exit 1 on an arrival
    python scripts/check_principles.py --require-state   # box: also fail on a NEW unmeasured
    python scripts/check_principles.py --json            # the whole pass as JSON
    python scripts/check_principles.py --update          # drop healed names from the floor

The principles (no sacred strategy/model/source/geography; structural change triggers relearning;
cash is an allocation; research never stops; validation never relaxes; execution teaches
research; ontology stays open) are mapped to their enforcing organs in
`docs/research/principles_map.json` and measured by `libs/tiers/principles.py`. This fence
re-derives that pass -- it never trusts the hourly report -- and FAILS on:

  * a principle with NO resolving organ (UNENFORCED): the principle is prose again;
  * a NEW finding -- an organ the map names that no longer resolves (MISSING_ORGAN), or a
    measurement that newly reads VIOLATED (a sacred constant, a LIVE sleeve with no retirement
    path, a structural-change trigger nobody re-judged, a gate bound looser than its strictest
    value in git history, a floor below its high-water mark, a closed registry ...);
  * with `--require-state` (the box's hourly gate): a principle UNMEASURED that the floor does
    not already list -- on the box, absence of the artifact is itself the defect.

A RATCHET THAT ONLY TIGHTENS. `docs/research/principles_floor.json` names today's findings and
today's UNMEASURED principles; only an ARRIVAL fails, and `--update` rewrites the floor to the
smaller set and refuses to add a name. Pre-existing UNMEASURED states on a cloud clone therefore
never redden CI, and a regression always does (L1.43: a fence red on the day it is built gets
switched off).

It caps no capital and lowers no heat; it is about research and validation discipline only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.tiers import principles as P  # noqa: E402

FLOOR = ROOT / "docs" / "research" / "principles_floor.json"
REPORT_REL = "desks/mt5/reports/PRINCIPLES.json"
#: The hourly leg's report must be this fresh on the box (`--require-state`): two cycles.
REPORT_MAX_AGE_S = 3 * 3600


def report_clock(root: Path, now: datetime | None = None) -> tuple[bool, str]:
    """Is the hourly `principles` leg actually running here? Its report, fresh."""
    p = root / REPORT_REL
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return False, f"{REPORT_REL} absent or unreadable: the hourly leg has not run here"
    at = P._parse_ts(doc.get("generated_utc")) if isinstance(doc, dict) else None
    if at is None:
        return False, f"{REPORT_REL} carries no generated_utc"
    age = ((now or datetime.now(UTC)) - at).total_seconds()
    if age > REPORT_MAX_AGE_S:
        return False, f"{REPORT_REL} is {age / 3600:.1f}h old (> {REPORT_MAX_AGE_S // 3600}h)"
    return True, f"{REPORT_REL} {age / 60:.0f} min old"


def read_floor(path: Path = FLOOR) -> dict | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def shrink_floor(floor: dict | None, doc: dict) -> dict:
    """The floor with healed names removed. Never adds: a floor written from scratch takes the
    current state only when no floor exists yet (the first run)."""
    findings = P.findings_of(doc)
    unmeasured = {r["id"] for r in doc["principles"] if r["verdict"] == P.UNMEASURED}
    if floor is None:
        keep_f, keep_u = findings, unmeasured
    else:
        keep_f = set(floor.get("findings") or []) & findings
        keep_u = set(floor.get("unmeasured") or []) & unmeasured
    return {"updated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "measured_by": "scripts/check_principles.py",
            "law": ("ARCH-32: these names are pre-existing debt. The floor only shrinks; a name "
                    "not listed here that appears is an arrival and fails the law gate."),
            "findings": sorted(keep_f), "unmeasured": sorted(keep_u)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-state", action="store_true",
                    help="also fail on a principle UNMEASURED that the floor does not list")
    ap.add_argument("--update", action="store_true",
                    help="drop healed names from the floor (never adds one)")
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root)
    floor_path = root / "docs" / "research" / "principles_floor.json"
    try:
        doc = P.evaluate(root)
    except ValueError as exc:
        print(f"check_principles: BREACH -- {exc}")
        return 1
    floor = read_floor(floor_path)
    if a.update:
        new = shrink_floor(floor, doc)
        floor_path.write_text(json.dumps(new, indent=1) + "\n", encoding="utf-8")
        print(f"floor -> {floor_path} ({len(new['findings'])} finding(s), "
              f"{len(new['unmeasured'])} unmeasured)")
        floor = new
    rat = P.ratchet(doc, floor, require_state=a.require_state)
    if a.require_state:
        # THE CLOCK IS PART OF THE STATE: on the box the leg must be publishing, or the
        # principles are enforced only when someone runs this fence by hand.
        fresh, why_clock = report_clock(root)
        rat["report_clock"] = why_clock
        if not fresh:
            rat["ok"] = False
    doc["ratchet"] = rat
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        for r in doc["principles"]:
            print(f"  {r['verdict']:<11} {r['id']:<32} organs {r['organs_enforcing']}/"
                  f"{r['organs_declared']}  findings {len(r['findings'])}")
        if floor is None:
            print("  (no floor committed: every finding counts as an arrival)")
        for x in rat["unenforced"]:
            print(f"  UNENFORCED  {x}: no organ the map names resolves")
        for x in rat["arrived"]:
            print(f"  ARRIVED     {x}")
        for x in rat["new_unmeasured"]:
            print(f"  UNMEASURED  {x} (not in the floor; --require-state)")
        if rat.get("report_clock"):
            print(f"  clock: {rat['report_clock']}")
        if rat["healed"]:
            print(f"  healed since the floor: {len(rat['healed'])} (run --update to drop them)")
    print(f"check_principles: {'OK' if rat['ok'] else 'BREACH'} "
          f"({len(rat['pre_existing'])} pre-existing finding(s), "
          f"{len(rat['unmeasured'])} unmeasured)")
    return 0 if rat["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
