#!/usr/bin/env python3
"""Retire certificates on symbols this desk can never trade. Explicitly, with a reason.

WHY THEY MUST BE RETIRED AND NOT JUST REPORTED. Eight certificates -- six on AFG, two on AFL --
passed all ten gates on symbols absent from `universe.json` with no H1 parquet on the box. They
can never enrol a forward clock and can never hold capital (L1.49: a gate that cannot be cashed
is not a survivor). Gate 0 refuses new ones since 2026-09-02, but the ones minted before it stay
in the ledger forever, where they:

  * inflate the certificate count that every dashboard and health report reads,
  * are printed as a CERTIFIED-UNTRADEABLE defect on every pipeline check, which is a permanent
    finding on a rolling report and the surest way to train a reader to skip the section,
  * and sit in `authorized_specs`, so the forward engine keeps being asked to enrol them.

REVOCATION IS WRITTEN, NEVER SILENT. The retired rows move to `retired_certificates` with their
reason and timestamp rather than being deleted -- `check_authority_ratchet.REVOCATION_KEYS`
recognises that key, so the certificate count may fall without the ratchet reading it as evidence
destroyed. A count that drops with no record is indistinguishable from a wipe, which is the exact
failure the ratchet exists to catch.

THE PREDICATE IS GATE 0's OWN. `external_gauntlet.symbol_is_tradeable`, imported rather than
restated, so admission and retirement can never disagree about which symbols exist. A symbol the
broker starts quoting tomorrow is tradeable tomorrow, and this stops retiring it.

IDEMPOTENT AND FAIL-CLOSED. Re-running changes nothing; a symbol whose tradeability cannot be
measured is LEFT ALONE, because "cannot tell" is not "cannot trade" (L1.28a).

    python3 desks/mt5/research/retire_untradeable.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SURVIVORS = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"


def _symbol_of(row: dict[str, Any]) -> str:
    spec = row.get("shadow_spec")
    if isinstance(spec, dict) and spec.get("symbol"):
        return str(spec["symbol"])
    if row.get("sym"):
        return str(row["sym"])
    return str(row.get("cell") or "").split(".")[0].split()[0]


def retire(dry_run: bool = False) -> dict[str, Any]:
    if not SURVIVORS.exists():
        return {"error": "no UNIVERSAL_SURVIVORS.json", "retired": 0}
    try:
        from external_gauntlet import symbol_is_tradeable
    except Exception as exc:
        # WITHOUT THE PREDICATE NOTHING IS RETIRED. Guessing which symbols exist is precisely
        # what this module refuses to do.
        return {"error": f"cannot import the gate-0 predicate ({type(exc).__name__})",
                "retired": 0}

    doc = json.loads(SURVIVORS.read_text(encoding="utf-8"))
    meta = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    rows = doc.get("survivors")
    as_dict = isinstance(rows, dict)
    items = list(rows.items()) if as_dict else list(enumerate(rows or []))

    keep: Any = {} if as_dict else []
    retired: list[dict[str, Any]] = []
    for key, row in items:
        if not isinstance(row, dict):
            (keep.__setitem__(key, row) if as_dict else keep.append(row))
            continue
        sym = _symbol_of(row)
        ok, why = symbol_is_tradeable(sym, meta) if sym else (True, "")
        if ok:
            (keep.__setitem__(key, row) if as_dict else keep.append(row))
            continue
        retired.append({
            "key": str(key), "cell": str(row.get("cell") or ""), "symbol": sym,
            "reason": why, "revoked_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "authority": "gate 0 symbol eligibility (L1.49: a gate that cannot be cashed is "
                         "not a survivor)",
        })

    out = {
        "checked_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "certificates_before": len(items),
        "certificates_after": len(keep),
        "retired": len(retired),
        "rows": retired,
    }
    if not retired or dry_run:
        return out

    doc["survivors"] = keep
    doc["n"] = len(keep)
    # THE REVOCATION KEY the authority ratchet looks for. Appended, never replaced: a second run
    # that retires a newly-delisted symbol must not erase the record of the first.
    prior = doc.get("retired_certificates")
    doc["retired_certificates"] = ([*prior, *retired] if isinstance(prior, list) else retired)
    doc["revoked_at"] = out["checked_utc"]
    SURVIVORS.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = retire(args.dry_run)
    if out.get("error"):
        print(f"REFUSING: {out['error']}")
        return 2
    print(f"certificates {out['certificates_before']} -> {out['certificates_after']}; "
          f"retired {out['retired']}" + (" (dry run)" if args.dry_run else ""))
    for r in out["rows"][:10]:
        print(f"  {r['symbol']:<8} {r['cell'][:46]:<48} {r['reason'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
