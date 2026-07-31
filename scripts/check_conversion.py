#!/usr/bin/env python3
"""CONVERSION FENCE (L1.28b) -- finding without fixing is half a deliverable.

THE MEASURED DEFECT THIS FENCE EXISTS FOR (deep sweep 2026-07-31, meta seat): findings arrive
at ~14/day across all organs and cross-session repairs complete at ~0.6/day; no ledger row older
than 3.67 days had ever been implemented; >=80% of audit output converted to nothing. The desk's
BUILD capability compounds while its CONVERT capability does not, and nothing measured that gap
daily -- so it widened silently, exactly like unmeasured utilisation before L1.28a.

WHAT IT MEASURES, from docs/research/recommendation_ledger.json (the de-facto winning queue --
the sweep's M10 finding is that split stores recreate the defect, so this fence reads ONE store):
  backlog            rows still open or scheduled
  past_due           backlog rows whose due date has passed
  dispositions_7d    rows moved to implemented/rejected in the last 7 days (a reasoned
                     rejection IS a conversion -- the defect is silence, not the verdict)
  arrivals_7d        rows raised in the last 7 days
  oldest_backlog_age the age of the oldest still-open row, in days
  queue_dispositioned all-time fraction of rows that reached a terminal verdict

STATUSES (fail LOUD, never advisory):
  FLATLINE     zero dispositions in 7 days while the backlog is non-empty -- found-never-fixed
               as a steady state. Exit 2: this is the fence failure.
  REPAIR-MODE  backlog above the deep-sweep backpressure line (25). Exit 0 but the artifact
               carries repair_mode=true, and every consumer of the artifact (max-push queue,
               sweep prompts, brain briefs) is expected to flip effort from finding to fixing.
               Queueing theory (meta M8): at rho~4, exhortation cannot drain a queue -- only
               capacity or admission control can, and this flag is the admission signal.
               BOUNDARY (L1.28b(f), principal 2026-07-31): repair-mode redirects DISCRETIONARY
               ENGINEERING ATTENTION ONLY. It never reduces raw information quantity --
               collectors, recorders, miners, diggers, screens-on-discovery, forward clocks and
               every scheduled detector run at full cadence unconditionally. Acquisition is
               never cut to meet extraction.
  OK           dispositions flowing and backlog under the line.

Artifact: data/conversion_status.json -- consumed by run_max_push.py so conversion debt ranks
in the SAME daily queue as every other below-ceiling aspect (L1.28b: conversion hunts 100%
daily exactly as utilisation does).

    python scripts/check_conversion.py [--report-only] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent

# L1.42 LAWFUL ENTRY: this organ ran on a cron line that passed through no gate at
# all -- 60 manifest lines did. guard() verifies the sealed core and that the doctrine
# still carries every law family; it is TTL-cached (~0ms after the first call in a
# window) and pages-but-does-not-block, so a governance fault never silences an organ.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from libs.ops.lawful import guard as _law_guard  # noqa: E402

# The deep-sweep backpressure line: open+past-due above this flips audit windows to repair.
REPAIR_MODE_BACKLOG = 25
_TERMINAL = frozenset({"implemented", "rejected", "retired"})


def _parse_ts(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def build_report(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    week_ago = now - timedelta(days=7)
    ledger = root / "docs/research/recommendation_ledger.json"
    try:
        rows = json.loads(ledger.read_text("utf-8")).get("recommendations", [])
    except (OSError, ValueError):
        rows = None

    if not rows:
        # A missing/empty ledger is UNMEASURED conversion, which counts as zero (L1.28a
        # inheritance) -- never as OK.
        return {
            "generated": now.isoformat(), "status": "FLATLINE", "repair_mode": True,
            "law": "L1.28b", "backlog": None, "past_due": None,
            "detail": f"ledger unreadable or empty at {ledger} -- unmeasured conversion "
                      "counts as ZERO conversion",
        }

    backlog = [r for r in rows if r.get("status") not in _TERMINAL]
    today = now.date().isoformat()
    past_due = [r for r in backlog if isinstance(r.get("due"), str) and r["due"] < today]
    arrivals_7d = sum(1 for r in rows if (t := _parse_ts(r.get("raised"))) and t >= week_ago)
    dispositions_7d = sum(
        1 for r in rows
        if r.get("status") in _TERMINAL
        and (t := _parse_ts(r.get("disposed"))) and t >= week_ago)
    terminal = sum(1 for r in rows if r.get("status") in _TERMINAL)
    oldest = min((_parse_ts(r.get("raised")) for r in backlog if _parse_ts(r.get("raised"))),
                 default=None)
    oldest_age = round((now - oldest).total_seconds() / 86400, 2) if oldest else 0.0

    if dispositions_7d == 0 and backlog:
        status = "FLATLINE"
    elif len(backlog) > REPAIR_MODE_BACKLOG:
        status = "REPAIR-MODE"
    else:
        status = "OK"
    return {
        "generated": now.isoformat(), "status": status,
        "repair_mode": status != "OK",
        "law": "L1.28b -- conversion hunts 100% daily; a found-unfixed defect is unbooked "
               "loss aging at its stated ROI",
        "backlog": len(backlog), "past_due": len(past_due),
        "past_due_ids": [r.get("id") for r in past_due][:20],
        "arrivals_7d": arrivals_7d, "dispositions_7d": dispositions_7d,
        "arrival_rate_per_day": round(arrivals_7d / 7, 3),
        "disposition_rate_per_day": round(dispositions_7d / 7, 3),
        "oldest_backlog_age_days": oldest_age,
        "queue_dispositioned": round(terminal / max(len(rows), 1), 4),
        "repair_mode_line": REPAIR_MODE_BACKLOG,
        "detail": f"{len(backlog)} rows in backlog ({len(past_due)} past due, oldest "
                  f"{oldest_age}d); last 7d: {arrivals_7d} raised vs {dispositions_7d} "
                  f"dispositioned",
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact and always exit 0 (for queue refresh)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(_ROOT)
    out = _ROOT / "data/conversion_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"conversion fence (L1.28b): {rep['status']} -- {rep.get('detail', '')}")
        print(f"-> {out}")
    if args.report_only:
        return 0
    return 2 if rep["status"] == "FLATLINE" else 0


if __name__ == "__main__":
    sys.exit(main())
