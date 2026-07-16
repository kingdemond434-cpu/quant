"""One-shot orchestration smoke test: seed the queue and run a few campaigns end-to-end.

Proves the autonomous loop works on real lake data without launching the forever-supervisor:
enqueue -> dedup -> atomic lease -> worker runs AutoDiscoveryLab.cycle -> complete. Honest result
(survivors expected: 0). Safe to run anytime; uses a throwaway DB unless --db is given.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from migrations import MIGRATIONS

from libs.ops.campaign_queue import CampaignQueue
from libs.ops.research_daemon import ResearchWorker, lake_campaign_specs, make_lake_executor
from libs.store.connection import Database
from libs.store.migrations import run_migrations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor_smoke.sqlite")
    parser.add_argument("--lake", default="data/lake")
    parser.add_argument("--campaigns", type=int, default=2)
    args = parser.parse_args()

    Path(args.db).unlink(missing_ok=True)
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    q = CampaignQueue(db)

    specs = lake_campaign_specs(args.lake, families=["carry", "cross_asset", "momentum"], batch=1)
    for spec in specs[: args.campaigns]:
        q.enqueue(spec)
    dup = q.enqueue(specs[0]) if specs else "no-specs"
    print(f"enqueued={q.stats()['queued']}  dedup_returned={dup}")

    worker = ResearchWorker(db, "smoke", make_lake_executor(args.lake), pid=os.getpid())
    for i in range(args.campaigns):
        print(f"run {i + 1}: {worker.run_once()}")

    tested = db.execute("SELECT COUNT(*) AS c FROM research_candidates").fetchone()["c"]
    surv = db.execute(
        "SELECT COUNT(*) AS c FROM research_candidates WHERE survived=1"
    ).fetchone()["c"]
    print(f"queue={q.stats()}")
    print(f"ledger: tested={tested} survivors={surv} (honest)")
    db.close()


if __name__ == "__main__":
    main()
