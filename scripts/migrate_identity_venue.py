#!/usr/bin/env python3
"""MIGRATE SLEEVE IDENTITIES ONTO THE VENUE SCHEMA -- archive the old, start a NEW window.

WHY A MIGRATION AND NOT A RE-BLESS. `sleeve_registry.identity()` used to take `data_venue` from
`Bars.source`, which is the ROUTE the bars arrived by -- "MT5:<server>" from a live terminal,
"CACHE:<file>" from the parquet cache. Those are the same PRINTS by the same venue, so the field
was recording transport rather than identity, and every clock broke terminally on any run where
the Windows box was down and bars came from cache. Measured 2026-08-26: 11 of 15 registered
sleeves sat IDENTITY_BROKEN for exactly that reason, and readiness was blocked on it.

The field now holds `Bars.evidence_venue` -- WHOSE prints the bars are -- which is stable across
routes. But a row frozen under the old meaning is NOT a pre-registration of the new quantity: it
attested to something else. Silently re-blessing it would be backdating a claim, the same offence
as counting selection-era trades as forward evidence.

So this ARCHIVES every pre-schema row with its accrued evidence intact and lets the next engine
pass freeze a NEW identity and start a NEW forward window. That costs the desk elapsed days, and
paying them is the point: the alternative is a clock whose start date attests to a definition it
never used.

    python3 scripts/migrate_identity_venue.py            # report only
    python3 scripts/migrate_identity_venue.py --apply    # archive and clear
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "desks" / "mt5" / "data" / "sleeve_registry.json"
ARCHIVE = ROOT / "desks" / "mt5" / "data" / "sleeve_registry_archive.json"
CURRENT_SCHEMA = "venue-2026-08-26"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="archive and clear; default is report")
    args = ap.parse_args()

    try:
        reg = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        print(f"registry unreadable ({exc}) -- nothing to migrate")
        return 1

    rows = reg.get("sleeves") or {}
    stale = {k: v for k, v in rows.items()
             if str(v.get("identity_schema") or "") != CURRENT_SCHEMA}
    broken = [k for k, v in rows.items()
              if str(v.get("status") or "").upper() == "IDENTITY_BROKEN"]

    print(f"registry rows        : {len(rows)}")
    print(f"on current schema    : {len(rows) - len(stale)}  ({CURRENT_SCHEMA})")
    print(f"PRE-SCHEMA rows      : {len(stale)}  -- attest to a different quantity")
    print(f"IDENTITY_BROKEN      : {len(broken)}")

    if not stale:
        print("nothing to migrate")
        return 0
    if not args.apply:
        print("\nreport only. Re-run with --apply to archive them and start new windows.")
        for k in sorted(stale)[:8]:
            print(f"   would archive: {k}")
        return 0

    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    try:
        archive = json.loads(ARCHIVE.read_text("utf-8"))
    except (OSError, ValueError):
        archive = {"archived": []}
    for key, row in stale.items():
        archive.setdefault("archived", []).append({
            "key": key, "archived_at": now,
            "reason": ("frozen under the pre-venue schema, where data_venue held the ROUTE "
                       "(MT5:/CACHE:) rather than the venue. Not a pre-registration of the "
                       "current quantity; evidence retained here, clock restarts."),
            "row": row,
        })
        rows.pop(key, None)
    archive["updated_at"] = now
    ARCHIVE.write_text(json.dumps(archive, indent=1, default=str), "utf-8")

    reg["sleeves"] = rows
    reg["updated_at"] = now
    reg["migration"] = {"at": now, "to_schema": CURRENT_SCHEMA, "archived": len(stale),
                        "note": "next engine pass freezes new identities and new windows"}
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), "utf-8")
    print(f"\narchived {len(stale)} pre-schema row(s) -> {ARCHIVE.name}")
    print("the next shadow pass will freeze fresh identities and start fresh forward windows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
