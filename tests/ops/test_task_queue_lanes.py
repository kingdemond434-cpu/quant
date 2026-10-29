"""DATA-50: two linked lanes, release timing, per-host rate limits, targeted invalidation.

Each test pins one property the audit found missing from the single durable queue:

    LINKED      completing an information task queues its dependent strategy task, once
    RELEASE     a task is not claimable before its release time, and says when it will be
    RATE LIMIT  a throttled host is SKIPPED, never waited on: the next eligible task is claimed
    NO IDLE GAP `claim_next` falls through an empty lane to the next one
    TARGETED    a new data version invalidates only what its lineage names, transitively
    COMPATIBLE  a pre-lane journal row folds exactly as it did before
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.task_queue import (  # noqa: E402
    INFORMATION,
    STRATEGY,
    TaskQueue,
    lineage_dependents,
)

T0 = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


def test_an_information_completion_queues_its_linked_strategy_task_once(q):
    q.link("ingest_version", "rebuild")
    q.link("ingest_version", "rebuild")                       # idempotent
    assert len(q.links()) == 1
    t = q.submit("ingest_version", lane=INFORMATION, payload={"series": "s1"},
                 dedupe_key="ingest|s1@v2")
    got = q.claim("w", lane=INFORMATION)
    assert got is not None and got.id == t.id
    assert q.complete(t.id, "w", produced={"version": "v2"})
    spawned = q.last_spawned
    assert [s.kind for s in spawned] == ["rebuild"]
    child = q.tasks()[spawned[0].id]
    assert child.lane == STRATEGY and child.parent == t.id
    assert child.payload["produced"] == {"version": "v2"} and child.payload["series"] == "s1"
    # a replayed completion queues nothing more
    assert q.complete(t.id, "w") and q.last_spawned == []
    assert sum(1 for x in q.tasks().values() if x.kind == "rebuild") == 1


def test_a_strategy_completion_queues_nothing(q):
    q.link("rebuild", "never")
    t = q.submit("rebuild", lane=STRATEGY)
    q.claim("w")
    q.complete(t.id, "w")
    assert q.last_spawned == []


def test_nothing_is_claimable_before_its_release_time(q):
    rel = T0 + timedelta(minutes=30)
    q.submit("fetch_release", lane=INFORMATION, not_before=rel)
    assert q.claim("w", now=T0) is None
    assert q.next_eligible_at(now=T0) == rel.isoformat()
    assert q.census(now=T0)["waiting_release"] == 1
    got = q.claim("w", now=rel)
    assert got is not None and got.kind == "fetch_release"


def test_a_throttled_host_is_skipped_and_the_next_task_is_claimed(q):
    q.set_rate_limit("slow.example.org", per_s=1 / 60, burst=1)
    a = q.submit("fetch", lane=INFORMATION, host="slow.example.org", priority=9)
    b = q.submit("fetch", lane=INFORMATION, host="slow.example.org", priority=8)
    c = q.submit("fetch", lane=INFORMATION, host="other.example.org", priority=1)
    assert q.claim("w", now=T0).id == a.id               # the bucket's one token
    assert q.claim("w", now=T0).id == c.id               # b is throttled: SKIPPED, not waited on
    assert q.claim("w", now=T0) is None
    assert q.next_eligible_at(now=T0) == (T0 + timedelta(seconds=60)).isoformat()
    assert q.claim("w", now=T0 + timedelta(seconds=61)).id == b.id


def test_a_rate_limit_must_be_a_real_rate(q):
    with pytest.raises(ValueError):
        q.set_rate_limit("h", per_s=0)


def test_claim_next_falls_through_an_empty_lane_so_no_worker_idles(q):
    s = q.submit("rebuild", lane=STRATEGY)
    assert q.claim_next("w", now=T0).id == s.id          # information lane empty: no idle gap
    i = q.submit("ingest", lane=INFORMATION)
    q.submit("rebuild2", lane=STRATEGY, priority=99)
    assert q.claim_next("w", now=T0).id == i.id          # information first, whatever priority


def test_an_unknown_lane_is_refused(q):
    with pytest.raises(ValueError):
        q.submit("x", lane="gossip")


def test_lineage_dependents_is_transitive_and_cycle_safe():
    rows = [{"artifact_id": "feature:f1", "input_artifact_ids": "dataset:a"},
            {"artifact_id": "cell:c1", "input_artifact_ids": ["feature:f1", "dataset:z"]},
            {"artifact_id": "cell:c2", "input_artifact_ids": "cell:c1"},
            {"artifact_id": "cell:c1", "input_artifact_ids": "cell:c2"},       # a cycle
            {"artifact_id": "feature:f2", "input_artifact_ids": "dataset:b"}]
    assert lineage_dependents("dataset:a", rows) == ["cell:c1", "cell:c2", "feature:f1"]
    assert lineage_dependents("dataset:nobody", rows) == []


def test_a_new_version_invalidates_only_what_its_lineage_names(q):
    rows = [{"artifact_id": "feature:f1", "input_artifact_ids": "dataset:a"},
            {"artifact_id": "cell:c1", "input_artifact_ids": "feature:f1"},
            {"artifact_id": "feature:f2", "input_artifact_ids": "dataset:b"},
            {"artifact_id": "cell:c2", "input_artifact_ids": "feature:f2"}]
    res = q.invalidate("dataset:a", "v7", lineage_rows=rows)
    assert res["affected"] == ["cell:c1", "feature:f1"]
    assert res["untouched"] == 2                         # f2 and c2 are left alone
    queued = {t.payload["artifact_id"] for t in q.tasks().values()}
    assert queued == {"cell:c1", "feature:f1"}
    assert all(t.lane == STRATEGY for t in q.tasks().values())
    again = q.invalidate("dataset:a", "v7", lineage_rows=rows)
    assert again["queued"] == []                         # the same version queues nothing twice


def test_a_pre_lane_journal_row_folds_as_before(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text(json.dumps({"id": "abc", "kind": "wire", "state": "READY", "priority": 1.0,
                             "created_at": T0.isoformat()}) + "\n", "utf-8")
    q = TaskQueue(p)
    t = q.tasks()["abc"]
    assert t.lane == "" and t.not_before == "" and t.host == ""
    assert q.claim("w", now=T0).id == "abc"
    assert "unlaned" in q.census(now=T0)["by_lane"]
