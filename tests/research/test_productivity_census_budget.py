"""THE CENSUS'S BUDGET IS ENFORCED INSIDE THE PASS, AND A PARTIAL CENSUS IS READ AS PARTIAL.

Measured 2026-11-05 from box-published state: PRODUCTIVITY_CENSUS.json was last written
2026-10-22T17:06Z, 14 days stale, while `--budget-s` was only a label read after the pass ended.
These tests pin the repair:

  * the deadline stops the registry scan between steps AND inside a running statement, and an
    interrupted statement is never an empty (zero) result;
  * a cut pass still writes a census, stamped `partial: true` with scanned/total, and every
    stage it did not scan is UNMEASURED -- never zero, never accused in `zero_cell_compute`;
  * a resume cursor carries finished steps into the next pass, which completes the census;
  * the judge-input scan resumes from its byte offset;
  * the fence judges a partial census as partial, and fails when none completes in 26h;
  * `check_producer_yield` reads a census older than 26h as STALE, not current.
"""
from __future__ import annotations

import importlib
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pc = importlib.import_module("desks.mt5.research.productivity_census")
cols = importlib.import_module("tests.research.test_productivity_census_columns")
fence = importlib.import_module("scripts.check_productivity_census")
pyf = importlib.import_module("scripts.check_producer_yield")

census_env = cols.census_env  # the shared fixture: every census path under tmp_path


