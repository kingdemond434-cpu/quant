"""A stuck 24/7 research/data resident is ended and restarted; nothing else is ever ended."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import never_stale as ns  # noqa: E402


def _row(name: str, **kw: object) -> dict:
    row = {"name": name, "verdict": "STALE", "artifact": "desks/mt5/data/x.json",
           "resident": True, "lane": "research", "why": "older than its contract"}
    row.update(kw)
    return row


def _board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> list[tuple]:
    health = tmp_path / "process_health.json"
    health.write_text(json.dumps({"processes": rows}), encoding="utf-8")
    monkeypatch.setattr(ns, "HEALTH", health)
    monkeypatch.setattr(ns, "_capital_faults", lambda: [])
    calls: list[tuple] = []
    monkeypatch.setattr(ns, "_end", lambda t: (calls.append(("end", t)), (True, "ok"))[1])
    monkeypatch.setattr(ns, "_start", lambda t: (calls.append(("run", t)), (True, "ok"))[1])
    return calls


@pytest.mark.parametrize("row,expected", [
    (_row("MT5-Forest-Korea"), True),
    (_row("MT5-TickRecorder", lane="data"), False),
    (_row("MT5-AllocatorPulse", lane="money"), False),
    (_row("MT5-Forest-Korea", resident=False), False),
    (_row("MT5-Forest-Korea", verdict="FAILING"), False),
    (_row("MT5-Forest-Korea", artifact=None), False),
])
def test_only_contracted_stuck_research_or_data_residents_qualify(row: dict,
                                                                   expected: bool) -> None:
    assert ns.resident_restartable(row) is expected


def test_stuck_resident_is_ended_then_started(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _board(tmp_path, monkeypatch, [_row("MT5-Forest-China")])
    out = ns.run(apply=True)
    assert calls == [("end", "MT5-Forest-China"), ("run", "MT5-Forest-China")]
    assert out["acted"][0]["action"] == "resident restarted"


def test_money_resident_and_plain_task_are_only_started(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _board(tmp_path, monkeypatch, [_row("MT5-AllocatorPulse", lane="money"),
                                           _row("MT5-Harvest", resident=False)])
    ns.run(apply=True)
    assert ("end", "MT5-AllocatorPulse") not in calls
    assert all(kind == "run" for kind, _ in calls)


def test_dry_run_ends_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _board(tmp_path, monkeypatch, [_row("MT5-Forest-China")])
    out = ns.run(apply=False)
    assert calls == []
    assert out["acted"][0]["action"] == "would restart resident"


def test_a_failed_end_is_a_failed_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    monkeypatch.setattr(ns, "_end", lambda t: (False, "access denied"))
    monkeypatch.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    ok, why = ns._restart_resident("MT5-Forest-China")
    assert ok is False and "end FAILED" in why and started == []
