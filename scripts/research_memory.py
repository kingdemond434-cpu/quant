#!/usr/bin/env python3
"""RESEARCH MEMORY CLI (2026-07-24) -- the conversion loop's ledger, made one-line writable.

The external audit and the desk's own fence agree: research_memory had 0 rows EVER while every
mission directive claimed analyst passes write to it -- the hypothesis factory's memory was a
null pipe. The table existed; the FRICTION did (raw sqlite from a prompt-driven organ). This
CLI removes it, exactly like blind_spot.py did for gap-origin logging.

Usage:
  research_memory.py log --category hypothesis --statement "..." --result pending
        [--lessons "..."] [--failure-cause data|construction|stats|economics]
        [--failure-stage screen|clock|gauntlet] [--metrics '{"ic":0.03}'] [--predecessor rm-...]
  research_memory.py report [--days 30]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

_DB = Path(__file__).resolve().parent.parent / "data/sor_research.sqlite"
_CATS = ("hypothesis", "dataset", "method", "mission", "construction")
# The table CHECK constraint allows only pending/success/failure -- richer statuses map onto it
# and the granular label is preserved in metrics_json.status_granular.
_RES_MAP = {"pending": "pending", "screening": "pending", "clock-accruing": "pending",
            "validated": "success", "rejected": "failure", "abandoned": "failure"}


def log(a) -> None:
    rid = f"rm-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    metrics = {}
    if a.metrics:
        try:
            metrics = json.loads(a.metrics)
        except Exception:
            metrics = {"raw": a.metrics}
    metrics.setdefault("status_granular", a.result)
    con = sqlite3.connect(_DB)
    con.execute(
        "INSERT INTO research_memory (id, created_at, category, statement, result, "
        "failure_cause, failure_reason, success_reason, failure_stage, lessons, metrics_json, "
        "predecessor_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, datetime.now(tz=UTC).isoformat(), a.category, a.statement[:600],
         _RES_MAP[a.result],
         a.failure_cause, a.failure_reason, a.success_reason, a.failure_stage,
         a.lessons, json.dumps(metrics), a.predecessor))
    con.commit()
    con.close()
    print(f"research-memory logged: {rid} [{a.category}/{a.result}] {a.statement[:60]}")


def report(a) -> None:
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    cut = f"-{a.days} days"
    rows = list(con.execute(
        "SELECT * FROM research_memory WHERE created_at >= datetime('now', ?) "
        "ORDER BY created_at DESC", (cut,)))
    total = con.execute("SELECT COUNT(*) FROM research_memory").fetchone()[0]
    by: dict[str, int] = {}
    for r in rows:
        k = f"{r['category']}/{r['result']}"
        by[k] = by.get(k, 0) + 1
    print(f"RESEARCH MEMORY: {total} rows total, {len(rows)} in last {a.days}d")
    for k, v in sorted(by.items()):
        print(f"  {k}: {v}")
    for r in rows[:10]:
        print(f"  {r['id']}  {r['statement'][:70]}")
    con.close()


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--category", required=True, choices=_CATS)
    lg.add_argument("--statement", required=True)
    lg.add_argument("--result", required=True, choices=list(_RES_MAP))
    lg.add_argument("--failure-cause", dest="failure_cause", default=None)
    lg.add_argument("--failure-reason", dest="failure_reason", default=None)
    lg.add_argument("--success-reason", dest="success_reason", default=None)
    lg.add_argument("--failure-stage", dest="failure_stage", default=None)
    lg.add_argument("--lessons", default=None)
    lg.add_argument("--metrics", default=None)
    lg.add_argument("--predecessor", default=None)
    lg.set_defaults(fn=log)
    rp = sub.add_parser("report")
    rp.add_argument("--days", type=int, default=30)
    rp.set_defaults(fn=report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
