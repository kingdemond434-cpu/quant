"""Migration 0006 — autonomous 24/7 orchestration state.

A durable campaign queue and a worker registry that make continuous operation crash-safe:
  * ``campaigns``  -- the work queue. Lease-based: a worker atomically claims a queued campaign,
    sets a lease expiry, and must renew it; if the worker dies the lease expires and the campaign is
    reclaimed (no lost work, no duplicate execution). content_hash dedups identical specs.
  * ``workers``    -- heartbeat registry so the supervisor can detect dead workers and reclaim work.

This is OPERATIONAL state (mutable, cleanable), deliberately separate from the append-only audit log
and research ledger, which remain immutable. No statistical thresholds or audit history are touched.
"""

from __future__ import annotations

from libs.store.migrations import Migration

_STATUS = "'queued', 'leased', 'done', 'failed', 'cancelled'"

STATEMENTS: tuple[str, ...] = (
    f"""
    CREATE TABLE campaigns (
        seq              INTEGER PRIMARY KEY AUTOINCREMENT,
        id               TEXT NOT NULL UNIQUE,
        content_hash     TEXT NOT NULL UNIQUE,
        spec_json        TEXT NOT NULL,
        priority         INTEGER NOT NULL DEFAULT 100,
        status           TEXT NOT NULL CHECK (status IN ({_STATUS})),
        worker_id        TEXT,
        lease_expires_at TEXT,
        attempts         INTEGER NOT NULL DEFAULT 0,
        max_attempts     INTEGER NOT NULL DEFAULT 3,
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL,
        started_at       TEXT,
        finished_at      TEXT,
        error            TEXT,
        result_json      TEXT
    )
    """,
    """
    CREATE TABLE workers (
        worker_id      TEXT PRIMARY KEY,
        pid            INTEGER NOT NULL,
        host           TEXT NOT NULL,
        status         TEXT NOT NULL,
        current_campaign TEXT,
        started_at     TEXT NOT NULL,
        last_seen      TEXT NOT NULL,
        campaigns_done INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX idx_campaigns_status_priority ON campaigns(status, priority, seq)",
    "CREATE INDEX idx_campaigns_lease ON campaigns(status, lease_expires_at)",
)

MIGRATION = Migration(version=6, name="orchestration", statements=STATEMENTS)
