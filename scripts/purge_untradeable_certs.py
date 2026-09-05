"""Retire certificates whose symbol the broker does not list. Archived, never deleted.

WHY THIS EXISTS (2026-09-04)

Eight certificates passed all ten gates on symbols absent from the Fusion universe: AFG (6) and
AFL (2). They are not weak candidates -- they are UNENROLLABLE. A forward clock needs a symbol the
desk can trade and replay, so these can never start one, never accrue a day, and never be refuted.
They sit in the canon inflating the certificate count with rows that cannot become money.

Bars exist for them (AFG_H1.parquet is on the box), which is exactly how they got this far: the
gauntlet had data to test and nothing checked the symbol against the tradeable universe. Data
availability is not tradeability, and conflating the two is what produced a certificate for an
instrument the broker does not offer.

ARCHIVED, NEVER DELETED. The canon is a ledger and a vanished record reads identically to a
resolved one. Retired rows move to UNTRADEABLE_CERTS.json with the reason and the date, so the
count drops honestly and the evidence survives for audit.

IDEMPOTENT. Re-running finds nothing to retire once the canon is clean, so this is safe on a timer.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
ARCHIVE = DESK / "data" / "UNTRADEABLE_CERTS.json"


def tradeable_symbols() -> set[str]:
    blob = json.loads(UNIVERSE.read_text("utf-8"))
    syms = blob.get("symbols") if isinstance(blob.get("symbols"), dict) else blob
    return set(syms.keys())


def main() -> int:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    syms = tradeable_symbols()
    if len(syms) < 50:
        # A TRUNCATED UNIVERSE WOULD RETIRE THE WHOLE BOOK. The registry has been left a stump by
        # a rogue writer before (23 rows, 2026-08-27), and reading one here would mark every
        # certificate untradeable and archive the entire canon in one pass.
        print(f"universe has only {len(syms)} symbol(s) -- refusing to judge tradeability "
              f"against a stump. Nothing retired.")
        return 1

    canon = json.loads(CANON.read_text("utf-8"))
    survivors = canon.get("survivors") or {}
    keep, retire = {}, {}
    for key, row in survivors.items():
        sym = str((row.get("shadow_spec") or {}).get("symbol") or row.get("sym") or "")
        if sym and sym not in syms:
            retire[key] = {**row, "retired_at": now,
                           "retired_why": (f"symbol {sym!r} is not in the Fusion universe "
                                           f"({len(syms)} symbols); a forward clock can never "
                                           f"be enrolled, so this certificate cannot become "
                                           f"money and is not weak evidence -- it is no evidence")}
        else:
            keep[key] = row

    print(f"UNTRADEABLE CERT PURGE {now}")
    print(f"  canon: {len(survivors)} survivor(s); tradeable universe: {len(syms)} symbol(s)")
    if not retire:
        print("  nothing to retire -- every certificate is on a listed symbol")
        return 0

    by_sym: dict[str, int] = {}
    for row in retire.values():
        s = str((row.get("shadow_spec") or {}).get("symbol") or row.get("sym") or "?")
        by_sym[s] = by_sym.get(s, 0) + 1
    print(f"  retiring {len(retire)}: {by_sym}")

    archive = json.loads(ARCHIVE.read_text("utf-8")) if ARCHIVE.exists() else {"retired": {}}
    archive.setdefault("retired", {}).update(retire)
    archive["updated_at"] = now
    ARCHIVE.write_text(json.dumps(archive, indent=1), "utf-8")

    canon["survivors"] = keep
    canon["n"] = len(keep)
    canon["untradeable_retired"] = {"at": now, "count": len(retire), "by_symbol": by_sym,
                                    "archive": str(ARCHIVE.relative_to(ROOT))}
    CANON.write_text(json.dumps(canon, indent=1), "utf-8")
    print(f"  canon now {len(keep)} survivor(s); retired rows archived -> {ARCHIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
