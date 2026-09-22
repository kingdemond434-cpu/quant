"""Edges are proven by producer run id + consumer acknowledgement inside a valid lease."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.control_plane import edges, lease
from libs.ops.control_plane.edges import Edge


def _env(art: str, producer: str, run: str, ttl_s: int = 3600, epoch: str = "E1") -> dict:
    now = datetime.now(tz=UTC)
    return {"artifact_id": art, "producer_component_id": producer, "producer_run_id": run,
            "epoch_id": epoch, "created_at": now.isoformat(timespec="seconds"),
            "valid_until": (now + timedelta(seconds=ttl_s)).isoformat(timespec="seconds")}


def _ack(art: str, consumer: str, run: str | None) -> dict:
    return {"consumer_component_id": consumer, "consumed_artifact_id": art,
            "consumer_run_id": f"{consumer}#1", "producer_run_id": run,
            "consumed_at": datetime.now(tz=UTC).isoformat(timespec="seconds")}


def test_the_mandatory_path_is_declared_as_data():
    stages = {e.stage for e in edges.REQUIRED_EDGES}
    for needed in ("forest->compiler", "docket->gauntlet", "gauntlet->forward",
                   "forward->promoter", "promoter->allocator", "allocator->gateway",
                   "discovery->registry->compiler", "controller->allocation",
                   "allocation->departments"):
        assert needed in stages
    assert all(e.criticality == "required" for e in edges.REQUIRED_EDGES)
    assert edges.edges_for(consumer="task:MT5-Gateway")[0].producer == "leg:pf_allocator"


def test_edge_states_in_order_of_proof(tmp_path: Path):
    db = tmp_path / "lineage.sqlite"
    e = Edge("leg:p", "leg:c", "reports/A.json", "p->c")
    assert edges.observe(e, path=db)["state"] == "UNPRODUCED"
    assert edges.record_artifact(_env("reports/A.json", "leg:p", "run-1"), db)
    assert edges.observe(e, path=db)["state"] == "UNACKED"
    edges.record_ack(_ack("reports/A.json", "leg:c", "UNMEASURED"), db)
    weak = edges.observe(e, path=db)
    assert weak["state"] == "ACK_WEAK" and not weak["observed"]
    edges.record_ack({**_ack("reports/A.json", "leg:c", "run-1"), "consumer_run_id": "c#2"}, db)
    ok = edges.observe(e, path=db)
    assert ok["state"] == "OBSERVED" and ok["observed"] and ok["acks_of_this_run"] == 1
    # the producer writes a NEW run: the old ack no longer proves the edge
    edges.record_artifact(_env("reports/A.json", "leg:p", "run-2"), db)
    assert edges.observe(e, path=db)["state"] == "ACK_WEAK"


def test_expired_lease_and_wrong_producer_are_named(tmp_path: Path):
    db = tmp_path / "lineage.sqlite"
    e = Edge("leg:p", "leg:c", "reports/B.json", "p->c")
    edges.record_artifact(_env("reports/B.json", "leg:p", "r1", ttl_s=1), db)
    edges.record_ack(_ack("reports/B.json", "leg:c", "r1"), db)
    later = datetime.now(tz=UTC) + timedelta(seconds=5)
    assert edges.observe(e, now=later, path=db)["state"] == "LEASE_EXPIRED"
    edges.record_artifact(_env("reports/B.json", "leg:intruder", "r9"), db)
    r = edges.observe(e, path=db)
    assert r["state"] == "WRONG_PRODUCER" and r["producer_seen"] == "leg:intruder"


def test_closed_loop_requires_every_required_edge(tmp_path: Path):
    db = tmp_path / "lineage.sqlite"
    es = (Edge("a", "b", "x.json", "a->b"), Edge("b", "c", "y.json", "b->c"))
    edges.record_artifact(_env("x.json", "a", "r1"), db)
    edges.record_ack(_ack("x.json", "b", "r1"), db)
    doc = edges.closed_loop(es, path=db)
    assert doc["required"] == 2 and doc["observed"] == 1 and doc["open"] == ["b -> c"]
    assert doc["closed"] is False
    edges.record_artifact(_env("y.json", "b", "r2"), db)
    edges.record_ack(_ack("y.json", "c", "r2"), db)
    assert edges.closed_loop(es, path=db)["closed"] is True
    assert edges.closed_loop((), path=db)["closed"] is False        # nothing proven is not closed


def test_write_report_and_ack_feed_the_store_end_to_end(tmp_path: Path, monkeypatch):
    db = tmp_path / "lineage.sqlite"
    monkeypatch.setattr(edges, "LINEAGE_DB", db)
    monkeypatch.setattr(lease, "ACK_LOG", tmp_path / "acks.jsonl")
    art = tmp_path / "R.json"
    lease.write_report(art, {"k": 1}, "leg:p", ttl="hourly", root=tmp_path)
    lease.ack_artifact("leg:c", art)
    assert edges.observe(Edge("leg:p", "leg:c", "R.json", "p->c"), path=db)["state"] == "OBSERVED"
