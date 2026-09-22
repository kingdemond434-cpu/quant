"""Freshness is a lease: envelopes, TTLs by class, staleness from leases, acknowledgements."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops.control_plane import edges, lease
from libs.ops.control_plane.specs import spec


def test_ttl_table_has_the_desks_classes_and_no_defaults():
    assert lease.ttl_for("hourly") == 7_200 and lease.ttl_for("daily") == 93_600
    assert lease.ttl_for("tick") <= 300 and lease.ttl_for("news") <= 900
    assert lease.ttl_for("monthly_revision_sensitive") == lease.ttl_for("monthly")
    assert "monthly_revision_sensitive" in lease.REVISION_SENSITIVE
    assert lease.ttl_for("no_such_class") is None


def test_write_report_stamps_envelope_inside_and_beside(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "lineage.sqlite")
    monkeypatch.setattr(lease, "ACK_LOG", tmp_path / "acks.jsonl")
    s = spec("leg:x", cadence_s=3600, schedule="hourly_cycle:x", artifact_class="hourly")
    out = tmp_path / "reports" / "X.json"
    env = lease.write_report(out, {"n": 1}, s, inputs=["a.json"], epoch_id="E1", root=tmp_path)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["n"] == 1 and doc["_envelope"]["producer_component_id"] == "leg:x"
    assert env["artifact_id"] == "reports/X.json" and env["epoch_id"] == "E1"
    assert env["input_artifact_ids"] == ["a.json"] and env["ttl_s"] == 7_200
    assert env["valid_until"] != lease.UNMEASURED and env["schema_version"] == "1"
    assert (tmp_path / "reports" / "X.json.envelope.json").exists()
    assert lease.read_envelope(out)["producer_run_id"] == env["producer_run_id"]
    assert edges.latest_artifact("reports/X.json", tmp_path / "lineage.sqlite")["epoch_id"] == "E1"


def test_staleness_comes_from_leases_never_mtimes(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "lineage.sqlite")
    fresh = tmp_path / "fresh.json"
    lease.write_report(fresh, {"a": 1}, "leg:a", ttl="hourly", root=tmp_path)
    old = tmp_path / "old.json"
    lease.write_report(old, {"a": 1}, "leg:a", ttl=1, root=tmp_path)
    bare = tmp_path / "bare.json"
    bare.write_text("{}", encoding="utf-8")          # touched NOW, and still not fresh
    later = datetime.now(tz=UTC) + timedelta(seconds=30)
    v = lease.staleness([fresh, old, bare, tmp_path / "missing.json"], now=later, root=tmp_path)
    assert v["fresh.json"]["verdict"] == "VALID"
    assert v["old.json"]["verdict"] == "STALE"
    assert v["bare.json"]["verdict"] == "UNLEASED"
    assert v["missing.json"]["verdict"] == "MISSING"
    assert lease.valid(None) is None and lease.valid({"valid_until": "UNMEASURED"}) is None


def test_ack_records_consumer_run_and_producer_run(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "lineage.sqlite")
    log = tmp_path / "acks.jsonl"
    monkeypatch.setattr(lease, "ACK_LOG", log)
    art = tmp_path / "A.json"
    env = lease.write_report(art, {"x": 1}, "leg:producer", ttl="hourly", root=tmp_path)
    row = lease.ack_artifact("leg:consumer", art, epoch_id="E9")
    assert row["written"] and row["consumed_artifact_id"] == "A.json"
    assert row["producer_run_id"] == env["producer_run_id"] and row["epoch_id"] == "E9"
    assert lease.acks_for("A.json", log)[0]["consumer_component_id"] == "leg:consumer"
    assert edges.acks_of("A.json", "leg:consumer", tmp_path / "lineage.sqlite")


def test_stamp_sidecar_leases_a_file_another_writer_wrote(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(edges, "LINEAGE_DB", tmp_path / "lineage.sqlite")
    p = tmp_path / "docket.json"
    p.write_text("[1,2,3]", encoding="utf-8")
    env = lease.stamp_sidecar(p, "leg:merge_docket", ttl="hourly", root=tmp_path)
    assert env["written"] and p.read_text(encoding="utf-8") == "[1,2,3]"     # untouched
    assert lease.read_envelope(p)["producer_component_id"] == "leg:merge_docket"
    assert env["content_hash"] != lease.UNMEASURED
