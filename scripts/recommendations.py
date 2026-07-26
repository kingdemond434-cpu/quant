#!/usr/bin/env python3
"""RECOMMENDATION LEDGER (§41, principal 2026-07-26) -- nothing recommended is ever forgotten.

THE HOLE. track_findings.py governs PANEL findings only (model / summary / accepted-or-rejected).
Everything else this desk produces a recommendation from -- max_audit defects, the weekly deep cold
audit, cycle reports, the proactive battery, external reviews -- had no ledger and no forced
disposition. A deep sweep could name eight high-ROI improvements, the report gets written, the
window closes, and by the next Sunday nobody knows they existed. That is the same class as the
findings hole it was built to close, one layer up.

THE LAW. Every recommendation gets exactly one row, and every row must reach a DISPOSITION:
IMPLEMENTED (with a commit), REJECTED (with a real reason), or SCHEDULED (with a due date that is
itself enforced). "No decision" is not a state a row may rest in -- an undisposed row past its
grace window is a DEFECT, not backlog. Rejection is always available and is a legitimate answer,
because the principal's instruction is that nothing is SKIPPED, not that everything is BUILT: a
reasoned no is a decision, silence is the failure.

WHY IT CANNOT BE GAMED. Rows are never deleted and dispositions never revert to none, so the
cheap escape -- quietly dropping an inconvenient row -- is closed the same way the mining ratchet
closes shrinking the denominator. A rejection needs a substantive reason (a bare "no" is refused
at the CLI), and a SCHEDULED row that passes its due date fires exactly like an orphan, so
"scheduled" cannot become a place recommendations go to die.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "docs/research/recommendation_ledger.json"

# A recommendation may sit undisposed for one cycle -- long enough to be triaged in the next
# organ run, short enough that it cannot quietly become permanent.
GRACE_H = 24.0
_TERMINAL = ("implemented", "rejected")
_MIN_REASON = 25          # a bare "no" / "wontfix" is not a disposition


def _load() -> dict[str, Any]:
    if LEDGER.exists():
        try:
            return json.loads(LEDGER.read_text("utf-8"))
        except Exception:
            pass
    return {"recommendations": []}


def _save(d: dict[str, Any]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1), "utf-8")
    tmp.replace(LEDGER)          # atomic: a torn ledger would lose the very rows it protects


def _age_h(iso: str) -> float:
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except Exception:
        return 0.0


def add(a: argparse.Namespace) -> None:
    d = _load()
    # DEDUPE on (source, summary): organs re-read the same audit report every cycle, and a ledger
    # that grows a duplicate row per read becomes noise nobody triages -- which is the failure it
    # exists to prevent, arriving by a different route.
    for r in d["recommendations"]:
        if r["source"] == a.source and r["summary"].strip() == a.summary.strip():
            print(f"{r['id']} already ledgered ({r['status']})")
            return
    rid = f"R{len(d['recommendations']) + 1:04d}"
    d["recommendations"].append({
        "id": rid, "source": a.source, "summary": a.summary,
        "roi_bps": a.roi_bps, "raised": datetime.now(tz=UTC).isoformat(),
        "status": "open", "reason": None, "commit": None, "due": None, "disposed": None})
    _save(d)
    print(f"{rid} ledgered from {a.source} -- OPEN, disposition owed within {GRACE_H:.0f}h")


def dispose(a: argparse.Namespace) -> None:
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] in _TERMINAL:
        raise SystemExit(f"{a.id} is already {row['status']} -- dispositions do not revert")
    if a.status == "rejected" and len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(
            f"a rejection needs a real reason (>={_MIN_REASON} chars). The principal's "
            "standard is that nothing is SKIPPED, not that everything is built -- a "
            "reasoned no is a decision, a bare no is silence wearing a label.")
    if a.status == "scheduled" and not a.due:
        raise SystemExit("a scheduled recommendation needs --due YYYY-MM-DD, else 'scheduled' "
                         "becomes the place recommendations go to die")
    if a.status == "implemented" and not a.commit:
        raise SystemExit("an implemented recommendation needs --commit: the desk's standing rule "
                         "is that an artifact proves the work, never a claim")
    row.update(status=a.status, reason=a.reason, commit=a.commit, due=a.due,
               disposed=datetime.now(tz=UTC).isoformat())
    _save(d)
    print(f"{a.id} -> {a.status.upper()}")


def owed(d: dict[str, Any]) -> tuple[list[Any], list[Any]]:
    """(undisposed past grace, scheduled past due) -- the two ways a row goes stale."""
    now = datetime.now(tz=UTC)
    orphans = [r for r in d["recommendations"]
               if r["status"] == "open" and _age_h(r["raised"]) > GRACE_H]
    overdue = []
    for r in d["recommendations"]:
        if r["status"] != "scheduled" or not r.get("due"):
            continue
        try:
            if datetime.fromisoformat(str(r["due"])).replace(tzinfo=UTC) < now:
                overdue.append(r)
        except Exception:
            overdue.append(r)          # an unparseable due date is not a valid schedule
    return orphans, overdue


def report(_a: argparse.Namespace) -> None:
    d = _load()
    rows = d["recommendations"]
    orphans, overdue = owed(d)
    done = [r for r in rows if r["status"] == "implemented"]
    print(f"recommendations: {len(rows)} total | {len(done)} implemented | "
          f"{sum(1 for r in rows if r['status'] == 'rejected')} rejected | "
          f"{sum(1 for r in rows if r['status'] == 'scheduled')} scheduled | "
          f"{sum(1 for r in rows if r['status'] == 'open')} open")
    for label, group in (("UNDISPOSED past grace", orphans), ("SCHEDULED past due", overdue)):
        for r in group:
            print(f"  DEFECT [{label}] {r['id']} ({r['source']}, {_age_h(r['raised']) / 24:.1f}d): "
                  f"{r['summary'][:110]}")
    if not orphans and not overdue:
        print("  no orphans, nothing overdue -- every recommendation has a decision")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="ledger a recommendation (status opens as undisposed)")
    p.add_argument("--source", required=True,
                   help="max_audit | deep_sweep | cycle | panel | proactive_battery | principal")
    p.add_argument("--summary", required=True)
    p.add_argument("--roi-bps", dest="roi_bps", type=float, default=None)
    p.set_defaults(func=add)
    p = sub.add_parser("dispose", help="record the decision -- the only way a row leaves open")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=["implemented", "rejected", "scheduled"])
    p.add_argument("--reason")
    p.add_argument("--commit")
    p.add_argument("--due", help="YYYY-MM-DD, required for scheduled")
    p.set_defaults(func=dispose)
    p = sub.add_parser("report", help="orphans and overdue -- both are defects, not backlog")
    p.set_defaults(func=report)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
