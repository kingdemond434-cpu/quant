#!/usr/bin/env python3
"""External stage-A survivors -> canonical research queue (principal 2026-08-25: conversion of
gathered raw info MUST produce survivors daily, always catching up).

The discovery chain (12 miners -> hypotheses -> bridge_to_hunt -> external backtest) banks
stage-A passes into desks/mt5/data/hypotheses/external_survivors.json -- and until this wire,
they STOPPED there: screen-passes with no path to the canonical ten-gate gauntlet, the exact
III.16 defect at the discovery system's last mile. This script promotes each NEW external
survivor into desks/mt5/data/research_queue.json as a canonical-gauntlet lineage card.
external_gauntlet.py consumes the source docket directly and reconcile_external_queue.py
records its verdict here. The generic run_hunt18 worker must not consume this different route.

Dedup is content-keyed (symbol+family+params) against BOTH the queue and its own ledger, so
re-runs and re-discoveries never double-mint a trial (novelty-gate discipline). Every fresh exact
cell is projected in the same run; the queue is lineage, not a manual review waiting room.

    .venv/bin/python scripts/promote_external_to_queue.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
SURV = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "external_survivors.json"
QUEUE = ROOT / "desks" / "mt5" / "data" / "research_queue.json"
LEDGER = ROOT / "desks" / "mt5" / "data" / "hypotheses" / "queued_external.json"


def key(s: dict) -> str:
    raw = json.dumps({"sym": s.get("symbol"), "fam": s.get("family"),
                      "params": s.get("params", {})}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def main() -> int:
    try:
        surv = json.loads(SURV.read_text("utf-8"))
    except (OSError, ValueError):
        print("no external survivors file -- nothing to promote")
        return 0
    items = surv if isinstance(surv, list) else surv.get("survivors", [])
    try:
        queue = json.loads(QUEUE.read_text("utf-8"))
    except (OSError, ValueError):
        queue = []
    try:
        seen = set(json.loads(LEDGER.read_text("utf-8")))
    except (OSError, ValueError):
        seen = set()

    fresh = [s for s in items if isinstance(s, dict) and key(s) not in seen]
    fresh.sort(key=lambda s: abs(float(s.get("t_stat", 0) or 0)), reverse=True)
    now = datetime.now(tz=UTC)
    added = 0
    for s in fresh:
        k = key(s)
        card = {
            "id": f"ext-{now:%Y%m%d}-{k[:6]}",
            "geneology_id": f"external:{s.get('source', 'discovery_miners')}",
            "hypothesis": (
                f"EXTERNAL STAGE-A SURVIVOR promoted to the canonical gauntlet: "
                f"{s.get('symbol')} {s.get('family')} params={s.get('params')} screened at "
                f"n={s.get('n')} exp={s.get('exp_r')}R t={s.get('t_stat')} "
                f"pf={s.get('profit_factor')} maxDD={s.get('max_dd_r')}R by the external "
                f"backtest chain. Screen authority is ZERO (two-stage law); this card exists "
                f"so the exact ten-gate gauntlet and forward clock judge it like every other "
                f"candidate."),
            "family": str(s.get("family")),
            "side": str(s.get("side", "BOTH")).upper(),
            "params": s.get("params", {}),
            "created_at": now.isoformat(),
            "status": "QUEUED_CANONICAL_GAUNTLET",
            "route": "external_gauntlet",
            "promotion_authority": False,
            "external_screen": {kk: s.get(kk) for kk in
                                ("n", "exp_r", "t_stat", "profit_factor", "max_dd_r",
                                 "win_rate", "symbol")},
        }
        queue.append(card)
        seen.add(k)
        added += 1
    if added:
        QUEUE.write_text(json.dumps(queue, indent=1), "utf-8")
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(sorted(seen), indent=0), "utf-8")
    print(f"external->queue: {added} promoted ({len(fresh)} fresh of {len(items)} banked); "
          f"queue now {len(queue)} cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