@pytest.fixture()
def cursor_paths(census_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    reports = census_env / "reports"
    monkeypatch.setattr(pc, "CURSOR", reports / "PRODUCTIVITY_CENSUS.cursor.json")
    monkeypatch.setattr(pc, "REACH_SIDECAR", reports / "PRODUCTIVITY_CENSUS.reach_ids.txt")
    monkeypatch.setattr(pc, "OUT", reports / "PRODUCTIVITY_CENSUS.json")
    monkeypatch.setattr(pc, "DOC", census_env / "PRODUCTIVITY_CENSUS.md")
    cols._roster(census_env, [{"producer": "alpha_evolution", "kind": "seat",
                               "clock": "hourly_cycle:alpha_evolution"}])
    cols._registry(census_env / "alpha_registry.sqlite", [
        {"generator": "alpha_evolution", "grid_cell": "x", "judged_at": "2026-09-24T00:00:00"},
        {"generator": "alpha_evolution", "grid_cell": "y"},
    ])
    cols._judge_input(census_env / "external_survivors.json", ["c0", "c1"])
    return census_env


def _cut_after(monkeypatch: pytest.MonkeyPatch, step_name: str) -> dict[str, bool]:
    """Make the budget expire the moment `step_name` finishes, while `armed["on"]`."""
    real = pc._step
    armed = {"on": True}

    def wrapped(name: str, *a: Any, **k: Any) -> None:
        real(name, *a, **k)
        if name == step_name and armed["on"]:
            pc._BUDGET.deadline = 0.0

    monkeypatch.setattr(pc, "_step", wrapped)
    return armed


def _row(census: dict[str, Any], key: str = "alpha_evolution") -> dict[str, Any]:
    return next(r for r in census["producers"] if r["key"] == key)


def test_a_cut_pass_is_partial_and_its_unscanned_stages_are_unmeasured(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _cut_after(monkeypatch, "cells")
    census = pc.build(budget_s=600.0)
    assert census["partial"] is True
    scan = census["scan"]
    assert scan["scanned"] == pc.STEPS.index("cells") + 1 and scan["total"] == len(pc.STEPS)
    assert "judged" in scan["unscanned"] and "cells_judged" in scan["unscanned_fields"]
    row = _row(census)
    assert row["funnel"]["raw_cells"] == 2                       # scanned: measured
    assert row["funnel"]["cells_judged"] == pc.UNMEASURED        # not scanned: never zero
    assert row["funnel"]["gauntlet_submitted"] == pc.UNMEASURED
    assert not any(z["key"] == "alpha_evolution" for z in census["zero_cell_compute"])
    assert pc.CURSOR.exists()


def test_the_cursor_resumes_and_the_next_pass_completes(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    armed = _cut_after(monkeypatch, "cells")
    pc.build(budget_s=600.0)
    armed["on"] = False
    census = pc.build(budget_s=600.0)
    assert census["partial"] is False
    assert "cells" not in census["scan"]["ran_this_pass"]       # carried, not re-run
    assert "judged" in census["scan"]["ran_this_pass"]
    assert _row(census)["funnel"]["cells_judged"] == 1
    assert not pc.CURSOR.exists()                                # a complete cycle clears it


def test_an_interrupted_statement_raises_and_is_never_an_empty_result(tmp_path: Path) -> None:
    db = tmp_path / "r.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table t (x int)")
    con.executemany("insert into t values (?)", ((i,) for i in range(5000)))
    con.commit()
    pc._BUDGET = pc._Budget(0.0)          # already expired
    con.set_progress_handler(pc._BUDGET.progress, 10)
    try:
        with pytest.raises(pc._OutOfBudget):
            pc._rows(con.cursor(), "select count(*) from t a, t b")
    finally:
        con.close()
        pc._BUDGET = pc._Budget(None)
    # and a schema error with no deadline stays the table's own empty answer
    con = sqlite3.connect(db)
    assert pc._rows(con.cursor(), "select * from no_such_table") == []
    con.close()


def test_the_judge_input_scan_resumes_from_its_offset(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = cursor_paths / "big.json"
    cols._judge_input(path, [f"cand{i:05d}" for i in range(400)])
    monkeypatch.setattr(pc, "_CHUNK", 4096)

    class Once:
        def __init__(self) -> None:
            self.calls = 0

        def expired(self) -> bool:
            self.calls += 1
            return self.calls == 1

    ids, meta = pc._judge_input_ids(path, budget=Once(), resume=True)
    assert meta["status"] == "PARTIAL" and 0 < meta["scanned_bytes"] < meta["bytes"]
    ids, meta = pc._judge_input_ids(path, budget=None, resume=True)
    assert meta["status"] == "MEASURED" and meta["resumed_from_byte"] > 0
    assert len(ids) == 400


def test_main_always_writes_even_when_the_budget_is_spent(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    monkeypatch.setattr(pc, "measure_compute", lambda _d: {
        "available": False, "why": "x", "hours": {}, "window_days": 7.0})
    assert pc.main(["--once", "--budget-s", "0"]) == 0
    doc = json.loads(pc.OUT.read_text(encoding="utf-8"))
    assert doc["partial"] is True and doc["scan"]["scanned"] == 0
    assert doc["last_complete_at"] is None
    assert _row(doc)["funnel"]["raw_cells"] == pc.UNMEASURED


def _fence_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, census: dict[str, Any]) -> dict:
    path = tmp_path / "census.json"
    path.write_text(json.dumps(census), encoding="utf-8")
    monkeypatch.setattr(fence, "CENSUS", path)
    monkeypatch.setattr(fence, "RATCHET", tmp_path / "ratchet.json")
    monkeypatch.setattr(fence, "BLOCKERS", tmp_path / "blockers.json")
    return fence.check(require_state=True, tighten=False)


def test_the_fence_judges_a_partial_census_as_partial(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    base = {"at": now.isoformat(), "partial": True,
            "scan": {"scanned": 5, "total": 14, "unscanned": ["judged"],
                     "cannot_finish_in_budget": []},
            "zero_cell_compute": []}
    ok = _fence_on(tmp_path, monkeypatch,
                   {**base, "last_complete_at": (now - timedelta(hours=3)).isoformat()})
    assert ok["partial"] is True and ok["coverage"]["verdict"] == "PARTIAL"
    assert not ok["failures"]
    bad = _fence_on(tmp_path, monkeypatch, {**base, "last_complete_at": None})
    assert any("PARTIAL" in f and "26" in f for f in bad["failures"])


def test_producer_yield_reads_a_day_old_census_as_stale() -> None:
    now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    fresh = pyf.census_freshness({"at": (now - timedelta(hours=2)).isoformat()}, now)
    stale = pyf.census_freshness({"at": "2026-10-22T17:06:15+00:00"}, now)
    absent = pyf.census_freshness({}, now)
    assert fresh["status"] == "MEASURED"
    assert stale["status"] == "STALE" and stale["age_hours"] > 26
    assert absent["status"] == "UNMEASURED"


def test_a_stale_census_never_moves_the_owing_ratchet(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pyf, "RATCHET", tmp_path / "r.json")
    (tmp_path / "r.json").write_text(json.dumps({"owing_max": 56}), encoding="utf-8")
    doc = {"registry": {"available": True}, "n_owing": 0,
           "census": {"status": "STALE"}, "cells_to_judge_per_hour": None,
           "orthogonal_cells_to_judge_per_hour": None}
    moved = pyf.tighten_ratchet(doc)
    assert moved is None or moved.get("owing_max") == 56


def test_a_cursor_older_than_the_cycle_bound_expires_and_restarts(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    armed = _cut_after(monkeypatch, "cells")
    pc.build(budget_s=600.0)
    doc = json.loads(pc.CURSOR.read_text(encoding="utf-8"))
    doc["cycle_started"] = (datetime.now(UTC) - timedelta(hours=30)).isoformat()
    pc.CURSOR.write_text(json.dumps(doc), encoding="utf-8")
    armed["on"] = False
    census = pc.build(budget_s=600.0)
    scan = census["scan"]
    assert scan["cursor_expired"] and scan["cursor_expired"]["age_hours"] > 26
    assert "sources" in scan["ran_this_pass"]                  # restarted from step one
    assert census["partial"] is False


def test_a_complete_census_publishes_its_cycle_span(
        cursor_paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    armed = _cut_after(monkeypatch, "cells")
    pc.build(budget_s=600.0)
    doc = json.loads(pc.CURSOR.read_text(encoding="utf-8"))
    old = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    for step in doc["steps"].values():
        step["at"] = old
    doc["cycle_started"] = old
    pc.CURSOR.write_text(json.dumps(doc), encoding="utf-8")
    armed["on"] = False
    census = pc.build(budget_s=600.0)
    scan = census["scan"]
    assert 4.9 < scan["cycle_span_h"] < 5.1 and scan["cycle_span_within_bound"] is True
    one = pc.build(budget_s=600.0)                              # a one-pass census
    assert one["scan"]["cycle_span_h"] < 0.1
    partial = pc.build(budget_s=0.0)
    assert partial["partial"] is True and partial["scan"]["cycle_span_h"] is None


def _complete(span: float | None) -> dict[str, Any]:
    scan: dict[str, Any] = {"scanned": 14, "total": 14, "unscanned": []}
    if span is not None:
        scan.update({"cycle_span_h": span, "cycle_max_age_h": 26.0,
                     "cycle_span_within_bound": span <= 26.0})
    return {"at": datetime.now(UTC).isoformat(), "partial": False, "scan": scan,
            "zero_cell_compute": [], "n_producers": 2,
            "measurement_coverage": {"n_producers": 2,
                                     "columns": {"cells": {"coverage": 1.0, "measured": 2}},
                                     "region": {"coverage": 1.0, "regional": 1,
                                                "not_regional": 1, "of": 2}}}


@pytest.mark.parametrize(("span", "tightens"), [(0.0, True), (20.0, True), (30.0, False),
                                                (None, True)])
def test_the_ratchet_tightens_only_within_the_cycle_bound(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, span: float | None,
        tightens: bool) -> None:
    path = tmp_path / "census.json"
    path.write_text(json.dumps(_complete(span)), encoding="utf-8")
    monkeypatch.setattr(fence, "CENSUS", path)
    monkeypatch.setattr(fence, "RATCHET", tmp_path / "ratchet.json")
    monkeypatch.setattr(fence, "BLOCKERS", tmp_path / "blockers.json")
    out = fence.check(require_state=True, tighten=True)
    assert out["ratchet_span_ok"] is tightens
    assert (tmp_path / "ratchet.json").exists() is tightens
