#!/usr/bin/env python3
"""`queue_consumers`: the hourly leg that claims the strategy-lane `invalidate` and `screen_class`
tasks and does their work. A thin entry point -- the work lives in `libs.ops.queue_cycle.consume`,
beside the producer (`_lanes`) that queues both kinds.

WHY IT EXISTS (auditor HOLD on #289). `queue_cycle._lanes` queues one `invalidate` per lineage
dependent of every new data version, and a met `acquire_class` mission queues its linked
`screen_class`; the hourly cycle claimed only `recertify`, so both kinds sat READY forever while
`check_no_queues` (which did not watch the journal) stayed green. Now each task is claimed,
done, and completed or failed by its outcome, and the fence fails when READY rows of any kind age
past its bound.

    python desks/mt5/research/queue_consumers.py [--max N]

Artifact: `desks/mt5/reports/QUEUE_CONSUMERS.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.queue_cycle import CONSUME_MAX, consume, queue_path  # noqa: E402

OUT = DESK / "reports" / "QUEUE_CONSUMERS.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="claim and do invalidate / screen_class tasks")
    ap.add_argument("--max", type=int, default=CONSUME_MAX)
    args = ap.parse_args(argv)
    if not queue_path(ROOT).exists():
        res: dict = {"status": "STOOD_DOWN",
                     "why": "no task_queue.jsonl on this host; queue_cycle has not produced yet"}
    else:
        res = consume(ROOT, max_tasks=int(args.max))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    print(f"queue_consumers: {res.get('status')} claimed={res.get('claimed', 0)} "
          f"outcomes={res.get('outcomes', {})} failed={len(res.get('failed') or [])} "
          f"ready_left={res.get('ready_left', 0)}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
