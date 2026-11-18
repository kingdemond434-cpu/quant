#!/usr/bin/env python3
"""RED WHEN NO NOON CRO PASS HAS LANDED IN 26 HOURS.

    python scripts/check_cro_noon_freshness.py [--ledger <cro_cycle_ledger.jsonl>] [--out <json>]
        [--state <CRO_NOON_STATE.json>] [--max-age-h 26] [--now <iso>]

Clock: hourly leg `cro_noon_freshness` (desks/mt5/research/hourly_cycle.py, CORE). Artifact:
desks/mt5/reports/CRO_NOON_FRESHNESS.json.

WHY (measured 2026-10-29). The noon pass was driven from the laptop through a Remote Control
session that had sat parked since 2026-09-29; the routine reported "instructions delivered" every
day and the ledger carried two noon rows in a month (09-30, 10-21). Nothing turned red. The pass
now runs on the box as MT5-CycleNoon, and this check is what notices when it stops: the newest
LANDED pass whose lane is `noon` or `noon_box` must be younger than 26 h (a daily pass plus two
hours of slack). A landed pass is the launcher's `end` row with rc 0, or a pass's own summary row
(no `event` key, as the laptop and box-only passes wrote). A `start` row, or an `end` with a
non-zero rc, is a pass that began and did not land: it never makes the check GREEN. A row stamped
more than ten minutes in the future is malformed, not fresh. An absent, unreadable or undecodable
ledger, or one with no landed noon row at all, is RED, never GREEN (L1.28a: absence never
resolves to a clean verdict).

A NON-ZERO EXIT IS RED TOO (K6, 2026-11-17). The launcher's early exits (5 when the lease is not
acquired, 3 when the agent CLI is missing, ...) write no ledger row at all, so a lane that keeps
failing to start read only as "age" until 26 h had passed. `scripts/publish_cro_lane_state.py`
(hourly leg `cro_lane_state`, just before this one) publishes the lane's parsed exit codes and
checkpoint fields as desks/mt5/reports/CRO_NOON_STATE.json with the last exit code it read. When that code is
non-zero and is NEWER than the newest landed noon pass, this check is RED whatever the age. An
absent or unreadable state file changes nothing here and is recorded as `published_state:
UNMEASURED`.

Exits 0 on GREEN and 2 on RED: 2 is declared a verdict exit for this leg in hourly_cycle's
VERDICT_EXITS, so a RED hour is recorded as the reading it is, not as a failed leg. The noon CRO
routine reads the artifact and routes a RED to Desk health.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "desks" / "mt5" / "data" / "cro_cycle_ledger.jsonl"
ARTIFACT = ROOT / "desks" / "mt5" / "reports" / "CRO_NOON_FRESHNESS.json"
NOON_STATE = ROOT / "desks" / "mt5" / "reports" / "CRO_NOON_STATE.json"
NOON_LANES = ("noon", "noon_box")
MAX_AGE_H = 26.0
FUTURE_SLACK = timedelta(minutes=10)
EXIT_RED = 2


def _row_time(row: dict) -> tuple[datetime, bool] | None:
    """The row's own UTC stamp and whether it is date-only: `at`, else the start of its `date`."""
    for key in ("at", "date"):
        raw = row.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        try:
            t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        return (t if t.tzinfo else t.replace(tzinfo=UTC)), key == "date"
    return None


def _landed(row: dict) -> bool:
    """A pass that finished: the launcher's clean `end` row, or a pass's own summary row."""
    event = row.get("event")
    if event is None:
        return True
    return event == "end" and row.get("rc") == 0


def _published_exit(path: Path | None) -> tuple[str, int | None, datetime | None]:
    """(status, last rc, when) from the published noon lane state; UNMEASURED when unreadable."""
    if path is None:
        return "UNMEASURED", None, None
    try:
        doc = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return "UNMEASURED", None, None
    if not isinstance(doc, dict):
        return "UNMEASURED", None, None
    rc = doc.get("last_rc")
    if not isinstance(rc, int) or isinstance(rc, bool):
        return "UNMEASURED", None, None
    stamp = _row_time({"at": doc.get("last_rc_at")})
    return "PRESENT", rc, (stamp[0] if stamp else None)


