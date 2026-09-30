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

APPLICABILITY IS DECIDED BY LIVE EVIDENCE, NEVER BY A FILE EXISTING (audit of PR #130). The
decision ledger, the gateway state and the identity verdict are all TRACKED in git, so every
checkout -- the cloud, the VPS, CI -- has them, carrying whatever rows the box last published.
Keyed to existence, the fence read 09-07..09-11 rows on the VPS as a current halt and held the
VPS law gate red for good. So:

  * no ledger and no gateway state: NOT_APPLICABLE, passes saying so (L1.43).
  * a ledger whose newest row is older than `LEDGER_LIVE_HOURS`: UNMEASURED, and reported as
    UNMEASURED -- `ok` is None, not True, because it is not a clean pass, but it does not fail
    the gate either: stale rows are no evidence of a halt NOW, and a gate red on every machine
    that was never going to trade gets switched off. Nothing is written to the committed report.
  * a live ledger (or a gateway state whose `last_reconcile` is live) with no readable rows:
    UNMEASURED and FAILS (L1.28a, WS-005), because "no evidence" is what the outage looked like.

A RUN AGES OUT. A refusal run whose last row is older than `RUN_MAX_AGE_HOURS`, or whose sleeve
the sleeve registry names with a status other than LIVE, is history -- reported as a note, never
a current halt -- or a retired sleeve would hold the fence red forever.

A STALE IDENTITY IS LOUD. On a host whose ledger is live, an identity verdict older than
`IDENTITY_MAX_AGE_HOURS` (or missing, or unstamped) FAILS as IDENTITY_STALE: a gateway that has
stopped writing its verdict is the dead-gateway case breach (b) exists for, so it may never
read as silence.

Artifact: `desks/mt5/data/placement_interlock.json` -- committed (not gitignored), carried to the
branch by `desks/mt5/scripts/sync_shadow_to_git.ps1` (declared in `release.NON_CODE`), and
written only on a host where the fence is applicable -- an entry in `data/alert_ledger.json`
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
#: Committed (NOT under the gitignored `**/reports/*`), a box-written state path the box's
#: 15-minute sync publishes; origin never hand-edits it, and an off-box run never writes it.
OUT_REL = "desks/mt5/data/placement_interlock.json"
OUT = ROOT / Path(*OUT_REL.split("/"))

LEDGER_REL = "desks/mt5/data/decision_ledger.jsonl"
IDENTITY_REL = "desks/mt5/data/release_identity.json"
GATEWAY_STATE_REL = "desks/mt5/data/gateway_state.json"
#: READ ONLY -- to learn whether a sleeve with a refusal run is still LIVE. Never written here.
SLEEVE_REGISTRY_REL = "desks/mt5/data/" + "sleeves" + ".json"

#: Consecutive same-reason refusals for one sleeve that count as a halt rather than a hiccup.
#: The gateway writes one row per pass per sleeve, and a pass is a minute.
TRAILING_REFUSALS_MAX = 30
#: ...or the same run measured in time, for a gateway whose pass interval is longer.
TRAILING_HOURS_MAX = 1.0
#: The ledger counts as LIVE evidence only if its newest row is at most this old. Older rows are
#: what a checkout that only carries the box's last published copy holds: no evidence of now.
LEDGER_LIVE_HOURS = 24.0
#: A refusal run whose last row is older than this is history, not a current halt.
RUN_MAX_AGE_HOURS = 24.0
#: The gateway rewrites its identity verdict every pass (a minute); three hours of silence is a
#: gateway that has stopped, which is the case breach (b) exists for.
IDENTITY_MAX_AGE_HOURS = TRAILING_HOURS_MAX * 3

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


def _age_h(stamp: datetime | None, now: datetime) -> float | None:
    return (now - stamp).total_seconds() / 3600.0 if stamp else None


def sleeve_status(base: Path) -> dict[str, str]:
    """name -> status from the sleeve registry, READ ONLY. An absent or unreadable registry is an
    empty map: a sleeve the registry does not name (the gold windows) is judged by age alone."""
    doc = _read_json(base / Path(*SLEEVE_REGISTRY_REL.split("/")))
    rows = (doc or {}).get("sleeves")
    out: dict[str, str] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("name"):
                out[str(row["name"])] = str(row.get("status") or "")
    return out


def _gateway_live(gateway_state: Path, now: datetime) -> bool:
    """A gateway state whose `last_reconcile` is inside the live window: this host runs one."""
    doc = _read_json(gateway_state) or {}
    age = _age_h(_parse_iso(doc.get("last_reconcile")), now)
    return age is not None and age <= LEDGER_LIVE_HOURS


def _no_evidence(doc: dict[str, Any], problem: str, *, live: bool) -> dict[str, Any]:
    """No readable rows. On a host with a live gateway that FAILS; elsewhere it is UNMEASURED
    and reported so, neither a pass nor a halt."""
    doc["verdict"] = UNMEASURED
    if live:
        doc.update(ok=False, applicable=True)
        doc["problems"].append(problem)
    else:
        doc.update(ok=None, applicable=False)
        doc["notes"].append(problem + " -- and no live gateway evidence here, so UNMEASURED "
                            "on this host (not a pass, not a halt)")
    return doc


def scan(root: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    base = Path(root or ROOT)
    t_now = now or _now()
    ledger = base / Path(*LEDGER_REL.split("/"))
    identity = base / Path(*IDENTITY_REL.split("/"))
    gateway_state = base / Path(*GATEWAY_STATE_REL.split("/"))

    doc: dict[str, Any] = {
        "generated": t_now.isoformat(timespec="seconds"), "root": str(base),
        "thresholds": {"trailing_refusals_max": TRAILING_REFUSALS_MAX,
                       "trailing_hours_max": TRAILING_HOURS_MAX,
                       "ledger_live_hours": LEDGER_LIVE_HOURS,
                       "run_max_age_hours": RUN_MAX_AGE_HOURS,
                       "identity_max_age_hours": IDENTITY_MAX_AGE_HOURS},
        "problems": [], "notes": [], "runs": {}, "ok": True, "verdict": "OK",
        "applicable": True,
    }

    # NOT APPLICABLE: a host that never places orders has nothing to be silent about.
    if not ledger.exists() and not gateway_state.exists():
        doc.update(verdict="NOT_APPLICABLE", applicable=False)
        doc["notes"].append(
            "no decision ledger and no gateway state here -- this host does not place orders, "
            "so there is no placement halt it could be hiding")
        return doc

    gw_live = _gateway_live(gateway_state, t_now)
    if not ledger.exists():
        return _no_evidence(doc, (
            f"this host has {GATEWAY_STATE_REL} but no {LEDGER_REL}: a gateway that places "
            "orders and records no decisions is exactly what a silent halt looks like"),
            live=gw_live)

    rows, problem = read_ledger(ledger)
    if problem:
        return _no_evidence(doc, problem, live=gw_live)
    if not rows:
        return _no_evidence(doc, f"{LEDGER_REL} holds no readable decision rows", live=gw_live)

    # (1) IS THE LEDGER LIVE? Existence proves nothing: the file is tracked in git.
    stamps = [t for t in (_row_time(r) for r in rows) if t is not None]
    newest = max(stamps) if stamps else None
    ledger_age = _age_h(newest, t_now)
    doc["ledger_newest_at"] = newest.isoformat(timespec="seconds") if newest else UNMEASURED
    doc["ledger_age_h"] = round(ledger_age, 3) if ledger_age is not None else UNMEASURED
    doc["rows_scanned"] = len(rows)
    if ledger_age is None or ledger_age > LEDGER_LIVE_HOURS:
        doc.update(ok=None, applicable=False, verdict=UNMEASURED)
        doc["notes"].append(
            f"{LEDGER_REL}'s newest row is {doc['ledger_newest_at']}"
            + (f" ({ledger_age:.1f}h old)" if ledger_age is not None else "")
            + f", past the {LEDGER_LIVE_HOURS:.0f}h live window: this is a published copy, not "
              "a live ledger, so whether a sleeve is halted NOW is UNMEASURED on this host")
        return doc

    runs = trailing_runs(rows, t_now)
    doc["runs"] = runs
    registry = sleeve_status(base)

    halted = False
    for sleeve, run in sorted(runs.items()):
        long_by_count = run["count"] >= TRAILING_REFUSALS_MAX
        span = run.get("span_h")
        long_by_time = isinstance(span, (int, float)) and span >= TRAILING_HOURS_MAX
        # (2) A RUN AGES OUT: by the age of its last row, or by its sleeve leaving LIVE.
        age = run.get("age_h")
        status = registry.get(sleeve)
        if age is None or age > RUN_MAX_AGE_HOURS:
            run["current"] = False
            run["not_current_because"] = (
                f"last row {run['last_at']} is older than {RUN_MAX_AGE_HOURS:.0f}h")
        elif status is not None and status != "LIVE":
            run["current"] = False
            run["not_current_because"] = f"sleeve is {status or 'unstatused'}, not LIVE"
        else:
            run["current"] = True
        if not (long_by_count or long_by_time):
            continue
        if not run["current"]:
            doc["notes"].append(
                f"{sleeve}: {run['count']}x '{run['reason']}' is history, not a current halt "
                f"({run['not_current_because']})")
            continue
        if run["venue_reason"]:
            doc["notes"].append(
                f"{sleeve}: {run['count']} consecutive '{run['reason']}' rows -- the VENUE's "
                "answer, not the desk declining to trade; reported, not breached")
            continue
        halted = True
        doc["ok"] = False
        doc["problems"].append(
            f"{sleeve} has been refused {run['count']} times in a row on '{run['reason']}' "
            f"since {run['first_at']}"
            + (f" ({span:.1f}h)" if isinstance(span, (int, float)) else "")
            + " with no placement in between -- a halt this long has to be visible somewhere, "
              "and until this fence existed it was not")

    # (b) The verdict itself, for the case where the gateway stops writing rows entirely.
    # (3) The ledger is live on this host, so a missing or stale verdict is LOUD, never silence.
    identity_stale = False
    ident = _read_json(identity)
    if ident is None:
        identity_stale = True
        doc["ok"] = False
        doc["identity"] = {"verdict": UNMEASURED}
        doc["problems"].append(
            f"{IDENTITY_REL} is missing or unreadable on a host whose decision ledger is live: "
            "the rail that decides whether new risk may open cannot be read, so a halt it "
            "imposes would be invisible")
    else:
        doc["identity"] = {
            "verdict": ident.get("verdict"), "allows_new_risk": ident.get("allows_new_risk"),
            "at": ident.get("at"), "reason": str(ident.get("reason") or "")[:400],
        }
        age_h = _age_h(_parse_iso(ident.get("at")), t_now)
        doc["identity"]["age_h"] = round(age_h, 3) if age_h is not None else UNMEASURED
        if age_h is None or age_h > IDENTITY_MAX_AGE_HOURS:
            identity_stale = True
            doc["ok"] = False
            doc["problems"].append(
                f"{IDENTITY_REL} is "
                + (f"{age_h:.1f}h old" if age_h is not None else "unstamped")
                + f" (limit {IDENTITY_MAX_AGE_HOURS:.0f}h) while the decision ledger is live: "
                  "the gateway has stopped writing its release verdict -- the dead-gateway case "
                  f"-- and its last word was allows_new_risk={ident.get('allows_new_risk')}")
        elif ident.get("allows_new_risk") is False:
            halted = True
            doc["ok"] = False
            doc["problems"].append(
                "the release identity currently refuses new risk "
                f"({ident.get('verdict')}): {str(ident.get('reason') or '')[:220]}")

    if halted:
        doc["verdict"] = "HALTED"
    elif identity_stale:
        doc["verdict"] = "IDENTITY_STALE"
    else:
        doc["verdict"] = "OK"
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
        if doc.get("ok") is None:
            # UNMEASURED here: neither evidence that a halt ended nor that one is live.
            return None
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
    if doc.get("verdict") == "NOT_APPLICABLE" or doc.get("ok") is None:
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
        # Only a host where the fence is applicable writes the committed report: an off-box
        # checkout must never dirty a box-state path with a verdict about stale copies.
        if doc.get("applicable"):
            write_artifact(doc)
        doc["alert"] = record_alert(doc)
        doc["event"] = record_event(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 2 if doc["ok"] is False else 0

    print(f"placement interlock: {doc.get('verdict')}; "
          f"{len(doc.get('runs') or {})} sleeve(s) with a trailing refusal run")
    for sleeve, run in sorted((doc.get("runs") or {}).items()):
        print(f"  {sleeve}: {run['count']}x '{run['reason']}' since {run['first_at']}")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"] is None:
        print("check_placement_interlock: UNMEASURED -- no live placement evidence on this host "
              "(not a clean pass; nothing here to halt)")
        return 0
    if doc["ok"]:
        print(f"check_placement_interlock: {doc.get('verdict')} -- no sleeve is silently halted")
        return 0
    print("check_placement_interlock: FAILED -- the desk has stopped placing and did not say so")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
