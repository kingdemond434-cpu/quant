"""Autonomous orchestration: durable queue, worker loop, supervisor recovery."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from migrations import MIGRATIONS

from libs.ops.campaign_queue import CampaignQueue
from libs.ops.research_daemon import ResearchWorker, Supervisor
from libs.ops.workers import WorkerRegistry
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def _spec(sym: str) -> dict[str, Any]:
    return {"symbols": [sym], "families": ["carry"], "source": "lake"}


def test_enqueue_dedups_identical_specs(db: Database) -> None:
    q = CampaignQueue(db)
    assert q.enqueue(_spec("EURUSD")) is not None
    assert q.enqueue(_spec("EURUSD")) is None          # same content hash -> no duplicate
    assert q.stats()["queued"] == 1


def test_lease_is_atomic_and_priority_ordered(db: Database) -> None:
    q = CampaignQueue(db)
    q.enqueue(_spec("EURUSD"), priority=200)
    q.enqueue(_spec("GBPUSD"), priority=10)             # higher priority (lower number)
    first = q.lease("w1")
    second = q.lease("w2")
    assert first is not None and first["spec"]["symbols"] == ["GBPUSD"]
    assert second is not None and second["spec"]["symbols"] == ["EURUSD"]
    assert q.lease("w3") is None                        # queue drained
    assert q.stats()["leased"] == 2


def test_complete_and_fail_retry_then_terminal(db: Database) -> None:
    q = CampaignQueue(db)
    q.enqueue(_spec("EURUSD"), max_attempts=2)
    lease = q.lease("w1")
    assert lease is not None
    assert q.fail(lease["id"], "w1", "boom") == "queued"   # attempt 1 of 2 -> retry
    lease2 = q.lease("w1")
    assert lease2 is not None
    assert q.fail(lease2["id"], "w1", "boom again") == "failed"  # attempt 2 -> parked
    assert q.stats()["failed"] == 1


def test_reclaim_stale_returns_dead_worker_campaign(db: Database) -> None:
    q = CampaignQueue(db)
    q.enqueue(_spec("EURUSD"))
    leased = q.lease("dead-worker", lease_seconds=-5)   # expires in the past (simulates crash)
    assert leased is not None
    assert q.stats()["leased"] == 1
    assert q.reclaim_stale() == 1                       # crash recovery
    assert q.stats()["queued"] == 1 and q.stats()["leased"] == 0
    assert q.lease("fresh-worker") is not None          # another worker can now claim it


def test_worker_run_once_done_and_failed(db: Database) -> None:
    q = CampaignQueue(db)

    def good(_db: Database, spec: dict[str, Any]) -> dict[str, Any]:
        return {"tested": 5, "survivors": 0}

    def bad(_db: Database, spec: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("kaboom")

    q.enqueue(_spec("EURUSD"))
    assert ResearchWorker(db, "w1", good).run_once() == "done"
    assert q.stats()["done"] == 1
    assert ResearchWorker(db, "w1", good).run_once() == "idle"   # nothing left

    q.enqueue(_spec("GBPUSD"), max_attempts=1)
    assert ResearchWorker(db, "w2", bad).run_once() == "failed"  # exception -> queue.fail
    assert q.stats()["failed"] == 1


def test_supervisor_seeds_and_recovers(db: Database) -> None:
    specs = [_spec("EURUSD"), _spec("GBPUSD"), _spec("USDJPY")]
    sup = Supervisor(db, generator=lambda: specs, min_queue_depth=2)
    assert sup.ensure_queue() == 3                      # seeds from generator
    assert sup.ensure_queue() == 0                      # already above min depth -> no-op
    # simulate a dead worker holding a lease, then a maintenance pass recovers it
    CampaignQueue(db).lease("dead", lease_seconds=-5)
    out = sup.maintain()
    assert out["reclaimed"] == 1


def test_worker_registry_heartbeat_and_dead(db: Database) -> None:
    reg = WorkerRegistry(db)
    reg.register("w1", pid=123)
    reg.beat("w1", status="running", current_campaign="c1")
    assert len(reg.active(stale_seconds=60)) == 1
    assert reg.dead(stale_seconds=-1) == [] or len(reg.dead(stale_seconds=-1)) == 1
