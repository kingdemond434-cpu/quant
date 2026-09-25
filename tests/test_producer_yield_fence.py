"""EVERY PRODUCER OWES CELLS (LAWS 7) -- the properties the fence is only worth having if it has.

Every test builds its own registry and census in `tmp_path`: the fence reads the desk's live
artifacts, and a test that read them too would pass or fail on whatever the last hourly cycle
happened to do, which is not a test of anything.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from scripts import check_producer_yield as fence


def _registry(path: Path, rows: list[dict[str, Any]]) -> None:
    """A registry with just the two columns the attribution join needs."""
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute("create table research_candidates (created_at text, generator text, "
                    "grid_cell text, content_hash text, family text, symbol text, horizon text, "
                    "donated_cell text, status text, discovery_id text)")
        con.execute("create table discoveries (discovery_id text, generator text)")
        for r in rows:
            con.execute("insert into research_candidates values (?,?,?,?,?,?,?,?,?,?)",
                        (r["created_at"], r.get("generator"), r.get("grid_cell"),
                         r.get("content_hash", "h"), r.get("family"), r.get("symbol"),
                         r.get("horizon"), r.get("donated_cell"), r.get("status"),
                         r.get("discovery_id")))
            if r.get("discovery_id") and r.get("discovery_generator"):
                con.execute("insert into discoveries values (?,?)",
                            (r["discovery_id"], r["discovery_generator"]))
        con.commit()
    finally:
        con.close()


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(fence, "CENSUS", tmp_path / "census.json")
    monkeypatch.setattr(fence, "BLOCKERS", tmp_path / "blockers.json")
    monkeypatch.setattr(fence, "RATCHET", tmp_path / "ratchet.json")
    monkeypatch.setattr(fence, "REGISTRY_DB", tmp_path / "reg.sqlite")
    return tmp_path


def _census(desk: Path, rows: list[dict[str, Any]]) -> None:
    (desk / "census.json").write_text(json.dumps({"at": "2026-09-23T00:00:00+00:00",
                                                  "producers": rows}), encoding="utf-8")


def test_a_producer_that_burned_compute_with_no_cell_owes(desk: Path) -> None:
    _census(desk, [{"producer": "barren", "key": "barren", "clock": "hourly_cycle:barren",
                    "compute_hours": 0.4, "compute_hours_ledger": 0.4,
                    "compute_hours_registry": 0.0}])
    _registry(desk / "reg.sqlite", [])
    doc = fence.yield_audit(window_hours=24.0)
    # An empty registry is UNMEASURED, and UNMEASURED never convicts (L1.28a).
    assert doc["n_owing"] == 0, "an unreadable window must not manufacture a defect"

    _registry(desk / "reg.sqlite", [{"created_at": "2999-01-01T00:00:00+00:00",
                                     "generator": "other", "grid_cell": "g", "status": "judged"}])
    doc = fence.yield_audit(window_hours=24.0)
    assert [r["producer"] for r in doc["owing"]] == ["barren"]


def test_a_declaration_clears_the_debt_and_a_thin_one_does_not(desk: Path) -> None:
    _census(desk, [{"producer": "barren", "key": "barren", "compute_hours": 0.4,
                    "compute_hours_ledger": 0.4, "compute_hours_registry": 0.0}])
    _registry(desk / "reg.sqlite", [{"created_at": "2999-01-01T00:00:00+00:00",
                                     "generator": "other", "grid_cell": "g", "status": "judged"}])

    # Too thin to be a declaration: no owner, and a sentence nobody could act on.
    (desk / "blockers.json").write_text(json.dumps({"barren": {"why": "broken"}}),
                                        encoding="utf-8")
    assert fence.yield_audit(window_hours=24.0)["n_owing"] == 1

    (desk / "blockers.json").write_text(json.dumps({"blockers": {"barren": {
        "why": "the conversion gate leaves every discovery UNPROCESSED",
        "owner": "the organ that mints them"}}}), encoding="utf-8")
    doc = fence.yield_audit(window_hours=24.0)
    assert doc["n_owing"] == 0 and doc["n_declared"] == 1
    assert doc["declared"][0]["declared"]["kind"] == "BLOCKER"

    # The exploratory form: it must say WHAT it makes instead and WHO reads it.
    (desk / "blockers.json").write_text(json.dumps({"barren": {
        "exempt": True, "produces": "canonical mechanism rows",
        "consumer": "desks/mt5/research/discovery_compiler.py"}}), encoding="utf-8")
    assert fence.yield_audit(window_hours=24.0)["declared"][0]["declared"]["kind"] == "EXEMPTION"


def test_the_cell_is_credited_to_its_cause_not_to_the_compiler(desk: Path) -> None:
    """The measured 2026-09-17 defect: the compiler stamps its own generator on every cell."""
    _census(desk, [])
    _registry(desk / "reg.sqlite", [{
        "created_at": "2999-01-01T00:00:00+00:00", "generator": "discovery_compiler",
        "grid_cell": "g1", "family": "carry", "symbol": "eurusd", "horizon": "4h",
        "status": "judged", "discovery_id": "d1", "discovery_generator": "japan:gotobi"}])
    doc = fence.yield_audit(window_hours=24.0)
    by = {r["producer"]: r for r in doc["producers"]}
    assert by["japan:gotobi"]["cells_to_judge_per_hour"] > 0
    assert "discovery_compiler" not in by


def test_a_hundred_copies_of_one_rule_are_one_cell_of_breadth(desk: Path) -> None:
    """The orthogonality column, which is the number the desk optimises."""
    same = {f"p{i}": ["carry|eurusd|4h"] for i in range(5)}
    got = fence._breadth(same)
    if not got.get("available"):  # pragma: no cover - numpy-absent host
        pytest.skip(str(got.get("why")))
    assert got["total"] == pytest.approx(1.0, abs=1e-6)
    assert all(v == 0.0 for v in got["marginal"].values()), "a copy adds no breadth"

    spread = {f"p{i}": [f"f{i}|s{i}|4h"] for i in range(5)}
    assert fence._breadth(spread)["total"] == pytest.approx(5.0, abs=1e-6)


def test_the_ratchet_falls_only(desk: Path) -> None:
    (desk / "ratchet.json").write_text(json.dumps({
        "owing_max": 3, "cells_to_judge_per_hour_best": 100.0,
        "orthogonal_cells_to_judge_per_hour_best": 10.0}), encoding="utf-8")
    base = {"registry": {"available": True}, "n_owing": 5,
            "cells_to_judge_per_hour": 50.0, "orthogonal_cells_to_judge_per_hour": 4.0}
    assert fence.tighten_ratchet(base) is None, "a worse reading may never loosen the ratchet"

    better = dict(base, n_owing=1, cells_to_judge_per_hour=120.0,
                  orthogonal_cells_to_judge_per_hour=11.0)
    moved = fence.tighten_ratchet(better)
    assert moved is not None
    assert moved["owing_max"] == 1
    assert moved["cells_to_judge_per_hour_best"] == 120.0
    assert moved["orthogonal_cells_to_judge_per_hour_best"] == 11.0


def test_a_rising_owing_count_and_a_collapsed_throughput_both_fail(desk: Path) -> None:
    _census(desk, [{"producer": "barren", "key": "barren", "compute_hours": 0.4,
                    "compute_hours_ledger": 0.4, "compute_hours_registry": 0.0}])
    _registry(desk / "reg.sqlite", [{"created_at": "2999-01-01T00:00:00+00:00",
                                     "generator": "live", "grid_cell": "g", "family": "carry",
                                     "symbol": "eurusd", "horizon": "4h", "status": "judged"}])
    (desk / "ratchet.json").write_text(json.dumps({
        "owing_max": 0, "cells_to_judge_per_hour_best": 1000.0}), encoding="utf-8")
    doc = fence.yield_audit(window_hours=24.0)
    assert len(doc["failures"]) == 2, doc["failures"]
    assert "owe cells against a ratchet" in doc["failures"][0]
    assert "no stated reason" in doc["failures"][1]

    # A stated reason is the release valve, and it is a SENTENCE, not a silent rebase.
    (desk / "ratchet.json").write_text(json.dumps({
        "owing_max": 0, "cells_to_judge_per_hour_best": 1000.0,
        "regression_reason": "the universe rebuild is rewriting every parquet"}), encoding="utf-8")
    assert len(fence.yield_audit(window_hours=24.0)["failures"]) == 1
