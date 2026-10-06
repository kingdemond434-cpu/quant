"""A successful launch is not delivery; independently test every completion verdict."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from libs.ops import completion as C


@pytest.fixture
def desk(tmp_path, monkeypatch):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("ignored/\n")
    cycle = tmp_path / C.CYCLES[0]
    cycle.parent.mkdir(parents=True)
    names = ["unknown", "never", "failed", "ledger_failed", "missing_output", "remote",
             "stale", "orphan", "delivered"]
    cycle.write_text("\n".join(f'_costed("{name}", None)' for name in names))
    nodes = {name: SimpleNamespace(name=name, writes=(f"state/{name}.json",),
                                  reads=(), authority=("allocation",), freshness_s={})
             for name in names if name != "unknown"}
    nodes["remote"].writes = ("ignored/remote.json",)
    nodes["reader"] = SimpleNamespace(name="reader", writes=(), authority=(),
                                    reads=("state/delivered.json",))
    monkeypatch.setattr(C, "_nodes", lambda: nodes)
    marker = tmp_path / "marker.json"
    marker.write_text(json.dumps({name: {"exit_code": 0} for name in names if name != "never"}
                                | {"failed": {"exit_code": 2, "tail": "fixture failure"}}))
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("\n".join(json.dumps(row) for row in [
        {"run": "failed", "at": "2026-10-04", "outcome": "ok"},
        {"run": "failed", "at": "2026-10-05", "outcome": "error"},
        {"run": "failed", "at": "2026-10-05", "outcome": "error"},
        {"run": "ledger_failed", "at": "2026-10-05", "outcome": "error"}]))
    for name in ("stale", "orphan", "delivered"):
        target = tmp_path / f"state/{name}.json"
        target.parent.mkdir(exist_ok=True)
        target.write_text("{}")
    os.utime(tmp_path / "state/stale.json", (0, 0))
    return tmp_path, marker, ledger


def test_all_delivery_verdicts_and_authority_breaches_are_measured(desk):
    root, marker, ledger = desk
    doc = C.report(root, marker_path=marker, ledger_path=ledger)
    by_name = {row["name"]: row for row in doc["legs"]}
    assert {name: row["verdict"] for name, row in by_name.items()} == {
        "unknown": C.UNDECLARED, "never": C.NEVER_RAN, "failed": C.FAILING,
        "ledger_failed": C.FAILING, "missing_output": C.NO_OUTPUT, "remote": C.UNKNOWN_HERE,
        "stale": C.STALE, "orphan": C.UNREAD, "delivered": C.COMPLETED}
    assert by_name["failed"]["streak"] == 2
    assert "outage" in by_name["failed"]["why"]
    assert by_name["delivered"]["readers"] == ("reader",)
    assert {row["name"] for row in doc["static_findings"]} == {"unknown", "orphan"}
    assert "remote" not in {row["name"] for row in doc["authority_breaches"]}
    assert C.render(doc).startswith("COMPLETION  9 legs:")


@pytest.mark.parametrize("result, expected", [
    ({"error": "connection lost"}, "raised"),
    ({"status": "MISSING", "why": "absent script"}, "MISSING"),
    ({"status": "FAILED", "note": "bad"}, "FAILED"),
    ({"status": "ERROR"}, "ERROR"),
    ({"exit_code": None, "timeout_s": 300}, "budget"),
    ({"exit_code": 3, "tail": "line1\nline2"}, "line1 line2"),
    ({"exit_code": 0}, None), (None, None), ({}, None),
])
def test_failure_shapes_are_not_reported_completed(result, expected):
    failure = C._failed(result)
    assert (failure is None) if expected is None else expected in failure


def test_bad_inputs_remain_unreadable_not_successful(tmp_path):
    missing = tmp_path / "missing.json"
    assert C.marker(missing) == {}
    missing.write_text("not json")
    assert C.marker(missing) == {}
    missing.write_text("[]")
    assert C.marker(missing) == {}
    assert C.ledger_runs(tmp_path / "absent") == {}
    ledger = tmp_path / "ledger"
    ledger.write_text('\ninvalid\n{}\n' + "\n".join(
        json.dumps({"run": "leg", "outcome": value}) for value in ["error", "error", "ok"]))
    assert len(C.ledger_runs(ledger, window=2)["leg"]) == 2
    assert C._streak(C.ledger_runs(ledger)["leg"]) == 0


def test_unavailable_ignore_authority_does_not_claim_never_produced(tmp_path, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("git unavailable")
    monkeypatch.setattr(C.subprocess, "run", unavailable)
    assert C.artifact_state(tmp_path, "missing")["state"] == C.UNKNOWN_HERE


def test_json_cli_writes_consumable_report_to_requested_root(desk, capsys):
    root, marker, ledger = desk
    doc = C.report(root, datetime(2026, 10, 5, tzinfo=UTC),
                   marker_path=marker, ledger_path=ledger)
    assert doc["at"] == "2026-10-05T00:00:00+00:00"
    assert C.main(["--root", str(root), "--json"]) == 0
    saved = json.loads((root / C.OUT_REL).read_text())
    assert saved["n_legs"] == 9
    assert "written:" in capsys.readouterr().out


def test_missing_graph_is_explicit_and_many_breaches_are_truncated():
    doc = {"n_legs": 25, "by_verdict": {C.UNDECLARED: 25}, "graph_available": False,
           "authority_breaches": [], "runtime_findings": [], "static_findings": [
               {"verdict": C.UNDECLARED, "name": str(i), "why": "no graph", "streak": 3}
               for i in range(25)]}
    output = C.render(doc)
    assert "UNIMPORTABLE" in output
    assert "5 more" in output
    assert "x3" in output
