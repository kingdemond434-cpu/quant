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
