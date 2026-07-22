#!/usr/bin/env python3
"""BLIND-SPOT ORIGIN LEDGER (principal 2026-07-21): the objective readout of whether the
maximization system actually works -- does the DESK find its own gaps, or does the PRINCIPAL
still have to point them out?

Every gap found gets one line, tagged by ORIGIN:
  self      -- the brain's self-interrogation / a cycle found it
  guard     -- a mechanical max_audit check fired it
  principal -- the principal had to surface it (the FAILURE signal: the system missed it)

THE METRIC: over a rolling window, (self + guard) / total should climb toward 1.0 and
principal toward 0. If principal-found stays high, the maximization apparatus is NOT working and
the principal is still the gap-finder -- which is the exact thing this whole build exists to end.

Usage:
  blind_spot.py log --origin self|guard|principal --summary "..." [--angle N] [--severity med]
  blind_spot.py report [--days 30]     # the self-sufficiency readout
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent / "data/blind_spot_ledger.jsonl"


def log(a) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(),
            "origin": a.origin, "angle": getattr(a, "angle", None),
            "severity": getattr(a, "severity", "med"),
            "summary": a.summary[:300],
        }) + "\n")
    print(f"blind-spot logged: {a.origin} -- {a.summary[:60]}")


def _rows():
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text("utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def report(a) -> dict:
    rows = _rows()
    if getattr(a, "days", None):
        cut = datetime.now(tz=UTC).timestamp() - a.days * 86400
        rows = [r for r in rows if datetime.fromisoformat(r["ts"]).timestamp() >= cut]
    n = len(rows)
    by = {"self": 0, "guard": 0, "principal": 0}
    for r in rows:
        by[r.get("origin", "principal")] = by.get(r.get("origin", "principal"), 0) + 1
    self_suff = (by["self"] + by["guard"]) / n if n else 0.0
    print(f"BLIND-SPOT ORIGIN ({n} gaps{f', last {a.days}d' if getattr(a,'days',None) else ''}):")
    print(f"  self-found (desk)      : {by['self']}")
    print(f"  guard-found (mechanical): {by['guard']}")
    print(f"  principal-found (MISS) : {by['principal']}")
    print(f"  SELF-SUFFICIENCY       : {self_suff*100:.0f}%  (target: climbing to ~100%)")
    if n >= 8 and by["principal"] > by["self"] + by["guard"]:
        print("  VERDICT: principal is STILL the primary gap-finder -- system not yet working")
    elif n >= 8 and self_suff >= 0.7:
        print("  VERDICT: desk finds most of its own gaps -- the maximization system is working")
    return {"n": n, **by, "self_sufficiency": self_suff}


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--origin", required=True, choices=["self", "guard", "principal"])
    lg.add_argument("--summary", required=True)
    lg.add_argument("--angle", default=None)
    lg.add_argument("--severity", default="med")
    lg.set_defaults(fn=log)
    rp = sub.add_parser("report")
    rp.add_argument("--days", type=int, default=None)
    rp.set_defaults(fn=report)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
