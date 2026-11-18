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
    monkeypatch.setattr(ly, "LAB_REPORTS", {n: tmp_path / f"{n}.absent" for n in ly.LAB_REPORTS})
    monkeypatch.setattr(ly, "LEG_CONTRACT", tmp_path / "WRITE_OR_EXPLAIN.absent")
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


def _lab_report(path: Path, at: datetime, **donation: Any) -> None:
    path.write_text(json.dumps({"at": at.isoformat(), "dry_run": False,
                                "donation": donation}), "utf-8")


def test_a_lab_that_ran_and_gave_nothing_is_red_with_its_reason(
        paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reports = {n: paths / f"{n}.json" for n in ("mathlab", "physics_lab", "world_lab")}
    monkeypatch.setattr(ly, "LAB_REPORTS", reports)
    _lab_report(reports["mathlab"], NOW - timedelta(hours=1), donated=0, status="NOTHING_NEW",
                already_donated_in_a_previous_pass=132, refused_untradeable=0)
    _lab_report(reports["physics_lab"], NOW - timedelta(hours=30), donated=5)
    _lab_report(reports["world_lab"], NOW - timedelta(hours=1), donated=3,
                by_tradition={"causal": 3})
    doc = ly.run(now=NOW)
    got = {(v["check"], v["generator"]) for v in doc["violations"]}
    assert got == {("lab_gave_nothing", "mathlab"), ("lab_clock_stale", "physics_lab")}
    assert "NOTHING_NEW" in next(v["why"] for v in doc["violations"]
                                 if v["generator"] == "mathlab")
    assert doc["labs"]["world_lab"]["partial"] is False


def test_a_checkpointed_lab_report_says_it_is_partial(
        paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = paths / "mathlab.json"
    monkeypatch.setattr(ly, "LAB_REPORTS", {"mathlab": report})
    report.write_text(json.dumps({"at": (NOW - timedelta(hours=1)).isoformat(), "partial": True,
                                  "phase": "donated", "dry_run": False,
                                  "donation": {"donated": 4, "status": "DONATED"}}), "utf-8")
    row = ly.labs(NOW)["mathlab"]
    assert (row["partial"], row["phase"], row["donated"]) == (True, "donated", 4)


def test_producer_fence_flags_a_dead_replacement() -> None:
    import importlib
    fence = importlib.import_module("scripts.check_producer_yield")
    assert fence.replacement_target("mathlab -- the lab") == "mathlab"
    assert fence.replacement_target("NONE DECLARED -- x") == ""
    for name in ("lab_probability", "lab_timeseries", "lab_crossasset", "lab_microstructure",
                 "mathlab", "physics_lab"):
        target = fence.replacement_target(fence.REPLACEMENTS[name])
        assert target not in {"mathlab", "physics_lab", "lab_crossasset", "lab_timeseries",
                              "lab_probability", "lab_microstructure"}, name


def test_a_leg_that_times_out_every_pass_is_red(paths: Path, monkeypatch: pytest.MonkeyPatch,
                                                ) -> None:
    from libs.ops import write_or_explain as woe
    at = [(datetime.now(UTC) - timedelta(hours=3 - i)).isoformat() for i in range(4)]
    rows = [{"leg": "math_lab", "verdict": woe.LEG_TIMEOUT, "wrote": [], "at": at[i]}
            for i in range(3)]
    rows.insert(1, {"leg": "other", "verdict": woe.OK, "wrote": ["x"], "at": at[0]})
    chronic = woe.chronic_timeouts(rows)
    assert [c["leg"] for c in chronic] == ["math_lab"]
    assert woe.chronic_timeouts(rows[:-1]) == []           # two in a row is not chronic yet
    assert woe.chronic_timeouts([*rows, {"leg": "math_lab", "verdict": woe.OK,
                                         "wrote": ["r"], "at": at[3]}]) == []
    # SF1: a checkpointed (partial) write does not acquit a leg killed at its cap every pass.
    partial = [dict(r, wrote=["MATH_LAB.json"]) if r["leg"] == "math_lab" else r for r in rows]
    got = woe.chronic_timeouts(partial)
    assert [c["leg"] for c in got] == ["math_lab"]
    assert got[0]["passes_that_moved_a_partial_artifact"] == 3
    # SF2: a crash between two kills neither extends nor breaks the streak ...
    crash = {"leg": "math_lab", "verdict": woe.LEG_FAILED, "wrote": [], "at": at[3]}
    assert [c["leg"] for c in woe.chronic_timeouts([*rows[:2], crash, *rows[2:]])] == [
        "math_lab"]
    # ... and a streak older than the window is history, not the leg's state now.
    old = [dict(r, at=(datetime.now(UTC) - timedelta(hours=48)).isoformat()) for r in rows]
    assert woe.chronic_timeouts(old) == []
    assert woe.chronic_timeouts([dict(r, at="t") for r in rows]) == []
    contract = paths / "woe.json"
    stranger = {"leg": "bars_state", "detail": "not a producer"}
    contract.write_text(json.dumps({"chronic_timeouts": [*chronic, stranger]}), "utf-8")
    monkeypatch.setattr(ly, "LEG_CONTRACT", contract)
    found = {(v["check"], v["generator"]) for v in ly.run(now=NOW)["violations"]}
    assert ("chronic_timeout", "math_lab") in found
    assert ("chronic_timeout", "bars_state") not in found   # SF3: only producers are ours
