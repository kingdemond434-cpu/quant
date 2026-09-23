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

    python3 scripts/migrate_identity_venue.py                    # report only
    python3 scripts/migrate_identity_venue.py --apply            # archive PRE-SCHEMA rows
    python3 scripts/migrate_identity_venue.py --restart-broken   # archive IDENTITY_BROKEN rows

A CLOCK BROKEN ON THE CURRENT SCHEMA HAD NO RESTART PATH AT ALL (found 2026-08-26). This script
selected rows by `identity_schema != CURRENT_SCHEMA` and merely COUNTED the broken ones, so with
11 sleeves sitting IDENTITY_BROKEN on the current schema it printed "nothing to migrate" and
exited 0 -- while `check_live_readiness` blocked rung 0 on exactly those 11. IDENTITY_BROKEN is
terminal by design and nothing else in the codebase clears it, so the desk's own path to first
live capital was closed by the one tool built to open it.

`--restart-broken` is a SEPARATE, EXPLICIT act and is deliberately not automatic. Auto-restarting
on every engine pass would hide a sleeve whose definition keeps moving -- the drift would be
erased as fast as it appeared. The archive therefore counts restarts per key, so a repeat drifter
is visible as a repeat drifter rather than as a sleeve that is always young.

RESTART MEANS BOTH ARTIFACTS. The registry holds the frozen identity; `shadow_state.json` holds
the clock (`forward_start`, `n`, `cum_r`, `days_active`) and its own `status`. Clearing only the
registry leaves `status: IDENTITY_BROKEN` in the state file, and the engine's verdict branch is
gated on `status == "ACTIVE"` -- so the sleeve would carry a new identity and still never be
judged. Both rows go, and the accrued evidence is archived rather than deleted: a new window
starts at zero and inherits nothing, which is what stops a restart from laundering a bad record.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "desks" / "mt5" / "data" / "sleeve_registry.json"
ARCHIVE = ROOT / "desks" / "mt5" / "data" / "sleeve_registry_archive.json"
SHADOW = ROOT / "desks" / "mt5" / "reports" / "shadow" / "shadow_state.json"
CURRENT_SCHEMA = "venue-2026-08-26"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="archive and clear PRE-SCHEMA rows; default is report")
    ap.add_argument("--restart-broken", action="store_true",
                    help="archive IDENTITY_BROKEN rows and their clocks so a NEW window starts")
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

    if broken and not args.restart_broken:
        print("\n"
              f"{len(broken)} clock(s) are IDENTITY_BROKEN ON THE CURRENT SCHEMA. Nothing in the\n"
              "codebase clears that status, so these are terminal and readiness stays blocked on\n"
              "them until they are restarted. Re-run with --restart-broken to archive their\n"
              "evidence and start NEW pre-registered windows:")
        for key in sorted(broken)[:12]:
            why = str((rows.get(key) or {}).get("status_why") or "")
            print(f"   {key}: {why or 'no reason recorded'}")

    if args.restart_broken:
        if not broken:
            print("\nno IDENTITY_BROKEN rows to restart")
        else:
            n = _archive_and_clear(
                rows, broken,
                reason=("identity drifted after the clock froze; evidence archived and the clock "
                        "restarts from zero. A new window inherits nothing -- that is what stops "
                        "a restart from laundering a record."),
                restart=True)
            print(f"\nrestarted {n} clock(s): registry rows archived, shadow_state rows cleared. "
                  f"The next engine pass freezes a NEW identity and a NEW forward window.")
            _write_registry(reg, rows, archived=n, note="clocks restarted from zero")
            return 0

    if not stale:
        if not broken:
            print("nothing to migrate")
        return 0
    if not args.apply:
        print("\nreport only. Re-run with --apply to archive them and start new windows.")
        for k in sorted(stale)[:8]:
            print(f"   would archive: {k}")
        return 0

    n = _archive_and_clear(
        rows, sorted(stale),
        reason=("frozen under the pre-venue schema, where data_venue held the ROUTE "
                "(MT5:/CACHE:) rather than the venue. Not a pre-registration of the "
                "current quantity; evidence retained here, clock restarts."),
        restart=True)
    _write_registry(reg, rows, archived=n, note="next engine pass freezes new identities")
    print(f"archived {n} pre-schema row(s); next engine pass starts new windows")
    return 0


def _archive_and_clear(rows: dict, keys: list[str], *, reason: str, restart: bool) -> int:
    """Move `keys` into the archive with their evidence, and clear both live artifacts."""
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    try:
        archive = json.loads(ARCHIVE.read_text("utf-8"))
    except (OSError, ValueError):
        archive = {"archived": []}
    prior = archive.get("archived") or []
    # HOW MANY TIMES THIS KEY HAS BEEN RESTARTED. A sleeve whose definition keeps moving must not
    # look permanently young: without it, every restart erases the record that exposes the drift.
    seen = {}
    for row in prior:
        seen[row.get("key")] = seen.get(row.get("key"), 0) + 1

    state = {}
    if restart:
        try:
            state = json.loads(SHADOW.read_text("utf-8"))
        except (OSError, ValueError):
            state = {}

    for key in keys:
        row = rows.get(key)
        entry = {"key": key, "archived_at": now, "reason": reason,
                 "restart_number": seen.get(key, 0) + 1, "row": row}
        if restart and key in state:
            # The CLOCK travels with the identity. Archiving it here is what lets the new window
            # start at zero without the evidence being destroyed.
            entry["clock"] = state.pop(key)
        prior.append(entry)
        rows.pop(key, None)
    archive["archived"] = prior
    archive["updated_at"] = now
    ARCHIVE.write_text(json.dumps(archive, indent=1, default=str), "utf-8")
    if restart and state:
        SHADOW.write_text(json.dumps(state, indent=1, default=str), "utf-8")
    return len(keys)


def _write_registry(reg: dict, rows: dict, *, archived: int, note: str) -> None:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    reg["sleeves"] = rows
    reg["updated_at"] = now
    reg["migration"] = {"at": now, "to_schema": CURRENT_SCHEMA, "archived": archived,
                        "note": note}
    REGISTRY.write_text(json.dumps(reg, indent=1, default=str), "utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
