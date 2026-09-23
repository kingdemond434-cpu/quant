"""A single research worker: leases campaigns and runs them forever until signalled.

Spawned and supervised by scripts/run_supervisor.py (which restarts it if it dies). Can also be run
standalone. Each worker owns its own SQLite connection.

Usage:
    python scripts/run_worker.py --id worker-1 --db data/sor_research.sqlite --lake data/lake
"""

from __future__ import annotations

import argparse
import os
import signal
from pathlib import Path
from types import FrameType

from migrations import MIGRATIONS

from libs.ops.research_daemon import ResearchWorker, make_lake_executor
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_STOP = False


def _handle(_sig: int, _frame: FrameType | None) -> None:
    global _STOP
    _STOP = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--db", default="data/sor_research.sqlite")
    parser.add_argument("--lake", default="data/lake")
    parser.add_argument("--lease-seconds", type=int, default=600)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    executor = make_lake_executor(args.lake)
    worker = ResearchWorker(
        db, args.id, executor, lease_seconds=args.lease_seconds, pid=os.getpid()
    )
    print(f"worker {args.id} pid={os.getpid()} online")
    try:
        worker.run_forever(stop=lambda: _STOP)
    finally:
        db.close()
        print(f"worker {args.id} stopped")


if __name__ == "__main__":
    main()
