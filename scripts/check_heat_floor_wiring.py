#!/usr/bin/env python3
"""HEAT FLOOR WIRING (state fence, box) -- the 20% floor is deployed, 24/7, and more when growth says.

Reads the allocator's live artifact and the arm files and refuses when:

  * `pf_allocation.json` is absent or older than two allocator clocks (the floor is not being
    solved for);
  * the resolved total heat is below HEAT_TARGET or above HEAT_HARD_CEILING, unless the
    catastrophe layer says so by name;
  * the funded book does not sum to the resolved total (the floor was reported, not held);
  * the fallback baseline book is missing while the proof failed (the gateway would size the
    floor with nothing);
  * `PF_ALLOCATOR_ARMED` is absent (the gateway would ignore the allocator entirely).

    python scripts/check_heat_floor_wiring.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
sys.path.insert(0, str(DESK))
MAX_AGE_S = 2 * 3600


def check() -> list[dict[str, str]]:
    f: list[dict[str, str]] = []
    from mt5desk.gateway_config_fallback import HEAT_HARD_CEILING, HEAT_TARGET
    art_p = DESK / "reports" / "pf_allocation.json"
    if not (DESK / "data" / "PF_ALLOCATOR_ARMED").exists():
        f.append({"check": "ARMED", "why": "data/PF_ALLOCATOR_ARMED absent: gateway ignores the allocator"})
    if not art_p.exists():
        return [*f, {"check": "ARTIFACT", "why": "reports/pf_allocation.json absent: the floor is not being solved"}]
    age = time.time() - art_p.stat().st_mtime
    if age > MAX_AGE_S:
        f.append({"check": "FRESH", "why": f"pf_allocation.json is {age / 3600:.1f}h old"})
    try:
        art = json.loads(art_p.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return [*f, {"check": "ARTIFACT", "why": f"unreadable: {exc}"}]
    heat = art.get("heat") or {}
    total = float(heat.get("total") or 0.0)
    binding = str(heat.get("binding"))
    if binding != "catastrophe":
        if total < HEAT_TARGET - 1e-4:
            f.append({"check": "FLOOR", "why": f"resolved heat {total:.2%} below the {HEAT_TARGET:.0%} floor (binding={binding})"})
        if total > HEAT_HARD_CEILING + 1e-4:
            f.append({"check": "CEILING", "why": f"resolved heat {total:.2%} above the {HEAT_HARD_CEILING:.0%} ceiling"})
        book_sum = float(sum(float(v) for v in (art.get("book") or {}).values()))
        if abs(book_sum - total) > 5e-4:
            f.append({"check": "FILLED", "why": f"book sums to {book_sum:.2%}, resolved {total:.2%}: the floor was reported, not held"})
        if not (art.get("proof") or {}).get("passed") and not (art.get("book_fallback") or {}).get("book"):
            f.append({"check": "FALLBACK", "why": "proof failed and no baseline fallback book is carried"})
        if not heat.get("certified"):
            f.append({"check": "CERTIFIED", "why": "the target is not certified on the growth curve; gateway falls back to the derived budget"})
    ag = art.get("aggression") or {}
    if ag.get("verdict") == "UNUSED_UPSIDE":
        f.append({"check": "UNUSED_UPSIDE", "why": f"growth wanted more and the tail bore it, book got less: {ag.get('unused_upside_heat')} unused"})
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    findings = check()
    if a.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=1))
    else:
        print(f"heat floor wiring: {'OK' if not findings else f'{len(findings)} breach(es)'}")
        for x in findings:
            print(f"  BREACH {x['check']}: {x['why']}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
