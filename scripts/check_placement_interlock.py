#!/usr/bin/env python
"""A RAIL THAT HALTS ALL TRADING MUST NOT BE ABLE TO DO SO QUIETLY.

WHAT HAPPENED, AND WHY THIS FILE EXISTS (2026-09-24).

`mt5desk/release_identity.verdict()` decides whether the box may open new risk. It is a good
rail and on 2026-09-24 it was right to fire: the box had sealed `dbbbbdcc4d2f` at 05:53Z and
every hourly re-seal afterwards was refused, so the running tree genuinely was not the sealed
one. The gateway did exactly what it was built to do -- it kept managing open positions, kept
ratcheting stops, and opened nothing.

It wrote that decision to `decision_ledger.jsonl` five hundred and eighty-three times that day,
once a minute, each row reading `release_identity_refused`. `gold_london_am` (10:00Z) and
`gold_afternoon` (14:00Z) placed nothing. **Not one of those rows reached an alert, a dashboard
or a human.** The principal found it by eye, and asked why the desk had not.

Walking the ledger backwards afterwards: the first `release_identity_refused` is
2026-09-07T07:35:15Z, seventeen days earlier. 1,200 rows. 19 gold sleeve-days lost against 22
placed -- the interlock silently took roughly 46% of the book's placement opportunities over
two and a half weeks, and the desk's own evidence recorded every one of them.

THE DEFECT IS NOT THE RAIL. It is that a halt could persist indefinitely while every organ
reported healthy: the gateway was alive and reconciling every minute, `gateway_state.json` had
a current `last_reconcile`, the task table read Ready, and the ledger filled up with the
evidence nobody read. An absence of orders looks exactly like a quiet market.

SO THIS FENCE READS THE HALT ITSELF, NOT ITS CAUSE. It does not ask why placement was refused;
it asks whether one reason has been repeating for one sleeve with no placement in between. That
generalises past today's instance on purpose -- the next halt will have a different `reason`
string, and a fence keyed to `release_identity_refused` would miss it exactly as thoroughly.

Two breaches, either sufficient:

  (a) A SLEEVE HAS BEEN REFUSED IN A RUN. `TRAILING_REFUSALS_MAX` consecutive not-taken rows
      sharing one reason, with no placement since, or a run spanning `TRAILING_HOURS_MAX`. At
      one row a minute, thirty rows is half an hour of a window that is open and not placing --
      short enough to catch the day it happens, long enough that a single contended seal or a
      minute of venue trouble does not page anybody.
  (b) THE IDENTITY VERDICT ITSELF REFUSES, and has for longer than the same grace. This is the
      belt to (a)'s braces: it fires even if the gateway stops writing ledger rows at all, which
      is the one failure mode a ledger-shaped fence cannot see.

IT CAPS NOTHING AND GATES NO CAPITAL. It never touches a sleeve, a lot, a threshold or the heat
floor; it fails a check when the desk has stopped placing and has not said so. If anything it
exists to make the book trade MORE, by ending halts in minutes rather than days.

NOT-APPLICABLE IS NOT UNMEASURED (L1.43). A host with no decision ledger and no gateway state
never places orders -- CI, a fresh clone, the VPS -- and passes saying so. A host that HAS a
gateway and produces no readable ledger is UNMEASURED and FAILS (L1.28a, WS-005), because "no
evidence" is precisely what the outage looked like.

Artifact: `desks/mt5/reports/PLACEMENT_INTERLOCK.json`, an entry in `data/alert_ledger.json`
so the condition has a lifecycle rather than only a count, and a PLACEMENT_HALTED /
PLACEMENT_CLEAR row on the desk's event log (`desks/mt5/data/events.jsonl`). Registered in
`scripts/run_law_gate.py` `_STATE_FENCES`, so the box's law-gate rotation runs it on a clock
and a halt reddens the gate itself. (Recovered from the unpushed box commit fe09b89b,
ported onto origin 2026-09-30.)

    python scripts/check_placement_interlock.py
    python scripts/check_placement_interlock.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
OUT = DESK / "reports" / "PLACEMENT_INTERLOCK.json"

LEDGER_REL = "desks/mt5/data/decision_ledger.jsonl"
IDENTITY_REL = "desks/mt5/data/release_identity.json"
GATEWAY_STATE_REL = "desks/mt5/data/gateway_state.json"

#: Consecutive same-reason refusals for one sleeve that count as a halt rather than a hiccup.
#: The gateway writes one row per pass per sleeve, and a pass is a minute.
TRAILING_REFUSALS_MAX = 30
#: ...or the same run measured in time, for a gateway whose pass interval is longer.
TRAILING_HOURS_MAX = 1.0

#: Reasons that are the VENUE's answer rather than the desk's own refusal. A broker rejection or
#: a freeze-band skip is the market saying no to one order; it is not the desk declining to
#: trade, and a run of them means something different. They are reported, never breached on.
VENUE_REASONS: frozenset[str] = frozenset({
    "broker_rejected", "entry_inside_freeze_band", "margin_guard",
})

#: The row's own field names, in the order the ledger has used them.
_TS_FIELDS = ("decided_at", "ts", "at", "time")
_TAKEN_REASONS = frozenset({"placed"})

UNMEASURED = "UNMEASURED"
ALERT_ID = "placement_interlock_halt"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _parse_iso(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def _row_time(row: dict[str, Any]) -> datetime | None:
    for field in _TS_FIELDS:
        if row.get(field):
            stamp = _parse_iso(row[field])
            if stamp is not None:
                return stamp
    return None


def _was_taken(row: dict[str, Any]) -> bool:
    """A row that put an order at the venue. `taken` is authoritative where present; the older
    rows carry only `reason`/`outcome`, so both are read rather than assumed."""
    if isinstance(row.get("taken"), bool):
        return bool(row["taken"])
    if str(row.get("reason") or "") in _TAKEN_REASONS:
        return True
    return str(row.get("outcome") or "").upper() in ("EXECUTED", "PLACED", "FILLED")


def read_ledger(path: Path, *, limit: int = 40000) -> tuple[list[dict[str, Any]], str | None]:
    """The last `limit` decision rows, newest last. Returns (rows, problem)."""
    try:
        raw = path.read_text("utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], f"{LEDGER_REL} exists but could not be read ({type(exc).__name__})"
    rows: list[dict[str, Any]] = []
    for line in raw[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows, None


def trailing_runs(rows: list[dict[str, Any]], now: datetime) -> dict[str, dict[str, Any]]:
    """Per sleeve: the run of consecutive not-taken rows sharing one reason at the END of its
    history. A placement, or a row with a different reason, ends the run -- which is what makes
    this a measure of "still refusing right now" rather than a lifetime count."""
    by_sleeve: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_sleeve.setdefault(str(row.get("sleeve") or row.get("strategy_id") or "?"),
                             []).append(row)
    runs: dict[str, dict[str, Any]] = {}
    for sleeve, history in by_sleeve.items():
        run: list[dict[str, Any]] = []
        reason: str | None = None
        for row in reversed(history):
            if _was_taken(row):
                break
            this = str(row.get("reason") or "")
            if reason is None:
                reason = this
            elif this != reason:
                break
            run.append(row)
        if not run or not reason:
            continue
        stamps = [s for s in (_row_time(r) for r in run) if s is not None]
        first, last = (min(stamps), max(stamps)) if stamps else (None, None)
        runs[sleeve] = {
            "reason": reason,
            "count": len(run),
            "first_at": first.isoformat(timespec="seconds") if first else UNMEASURED,
            "last_at": last.isoformat(timespec="seconds") if last else UNMEASURED,
            "span_h": round((last - first).total_seconds() / 3600.0, 3) if first and last
            else None,
            "age_h": round((now - last).total_seconds() / 3600.0, 3) if last else None,
            "venue_reason": reason in VENUE_REASONS,
        }
    return runs


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def scan(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    t_now = now or _now()
    ledger = base / Path(*LEDGER_REL.split("/"))
    identity = base / Path(*IDENTITY_REL.split("/"))
    gateway_state = base / Path(*GATEWAY_STATE_REL.split("/"))

    doc: dict[str, Any] = {
        "generated": t_now.isoformat(timespec="seconds"), "root": str(base),
        "thresholds": {"trailing_refusals_max": TRAILING_REFUSALS_MAX,
                       "trailing_hours_max": TRAILING_HOURS_MAX},
        "problems": [], "notes": [], "runs": {}, "ok": True, "verdict": "OK",
    }

    # NOT APPLICABLE: a host that never places orders has nothing to be silent about.
    if not ledger.exists() and not gateway_state.exists():
        doc["verdict"] = "NOT_APPLICABLE"
        doc["notes"].append(
            "no decision ledger and no gateway state here -- this host does not place orders, "
            "so there is no placement halt it could be hiding")
        return doc

    if not ledger.exists():
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(
            f"this host has {GATEWAY_STATE_REL} but no {LEDGER_REL}: a gateway that places "
            "orders and records no decisions is exactly what a silent halt looks like")
        return doc

    rows, problem = read_ledger(ledger)
    if problem:
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(problem)
        return doc
    if not rows:
        doc.update(ok=False, verdict="UNMEASURED")
        doc["problems"].append(f"{LEDGER_REL} holds no readable decision rows")
        return doc

    runs = trailing_runs(rows, t_now)
    doc["runs"] = runs
    doc["rows_scanned"] = len(rows)

    for sleeve, run in sorted(runs.items()):
        long_by_count = run["count"] >= TRAILING_REFUSALS_MAX
        span = run.get("span_h")
        long_by_time = isinstance(span, (int, float)) and span >= TRAILING_HOURS_MAX
        if not (long_by_count or long_by_time):
            continue
        if run["venue_reason"]:
            doc["notes"].append(
                f"{sleeve}: {run['count']} consecutive '{run['reason']}' rows -- the VENUE's "
                "answer, not the desk declining to trade; reported, not breached")
            continue
        doc["ok"] = False
        doc["problems"].append(
            f"{sleeve} has been refused {run['count']} times in a row on '{run['reason']}' "
            f"since {run['first_at']}"
            + (f" ({span:.1f}h)" if isinstance(span, (int, float)) else "")
            + " with no placement in between -- a halt this long has to be visible somewhere, "
              "and until this fence existed it was not")

    # (b) The verdict itself, for the case where the gateway stops writing rows entirely.
    ident = _read_json(identity)
    if ident is None:
        doc["notes"].append(f"{IDENTITY_REL} unreadable; the ledger half of this fence still ran")
    else:
        doc["identity"] = {
            "verdict": ident.get("verdict"), "allows_new_risk": ident.get("allows_new_risk"),
            "at": ident.get("at"), "reason": str(ident.get("reason") or "")[:400],
        }
        stamp = _parse_iso(ident.get("at"))
        age_h = (t_now - stamp).total_seconds() / 3600.0 if stamp else None
        doc["identity"]["age_h"] = round(age_h, 3) if age_h is not None else UNMEASURED
        if ident.get("allows_new_risk") is False and (age_h is None
                                                      or age_h <= TRAILING_HOURS_MAX * 3):
            doc["ok"] = False
            doc["problems"].append(
                "the release identity currently refuses new risk "
                f"({ident.get('verdict')}): {str(ident.get('reason') or '')[:220]}")

    doc["verdict"] = "OK" if doc["ok"] else "HALTED"
    return doc


def record_alert(doc: dict[str, Any], root: Path | None = None) -> str | None:
    """Give the condition a LIFECYCLE, not just a count. A halt that opens and is never closed
    is the shape this whole file is about; `AlertLedger` is where the desk already keeps that."""
    base = Path(root or ROOT)
    try:
        sys.path.insert(0, str(base))
        from libs.ops.alert_ledger import AlertLedger
    except Exception:
        return None
    try:
        ledger = AlertLedger(base / "data" / "alert_ledger.json")
        if doc.get("ok") or doc.get("verdict") == "NOT_APPLICABLE":
            alert = ledger.alerts.get(ALERT_ID)
            if alert is not None and alert.open:
                # `verify` and not an absence: this scan IS the re-run of the check, which is the
                # only evidence `AlertLedger` accepts for closing something (and rightly).
                ledger.verify(ALERT_ID, still_firing=False)
                ledger.save()
                return "FIXED"
            return None
        ledger.observe(ALERT_ID, "; ".join(str(p) for p in doc.get("problems", []))[:600],
                       scope="RUNTIME")
        ledger.save()
        return "OPEN"
    except Exception:
        return None


def record_event(doc: dict[str, Any], root: Path | None = None) -> str | None:
    """Put the halt on the desk's EVENT LOG too (`libs/ops/events.py`), the third surface an
    operator meets without asking. PLACEMENT_HALTED carries the halted sleeves and the problems;
    PLACEMENT_CLEAR is written on a clean pass on a host that places orders, so the absence of a
    halt is itself recorded rather than inferred from an absence of rows. A host that never
    places (NOT_APPLICABLE) writes nothing. The writer never raises."""
    if doc.get("verdict") == "NOT_APPLICABLE":
        return None
    base = Path(root or ROOT)
    try:
        if str(base) not in sys.path:
            sys.path.insert(0, str(base))
        from libs.ops import events
    except Exception:
        return None
    try:
        if doc.get("ok"):
            events.emit("PLACEMENT_CLEAR", producer="check_placement_interlock",
                        rows_scanned=doc.get("rows_scanned"))
            return "PLACEMENT_CLEAR"
        halted = sorted(s for s, r in (doc.get("runs") or {}).items()
                        if not r.get("venue_reason"))
        events.emit("PLACEMENT_HALTED", producer="check_placement_interlock",
                    priority=2, verdict=doc.get("verdict"), sleeves=halted,
                    problems=[str(p)[:300] for p in doc.get("problems", [])][:12])
        return "PLACEMENT_HALTED"
    except Exception:
        return None


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    args = ap.parse_args(argv)

    doc = scan()
    if not args.no_write:
        write_artifact(doc)
        doc["alert"] = record_alert(doc)
        doc["event"] = record_event(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc["ok"] else 2

    print(f"placement interlock: {doc.get('verdict')}; "
          f"{len(doc.get('runs') or {})} sleeve(s) with a trailing refusal run")
    for sleeve, run in sorted((doc.get("runs") or {}).items()):
        print(f"  {sleeve}: {run['count']}x '{run['reason']}' since {run['first_at']}")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"]:
        print("check_placement_interlock: OK -- no sleeve is silently halted")
        return 0
    print("check_placement_interlock: FAILED -- the desk has stopped placing and did not say so")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
