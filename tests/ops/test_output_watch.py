"""The output watch (zuck 2026-11-25 21:41Z): judged on output, never on a task's state."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.ops import output_watch as ow

NOW = datetime(2026, 11, 25, 22, 0, tzinfo=UTC)


def _r(run, h, outcome="ok"):
    return {"at": (NOW - timedelta(hours=h)).isoformat(), "run": run, "kind": "leg",
            "outcome": outcome}


def test_the_math_lab_shape_is_failing_not_alive():
    rows = [_r("math_lab", 50), _r("math_lab", 44), _r("math_lab", 38),
            _r("math_lab", 15, "TIMEOUT"), _r("math_lab", 5, "TIMEOUT")]
    (e,) = ow.runs(rows, NOW)
    assert e["flag"] == "FAILING_24H" and e["last_outcome"] == "TIMEOUT"


def test_silence_is_judged_on_the_runs_own_clock():
    daily = [_r("weekly_ish", h) for h in (150, 126, 102, 78, 54, 30)]
    assert ow.runs(daily, NOW)[0]["flag"] is None          # 30h < 2 x 24h cadence
    hourly = [_r("tape", h) for h in (40, 39, 38, 37, 30)]
    assert ow.runs(hourly, NOW)[0]["flag"] == "SILENT_24H"  # 30h > max(24h, 2h)
    once = [_r("oneoff", 100)]
    assert ow.runs(once, NOW)[0]["flag"] is None            # no clock to judge
    healthy = [_r("compile", h) for h in (3, 2, 1)]
    assert ow.runs(healthy, NOW)[0]["flag"] is None


def test_tasks_and_restarts_never_touch_the_money_path():
    health = {"processes": [
        {"name": "MT5-Dept-Mathlab", "verdict": "UNCONTRACTED"},
        {"name": "MT5-Compiler", "verdict": "STALE", "state": "Ready"},
        {"name": "MT5-Deepening", "verdict": "FAILING", "state": "Running"},
        {"name": "MT5-GatewayResident", "verdict": "STALE", "state": "Ready"},
        {"name": "MT5-Old", "verdict": "DISABLED", "expected_disabled": True},
    ]}
    bad, unwatched = ow.tasks(health)
    assert unwatched == ["MT5-Dept-Mathlab"]
    assert {b["task"] for b in bad} == {"MT5-Compiler", "MT5-Deepening", "MT5-GatewayResident"}
    lanes = {"MT5-Compiler": "research", "MT5-Deepening": "research",
             "MT5-GatewayResident": "research"}
    assert ow.restarts(bad, {}, NOW, lanes) == ["MT5-Compiler"]
    recent = {"started": {"MT5-Compiler": (NOW - timedelta(minutes=30)).isoformat()}}
    assert ow.restarts(bad, recent, NOW, lanes) == []
    assert ow.restarts(bad, {"started": "junk"}, NOW, lanes) == ["MT5-Compiler"]
    assert ow.restarts(bad, {}, NOW, {"MT5-Compiler": "ops"}) == []
    assert ow.restarts(bad, {}, NOW, {}) == []  # not in the manifest: page only


def test_real_manifest_never_restarts_ops_money_or_prop():
    root = Path(__file__).resolve().parents[2]
    lanes = ow.manifest_lanes((root / ow.MANIFEST_REL).read_text(encoding="utf-8"))
    assert lanes.get("MT5-RebootDrill") == "ops"
    assert len(lanes) >= 120
    bad = [{"task": n, "verdict": v, "state": "Ready", "money_path": bool(ow.MONEY.search(n))}
           for n in lanes for v in ow.RESTARTABLE]
    got = set(ow.restarts(bad, {}, NOW, lanes))
    for name in ("MT5-RebootDrill", "MT5-ReapGitWriters", "MT5-SshGuard", "MT5-OffsiteBackup"):
        assert name not in got
    assert all(lanes[n] in ("research", "data") for n in got)
    assert not {n for n, ln in lanes.items() if ln in ("ops", "money", "prop")} & got
    assert got  # research/data tasks are still restartable


def test_run_once_pages_once_per_shape_and_again_after_6h(tmp_path: Path):
    led = tmp_path / ow.LEDGER_REL
    led.parent.mkdir(parents=True)
    led.write_text("".join(json.dumps(r) + "\n" for r in
                           [_r("math_lab", 40), _r("math_lab", 34), _r("math_lab", 28),
                            _r("math_lab", 2, "TIMEOUT")])
                   + "garbage\n", encoding="utf-8")
    hp = tmp_path / ow.HEALTH_REL
    hp.parent.mkdir(parents=True)
    hp.write_text(json.dumps({"at": NOW.isoformat(), "processes": [
        {"name": "MT5-Compiler", "verdict": "STALE", "state": "Ready"},
        {"name": "MT5-RebootDrill", "verdict": "STALE", "state": "Ready"}]}), encoding="utf-8")
    mf = tmp_path / ow.MANIFEST_REL
    mf.parent.mkdir(parents=True)
    mf.write_text('TASK name="MT5-Compiler" trigger="hourly" lane="research"\n'
                  'TASK name="MT5-RebootDrill" trigger="daily" lane="ops"\n'
                  'TASK name="MT5-X" lane="research"\nTASK name="MT5-X" lane="ops"\n',
                  encoding="utf-8")
    assert ow.manifest_lanes(mf.read_text(encoding="utf-8"))["MT5-X"] == "CONFLICT"
    pages, started = [], []
    doc = ow.run_once(tmp_path, now=NOW, start=lambda t: started.append(t) or True,
                      page=pages.append)
    assert "FAILING_24H:math_lab" in doc["flagged"]
    assert "TASK_STALE:MT5-Compiler" in doc["flagged"]
    assert started == ["MT5-Compiler"] and len(pages) == 1
    assert {b["task"]: b["lane"] for b in doc["tasks_flagged"]}["MT5-RebootDrill"] == "ops"
    ow.run_once(tmp_path, now=NOW + timedelta(minutes=15), start=lambda t: True,
                page=pages.append)
    assert len(pages) == 1
    ow.run_once(tmp_path, now=NOW + timedelta(hours=7), start=lambda t: True, page=pages.append)
    assert len(pages) == 2
    assert json.loads((tmp_path / ow.REPORT_REL).read_text(encoding="utf-8"))["legs_flagged_n"]


def test_a_stale_process_health_is_itself_flagged(tmp_path: Path):
    doc = ow.run_once(tmp_path, now=NOW, start=lambda t: True, page=None)
    assert "PROCESS_HEALTH_STALE" in doc["flagged"]


def test_the_guardian_runs_it():
    src = (Path(__file__).resolve().parents[2] / "ops" / "run_guardian.cmd").read_text()
    assert "scripts\\output_watch.py\" --once" in src
