"""Autonomous research SUPERVISOR -- the never-stop daemon.

Runs forever and requires no human intervention:
  * On start, reclaims any leases orphaned by a previous crash (power-loss recovery).
  * Seeds + continuously refills the campaign queue from the lake generator (research loop).
  * Spawns N worker subprocesses and RESTARTS any that die (process-crash recovery).
  * Each maintenance tick: reclaim dead-worker leases, prune dead workers, clean old campaigns.

The supervisor is the in-app process manager. To make the SUPERVISOR ITSELF crash-proof, run it
under the OS resurrector (systemd / NSSM / Task Scheduler / Docker restart=always) -- see deploy/.

Usage:
    python scripts/run_supervisor.py --workers 3 --db data/sor_research.sqlite --lake data/lake
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import FrameType

from migrations import MIGRATIONS

from libs.ops.campaign_queue import CampaignQueue
from libs.ops.research_daemon import Supervisor, lake_campaign_specs
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_STOP = False
_WORKER_SCRIPT = Path(__file__).with_name("run_worker.py")


def _handle(_sig: int, _frame: FrameType | None) -> None:
    global _STOP
    _STOP = True


def _spawn(worker_id: str, db: str, lake: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, str(_WORKER_SCRIPT), "--id", worker_id, "--db", db, "--lake", lake]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--db", default="data/sor_research.sqlite")
    parser.add_argument("--lake", default="data/lake")
    parser.add_argument("--families", default="", help="comma-separated; empty = all 12")
    parser.add_argument("--min-queue-depth", type=int, default=8)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--batch", type=int, default=1, help="symbols per campaign")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    families = [f.strip() for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)

    # Crash recovery: return any leases orphaned by a previous run before workers start.
    reclaimed = CampaignQueue(db).reclaim_stale()
    print(f"supervisor: reclaimed {reclaimed} orphaned campaign(s) on startup")

    sup = Supervisor(
        db,
        generator=lambda: lake_campaign_specs(args.lake, families=families, batch=args.batch),
        min_queue_depth=args.min_queue_depth,
    )
    print(f"supervisor: seeded {sup.ensure_queue()} campaign(s)")

    procs: dict[str, subprocess.Popen[bytes]] = {}
    for i in range(args.workers):
        wid = f"worker-{i + 1}"
        procs[wid] = _spawn(wid, args.db, args.lake)
    print(f"supervisor: spawned {len(procs)} workers; entering forever loop")

    try:
        while not _STOP:
            for wid, proc in list(procs.items()):
                if proc.poll() is not None:  # worker died -> restart (its lease will be reclaimed)
                    print(f"supervisor: {wid} exited (code {proc.returncode}); restarting")
                    procs[wid] = _spawn(wid, args.db, args.lake)
            m = sup.maintain()
            s = sup.queue.stats()
            print(f"[supervisor] queue depth={s['depth']} done={s['done']} failed={s['failed']} "
                  f"| reclaimed={m['reclaimed']} enqueued={m['enqueued']} workers={len(procs)}")
            time.sleep(args.interval)
    finally:
        print("supervisor: shutting down workers...")
        for proc in procs.values():
            proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        db.close()
        print("supervisor: stopped")


if __name__ == "__main__":
    main()
