"""The deep forest on the box at cloud parity (zuck 2026-11-25 17:48Z): every region reached in
turn, Asia first, zero regions each 6-hour window, per-region output each pass, dark regions paged.
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


def _paths(tmp_path, monkeypatch):
    for name, rel in (("STATE", "data/s.json"), ("RUNS", "data/runs.jsonl"),
                      ("REPORT", "reports/DEEP_FOREST_REGIONS.json"), ("LOGS", "logs/df")):
        monkeypatch.setattr(dfr, name, tmp_path / rel)


def _runner(claims=3):
    def run(region):
        return {"region": region, "start": NOW.isoformat(), "end": NOW.isoformat(), "rc": 0,
                "claims_new": claims, "claims_total": 100,
                "kind": "zero" if region in dfr.ZERO else "producing"}
    return run


def test_the_lists_are_the_clouds_and_asia_leads():
    assert len(dfr.PRODUCING) == 33 and len(dfr.ZERO) == 20
    assert not set(dfr.PRODUCING) & set(dfr.ZERO)
    assert dfr.PRODUCING[:4] == ("cn", "jp", "kr", "tw")


def test_the_plan_resumes_at_the_cursor_and_puts_zero_regions_first_once_per_window():
    q = dfr.plan({"cursor": 2}, NOW)
    assert q[0] == "kr" and q[-1] == "jp" and len(q) == 33
    six = NOW.replace(hour=12)
    assert dfr.plan({}, six)[:20] == list(dfr.ZERO)
    assert dfr.plan({"zero_window": "2026-11-25T12"}, six)[0] == "cn"


def test_a_pass_publishes_every_region_and_advances_the_cursor(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    ticks = iter([0.0] + [0.0] * 3 + [10_000.0] * 100)        # budget runs out after 3 regions
    monkeypatch.setattr(dfr, "PARALLEL", 1)
    out = dfr.run_pass(NOW, runner=_runner(), clock=lambda: next(ticks))
    assert out["ran"] == ["cn", "jp", "kr"] and out["claims_new"] == 9
    assert json.loads((tmp_path / "data/s.json").read_text())["cursor"] == 3
    doc = json.loads((tmp_path / "reports/DEEP_FOREST_REGIONS.json").read_text())
    assert len(doc["regions"]) == 53 and doc["regions"]["jp"]["claims_24h"] == 3
    assert doc["regions"]["tw"]["last_end"] is None


def test_the_zero_window_is_spent_only_when_every_zero_region_ran(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(dfr, "PARALLEL", 2)
    six = NOW.replace(hour=18)
    dfr.run_pass(six, runner=_runner(0), clock=lambda: 0.0)
    st = json.loads((tmp_path / "data/s.json").read_text())
    assert st["zero_window"] == "2026-11-25T18" and st["cursor"] == 0


def test_the_guardian_pages_a_dark_region_and_a_stale_report(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(heal, "_is_producing_host", lambda root, rel: True)
    dfr.run_pass(NOW, runner=_runner(), clock=lambda: 0.0)
    rep = tmp_path / "reports/DEEP_FOREST_REGIONS.json"
    root = tmp_path / "root"
    (root / "desks/mt5/reports").mkdir(parents=True)
    (root / heal.DEEP_FOREST_REGIONS).write_text(rep.read_text())
    f = heal.check_deep_forest_regions(root, NOW + timedelta(minutes=30))
    assert not f.ok and "REGION_DARK: 20 region(s)" in f.detail      # zero regions never ran
    doc = json.loads(rep.read_text())
    for g in doc["regions"].values():
        g["last_end"] = NOW.isoformat()
    (root / heal.DEEP_FOREST_REGIONS).write_text(json.dumps(doc))
    assert heal.check_deep_forest_regions(root, NOW + timedelta(minutes=30)).ok
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
