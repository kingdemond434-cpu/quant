"""Transport receipts without a Boolean verdict must not consume unfinished research."""
import json
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest

from libs.moat import registry as R


@pytest.fixture
def registry(tmp_path, monkeypatch):
    previous = R.path()
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no-backup")
    R.set_path(tmp_path / "registry.sqlite")
    with closing(R.connect()) as connection:
        yield connection
    R.set_path(previous)


@pytest.mark.parametrize("passed", [None, "false", "true", 0, 1, [], {}])
def test_unknown_receipt_keeps_candidate_testable_then_real_verdict_completes(
        registry, tmp_path, passed):
    desk = tmp_path / "desk"
    directory = desk / "data/hypotheses"
    directory.mkdir(parents=True)
    ledger = directory / "gate_verdict_ledger.jsonl"
    lessons = tmp_path / "lessons.jsonl"
    lessons.write_text("", encoding="utf-8")
    cid = "candidate-unknown"
    R.enqueue_candidate(candidate_id=cid, family="carry", symbol="USDJPY", params={},
                        origin="DESK", conn=registry)
    original = dict(registry.execute("SELECT * FROM research_candidates WHERE id=?", (cid,))
                    .fetchone())
    row = {"cell": "USDJPY.carry.p=fixture", "graph_id": cid, "sym": "USDJPY",
           "family": "carry", "passed": passed, "terminal_gate": "UNKNOWN",
           "downstream_status": "deferred", "at": datetime.now(UTC).isoformat()}
    ledger.write_text(json.dumps(row) + "\n", encoding="utf-8")
    result = R.sync_from_desk(desk, lessons=lessons, conn=registry)
    assert result["trials"] == 1
    candidate = registry.execute("SELECT * FROM research_candidates WHERE id=?", (cid,)).fetchone()
    for key in ("status", "judged_at", "terminal_gate", "survived"):
        assert candidate[key] == original[key]
    assert registry.execute("SELECT passed FROM trials_ledger").fetchone()[0] is None
    assert registry.execute("SELECT COUNT(*) FROM provenance WHERE to_kind='verdict'")\
        .fetchone()[0] == 0
    assert R.sync_from_desk(desk, lessons=lessons, conn=registry)["trials"] == 0
    row.update(passed=False, terminal_gate="deflated_sharpe", downstream_status="rejected")
    with ledger.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
    assert R.sync_from_desk(desk, lessons=lessons, conn=registry)["trials"] == 1
    completed = registry.execute("SELECT * FROM research_candidates WHERE id=?", (cid,)).fetchone()
    assert completed["status"] == "judged" and completed["judged_at"] == row["at"]
    assert R.verify_trial_chain(conn=registry) == (True, 2)


def test_backlog_age_and_missing_receipts_are_named(registry, tmp_path):
    assert R.verdict_backlog(tmp_path, conn=registry)["status"] == "UNMEASURED"
    directory = tmp_path / "data/hypotheses"
    directory.mkdir(parents=True)
    ledger = directory / "gate_verdict_ledger.jsonl"
    old = datetime.now(UTC) - timedelta(seconds=R.SYNC_CYCLE_S + 60)
    ledger.write_text(json.dumps({"at": old.isoformat(), "passed": False}) + "\n"
                      + "broken\n[]\n\n", encoding="utf-8")
    assert R.verdict_backlog(tmp_path, conn=registry)["cursor"] is None
    R._seed_cursors(registry)
    backlog = R.verdict_backlog(tmp_path, conn=registry)
    assert backlog["status"] == "BREACH" and backlog["unsynced_rows"] == 1
    assert backlog["oldest_unsynced_age_s"] > R.SYNC_CYCLE_S
    registry.execute("UPDATE sync_cursor SET value=? WHERE key='gate_verdicts'",
                     (str(ledger.stat().st_size),))
    assert R.verdict_backlog(tmp_path, conn=registry)["status"] == "OK"
    registry.execute("UPDATE sync_cursor SET value='999999' WHERE key='gate_verdicts'")
    assert R.verdict_backlog(tmp_path, conn=registry)["unsynced_rows"] == 1


@pytest.mark.parametrize("at", [None, "invalid", "2025-01-01T00:00:00",
                               "2099-01-01T00:00:00+00:00"])
def test_invalid_backlog_clock_is_not_reported_fresh(registry, tmp_path, at):
    directory = tmp_path / "data/hypotheses"
    directory.mkdir(parents=True)
    (directory / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"at": at, "passed": False}) + "\n", encoding="utf-8")
    R._seed_cursors(registry)
    result = R.verdict_backlog(tmp_path, conn=registry)
    assert result["status"] == "BREACH" and result["oldest_unsynced_age_s"] is None
    assert "UNMEASURED" in result["why"]