def _rel(p: Path) -> str:
    """A repository-relative name: published artifacts carry no local paths."""
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return p.name


def measure(ledger: Path, now: datetime, max_age_h: float = MAX_AGE_H,
            state: Path | None = None) -> dict:
    doc = _measure(ledger, now, max_age_h)
    st, rc, rc_at = _published_exit(state)
    doc.update(published_state=st, last_launch_rc=rc,
               last_launch_rc_at=rc_at.isoformat() if rc_at else None)
    if st != "PRESENT" or rc in (None, 0):
        return doc
    last = doc.get("last_noon_at")
    landed_after = False
    if last and rc_at is not None:
        landed_after = datetime.fromisoformat(last) >= rc_at
    elif last and rc_at is None:
        landed_after = True  # an undated exit cannot outrank a dated landing
    if landed_after:
        return doc
    return {**doc, "status": "RED",
            "why": f"last noon launch exited rc={rc}"
            + (f" at {rc_at.isoformat()}" if rc_at else "")
            + ", after the newest landed pass; " + doc["why"]}


def _measure(ledger: Path, now: datetime, max_age_h: float) -> dict:
    doc: dict = {"at": now.isoformat(), "ledger": _rel(ledger), "max_age_h": max_age_h,
                 "lanes": list(NOON_LANES), "last_noon_at": None, "last_noon_lane": None,
                 "last_noon_date_only": None, "age_h": None, "noon_rows": 0,
                 "landed_rows": 0, "future_rows": 0, "malformed_rows": 0}
    try:
        # utf-8-sig: PS 5.1's Add-Content -Encoding UTF8 writes a BOM before the first row.
        lines = ledger.read_text("utf-8-sig").splitlines()
    except (OSError, ValueError) as exc:
        return {**doc, "status": "RED", "why": f"ledger unreadable: {exc.__class__.__name__}"}
    newest: tuple[datetime, str, bool] | None = None
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            doc["malformed_rows"] += 1
            continue
        if not isinstance(row, dict) or row.get("lane") not in NOON_LANES:
            continue
        doc["noon_rows"] += 1
        stamp = _row_time(row)
        if stamp is None:
            doc["malformed_rows"] += 1
            continue
        t, date_only = stamp
        if t > now + FUTURE_SLACK:
            doc["future_rows"] += 1
            doc["malformed_rows"] += 1
            continue
        if not _landed(row):
            continue
        doc["landed_rows"] += 1
        if newest is None or t > newest[0]:
            newest = (t, str(row["lane"]), date_only)
    if newest is None:
        return {**doc, "status": "RED", "why": "no landed noon pass in the ledger"}
    age_h = round((now - newest[0]) / timedelta(hours=1), 2)
    doc.update(last_noon_at=newest[0].isoformat(), last_noon_lane=newest[1],
               last_noon_date_only=newest[2], age_h=age_h)
    if age_h > max_age_h:
        return {**doc, "status": "RED",
                "why": f"newest landed noon pass is {age_h}h old, over the {max_age_h}h limit"}
    return {**doc, "status": "GREEN", "why": f"newest landed noon pass is {age_h}h old"
            + (" (date-only row, read as midnight UTC)" if newest[2] else "")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out", type=Path, default=ARTIFACT)
    ap.add_argument("--state", type=Path, default=None,
                    help="published noon lane state (scripts/publish_cro_lane_state.py); "
                         "defaults to the desk's own only when --ledger is the desk's own")
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H)
    ap.add_argument("--now", help="ISO timestamp to measure against (tests); default: now, UTC")
    a = ap.parse_args(argv)
    now = (datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now
           else datetime.now(UTC))
    state = a.state or (NOON_STATE if a.ledger == LEDGER else None)
    doc = measure(a.ledger, now, a.max_age_h, state)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), "utf-8")
    print(json.dumps({"status": doc["status"], "age_h": doc["age_h"], "why": doc["why"]}))
    return 0 if doc["status"] == "GREEN" else EXIT_RED


if __name__ == "__main__":
    sys.exit(main())
