from __future__ import annotations

import json

from research import state_replay_audit as audit


def test_restart_overlap_must_match_and_no_overlap_is_unmeasured(tmp_path, monkeypatch) -> None:
    ledger = tmp_path / "decision_ledger.jsonl"
    report = tmp_path / "STATE_REPLAY_PARITY.json"
    monkeypatch.setattr(audit, "LEDGER", ledger)
    monkeypatch.setattr(audit, "REPORT", report)
    one = {"state_identity": "s", "process_instance_id": "p1",
           "decided_at": "2026-09-27T10:00:01Z", "outcome": "EXECUTED", "side": "buy"}
    ledger.write_text(json.dumps(one) + "\n", "utf-8")
    assert audit.run()["status"] == "UNMEASURED"
    two = {**one, "process_instance_id": "p2", "decided_at": "2026-09-27T10:00:50Z"}
    ledger.write_text(json.dumps(one) + "\n" + json.dumps(two) + "\n", "utf-8")
    assert audit.run()["status"] == "PASS"
    ledger.write_text(json.dumps(one) + "\n" + json.dumps({**two, "side": "sell"}) + "\n",
                      "utf-8")
    assert audit.run()["status"] == "FAIL"
