"""REGISTRY SYNC -- the core leg that pours the desk's record into the canonical registry.

The canonical research registry (libs/moat/registry.py, data/alpha_registry.sqlite) is the one
store every miner writes. Until every writer is wired directly, this leg is the bridge: each
core pass it reads the hypothesis graph, the gate verdict ledger, the compute ledger, the
sleeves, the certified survivors, the lessons and the department locks, and lands them as
candidates, trials, runs, cards with events, memories and workers -- incrementally, by cursor,
idempotently. It then publishes the snapshot the principal read as a symptom (row counts per
table), the conversion-debt ledger, the queue depth by origin and status, the generator yields
and the trial-chain verification, so the registry's state is a report and not a claim.

    python registry_sync.py            # sync + write reports/RESEARCH_REGISTRY.json
    python registry_sync.py --dry-run  # counts and debt only, no sync
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.moat import registry as R  # noqa: E402

REPORT = DESK / "reports" / "RESEARCH_REGISTRY.json"
RULE = ("one canonical registry: every candidate, trial, run, card, memory and worker the desk "
        "produces lands in data/alpha_registry.sqlite; the chain alpha_cards -> alpha_events -> "
        "research_memory -> research_candidates -> research_runs -> trials_ledger -> gauntlet "
        "is populated by the organs that do the work, and this leg bridges what is not yet wired")


def run(*, dry_run: bool = False, max_rows: int = 20000) -> dict:
    t0 = time.monotonic()
    synced = {} if dry_run else R.sync_from_desk(max_rows=max_rows)
    ok, n_chain = R.verify_trial_chain()
    counts = R.counts()
    doc = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "registry": str(R.path()),
        "synced_this_pass": synced,
        "counts": counts,
        "research_chain": {k: counts.get(k, 0) for k in (
            "alpha_cards", "alpha_events", "research_memory", "research_candidates",
            "research_runs", "trials_ledger", "workers", "campaigns", "candidate_returns",
            "metric_points", "discoveries", "provenance")},
        "queue_depth": R.queue_depth(),
        "conversion_debt": R.conversion_debt(),
        "generator_yields": R.generator_yields()[:50],
        "workers_alive": [w["worker_id"] for w in R.workers_alive()],
        "trial_chain": {"ok": ok, "n": n_chain},
        "seconds": round(time.monotonic() - t0, 2),
        "rule": RULE,
    }
    return doc


def _write(doc: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, REPORT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-rows", type=int, default=20000)
    a = ap.parse_args(argv)
    doc = run(dry_run=a.dry_run, max_rows=a.max_rows)
    if not a.dry_run:
        _write(doc)
    chain = doc["research_chain"]
    print(f"registry sync: synced={doc['synced_this_pass']} chain={chain} "
          f"debt={doc['conversion_debt'].get('unexplained_missing_cells')} "
          f"trial_chain_ok={doc['trial_chain']['ok']} in {doc['seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
