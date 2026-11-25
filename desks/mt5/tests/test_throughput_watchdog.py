"""THROUGHPUT, NOT JUST LIVENESS (principal 2026-11-20: research runs 24/7 at full strength).

Measured 2026-11-20: every task read Running while the judge had made no verdict for 8.5h
(1.7k first verdicts/day against 100k) and the model seat made 237 completions against 670/day.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import desk_self_heal as heal  # noqa: E402

NOW = datetime(2026, 11, 20, 19, 38, tzinfo=UTC)


def _write(root: Path, rel: str, doc: object, age_h: float = 0.0) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc), encoding="utf-8")
    t = (NOW - timedelta(hours=age_h)).timestamp()
    os.utime(p, (t, t))
    return p


def _judge(root: Path, first: float, last_h: float) -> None:
    _write(root, "desks/mt5/reports/JUDGING_THROUGHPUT.json",
           {"rate": {"first_judged_per_day": first,
                     "verdicts": {"last_verdict_at": (NOW - timedelta(hours=last_h)).isoformat()}}})


def test_judge_stalled_is_rerun(tmp_path):
    _judge(tmp_path, 1717.0, 8.5)
    f = heal.check_judge_throughput(tmp_path, NOW)
    assert not f.ok and f.fixable and "8.5h" in f.detail and "100,000" in f.detail
    remedies, _ = heal.plan([f], run_task=lambda t: True)
    assert [r.action for r in remedies] == ["run MT5-Gauntlet"]


def test_judge_weak_but_flowing_escalates(tmp_path):
    _judge(tmp_path, 20_000.0, 0.2)
    f = heal.check_judge_throughput(tmp_path, NOW)
    assert not f.ok and not f.fixable
    remedies, escalate = heal.plan([f], run_task=lambda t: True)
    assert not remedies and escalate == [f]


def test_judge_at_target_passes(tmp_path):
    _judge(tmp_path, 120_000.0, 0.1)
    assert heal.check_judge_throughput(tmp_path, NOW).ok


def test_judge_unmeasured_is_not_healthy_on_the_box(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    assert not heal.check_judge_throughput(tmp_path, NOW).ok
    p = tmp_path / "desks/mt5/reports/JUDGING_THROUGHPUT.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    assert not heal.check_judge_throughput(tmp_path, NOW).ok


def test_llm_below_pace_escalates(tmp_path):
    _write(tmp_path, "desks/mt5/reports/LLM_BUDGET_CENSUS.json",
           {"at": "2026-11-20T17:53:00+00:00",
            "today": {"desk_completions": 237, "waste_rate": 0.51}})
    f = heal.check_llm_throughput(tmp_path, NOW)
    assert not f.ok and not f.fixable and "237" in f.detail and "0.51" in f.detail


def test_llm_on_pace_passes(tmp_path):
    _write(tmp_path, "desks/mt5/reports/LLM_BUDGET_CENSUS.json",
           {"at": "2026-11-20T12:00:00+00:00", "today": {"desk_completions": 330}})
    assert heal.check_llm_throughput(tmp_path, NOW).ok


def test_idle_lane_with_task_is_rerun_and_box_lanes_extend(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    _write(tmp_path, "desks/mt5/reports/CN_MODEL_ENSEMBLE.json", {}, age_h=5)
    _write(tmp_path, "desks/mt5/reports/LLM_BUDGET_CENSUS.json", {}, age_h=0.5)
    _write(tmp_path, "desks/mt5/reports/JUDGING_THROUGHPUT.json", {}, age_h=0.5)
    _write(tmp_path, "desks/mt5/reports/MATH_LAB.json", {}, age_h=3)
    _write(tmp_path, heal.LANES_FILE, [
        {"lane": "math lab", "path": "desks/mt5/reports/MATH_LAB.json", "max_age_h": 2,
         "task": "MT5-Dept-Mathlab"},
        {"lane": "bad", "path": "../x.json", "max_age_h": 1, "task": "MT5-X"},
        {"lane": "not ours", "path": "desks/mt5/reports/y.json", "max_age_h": 1,
         "task": "evil-task"}])
    found = {f.check: f for f in heal.check_lanes_idle(tmp_path, NOW)}
    assert "lane math lab" in found and "lane bad" not in found
    assert found["lane not ours"].task is None          # watched, never re-run
    assert found["lane llm budget census"].ok
    stale = [found["lane cn model ensemble"], found["lane math lab"]]
    assert not any(f.ok for f in stale)
    remedies, _ = heal.plan(stale, run_task=lambda t: True)
    assert sorted(r.action for r in remedies) == ["run MT5-DeepSeek", "run MT5-Dept-Mathlab"]
    # a lane with no report on the producing host is named, never silently healthy
    assert not found["lane forest africa"].ok


def test_audit_includes_throughput_checks(tmp_path):
    names = {f.check for f in heal.audit(tmp_path, NOW)}
    assert {"judge throughput", "llm throughput"} <= names


def test_a_lanes_file_can_never_rerun_a_live_or_release_task(tmp_path, monkeypatch):
    """Audit MF-1: a lanes file must not turn self-heal into a way to start a live executor,
    the follower, the gateway or the release adopter (any of which may be stopped on purpose)."""
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    live = ["MT5-E8-Executor", "MT5-AdoptRelease", "MT5-FTMO-Executor", "MT5-Follower",
            "MT5-Gateway", "MT5-Dept-LiveBridge", "MT5-Forest-E8"]
    rows = []
    for i, task in enumerate(live):
        rel = f"desks/mt5/reports/L{i}.json"
        _write(tmp_path, rel, {}, age_h=9)
        rows.append({"lane": f"l{i}", "path": rel, "max_age_h": 1, "task": task})
    _write(tmp_path, heal.LANES_FILE, rows)
    found = [f for f in heal.check_lanes_idle(tmp_path, NOW) if f.check[len("lane l"):].isdigit()]
    assert len(found) == len(live) and not any(f.ok for f in found)
    assert all(f.task is None for f in found)
    remedies, _ = heal.plan(found, run_task=lambda t: True)
    assert not any(any(t in r.action for t in live) for r in remedies)
    assert not any(heal._LIVE_TASK.search(t) for t in heal.RESEARCH_TASKS)
