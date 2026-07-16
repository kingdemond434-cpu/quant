"""Worker registry -- heartbeats so the supervisor can detect and reap dead workers.

A worker writes a heartbeat each loop. If ``last_seen`` falls behind ``stale_seconds`` the worker is
presumed dead (crash / power loss / OOM kill); the supervisor respawns it and the queue's lease
expiry returns its in-flight campaign to the pool. Operational state only.
"""

from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.store.connection import Database


def _iso(dt: datetime) -> str:
    return dt.isoformat()


class WorkerRegistry:
    def __init__(self, db: Database) -> None:
        self.db = db

    def register(self, worker_id: str, *, pid: int, host: str | None = None) -> None:
        now = _iso(datetime.now(tz=UTC))
        host = host or socket.gethostname()
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO workers
                   (worker_id, pid, host, status, started_at, last_seen, campaigns_done)
                   VALUES (?, ?, ?, 'idle', ?, ?, 0)
                   ON CONFLICT(worker_id) DO UPDATE SET
                       pid=excluded.pid, host=excluded.host, status='idle',
                       started_at=excluded.started_at, last_seen=excluded.last_seen""",
                (worker_id, pid, host, now, now),
            )

    def beat(self, worker_id: str, *, status: str, current_campaign: str | None = None,
             completed: bool = False) -> None:
        now = _iso(datetime.now(tz=UTC))
        inc = 1 if completed else 0
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE workers
                   SET status=?, current_campaign=?, last_seen=?,
                       campaigns_done=campaigns_done + ?
                   WHERE worker_id=?""",
                (status, current_campaign, now, inc, worker_id),
            )

    def active(self, *, stale_seconds: int = 60) -> list[dict[str, Any]]:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        rows = self.db.execute(
            "SELECT * FROM workers WHERE last_seen >= ? ORDER BY worker_id", (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]

    def dead(self, *, stale_seconds: int = 60) -> list[dict[str, Any]]:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        rows = self.db.execute(
            "SELECT * FROM workers WHERE last_seen < ? ORDER BY worker_id", (cutoff,)
        ).fetchall()
        return [dict(r) for r in rows]

    def prune(self, *, stale_seconds: int = 3600) -> int:
        cutoff = _iso(datetime.now(tz=UTC) - timedelta(seconds=stale_seconds))
        with self.db.transaction() as conn:
            cur = conn.execute("DELETE FROM workers WHERE last_seen < ?", (cutoff,))
            return int(cur.rowcount)

    def all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM workers ORDER BY worker_id")]
