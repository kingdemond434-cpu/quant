from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.research import durable_query_queue as Q


def _rows(n: int) -> list[dict]:
    return [{"country": "sg", "layer": "official", "domain": "rules",
             "query": f"query {i}", "languages": ["en"]} for i in range(n)]


def test_more_than_5000_queries_survive_restart_and_reconcile(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    assert Q.enqueue(path, _rows(5_501))["total"] == 5_501
    # Re-open from disk and enqueue the same rows: identity, not process memory, deduplicates.
    assert Q.enqueue(path, _rows(5_501)) == {"added": 0, "total": 5_501}
    rec = Q.reconcile(path)
    assert rec["balanced"] is True
    assert rec["states"]["QUEUED"] == 5_501


def test_lease_ack_and_crash_recovery_are_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "queue.json"
    Q.enqueue(path, _rows(3), at="2026-09-27T00:00:00+00:00")
    now = datetime(2026, 9, 27, 1, tzinfo=UTC)
    first = Q.lease(path, owner="forest_runner:asia", countries=["sg"], limit=2,
                    lease_s=10, now=now)
    assert len(first) == 2
    assert Q.acknowledge(path, [first[0]["query_id"]], owner="forest_runner:asia",
                         evidence="recorded source_seed") == 1
    # The unacknowledged lease expires and is offered again; the acknowledged one never is.
    again = Q.lease(path, owner="forest_runner:asia", countries=["sg"], limit=3,
                    lease_s=10, now=now + timedelta(seconds=11))
    got = {r["query_id"] for r in again}
    assert first[0]["query_id"] not in got
    assert first[1]["query_id"] in got
    assert Q.acknowledge(path, got, owner="forest_runner:asia") == 2
    rec = Q.reconcile(path)
    assert rec["balanced"] is True and rec["states"]["RESOLVED"] == 3
    raw = json.loads(path.read_text("utf-8"))
    assert all(row["consumer_acknowledgement"] for row in raw["items"].values())
