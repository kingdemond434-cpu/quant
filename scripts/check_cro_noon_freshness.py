#!/usr/bin/env python3
"""RED WHEN NO NOON CRO PASS HAS LANDED IN 26 HOURS.

    python scripts/check_cro_noon_freshness.py [--ledger <cro_cycle_ledger.jsonl>] [--out <json>]
        [--max-age-h 26] [--now <iso>]

Clock: hourly leg `cro_noon_freshness` (desks/mt5/research/hourly_cycle.py, CORE). Artifact:
desks/mt5/reports/CRO_NOON_FRESHNESS.json.

WHY (measured 2026-10-29). The noon pass was driven from the laptop through a Remote Control
session that had sat parked since 2026-09-29; the routine reported "instructions delivered" every
day and the ledger carried two noon rows in a month (09-30, 10-21). Nothing turned red. The pass
now runs on the box as MT5-CycleNoon, and this check is what notices when it stops: the newest
row whose lane is `noon` or `noon_box` must be younger than 26 h (a daily pass plus two hours of
slack). An absent or unreadable ledger, or one with no noon row at all, is RED, never GREEN
(L1.28a: absence never resolves to a clean verdict).

Exits 0 on GREEN and 1 on RED, so the leg's own outcome carries the verdict; the artifact carries
the detail.
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
NOON_LANES = ("noon", "noon_box")
MAX_AGE_H = 26.0


def _row_time(row: dict) -> datetime | None:
    """The row's own UTC stamp: `at`, else the start of its `date`."""
    for key in ("at", "date"):
        raw = row.get(key)
        if not isinstance(raw, str) or not raw:
            continue
        try:
            t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    return None


def measure(ledger: Path, now: datetime, max_age_h: float = MAX_AGE_H) -> dict:
    doc: dict = {"at": now.isoformat(), "ledger": str(ledger), "max_age_h": max_age_h,
                 "lanes": list(NOON_LANES), "last_noon_at": None, "last_noon_lane": None,
                 "age_h": None, "noon_rows": 0, "malformed_rows": 0}
    try:
        lines = ledger.read_text("utf-8").splitlines()
    except OSError as exc:
        return {**doc, "status": "RED", "why": f"ledger unreadable: {exc.__class__.__name__}"}
    newest: tuple[datetime, str] | None = None
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
        t = _row_time(row)
        if t is None:
            doc["malformed_rows"] += 1
            continue
        doc["noon_rows"] += 1
        if newest is None or t > newest[0]:
            newest = (t, str(row["lane"]))
    if newest is None:
        return {**doc, "status": "RED", "why": "no noon row in the ledger"}
    age_h = round((now - newest[0]) / timedelta(hours=1), 2)
    doc.update(last_noon_at=newest[0].isoformat(), last_noon_lane=newest[1], age_h=age_h)
    if age_h > max_age_h:
        return {**doc, "status": "RED",
                "why": f"newest noon row is {age_h}h old, over the {max_age_h}h limit"}
    return {**doc, "status": "GREEN", "why": f"newest noon row is {age_h}h old"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--out", type=Path, default=ARTIFACT)
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H)
    ap.add_argument("--now", help="ISO timestamp to measure against (tests); default: now, UTC")
    a = ap.parse_args(argv)
    now = (datetime.fromisoformat(a.now.replace("Z", "+00:00")) if a.now
           else datetime.now(UTC))
    doc = measure(a.ledger, now, a.max_age_h)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1), "utf-8")
    print(json.dumps({"status": doc["status"], "age_h": doc["age_h"], "why": doc["why"]}))
    return 0 if doc["status"] == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
