#!/usr/bin/env python3
"""RECOMMENDATION LEDGER (§42, principal 2026-07-26) -- nothing recommended is ever forgotten.

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
            loaded: dict[str, Any] = json.loads(LEDGER.read_text("utf-8"))
            return loaded
        except Exception as e:
            # A corrupt ledger must NEVER read as empty-healthy: `report` would print
            # "0 total, nothing overdue" and the next _save would atomically replace
            # every row with the empty dict -- the mass-deletion the ledger law forbids.
            # Observed live 2026-07-31: merge-conflict markers committed to origin read
            # here as a clean empty ledger. Refuse loudly; git history repairs it.
            raise SystemExit(
                f"REFUSING: {LEDGER} exists but cannot be parsed ({e}); repair it from "
                "git history -- an unreadable ledger must never become an empty one") from e
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


def _next_id(d: dict) -> str:
    """Allocate past BOTH the local ledger and the last-fetched origin/master copy (R0152).

    Count-based allocation minted the same id on two boxes three times on 2026-07-31
    (R0135-37, R0143, R0144): each box counts its own rows, so concurrent sessions collide
    and every merge renumbers rows and repoints code comments. Max-known-id with origin
    consulted (git show reads the fetched ref -- no network) shrinks the race window from
    all-day to since-last-fetch; an unreadable origin falls back to the local max, which
    still never re-mints an id a renumber has already retired.
    """
    import re
    import subprocess
    nums = [int(m.group(1)) for r in d["recommendations"]
            if (m := re.match(r"R(\d+)$", str(r.get("id", ""))))]
    try:
        remote = subprocess.run(
            ["git", "show", "origin/master:docs/research/recommendation_ledger.json"],
            capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).resolve().parent.parent)
        if remote.returncode == 0:
            nums += [int(x) for x in re.findall(r'"id":\s*"R(\d+)"', remote.stdout)]
    except (OSError, subprocess.SubprocessError):
        pass                                   # offline clone: local max still monotonic
    return f"R{(max(nums) if nums else 0) + 1:04d}"


def add(a: argparse.Namespace) -> None:
    d = _load()
    # DEDUPE on (source, summary): organs re-read the same audit report every cycle, and a ledger
    # that grows a duplicate row per read becomes noise nobody triages -- which is the failure it
    # exists to prevent, arriving by a different route.
    for r in d["recommendations"]:
        if r["source"] == a.source and r["summary"].strip() == a.summary.strip():
            print(f"{r['id']} already ledgered ({r['status']})")
            return
    rid = _next_id(d)
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
        raise SystemExit(f"{a.id} is already {row['status']} -- dispositions do not revert. "
                         "If it was MISFILED, use `correct --id --reason`, which logs the "
                         "reversal in the row history rather than erasing it.")
    # GUARD AGAINST DISPOSING THE WRONG ROW (2026-07-26): ids are assigned by count, so a
    # concurrent writer -- the weekly sweep ledgering seven rows mid-session -- shifts the id
    # a caller assumed. --expect makes the caller name what it thinks it is deciding.
    if a.expect and a.expect.lower() not in row["summary"].lower():
        raise SystemExit(
            f"{a.id} does not match --expect {a.expect!r}. Its summary is:\n  "
            f"{row['summary'][:200]}\nAnother writer may have taken the id you assumed.")
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


def correct(a: argparse.Namespace) -> None:
    """Reverse a MIS-ENTERED disposition, permanently logging that it happened.

    "Dispositions never revert" is the right guard against gaming and the wrong one against error:
    it made an honest mis-entry unfixable. What actually prevents laundering is not immovability
    but VISIBILITY -- a correction keeps the original disposition, its reason, and the reason it
    was wrong in the row's own history, so the record reads as "decided, then found misfiled",
    never as "never decided". Corrections are cheap to audit and impossible to hide.
    """
    d = _load()
    row = next((r for r in d["recommendations"] if r["id"] == a.id), None)
    if row is None:
        raise SystemExit(f"no such recommendation: {a.id}")
    if row["status"] == "open":
        raise SystemExit(f"{a.id} is already open -- nothing to correct")
    if len((a.reason or "").strip()) < _MIN_REASON:
        raise SystemExit(f"a correction needs a real reason (>={_MIN_REASON} chars): what was "
                         "misfiled, and why the original disposition did not apply to this row")
    row.setdefault("corrections", []).append({
        "was": row["status"], "was_reason": row.get("reason"),
        "was_commit": row.get("commit"), "was_due": row.get("due"),
        "corrected": datetime.now(tz=UTC).isoformat(), "why": a.reason})
    row.update(status="open", reason=None, commit=None, due=None, disposed=None)
    _save(d)
    print(f"{a.id} corrected -> OPEN (prior disposition kept in its history); "
          "a fresh disposition is now owed")


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
    p.add_argument("--expect", help="substring the target summary must contain -- "
                                    "guards against disposing a row another writer "
                                    "took the id of")
    p.set_defaults(func=dispose)
    p = sub.add_parser("correct", help="reverse a MISFILED disposition, logged")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=correct)
    p = sub.add_parser("report", help="orphans and overdue -- both are defects, not backlog")
    p.set_defaults(func=report)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
