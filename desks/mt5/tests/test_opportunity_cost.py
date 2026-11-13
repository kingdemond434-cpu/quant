"""The NOT-tested set is named, bounded, and joined to the hours that went elsewhere."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import opportunity_cost as oc  # noqa: E402


def test_compiler_shortfall_reads_the_intake_block() -> None:
    d = oc.compiler_shortfall({"intake": {"bound_hit": True, "deferred_files": 7,
                                          "max_rows_per_pass": 4000}, "seats_dark": ["kimi"]})
    assert d == {"bound_hit": True, "files_deferred": 7, "max_rows_per_pass": 4000,
                 "seats_dark": ["kimi"]}
    assert oc.compiler_shortfall({})["files_deferred"] == 0


def test_gauntlet_deferred_counts_only_the_budget_status() -> None:
    gates = {"swept_at": "t", "verdicts": [
        {"cell": "A", "sym": "XAUUSD", "downstream_status": oc.DEFERRED},
        {"cell": "B", "sym": "XAUUSD", "downstream_status": oc.DEFERRED},
        {"cell": "C", "sym": "EURUSD", "passed": True},
        {"cell": "D", "sym": "EURUSD", "downstream_status": "NOT_RUN_TERMINAL_GATE_1_REJECT"}]}
    d = oc.gauntlet_deferred(gates)
    assert d["cells_deferred"] == 2 and d["of_verdicts"] == 4
    assert d["by_symbol"] == {"XAUUSD": 2} and d["cells"] == ["A", "B"]


def test_queue_backlog_is_bounded_and_skips_terminal_rows(tmp_path: Path, monkeypatch) -> None:
    now = datetime(2026, 9, 9, tzinfo=UTC)
    q = tmp_path / "q.jsonl"
    rows = [{"status": "pending", "kind": "mutation", "family": "f", "symbol": "XAUUSD",
             "created_at": (now - timedelta(days=3)).isoformat()},
            {"status": "pending", "family": "g", "symbol": "EURUSD",
             "created_at": (now - timedelta(days=9)).isoformat()},
            {"status": "done", "kind": "mutation", "family": "f", "symbol": "XAUUSD"}]
    q.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    monkeypatch.setattr(oc, "SAMPLE", 1)
    d = oc.queue_backlog(now, q)
    assert d["pending_sampled"] == 1 and d["sample_cap"] == 1
    monkeypatch.setattr(oc, "SAMPLE", 5000)
    d = oc.queue_backlog(now, q)
    assert d["pending_sampled"] == 2 and d["by_kind"] == {"mutation": 1, "None": 1}
    assert d["oldest_pending_days"] == 9.0 and d["by_symbol"] == {"XAUUSD": 1, "EURUSD": 1}


def test_spent_ranks_hours_and_totals_them() -> None:
    d = oc.spent({"a": {"hours": 1.0}, "b": {"hours": 3.0}, "c": {}}, top=1)
    assert d == {"hours_by_run": {"b": 3.0}, "total_hours": 4.0, "costed_runs": 3}


def test_build_writes_one_document_with_a_headline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(oc, "COMPILED", tmp_path / "c.json")
    monkeypatch.setattr(oc, "GATES", tmp_path / "g.json")
    monkeypatch.setattr(oc, "OUT", tmp_path / "out.json")
    monkeypatch.setattr(oc, "FRONTIER", tmp_path / "absent_frontier.json")
    (tmp_path / "c.json").write_text(json.dumps({"intake": {"deferred_files": 2}}), "utf-8")
    import queue_store
    monkeypatch.setattr(queue_store, "QUEUE", tmp_path / "none.jsonl")
    monkeypatch.setattr(queue_store, "LEGACY", tmp_path / "none2.jsonl", raising=False)
    assert oc.main([]) == 0
    doc = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert doc["not_tested"]["compiler"]["files_deferred"] == 2
    assert "2 intake files unopened" in doc["headline"]
    assert set(doc["not_tested"]) == {"compiler", "gauntlet", "queue", "research_process"}
    assert "spent" in doc
    # No frontier report on disk is UNMEASURED, never "nothing untested".
    assert doc["not_tested"]["research_process"]["open"] is None
    assert "UNMEASURED research-process limits" in doc["headline"]


def test_research_process_lists_every_unmeasured_limitation() -> None:
    fr = {"at": "t", "measured_share": 0.5, "limitations": [
        {"id": "a", "status": "MEASURED", "owner": "x", "next_experiment": "n1"},
        {"id": "b", "status": "UNMEASURED", "owner": "y", "next_experiment": "n2"},
        {"id": "c", "status": "NOT_BUILT", "owner": "z", "next_experiment": "n3"},
        {"id": "d", "status": "BLOCKED_BY_POLICY", "owner": "w", "next_experiment": "n4"}]}
    d = oc.research_process(fr)
    assert d["status"] == "MEASURED" and d["of_limitations"] == 4
    assert [r["id"] for r in d["open"]] == ["b", "c", "d"]
    assert d["open"][0]["next_experiment"] == "n2"
    assert oc.research_process({})["status"] == "UNMEASURED"
