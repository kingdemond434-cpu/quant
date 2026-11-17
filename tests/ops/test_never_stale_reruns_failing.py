"""never_stale re-runs a FAILING task once, bounded, off the order path (2026-11-17).

Principal: routine recovery never waits on a person. A failure with no registration diagnosis
and no organ-specific remedy is started once more on its own action; the order path, the
diagnosed codes and a task that keeps failing still escalate exactly as before.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))

import never_stale as ns  # noqa: E402

MANIFEST = '''TASK name="MT5-Research" trigger="hourly" runs="x.py" installer="NONE" lane="research"
TASK name="MT5-GatewayResident" trigger="startup" runs="g.py" installer="NONE" lane="money"
TASK name="MT5-E8WindowGuard" trigger="1 min" runs="e.py" installer="NONE" lane="prop"
TASK name="MT5-GatewayResident2" trigger="10 min" runs="g.py" installer="NONE" lane="ops"
TASK name="MT5-FTMO-Allocator" trigger="hourly" runs="f.py" installer="NONE" lane="ops"
TASK name="MT5-FusionDeadmanDryRun" trigger="5 min" runs="d.py" installer="NONE" lane="research"
'''


def _run(tmp: Path, mp: pytest.MonkeyPatch, rows: list[dict], *, reruns: dict | None = None,
         manifest: str | None = MANIFEST, apply: bool = True) -> tuple[dict, list[str]]:
    health = tmp / "process_health.json"
    health.write_text(json.dumps({"scheduler_status": "OK schtasks", "processes": rows}),
                      encoding="utf-8")
    mp.setattr(ns, "HEALTH", health)
    mp.setattr(ns, "RERUNS", tmp / "reruns.json")
    if reruns is not None:
        (tmp / "reruns.json").write_text(json.dumps(reruns), encoding="utf-8")
    m = tmp / "box_tasks.manifest"
    if manifest is not None:
        m.write_text(manifest, encoding="utf-8")
    mp.setattr(ns, "MANIFEST", m)
    mp.setattr(ns, "_capital_faults", lambda: [])
    started: list[str] = []
    mp.setattr(ns, "_start", lambda t: (started.append(t), (True, "ok"))[1])
    return ns.run(apply=apply), started


def _failing(name: str, code: int) -> dict:
    return {"name": name, "verdict": "FAILING", "last_result_code": code, "why": "failed"}


def test_an_undiagnosed_research_failure_is_rerun_and_journalled(tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch
                                                                 ) -> None:
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)])
    assert started == ["MT5-Research"] and doc["escalated"] == []
    assert doc["acted"][0]["action"].startswith("JOURNAL re-run")
    assert "MT5-Research" in json.loads((tmp_path / "reruns.json").read_text())


def test_the_order_path_and_diagnosed_codes_still_escalate(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch
                                                           ) -> None:
    rows = [_failing("MT5-GatewayResident", 1), _failing("MT5-E8WindowGuard", 1),
            _failing("MT5-Research", 2147943645), _failing("MT5-TickRecorder", 4)]
    doc, started = _run(tmp_path, monkeypatch, rows)
    assert started == []
    assert {e["task"] for e in doc["escalated"]} == {r["name"] for r in rows}


def test_an_unreadable_manifest_reruns_nothing(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)], manifest=None)
    assert started == [] and doc["escalated"][0]["task"] == "MT5-Research"


def test_reruns_are_bounded_by_cooldown_and_daily_cap(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(tz=UTC)
    recent = {"MT5-Research": [(now - timedelta(minutes=10)).isoformat()]}
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)], reruns=recent)
    assert started == [] and "waiting" in doc["escalated"][0]["why"]
    capped = {"MT5-Research": [(now - timedelta(hours=h)).isoformat() for h in (2, 3, 4, 5)]}
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)], reruns=capped)
    assert started == [] and "escalating" in doc["escalated"][0]["why"]
    old = {"MT5-Research": [(now - timedelta(days=2)).isoformat()] * 9}
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)], reruns=old)
    assert started == ["MT5-Research"]


def test_dry_run_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Research", 1)], apply=False)
    assert started == [] and doc["acted"][0]["action"] == "would re-run"
    assert not (tmp_path / "reruns.json").exists()


def test_the_order_path_by_name_is_never_rerun_whatever_its_lane(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditor MF2 on #1226: MT5-GatewayResident carries lane "ops" on the box."""
    rows = [_failing("MT5-GatewayResident2", 1), _failing("MT5-FTMO-Allocator", 1),
            _failing("MT5-FusionDeadmanDryRun", 1)]
    doc, started = _run(tmp_path, monkeypatch, rows)
    assert started == []
    assert {e["task"] for e in doc["escalated"]} == {r["name"] for r in rows}


def test_a_task_missing_from_the_manifest_is_never_rerun(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MT5-Gateway is not in the manifest at all; an unknown task is never re-run."""
    doc, started = _run(tmp_path, monkeypatch, [_failing("MT5-Gateway", 1),
                                                _failing("MT5-Unlisted", 1)])
    assert started == [] and len(doc["escalated"]) == 2


def test_the_real_manifest_keeps_the_gateway_off_the_rerun_path() -> None:
    order, known = ns._manifest_tasks()
    assert known and "MT5-GatewayResident" in known
    for t in ("MT5-GatewayResident", "MT5-Gateway", "MT5-E8WindowGuard"):
        assert not ns._rerunnable(t, order, known), t
