"""A replay that writes into its tree is UNMEASURED (Audit, 2026-11-18, follow-up to #1353).

replay_child reports `tree_writes`: every file under the tree's data/ and logs/ roots that a
scenario wrote. Another scenario, or the other tree, may then read it, so that scenario's
agreement is not evidence. compare() counts each such scenario and side, reports it as an
UNMEASURED problem (never a PASS), and still compares its steps."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow_tw", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs: Any = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)


def _compare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writes: dict[str, list[str]],
    decide: dict[str, str] | None = None,
) -> dict[str, Any]:
    base, head = tmp_path / "base", tmp_path / "head"
    base.mkdir()
    head.mkdir()

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        doc = {"status": (decide or {}).get(tree.name, "OK")}
        step = {"hour": 7.0, "doc": doc, "intents": [{"a": 1}], "error": None, "ftmo": {}}
        return {"steps": [step], "imported": [], "tree_writes": writes.get(tree.name, [])}

    monkeypatch.setattr(rs, "run_tree", fake)
    monkeypatch.delenv(rs.DECLARED_ENV, raising=False)
    return rs.compare(base, head, [], [{"id": "s", "hours": [7.0]}])


def test_a_clean_replay_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rep = _compare(tmp_path, monkeypatch, {})
    assert rep["verdict"] == "PASS", rep["problems"]
    assert rep["tree_writes"] == []


@pytest.mark.parametrize("side", ["base", "head"])
def test_a_write_into_either_tree_is_unmeasured_counted_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str
) -> None:
    rep = _compare(tmp_path, monkeypatch, {side: ["desks/mt5/data/E8_GOLD_SLIP.json"]})
    assert rep["verdict"] == "FAIL"
    assert rep["tree_writes"] == [f"s:{side}"]
    assert any(p.startswith(f"UNMEASURED s: the {side} replay wrote into its tree")
               and "E8_GOLD_SLIP.json" in p for p in rep["problems"])  # fmt: skip


def test_a_leaking_scenario_is_still_compared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rep = _compare(tmp_path, monkeypatch, {"head": ["data/x.json"]}, {"head": "STOOD_DOWN"})
    assert rep["intents_compared"] == 1
    assert any("decides differently" in p for p in rep["problems"])


def test_an_older_child_with_no_tree_writes_field_reads_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}
        return {"steps": [step], "imported": []}

    (tmp_path / "b").mkdir()
    (tmp_path / "h").mkdir()
    monkeypatch.setattr(rs, "run_tree", fake)
    rep = rs.compare(tmp_path / "b", tmp_path / "h", [], [{"id": "s", "hours": [7.0]}])
    assert rep["tree_writes"] == [] and rep["verdict"] == "PASS", rep["problems"]
