#!/usr/bin/env python3
"""THE RECOMMENDATION-FLOW FENCE -- the lane from recommendation to implementation must DRAIN.

WHAT IT CAUGHT ON ITS FIRST READING (trading box, 2026-09-23). The ledger held 777 rows, 219 of
them OPEN, and had not been written for 281.7 hours. Nothing failed. `check_conversion` measures
arrivals against dispositions and reads a queue that has STOPPED ENTIRELY as a queue with no
arrivals -- which is not distinguishable, by that measurement, from a queue that is caught up.
`check_citation_integrity` verifies the citations of rows that reached a disposition and is silent
about rows that never will. `check_row_atomicity` asks whether a row bundles deliverables. Three
fences over one ledger, all green, while the CEO side wrote a fresh docket every day into a file
physically unwritable from the box that runs it.

THREE PROPERTIES, EACH FAILING FOR ITS OWN REASON.

  STALE     The ledger has its own cadence -- `implementer.CADENCE_H`, two hourly cycles of
            headroom -- and a ledger past it means the drain has stopped, whatever the counts
            say. This half is STATE: on a fresh clone `last_drain_at` is whatever the last commit
            carried, so it is reported without failing unless `--require-state` says the clock is
            supposed to be running here.

  ORPHAN    An OPEN row with no `owner` and no `next_action` is the defect the implementer exists
            to remove. Not "backlog": nobody is on it and there is no next step, so it will still
            be there next year unless someone stumbles over it. Portable and fatal -- the ledger
            is tracked, so this means the same thing in CI, in a fresh clone and on the box.

  RATCHET   The OPEN backlog ratchets DOWN only. A rise is legal exactly when the ratchet file
            records what caused it (intake from a named source). An unexplained rise means rows
            are arriving faster than anyone is deciding and nobody noticed -- and a LEVEL cannot
            see that: the desk measured its old level fence reading RED for 226 of 226
            informative hours, which is a gate carrying no information.

IT REPAIRS NOTHING. The organ on the other end (`desks/mt5/research/implementer.py`, leg
`hourly_cycle:implementer`) does the work; a fence that fixed its own subject would be both the
judge and the defendant.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEDGER_REL = "docs/research/recommendation_ledger.json"
RATCHET_REL = "desks/mt5/data/recommendation_ratchet.json"
REPORT_REL = "desks/mt5/reports/RECOMMENDATION_FLOW.json"

#: Mirrors `implementer.CADENCE_H`. Imported when the organ is importable and stated here as the
#: fallback, because a fence that cannot run without its subject is a fence that goes dark exactly
#: when the subject breaks.
CADENCE_H = 3.0

OK, FAIL = 0, 1


def _load(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _age_h(iso: Any) -> float | None:
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(str(iso))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return None


def _cadence() -> float:
    try:
        sys.path.insert(0, str(ROOT / "desks" / "mt5"))
        mod = importlib.import_module("research.implementer")
        return float(mod.CADENCE_H)
    except Exception:
        return CADENCE_H


def build_report(root: Path, require_state: bool = False) -> dict[str, Any]:
    ledger = _load(root / LEDGER_REL)
    if not isinstance(ledger, dict) or not isinstance(ledger.get("recommendations"), list):
        return {"status": "UNREADABLE", "detail": f"{LEDGER_REL} is missing or unparseable -- "
                "repair it from git history; an unreadable ledger must never read as empty",
                "failures": ["ledger unreadable"], "measured_at": datetime.now(tz=UTC).isoformat()}
    rows = ledger["recommendations"]
    cadence = _cadence()
    failures: list[str] = []
    unmeasured: list[str] = []

    # --- STALE ------------------------------------------------------------------------------
    stamps = [ledger.get("last_drain_at")]
    stamps += [r.get("disposed") for r in rows if r.get("disposed")]
    stamps += [r.get("raised") for r in rows if r.get("raised")]
    ages = [a for a in (_age_h(s) for s in stamps if s) if a is not None]
    stale_h = min(ages) if ages else None
    if stale_h is None:
        unmeasured.append("no readable timestamp anywhere in the ledger")
    elif stale_h > cadence:
        msg = (f"ledger is {stale_h:.1f}h stale against its own {cadence:g}h cadence "
               f"(last_drain_at={ledger.get('last_drain_at')}) -- the drain has stopped")
        if require_state:
            failures.append(msg)
        else:
            unmeasured.append(msg + " [reported, not fatal: no --require-state]")

    # --- ORPHAN -----------------------------------------------------------------------------
    open_rows = [r for r in rows if r.get("status") == "open"]
    orphans = [str(r.get("id")) for r in open_rows
               if not (str(r.get("owner") or "").strip()
                       and str(r.get("next_action") or "").strip())]
    if orphans:
        failures.append(
            f"{len(orphans)} OPEN row(s) carry no owner and no next action: {orphans[:12]} -- "
            "an open row nobody owns with no next step is not backlog, it is a row that will "
            "still be open next year. desks/mt5/research/implementer.py assigns both.")

    # --- RATCHET ----------------------------------------------------------------------------
    ratchet = _load(root / RATCHET_REL)
    open_now = len(open_rows)
    if not isinstance(ratchet, dict) or ratchet.get("floor") is None:
        unmeasured.append(f"{RATCHET_REL} absent or unseeded -- the OPEN ratchet has no floor "
                          "yet; the implementer seeds it on its first pass")
    else:
        floor = int(ratchet["floor"])
        if open_now > floor:
            rises = [x for x in (ratchet.get("rises") or [])
                     if int(x.get("to", 0)) >= open_now and str(x.get("reason") or "").strip()]
            if not rises:
                failures.append(
                    f"OPEN count {open_now} is above the ratchet floor {floor} and no recorded "
                    f"rise explains it ({RATCHET_REL}). The backlog ratchets DOWN only: rows may "
                    "arrive, but a pass that raises the count must name what raised it.")

    status = "FAIL" if failures else ("UNMEASURED" if unmeasured and stale_h is None else "OK")
    return {
        "status": status,
        "measured_at": datetime.now(tz=UTC).isoformat(),
        "cadence_h": cadence,
        "ledger_stale_h": round(stale_h, 2) if stale_h is not None else None,
        "last_drain_at": ledger.get("last_drain_at"),
        "n_rows": len(rows), "n_open": open_now,
        "n_open_without_owner": len(orphans),
        "open_without_owner": orphans[:50],
        "ratchet_floor": (ratchet or {}).get("floor") if isinstance(ratchet, dict) else None,
        "failures": failures, "unmeasured": unmeasured,
        "require_state": require_state,
        "law": ("The recommendation-to-implementation lane must DRAIN: the ledger moves on its "
                "own cadence, every OPEN row names an owner and a next action, and the OPEN "
                "backlog ratchets DOWN only."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--require-state", action="store_true",
                    help="grade ledger staleness as a failure (the box, where the clock runs)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="measure and always exit 0")
    a = ap.parse_args(argv)
    rep = build_report(ROOT, require_state=a.require_state)
    out = ROOT / REPORT_REL
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=1), "utf-8")
    except OSError as exc:
        print(f"  WARNING: report not written: {type(exc).__name__}: {exc}")
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"recommendation flow: {rep['status']} -- {rep['n_open']} open of "
              f"{rep['n_rows']}, stale {rep['ledger_stale_h']}h of {rep['cadence_h']:g}h, "
              f"{rep['n_open_without_owner']} without an owner")
        for f in rep["failures"]:
            print(f"  FAIL  {f}")
        for u in rep["unmeasured"]:
            print(f"  UNMEASURED  {u}")
        print(f"  -> {out}")
    if a.report_only:
        return OK
    return FAIL if rep["failures"] or rep["status"] == "UNREADABLE" else OK


if __name__ == "__main__":
    sys.exit(main())
