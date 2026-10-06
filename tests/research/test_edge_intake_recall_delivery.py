"""Repeated sightings must link provenance without removing unfinished experiments."""
from __future__ import annotations

import json

import pytest

from libs.research import edge_intake as E


def queue(root, entries):
    path = root / "queue.json"
    path.write_text(json.dumps({"queue": entries}), encoding="utf-8")
    return path


def test_later_sighting_preserves_pending_canonical_disposition(tmp_path, monkeypatch):
    path = queue(tmp_path, [{"video_id": "edge", "title": "carry entry rule", "score": 10}])
    monkeypatch.setattr(E, "_now", lambda: "2026-10-01T12:00:00+00:00")
    assert E.stamp_queue(path, root=tmp_path)["n_stamped"] == 1
    monkeypatch.setattr(E, "_now", lambda: "2026-10-02T12:00:00+00:00")
    second = E.stamp_queue(path, root=tmp_path)
    assert second["by_disposition"] == {"DUPLICATE_OF_EXISTING_TEST": 1}
    assert E.rows(tmp_path)[-1]["links_to"] == "edge"
    assert E.next_batch(root=tmp_path)[0]["ident"] == "edge"
    assert E.stamp_queue(path, root=tmp_path)["n_stamped"] == 0
    assert len(E.rows(tmp_path)) == 2
    audit = E.recall_audit(tmp_path, queue_report=path)
    assert audit["reconciles"]
    assert audit["by_disposition"] == {"NEXT_BATCH_TEST": 1}


def test_repeated_provenance_does_not_reset_admission_or_deferral(tmp_path, monkeypatch):
    path = queue(tmp_path, [{"video_id": "one", "title": "session open", "score": 1},
                            {"video_id": "two", "title": "London fix", "score": 100},
                            {"video_id": "topic", "title": "nice trading video"}])
    monkeypatch.setattr(E, "_now", lambda: "2026-10-01T12:00:00+00:00")
    stamped = E.stamp_queue(path, root=tmp_path)
    assert stamped["by_disposition"] == {"NEXT_BATCH_TEST": 2, "BLOCKED_PENDING_DATA": 1}
    assert E.defer(["one", "missing"], "capacity already in use", root=tmp_path) == 1
    assert E.next_batch(root=tmp_path, limit=1)[0]["ident"] == "one"
    assert E.admit(["one", "missing", "topic"], root=tmp_path) == 1
    assert [row["ident"] for row in E.next_batch(root=tmp_path)] == ["two"]
    admitted_at = E._current(tmp_path)["one"]["admitted_at"]
    monkeypatch.setattr(E, "_now", lambda: "2026-10-02T12:00:00+00:00")
    E.stamp_queue(path, root=tmp_path)
    folded = E._current(tmp_path)["one"]
    assert folded["admitted_at"] == admitted_at
    assert folded["deferrals"] == 1
    assert [row["ident"] for row in E.next_batch(root=tmp_path)] == ["two"]
    assert "capacity already in use" in folded["deferral_reason"]


def test_unaccounted_queue_rows_are_a_defect(tmp_path):
    path = queue(tmp_path, [{"video_id": "unseen", "title": "carry"}])
    audit = E.recall_audit(tmp_path, queue_report=path)
    assert not audit["reconciles"]
    assert audit["unaccounted_idents"] == ["unseen"]
    assert audit["edges_discovered"] == 1
    assert E.stamp_queue(path, root=tmp_path)["n_stamped"] == 1
    assert E.recall_audit(tmp_path, queue_report=path)["reconciles"]


def test_ledger_ignores_truncated_tail_without_inventing_a_disposition(tmp_path):
    assert E.rows(tmp_path) == []
    path = tmp_path / E.LEDGER
    path.parent.mkdir(parents=True)
    path.write_text('\ninvalid\n{"ident":"unfinished"', encoding="utf-8")
    assert E.rows(tmp_path) == []
    assert E._current(tmp_path) == {}


@pytest.mark.parametrize("content", [None, "invalid JSON"])
def test_unreadable_queue_returns_named_block(tmp_path, content):
    path = tmp_path / "queue.json"
    if content:
        path.write_text(content)
    result = E.stamp_queue(path, root=tmp_path)
    assert result["status"] == "BLOCKED"
    assert result["n_stamped"] == 0
    assert "unreadable" in result["why"]


def test_injectable_duty_adds_work_without_admitting_or_rejecting(tmp_path):
    path = queue(tmp_path, [{"video_id": str(i), "title": "carry entry rule"} for i in range(8)])
    E.stamp_queue(path, root=tmp_path)
    before = E.rows(tmp_path)
    duty = E.intake_duty(root=tmp_path)
    assert "8 candidate(s)" in duty
    assert "3 more" in duty
    assert "FULL CADENCE" in duty
    assert E.rows(tmp_path) == before
    E.admit([str(i) for i in range(8)], root=tmp_path)
    assert E.intake_duty(root=tmp_path) == ""


def test_missing_identity_and_future_admission_are_not_fabricated(tmp_path):
    queue(tmp_path, [{"title": "carry"}, {"video_id": "valid", "title": "arbitrage"}])
    assert E.stamp_queue("queue.json", root=tmp_path)["n_stamped"] == 1
    assert E.next_batch(root=tmp_path)[0]["admitted_at"] is None
    assert E.classify({"ident": "valid"}, seen=E._current(tmp_path))[0] == \
        "DUPLICATE_OF_EXISTING_TEST"
    assert not E._same_utc_day("", "2026-10-01")
