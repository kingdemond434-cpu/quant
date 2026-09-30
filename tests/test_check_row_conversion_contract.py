"""The mined-row gate measures real AlphaCells, not disposition labels or row volume."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from scripts import check_row_conversion as gate


def _desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> Path:
    desk = tmp_path / "desks" / "mt5"
    seat = desk / "data" / "intelligence" / "source_a"
    seat.mkdir(parents=True)
    (seat / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    universe = desk / "data" / "universe"
    universe.mkdir(parents=True)
    (universe / "universe.json").write_text(json.dumps(["EURUSD"]), encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "DESK", desk)
    monkeypatch.setattr(gate, "COMPILER_REPORT", desk / "data" / "hypotheses" / "missing.json")
    return desk


def _compiler(monkeypatch: pytest.MonkeyPatch, fn: object) -> None:
    research = types.ModuleType("research")
    compiler = types.ModuleType("research.miner_candidate_compiler")
    compiler.compile_row = fn  # type: ignore[attr-defined]
    research.miner_candidate_compiler = compiler  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "research", research)
    monkeypatch.setitem(sys.modules, "research.miner_candidate_compiler", compiler)


def _cell() -> dict:
    return {"symbol": "EURUSD", "family": "trend", "params": {},
            "mechanism_status": "NAMED",
            "mechanism_note": "forced participant flow persists across the stated horizon"}


def test_every_convertible_row_with_a_real_cell_is_full_conversion(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _desk(tmp_path, monkeypatch, [{"producer": "p", "text": "a"},
                                  {"producer": "p", "text": "b"}])
    _compiler(monkeypatch, lambda source, row, universe: ([_cell()], "TEXT_EXTRACTED"))

    doc = gate.audit()

    assert doc["summary"]["convertible_conversion_rate"] == 1.0
    assert doc["summary"]["silent_loss"] == 0
    assert doc["summary"]["conversion_debt"] == 0
    assert doc["failures"] == []
    assert doc["per_producer"][0]["converted_rows"] == 2


def test_a_disposition_label_cannot_hide_a_malformed_candidate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _desk(tmp_path, monkeypatch, [{"producer": "p", "text": "a"}])
    _compiler(monkeypatch, lambda source, row, universe: (
        [{"symbol": "EURUSD", "family": "trend"}], "TEXT_EXTRACTED"))

    doc = gate.audit()

    assert doc["n_invalid_candidates"] == 1
    assert doc["summary"]["convertible_conversion_rate"] == 0.0
    assert doc["summary"]["silent_loss"] == 1
    assert any("not valid AlphaCells" in failure for failure in doc["failures"])


def test_backlog_is_not_yield_but_non_evidence_is_an_honest_refusal(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _desk(tmp_path, monkeypatch, [{"producer": "p", "kind": "claim"},
                                  {"producer": "p", "kind": "fetch_error"}])

    def compile_row(source: str, row: dict, universe: set[str]) -> tuple[list[dict], str]:
        if row["kind"] == "fetch_error":
            return [], "OPERATIONAL_ROW"
        return [], "NEEDS_EXACT_RULE_EXTRACTION"

    _compiler(monkeypatch, compile_row)
    doc = gate.audit()

    assert doc["summary"]["convertible_rows"] == 1
    assert doc["summary"]["converted_rows"] == 0
    assert doc["summary"]["terminal_refusals"] == 1
    assert doc["per_producer"][0]["valid_refusals"] == 1
    assert doc["failures"]


def test_canonical_compiler_contract_is_consumed_without_recompiling_corpus(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = _desk(tmp_path, monkeypatch, [])
    report = desk / "data" / "hypotheses" / "miner_candidates.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        "compiled_at": "2026-09-28T00:00:00+00:00", "rows_accounted": 4,
        "executable_candidates": 2,
        "intake": {"files_seen": 3, "bound_hit": False, "deferred_files": 0},
        "per_source": {"p": {"rows": 4, "candidates": 2, "deepening": 1,
                                     "convertible_rows": 3, "converted_rows": 2,
                                     "valid_refusals": 1, "invalid_cells": 0,
                                     "owes_convertible_rows": 1,
                                     "convertible_conversion_rate": 0.666667}},
        "conversion_contract": {"convertible_rows": 3, "converted_rows": 2,
                                "convertible_conversion_rate": 0.666667,
                                "silent_loss": 1, "invalid_cells": 0,
                                "complete": False},
    }), encoding="utf-8")
    monkeypatch.setattr(gate, "COMPILER_REPORT", report)

    doc = gate.audit()

    assert doc["summary"]["silent_loss"] == 1
    assert doc["per_producer"][0]["owes_convertible_rows"] == 1
    assert any("emitted no valid" in failure for failure in doc["failures"])
