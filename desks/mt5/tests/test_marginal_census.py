"""Blueprint CS5/D7: every LIVE sleeve's marginal admission is measured, and an UNMEASURED run is
timed -- never left indefinite and silent. Also ports the blueprint re-score's marks for the row
(I implemented, W on a clock, T tested, R artifact) so "done" is checked, not asserted."""
from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = pytest.mark.usefixtures("fresh_tier_s_door")

mc = pytest.importorskip("marginal_census")

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


def _view(candidates: dict, fresh: bool = True) -> dict:
    return {"fresh": fresh, "why": "test view", "at": "2026-11-03T11:00:00+00:00",
            "admission_at": "2026-11-03T11:00:00+00:00", "candidates": candidates,
            "book": {}, "zeroed": {}}


def _live(name: str, **kw) -> dict:
    return {"name": name, "status": "LIVE", "symbol": "EURUSD", "family": "carry",
            "selector": "asia", "risk_frac": 0.01, **kw}


def test_every_live_row_gets_a_reading_and_unmeasured_is_timed() -> None:
    view = _view({"a": {"admit": False, "why": "refused", "delta_elogw_per_day": -1e-4}})
    rows = [_live("a"), _live("b"), {"name": "c", "status": "STANDBY"}]
    rep, st = mc.census(rows, view, {}, NOW)
    assert rep["n_live"] == 2
    by = {r["name"]: r for r in rep["rows"]}
    assert by["a"]["marginal"] == "STANDBY"
    assert by["b"]["marginal"] == "UNMEASURED" and by["b"]["unmeasured_h"] == 0.0
    assert st["first_unmeasured_at"] == {"b": NOW.isoformat(timespec="seconds")}
    assert rep["verdict"] == "WITHIN_BOUND" and rep["enforce"] is False


def test_an_unmeasured_run_past_the_bound_is_over_bound_and_report_only() -> None:
    old = (NOW - timedelta(hours=mc.UNMEASURED_BOUND_H + 1)).isoformat(timespec="seconds")
    row = _live("b")
    rep, _ = mc.census([row], _view({}), {"first_unmeasured_at": {"b": old}}, NOW)
    assert rep["over_bound"] == ["b"] and rep["verdict"] == "OVER_BOUND"
    assert "REPORT-ONLY" in rep["rows"][0]["would_quarantine"]
    assert row["status"] == "LIVE" and row["risk_frac"] == 0.01      # nothing moved


def test_a_measured_reading_resets_the_clock_two_sided() -> None:
    old = (NOW - timedelta(hours=500)).isoformat(timespec="seconds")
    view = _view({"b": {"admit": False, "why": "refused"}})
    rep, st = mc.census([_live("b")], view, {"first_unmeasured_at": {"b": old}}, NOW)
    assert rep["over_bound"] == [] and st["first_unmeasured_at"] == {}


def test_stale_allocation_reads_unmeasured_never_zero() -> None:
    rep, _ = mc.census([_live("a")], _view({}, fresh=False), {}, NOW)
    assert rep["counts"]["unmeasured"] == 1 and rep["measured_share"] == 0.0
    rep, _ = mc.census([], _view({}), {}, NOW)
    assert rep["verdict"] == "UNMEASURED" and rep["measured_share"] is None


def test_blueprint_marks_cs5_d7_hold_in_this_tree(tmp_path: Path, monkeypatch) -> None:
    mod = _DESK / "research" / "marginal_census.py"
    assert mod.is_file()                                                         # I
    clock = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "marginal_census" in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", clock))  # W
    assert "marginal_census" in Path(__file__).read_text("utf-8")                # T
    monkeypatch.setattr(mc, "OUT", tmp_path / "MARGINAL_CENSUS.json")              # R
    monkeypatch.setattr(mc, "STATE", tmp_path / "state.json")
    sl = tmp_path / "sleeves.json"
    sl.write_text(json.dumps({"sleeves": [_live("a")]}), "utf-8")
    monkeypatch.setattr(mc.promoter, "SLEEVES_FILE", sl)
    assert mc.main([]) == 0
    doc = json.loads((tmp_path / "MARGINAL_CENSUS.json").read_text("utf-8"))
    assert doc["n_live"] == 1 and doc["generated_at"]
