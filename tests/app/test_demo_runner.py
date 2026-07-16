"""End-to-end demo runner on a replay feed + paper venue."""

from __future__ import annotations

from tests.app.conftest import buy_observation

from app.demo_runner import DemoRunner
from app.feed import ReplayFeed
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_replay_feed_exhausts() -> None:
    feed = ReplayFeed([[buy_observation()], [buy_observation()]])
    assert feed.remaining == 2
    assert feed.poll()
    assert feed.poll()
    assert feed.poll() == []  # exhausted


def test_demo_runner_full_pipeline(db: Database) -> None:
    feed = ReplayFeed([[buy_observation()] for _ in range(3)])
    result = DemoRunner(db, capital=100_000.0).run(feed)
    assert result.ticks_processed == 3
    assert result.signals_generated >= 1
    assert result.allocations >= 1
    # the demo actually places paper orders through the risk gate and fills them
    assert result.orders_filled >= 1
    # dashboard snapshot reflects executed state and an intact audit chain
    assert result.dashboard.execution["fills"] >= 1
    assert result.dashboard.system_health["audit_chain_ok"] is True
    assert verify_audit_chain(db).ok


def test_demo_runner_handles_empty_feed(db: Database) -> None:
    result = DemoRunner(db).run(ReplayFeed([]))
    assert result.ticks_processed == 0
    assert result.orders_filled == 0
    assert result.dashboard.execution["orders"] == 0


def test_demo_runner_respects_max_ticks(db: Database) -> None:
    feed = ReplayFeed([[buy_observation()] for _ in range(10)])
    result = DemoRunner(db).run(feed, max_ticks=2)
    assert result.ticks_processed == 2
