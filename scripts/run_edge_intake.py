#!/usr/bin/env python3
"""Fold the latest miner queue into the intake ledger, then show the next batch.

WHY THIS RUNNER EXISTS RATHER THAN A LIBRARY CALL BURIED IN THE MINER. The miner's job is to
DISCOVER; intake's job is to guarantee nothing discovered disappears. Keeping them separate means
a miner failure cannot also destroy the accounting, and the accounting can be re-run over a queue
report the miner wrote days ago. It is also the thing a cron line can point at.

    python scripts/run_edge_intake.py [--limit N] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.edge_intake import next_batch, recall_audit, stamp_queue  # noqa: E402

QUEUE = "reports/research_queue.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--queue", default=QUEUE)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    stamped = stamp_queue(args.queue)
    batch = next_batch(limit=args.limit)
    audit = recall_audit(queue_report=args.queue)
    out = {"stamped": stamped, "next_batch": batch, "recall_audit": audit}

    if args.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
        return 0 if stamped["status"] == "OK" else 2
    if stamped["status"] != "OK":
        # DARK-DATA SAFE: a missing queue report is a blocked run, not a silent success.
        print(f"edge intake: BLOCKED -- {stamped['why']}")
        return 2
    print(f"edge intake: {stamped['n_stamped']} row(s) stamped {stamped['by_disposition']}")
    print(f"  recall: {audit['verdict']}")
    print(f"  next batch ({len(batch)}):")
    for r in batch:
        print(f"    [{r.get('score')}] {str(r.get('title'))[:64]}  ({r.get('channel')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
