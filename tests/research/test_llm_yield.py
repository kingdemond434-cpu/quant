"""LLM_YIELD: silent success and dead replacements go RED; the budget follows conversion."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from desks.mt5.research import llm_yield as ly

from libs.research import free_panel

NOW = datetime(2026, 10, 29, 16, 0, tzinfo=UTC)


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ly, "REPO", tmp_path)
    monkeypatch.setattr(ly, "SPEND", tmp_path / "data" / "llm_spend.jsonl")
    monkeypatch.setattr(ly, "PANEL", tmp_path / "data" / "free_panel_state.json")
    monkeypatch.setattr(ly, "LAB_ATTRIBUTION", tmp_path / "data" / "lab" / "attribution.json")
    monkeypatch.setattr(ly, "SEAT_QUEUES", tmp_path / "seats")
    monkeypatch.setattr(ly, "INTEL_ROOTS", (tmp_path / "intel",))
    monkeypatch.setattr(ly, "PRODUCER_YIELD", tmp_path / "PRODUCER_YIELD.json")
    monkeypatch.setattr(ly, "MINER_CANDIDATES", tmp_path / "miner_candidates.json")
    monkeypatch.setattr(ly, "REGISTRY", tmp_path / "absent.sqlite")
    monkeypatch.setattr(ly, "CERT_PROVENANCE", tmp_path / "cp.json")
    (tmp_path / "data").mkdir()
    return tmp_path


def _spend(root: Path, rows: list[dict[str, Any]]) -> None:
    (root / "data" / "llm_spend.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def _row(minutes_ago: int, model: str = "m/a:free", empty: bool = False) -> dict[str, Any]:
    return {"utc": (NOW - timedelta(minutes=minutes_ago)).isoformat(), "organ": "deepseek",
            "model": model, "tokens": 10, "empty_content": empty}


def test_absent_sources_are_unmeasured_not_clean(paths: Path) -> None:
    doc = ly.run(now=NOW)
    assert doc["calls"]["status"] == ly.UNMEASURED
    assert doc["lab"]["status"] == ly.UNMEASURED
    assert doc["generators"]["status"] == ly.UNMEASURED
    assert doc["generators"]["math_traditions"] == ly.UNMEASURED


def test_three_empty_replies_in_a_row_is_red(paths: Path) -> None:
    _spend(paths, [_row(50), _row(40, empty=True), _row(30, empty=True), _row(20, empty=True)])
    doc = ly.run(now=NOW)
    assert doc["red"]
    (v,) = doc["violations"]
    assert v["check"] == "silent_success" and v["model"] == "m/a:free"
    assert doc["priority"]["weights"]["m/a:free"] == ly.SILENT_WEIGHT


def test_two_empty_then_output_is_not_red(paths: Path) -> None:
    _spend(paths, [_row(40, empty=True), _row(30, empty=True), _row(20)])
    doc = ly.run(now=NOW)
    assert not doc["red"]
    (r,) = doc["calls"]["rows"]
    assert (r["ok"], r["empty"], r["empty_streak"]) == (1, 2, 0)


def test_dead_producer_with_dead_replacement_is_red(paths: Path) -> None:
    (paths / "PRODUCER_YIELD.json").write_text(json.dumps({"producers": [
        {"producer": "lab_probability", "verdict": "DEAD", "replacement": "mathlab -- the lab"},
        {"producer": "mathlab", "verdict": "DEAD", "replacement": "NONE"},
        {"producer": "fxmerge", "verdict": "DEAD", "replacement": "fxblue -- live"},
        {"producer": "fxblue", "verdict": "PRODUCING"},
    ]}), "utf-8")
    doc = ly.run(now=NOW)
    bad = [(v["generator"], v["replacement"]) for v in doc["violations"]]
    assert bad == [("lab_probability", "mathlab")]


def test_lab_roi_weights_the_free_panel(paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ly.LAB_ATTRIBUTION.parent.mkdir(parents=True)
    ly.LAB_ATTRIBUTION.write_text(json.dumps({"by_model": {
        "good:free": {"calls": 10, "compiled": 5, "passed": 1},
        "few:free": {"calls": 2, "compiled": 2, "passed": 0},
    }}), "utf-8")
    doc = ly.run(now=NOW)
    rows = {r["model"]: r for r in doc["lab"]["rows"]}
    assert rows["good:free"]["roi_per_call"] == pytest.approx(1.0)
    w = doc["priority"]["weights"]
    assert w["good:free"] == pytest.approx(11.0)
    assert "few:free" not in w                      # too few calls to weigh

    prio = paths / "prio.json"
    prio.write_text(json.dumps({"weights": {**w, "dead:free": 0.0}}), "utf-8")
    monkeypatch.setattr(free_panel, "PRIORITY", prio)
    monkeypatch.setattr(free_panel, "_state", lambda: {"calls": {
        "good:free": 50, "plain:free": 10, "dead:free": 0}})
    assert free_panel.available(("plain:free", "good:free", "dead:free")) == [
        "good:free", "plain:free"]


def test_free_panel_order_unchanged_without_priority_file(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(free_panel, "PRIORITY", tmp_path / "absent.json")
    monkeypatch.setattr(free_panel, "_state", lambda: {"calls": {"a": 3, "b": 1}})
    assert free_panel.available(("a", "b")) == ["b", "a"]


def test_all_zero_weights_never_darken_the_panel(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prio = tmp_path / "p.json"
    prio.write_text(json.dumps({"weights": {"a": 0, "b": 0}}), "utf-8")
    monkeypatch.setattr(free_panel, "PRIORITY", prio)
    monkeypatch.setattr(free_panel, "_state", lambda: {"calls": {"a": 3, "b": 1}})
    assert free_panel.available(("a", "b")) == ["b", "a"]


def test_main_writes_report_and_priority(paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ly, "REPORT", paths / "LLM_YIELD.json")
    monkeypatch.setattr(ly, "PRIORITY", paths / "llm_model_priority.json")
    _spend(paths, [_row(30, empty=True), _row(20, empty=True), _row(10, empty=True)])
    assert ly.main([]) == 1
    assert json.loads((paths / "LLM_YIELD.json").read_text())["red"] is True
    assert "weights" in json.loads((paths / "llm_model_priority.json").read_text())


def test_leg_is_wired_and_layered() -> None:
    from libs.research import layers
    src = (Path(ly.__file__).parent / "hourly_cycle.py").read_text("utf-8")
    assert '_producer("llm_yield", "research/llm_yield.py")' in src
    assert '"research/llm_budget_census.py"' in src
    assert layers.LEG_LAYER["llm_yield"] == "meta"
