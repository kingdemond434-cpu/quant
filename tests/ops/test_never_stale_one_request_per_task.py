"""never_stale asks for each scheduled task at most once per pass (2026-11-25).

Thirty organ-contract rows map onto MT5-FrontierAudit; one /Run per stale row made Task
Scheduler refuse ~8 requests a quarter hour (event 322, IgnoreNew). One request per task, none
when the task is already Running, and the report still counts every row coalesced.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import never_stale as ns  # noqa: E402

N = 30


def _pass(tmp: Path, mp: pytest.MonkeyPatch, state: str | None) -> tuple[dict, list[str]]:
    rows = [{"name": f"MT5-FrontierAudit (organ {i})", "task": "MT5-FrontierAudit",
             "verdict": "STALE", "why": "artifact old"} for i in range(N)]
    health = tmp / "process_health.json"
    health.write_text(json.dumps({"scheduler_status": "OK schtasks", "processes": rows}),
                      encoding="utf-8")
    mp.setattr(ns, "HEALTH", health)
    mp.setattr(ns, "RERUNS", tmp / "reruns.json")
    mp.setattr(ns, "_capital_faults", lambda: [])
    mp.setattr(ns, "_manifest_tasks", lambda: (frozenset(), frozenset()))
    mp.setattr(ns, "_task_state", lambda t: state)
    started: list[str] = []
    mp.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    return ns.run(apply=True), started


def test_thirty_stale_rows_one_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, started = _pass(tmp_path, monkeypatch, "Ready")
    assert started == ["MT5-FrontierAudit"]
    assert len(doc["acted"]) == N  # the board still sees every stale row
    assert doc["task_requests"]["MT5-FrontierAudit"] == {
        "rows": N, "requests_issued": 1, "coalesced": N - 1}


def test_no_request_when_task_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, started = _pass(tmp_path, monkeypatch, "Running")
    assert started == []
    rep = doc["task_requests"]["MT5-FrontierAudit"]
    assert rep["requests_issued"] == 0 and rep["rows"] == N and "skipped" in rep


def test_state_query_failure_keeps_old_behaviour(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    _, started = _pass(tmp_path, monkeypatch, None)
    assert started == ["MT5-FrontierAudit"]
