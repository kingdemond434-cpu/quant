"""Durable, crash-safe campaign queue for 24/7 autonomous operation.

Lease-based work queue over the system-of-record (SQLite WAL). The invariants that make continuous
operation safe with zero human intervention:

  * **No duplicate execution** -- a campaign is dedup'd by content hash on enqueue, and claimed by
    exactly one worker via an atomic ``BEGIN IMMEDIATE`` lease.
  * **No lost work on crash** -- a worker holds a time-boxed lease and must renew it; if the worker
    dies (power loss, OOM, kill), the lease expires and :meth:`reclaim_stale` returns the campaign
    to the queue. Re-running is safe because the research lab itself dedups candidates.
  * **Bounded retries** -- a failed campaign is re-queued until ``max_attempts``, then parked as
    ``failed`` for inspection (never silently dropped, never infinitely retried).

Operational state only: this table is mutable and cleanable, unlike the append-only audit log and
research ledger, which are never touched here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from libs.core.ids import generate_id
from libs.store.connection import Database


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def content_hash(spec: dict[str, Any]) -> str:
    """Stable hash of a campaign spec for deduplication (order-independent)."""
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CampaignQueue:
    """Atomic, lease-based campaign queue. Safe for multiple concurrent workers."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # --- producer ---------------------------------------------------------------
    def enqueue(
        self, spec: dict[str, Any], *, priority: int = 100, max_attempts: int = 3
    ) -> str | None:
        """Queue a campaign. Returns its id, or None if an identical spec already exists (dedup)."""
        h = content_hash(spec)
        now = _iso(_now())
        cid = generate_id("camp")
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM campaigns WHERE content_hash = ?", (h,)
            ).fetchone()
            if existing is not None:
                return None
            conn.execute(
                """INSERT INTO campaigns
                   (id, content_hash, spec_json, priority, status, attempts, max_attempts,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)""",
                (cid, h, json.dumps(spec), priority, max_attempts, now, now),
            )
        return cid

    # --- consumer (atomic) ------------------------------------------------------
    def lease(self, worker_id: str, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        """Atomically claim the highest-priority runnable campaign, or None if the queue is empty.

        Runnable = queued, OR leased with an expired lease (a previous worker died). Uses
        BEGIN IMMEDIATE so only one worker is ever in the critical section.
        """
        now = _now()
        now_iso = _iso(now)
        expires = _iso(now + timedelta(seconds=lease_seconds))
        conn = self.db.connection
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute(
                """SELECT id, spec_json, attempts, max_attempts FROM campaigns
                   WHERE status = 'queued'
                      OR (status = 'leased' AND lease_expires_at < ?)
                   ORDER BY priority ASC, seq ASC LIMIT 1""",
                (now_iso,),
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                """UPDATE campaigns
                   SET status='leased', worker_id=?, lease_expires_at=?, attempts=attempts+1,
                       started_at=COALESCE(started_at, ?), updated_at=?
                   WHERE id=?""",
                (worker_id, expires, now_iso, now_iso, row["id"]),
            )
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        return {"id": row["id"], "spec": json.loads(row["spec_json"]),
                "attempts": row["attempts"] + 1, "max_attempts": row["max_attempts"]}

    def renew(self, campaign_id: str, worker_id: str, *, lease_seconds: int = 300) -> bool:
        """Extend a held lease (call periodically while a long campaign runs)."""
        expires = _iso(_now() + timedelta(seconds=lease_seconds))
        with self.db.transaction() as conn:
            cur = conn.execute(
                """UPDATE campaigns SET lease_expires_at=?, updated_at=?
                   WHERE id=? AND worker_id=? AND status='leased'""",
                (expires, _iso(_now()), campaign_id, worker_id),
            )
            return cur.rowcount > 0

    def complete(self, campaign_id: str, worker_id: str, result: dict[str, Any]) -> None:
        now = _iso(_now())
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE campaigns
                   SET status='done', result_json=?, finished_at=?, updated_at=?, error=NULL
                   WHERE id=? AND worker_id=?""",
                (json.dumps(result), now, now, campaign_id, worker_id),
            )

    def fail(self, campaign_id: str, worker_id: str, error: str) -> str:
        """Re-queue for retry until max_attempts, then park as 'failed'. Returns the new status."""
        now = _iso(_now())
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT attempts, max_attempts FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            if row is None:
                return "missing"
            retry = row["attempts"] < row["max_attempts"]
            status = "queued" if retry else "failed"
            conn.execute(
                """UPDATE campaigns
                   SET status=?, worker_id=NULL, lease_expires_at=NULL, error=?,
                       finished_at=CASE WHEN ?='failed' THEN ? ELSE finished_at END, updated_at=?
                   WHERE id=?""",
                (status, error[:1000], status, now, now, campaign_id),
            )
        return status

    # --- recovery / maintenance -------------------------------------------------
    def reclaim_stale(self) -> int:
        """Return campaigns whose lease expired (dead workers) to the queue. Crash recovery."""
        now = _iso(_now())
        with self.db.transaction() as conn:
            cur = conn.execute(
                """UPDATE campaigns SET status='queued', worker_id=NULL, lease_expires_at=NULL,
                       updated_at=?
                   WHERE status='leased' AND lease_expires_at < ?""",
                (now, now),
            )
            return int(cur.rowcount)

    def cleanup(self, *, keep_days: int = 7) -> int:
        """Delete terminal campaigns older than keep_days (operational hygiene; audit untouched)."""
        cutoff = _iso(_now() - timedelta(days=keep_days))
        with self.db.transaction() as conn:
            cur = conn.execute(
                "DELETE FROM campaigns WHERE status IN ('done','cancelled') AND finished_at < ?",
                (cutoff,),
            )
            return int(cur.rowcount)

    def stats(self) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT status, COUNT(*) AS n FROM campaigns GROUP BY status"
        ).fetchall()
        counts = {r["status"]: int(r["n"]) for r in rows}
        oldest = self.db.execute(
            "SELECT MIN(created_at) AS t FROM campaigns WHERE status='queued'"
        ).fetchone()
        age = 0.0
        if oldest and oldest["t"]:
            age = (_now() - datetime.fromisoformat(oldest["t"])).total_seconds()
        return {
            "queued": counts.get("queued", 0), "leased": counts.get("leased", 0),
            "done": counts.get("done", 0), "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "depth": counts.get("queued", 0) + counts.get("leased", 0),
            "oldest_queued_age_s": round(age, 1),
        }
