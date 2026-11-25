"""The deep forest on the box at cloud parity and beyond (zuck 2026-11-25 17:48Z): every region in
the grounds file (derived, never listed), the 24 h floor first, compute by yield, Asia first,
per-region output each pass, dark regions paged.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))

import deep_forest_regions as dfr
import desk_self_heal as heal

NOW = datetime(2026, 11, 25, 13, 0, tzinfo=UTC)
DESK = Path(__file__).resolve().parents[1]


def _paths(tmp_path, monkeypatch, names=("cn", "jp", "de", "zz", "global")):
    src = tmp_path / "data/sources.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps({"grounds": [{"region": r} for r in names] + [{"name": "legacy"}]}))
    for name, rel in (("STATE", "data/s.json"), ("RUNS", "data/runs.jsonl"),
                      ("REPORT", "reports/DEEP_FOREST_REGIONS.json"), ("LOGS", "logs/df"),
                      ("SOURCES", "data/sources.json")):
        monkeypatch.setattr(dfr, name, tmp_path / rel)


def _row(region, h, claims=0):
    t = (NOW - timedelta(hours=h)).isoformat()
    return {"region": region, "start": t, "end": t, "rc": 0, "claims_new": claims}


def _runner(claims=3):
    def run(region):
        return {**_row(region, 0, claims)}
    return run


def test_every_region_in_the_real_grounds_file_is_in_the_rotation():
    names = dfr.regions(DESK / "data" / "deep_forest_sources.json")
    cfg = json.loads((DESK / "data" / "deep_forest_sources.json").read_text(encoding="utf-8"))
    assert set(names) == {str(g.get("region") or "cn") for g in cfg["grounds"]}
    assert len(names) >= 200 and {"global", "institutional", "cn"} <= set(names)
    assert dfr.plan(names, [], NOW)[0] == "cn"          # never run: all due, Asia leads
    assert set(dfr.plan(names, [], NOW)) == set(names)


def test_past_the_floor_first_then_yielding_before_zero_then_not_yet_due_left_out():
    names = ["cn", "jp", "de", "fr", "us"]
    rows = [_row("cn", 1, 5),            # yielding, ran 1h ago: not due (3h cadence)
            _row("jp", 4, 2),            # yielding, 4h: due
            _row("de", 7, 0),            # zero, 7h: due (6h)
            _row("fr", 2, 0),            # zero, 2h: not due
            _row("us", 30, 0)]           # past the 24h floor: first
    assert dfr.plan(names, rows, NOW) == ["us", "jp", "de"]


def test_a_pass_runs_and_publishes_every_derived_region(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(dfr, "PARALLEL", 1)
    ticks = iter([0.0] + [0.0] * 3 + [10_000.0] * 100)      # budget runs out after 3 regions
    out = dfr.run_pass(NOW, runner=_runner(), clock=lambda: next(ticks))
    assert out["regions"] == 5 and out["ran"] == ["cn", "jp", "de"] and out["claims_new"] == 9
    doc = json.loads((tmp_path / "reports/DEEP_FOREST_REGIONS.json").read_text())
    assert set(doc["regions"]) == {"cn", "jp", "de", "zz", "global"}
    assert doc["regions"]["jp"]["claims_24h"] == 3 and doc["regions"]["jp"]["cadence_h"] == 3.0
    assert doc["regions"]["zz"]["last_end"] is None and doc["regions"]["zz"]["floor_h"] == 24.0
    again = dfr.plan(dfr.regions(), dfr._rows(NOW - timedelta(days=3)), NOW)
    assert again[:2] == ["global", "zz"]                     # the never-run regions lead next


def test_a_new_ground_is_picked_up_with_no_code_change(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch, names=("cn", "xx"))
    assert dfr.regions() == ["cn", "xx"]


def test_the_guardian_pages_a_region_past_the_floor_and_a_stale_report(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    dfr.run_pass(NOW, runner=_runner(), clock=lambda: 0.0)
    root = tmp_path / "root"
    (root / "desks/mt5/reports").mkdir(parents=True)
    rep = root / heal.DEEP_FOREST_REGIONS
    rep.write_text((tmp_path / "reports/DEEP_FOREST_REGIONS.json").read_text())
    assert heal.check_deep_forest_regions(root, NOW + timedelta(minutes=30)).ok
    doc = json.loads(rep.read_text())
    doc["regions"]["de"]["last_end"] = (NOW - timedelta(hours=25)).isoformat()
    doc["regions"]["zz"]["last_end"] = None
    rep.write_text(json.dumps(doc))
    f = heal.check_deep_forest_regions(root, NOW)
    assert not f.ok and "REGION_DARK: 2 region(s)" in f.detail and "zz (never)" in f.detail
    late = heal.check_deep_forest_regions(root, NOW + timedelta(hours=4))
    assert not late.ok and "is 4.0h old" in late.detail


def test_an_absent_report_pages_on_the_box(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    f = heal.check_deep_forest_regions(tmp_path, NOW)
    assert not f.ok and "absent" in f.detail


def test_the_task_is_declared_with_its_installer():
    root = Path(__file__).resolve().parents[3]
    man = (root / "desks/mt5/ops/box_tasks.manifest").read_text(encoding="utf-8")
    assert 'TASK name="MT5-DeepForestRegions"' in man
    assert (root / "desks/mt5/scripts/install_deep_forest_regions_task.ps1").exists()


def test_two_processes_share_one_host_spacing(tmp_path, monkeypatch):
    """Audit H1: two gates (two miner processes) book the SAME host slots through the folder."""
    from libs.data import polite_fetch as pf
    clock = [1000.0]
    monkeypatch.setattr(pf.time, "time", lambda: clock[0])
    a = pf.SharedHostGate(tmp_path, default_s=5.0)
    b = pf.SharedHostGate(tmp_path, default_s=5.0)
    assert a.reserve("api.example") == 0.0
    assert b.reserve("api.example") == 5.0       # a per-process gate would have said 0
    assert b.reserve("other.example") == 0.0
    b.penalise("api.example", 60.0)
    assert a.reserve("api.example") >= 59.0


def test_the_shared_gate_is_chosen_by_the_environment(tmp_path, monkeypatch):
    from libs.data import polite_fetch as pf
    monkeypatch.setenv(pf.SHARED_GATE_ENV, str(tmp_path))
    assert isinstance(pf._gate_from_env(), pf.SharedHostGate)
    monkeypatch.delenv(pf.SHARED_GATE_ENV)
    assert type(pf._gate_from_env()) is pf.HostGate


def test_each_miner_process_gets_the_shared_gate_and_the_pass_ends_inside_the_task_limit(
        tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(dfr, "HOST_GATE", tmp_path / "gate")
    seen = {}

    class P:
        returncode, stdout, stderr = 0, "DEEP FOREST claims_new=4 total=10", ""

    def fake_run(argv, **kw):
        seen.update(kw)
        return P()

    monkeypatch.setattr(dfr.subprocess, "run", fake_run)
    r = dfr.run_region("cn")
    assert seen["env"]["QUANT_HOST_GATE_DIR"] == str(tmp_path / "gate") and r["claims_new"] == 4
    assert dfr.PASS_BUDGET_S + dfr.REGION_TIMEOUT_S < 58 * 60


def test_each_finished_region_is_published_before_the_pass_ends(tmp_path, monkeypatch):
    """Audit H2: a pass killed at the task limit keeps every region it finished."""
    _paths(tmp_path, monkeypatch)
    calls = []
    real = dfr.publish
    monkeypatch.setattr(dfr, "publish", lambda *a, **k: calls.append(1) or real(*a, **k))
    out = dfr.run_pass(NOW, runner=_runner(1), clock=lambda: 0.0)
    assert len(out["ran"]) == 5 and len(calls) == 5 + 1      # once per region, once at the end
