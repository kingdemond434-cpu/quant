"""The tradeable registry may never shrink. A stump here silently shrinks the whole search space.

WHY THIS EXISTS (2026-09-04)

Measured twice now. On 2026-08-27 "a rogue writer left a 23-row stump that a sync then
propagated". On 2026-09-04 at 01:28 UTC it happened again, on the trading box: 251 symbols and 22
fields were replaced by 23 symbols carrying 9 fields and ZERO `currency_profit`.

WHAT THAT COSTS, precisely. The gauntlet sweeps the registry, so it tested 23 instruments instead
of 251 -- a 91% cut to the search space that reported itself as a normal run. And
`currency_profit` is MetaTrader5's own answer to what a symbol is denominated in: without it
`quote_currency()` returns None, `spread_cost_per_lot` returns 0.0, and gate 8 (stress_costs)
cannot judge a candidate at all. So the desk swept a tenth of its universe and could not cost
anything it found. No certificate was minted for hours while the timer ran on schedule.

WHY THE EXISTING GUARDS DID NOT CATCH IT.
  * `pull_desk_state.sh` refuses a lossy INCOMING copy -- but this was written LOCALLY, on the box.
  * `check_artifact_monotonic` judges by declared generation stamp -- this file declares none, so
    it reads UNMEASURABLE. And a stamp would not help: a stump written NOW carries a newer stamp
    than the good copy it replaced. Freshness is the wrong question for a registry.

THE RIGHT QUESTION IS COUNT, and it ratchets. A registry that has held 251 symbols and 22 fields
may never quietly hold fewer. Broker delistings are real, so the floor is not absolute: a drop
within TOLERANCE is recorded and allowed, and anything larger is a breach that restores the
high-water copy. A symbol genuinely retired by the broker leaves through a named retirement, not
by vanishing between two runs.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json"
RECORD = ROOT / "docs" / "research" / "UNIVERSE_FLOOR.json"
KEEP = ROOT / "data" / "universe_high_water.json"

#: A broker may delist. Losing more than this between two runs is not delisting, it is a stump.
#: 5% of 251 is ~12 symbols, comfortably above real churn and far below the 91% cut measured.
TOLERANCE_FRAC = 0.05
#: Fields are structural: a column vanishing is never churn. Any loss is a breach.
FIELD_TOLERANCE = 0


def _load(p: Path) -> dict[str, Any] | None:
    try:
        return dict(json.loads(p.read_text("utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


def _shape(doc: dict[str, Any]) -> tuple[int, set[str]]:
    syms = doc.get("symbols") if isinstance(doc.get("symbols"), dict) else doc
    fields: set[str] = set()
    for v in syms.values():
        if isinstance(v, dict):
            fields |= set(v)
    return len(syms), fields


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="detect only; never restore")
    a = ap.parse_args()
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    doc = _load(UNIVERSE)
    if doc is None:
        print("universe floor: registry absent or unparseable -- UNMEASURED, never a clean pass")
        return 1
    n, fields = _shape(doc)
    rec = _load(RECORD) or {}
    hw_n = int(rec.get("high_water_symbols") or 0)
    hw_fields = set(rec.get("high_water_fields") or [])

    floor_n = int(hw_n * (1.0 - TOLERANCE_FRAC))
    lost_fields = sorted(hw_fields - fields)
    breach = (hw_n and n < floor_n) or len(lost_fields) > FIELD_TOLERANCE

    if not breach:
        # RATCHET UP. The high-water copy is kept alongside so a restore has something to restore
        # FROM -- a floor with no known-good copy can only ever report, never repair.
        if n >= hw_n and len(fields) >= len(hw_fields):
            rec.update({"high_water_symbols": n, "high_water_fields": sorted(fields),
                        "updated": now})
            RECORD.parent.mkdir(parents=True, exist_ok=True)
            RECORD.write_text(json.dumps(rec, indent=1), "utf-8")
            KEEP.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(UNIVERSE, KEEP)
        print(f"universe floor: {n} symbol(s), {len(fields)} field(s) -- at or above the mark "
              f"({hw_n}/{len(hw_fields)})")
        return 0

    print(f"universe floor BREACH: {n} symbol(s) vs floor {floor_n} (high water {hw_n}); "
          f"fields lost: {lost_fields or 'none'}")
    if a.report or not KEEP.exists():
        print("  REPORT ONLY -- no known-good copy to restore from" if not KEEP.exists()
              else "  REPORT ONLY (--report)")
        return 1
    stump = UNIVERSE.with_suffix(f".stump-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S')}")
    shutil.copy2(UNIVERSE, stump)
    shutil.copy2(KEEP, UNIVERSE)
    rn, rf = _shape(_load(UNIVERSE) or {})
    print(f"  RESTORED from high water: {rn} symbol(s), {len(rf)} field(s); "
          f"the stump is kept at {stump.name} as evidence")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
