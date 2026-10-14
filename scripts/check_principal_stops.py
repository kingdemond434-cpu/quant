#!/usr/bin/env python3
"""Fence: no sleeve the principal or the CRO stopped is LIVE with risk above 0.

Reads desks/mt5/data/PRINCIPAL_STOPS.json and desks/mt5/data/sleeves.json and writes
desks/mt5/reports/PRINCIPAL_STOPS_FENCE.json. Exit 1 (RED) when any active stop matches a LIVE
row with risk_frac > 0, or the stops file is unreadable; an absent stops file is UNMEASURED, exit 1. The gateway already refuses to place for
such a row (`decision_core.load_sleeves_verbose`); this fence says which organ wrote it LIVE.
An absent sleeves file is UNMEASURED and exits 1 too: it is never a clean reading.
See desks/mt5/mt5desk/principal_stops.py for why a stop is a record and not a status.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk.principal_stops import identity, load, match, why  # noqa: E402

SLEEVES = DESK / "data" / "sleeves.json"
STOPS = DESK / "data" / "PRINCIPAL_STOPS.json"
OUT = DESK / "reports" / "PRINCIPAL_STOPS_FENCE.json"

#: Fields an organ leaves when it lifts a row; the first present one names the writer.
WRITER_FIELDS = ("restored_by", "promoted_by", "risk_frac_source", "deployed_by")


def check(sleeves_path: Path = SLEEVES, stops_path: Path = STOPS) -> dict:
    stops, problem = load(stops_path)
    doc: dict = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                 "active_stops": [s.get("identity") or s.get("name") for s in stops],
                 "breaches": [], "held_off_live": 0}
    if problem:
        # Absent is UNMEASURED (no record to check against, and the healer is then holding every
        # STANDBY row); present but unreadable is RED. Both exit 1: neither is a clean reading.
        doc.update(status="UNMEASURED" if problem.endswith(" absent") else "RED", why=problem)
        return doc
    try:
        rows = json.loads(sleeves_path.read_text(encoding="utf-8-sig")).get("sleeves") or []
    except (OSError, ValueError, AttributeError) as exc:
        doc.update(status="UNMEASURED", why=f"sleeves unreadable ({type(exc).__name__}: {exc})")
        return doc
    for r in rows:
        if not isinstance(r, dict):
            continue
        e = match(r, stops)
        if e is None:
            continue
        live = str(r.get("status") or "").upper() == "LIVE"
        try:
            risk = float(r.get("risk_frac") or 0.0)
        except (TypeError, ValueError):
            risk = float("nan")
        if live and not risk <= 0:
            writer = next((f"{f}={r[f]}" for f in WRITER_FIELDS
                           if isinstance(r.get(f), str) and r.get(f)), "unrecorded")
            doc["breaches"].append({"sleeve": r.get("name"), "identity": identity(r),
                                    "risk_frac": r.get("risk_frac"), "written_by": writer,
                                    "restored_at": r.get("restored_at"), "stop": why(e)})
        else:
            doc["held_off_live"] += 1
    doc["status"] = "RED" if doc["breaches"] else "OK"
    return doc


def main() -> int:
    doc = check()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    for b in doc["breaches"]:
        print(f"check_principal_stops: BREACH {b['sleeve']} LIVE at {b['risk_frac']} "
              f"({b['written_by']}) -- {b['stop']}")
    print(f"check_principal_stops: {doc['status']} -- {len(doc['active_stops'])} active stop(s), "
          f"{len(doc['breaches'])} LIVE breach(es), {doc['held_off_live']} held"
          + (f"; {doc['why']}" if doc.get("why") else ""))
    return 0 if doc["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
