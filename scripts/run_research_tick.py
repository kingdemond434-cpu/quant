"""One bounded research TICK -- the schedulable unit of autonomous research.

Designed to be invoked by a scheduler (cron / Task Scheduler) or chained after data ingestion,
instead of a hot 24/7 loop burning CPU on static data. A tick:

  1. Recovers any campaigns orphaned by a previous crash (reclaim_stale).
  2. Seeds the queue from the lake generator (dedup skips anything already tested -> only NEW work).
  3. Drains the queue through the full validation gauntlet, then exits cleanly.
  4. Cleans up old terminal campaigns.

This is the honest cadence: research runs when there is genuinely new work (new data / new bars /
re-validation), not in a perpetual spin. Survivors expected: 0 (reported honestly).

    python scripts/run_research_tick.py --db data/sor_research.sqlite --lake data/lake
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
    parser.add_argument("--db", default="data/sor_research.sqlite")
    parser.add_argument("--lake", default="data/lake")
    parser.add_argument("--families", default="", help="comma-separated; empty = all 12")
    parser.add_argument("--batch", type=int, default=1, help="symbols per campaign")
    parser.add_argument("--max-campaigns", type=int, default=0, help="0 = drain the whole queue")
    parser.add_argument("--cleanup-days", type=int, default=7)
    args = parser.parse_args()

    families = [f.strip() for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    queue = CampaignQueue(db)

    reclaimed = queue.reclaim_stale()                      # crash recovery
    seeded = 0
    for spec in lake_campaign_specs(args.lake, families=families, batch=args.batch):
        if queue.enqueue(spec) is not None:                # dedup -> only genuinely new work
            seeded += 1
    print(f"tick: reclaimed={reclaimed} seeded={seeded} depth={queue.stats()['depth']}")

    worker = ResearchWorker(db, f"tick-{os.getpid()}", make_lake_executor(args.lake))
    processed = 0
    while args.max_campaigns == 0 or processed < args.max_campaigns:
        outcome = worker.run_once()
        if outcome == "idle":
            break
        processed += 1
        print(f"  [{processed}] {outcome}")

    cleaned = queue.cleanup(keep_days=args.cleanup_days)
    s = queue.stats()
    tested = db.execute("SELECT COUNT(*) AS c FROM research_candidates").fetchone()["c"]
    surv = db.execute(
        "SELECT COUNT(*) AS c FROM research_candidates WHERE survived=1"
    ).fetchone()["c"]
    print(f"tick done: processed={processed} done={s['done']} "
          f"failed={s['failed']} cleaned={cleaned}")
    print(f"ledger: tested={tested} survivors={surv} (honest)")
    db.close()


if __name__ == "__main__":
    main()
