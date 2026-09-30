"""THE GRID FILLS, AND ONLY AN EXHAUSTED LIST MAY STOP IT.

These pin the fence that would have caught `8 empty cells aimed at, 8 cells created` against
8,418 reachable empties -- a pass that ended on a clock while the ground was still there, and
reported it as a success because nothing asked WHY it stopped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grid_occupancy as fence  # noqa: E402


def _artifact(**fill: Any) -> dict[str, Any]:
    base = {"available": True, "occupied_cells_after": 1000, "occupancy_after": 0.5,
            "stopped_because": "list exhausted", "cells_created_in_empty_cells": 400,
            "frontier_cells_created": 40, "seconds_per_cell": 0.001, "targets_available": 400}
    base.update(fill)
    return {"generated_utc": "2026-09-23T22:00:00+00:00",
            "grid": {"available": True, "occupied_cells": 1000, "nominal_cells": 60345,
                     "occupancy": 0.5, "reachable_empty_cells": 0},
            "fill": base}


def _wire(monkeypatch: Any, tmp_path: Path, doc: dict[str, Any] | None,
          ratchet: dict[str, Any] | None) -> None:
    rep, rat = tmp_path / "INDEPENDENCE_INTAKE.json", tmp_path / "ratchet.json"
    if doc is not None:
        rep.write_text(json.dumps(doc), encoding="utf-8")
    if ratchet is not None:
        rat.write_text(json.dumps(ratchet), encoding="utf-8")
    monkeypatch.setattr(fence, "REPORT", rep)
    monkeypatch.setattr(fence, "RATCHET", rat)


def test_a_pass_that_ran_out_of_ground_passes(monkeypatch: Any, tmp_path: Path) -> None:
    _wire(monkeypatch, tmp_path, _artifact(), {"occupied_cells_best": 900})
    doc = fence.audit()
    assert doc["verdict"] == "MEASURED" and not doc["failures"]


def test_a_pass_that_ran_out_of_clock_fails_with_what_it_stopped_at(
        monkeypatch: Any, tmp_path: Path) -> None:
    _wire(monkeypatch, tmp_path,
          _artifact(stopped_because="time budget 75s reached after 8 cells",
                    cells_created_in_empty_cells=8, seconds_per_cell=0.927,
                    targets_available=8418),
          {"occupied_cells_best": 900})
    doc = fence.audit()
    assert doc["verdict"] == "FAIL"
    joined = " ".join(doc["failures"])
    assert "time budget 75s" in joined and "8418 targets in hand" in joined
    assert "0.927s per cell" in joined
    # and it names the remedy, which is never to raise the budget or lower the aim
    assert "rather than raising the budget or lowering the aim" in joined


def test_occupancy_may_not_fall_below_its_best_without_a_stated_reason(
        monkeypatch: Any, tmp_path: Path) -> None:
    _wire(monkeypatch, tmp_path, _artifact(occupied_cells_after=500),
          {"occupied_cells_best": 1000})
    assert fence.audit()["verdict"] == "FAIL"
    # a stated reason is what the ratchet asks for -- the fall is then a recorded decision
    _wire(monkeypatch, tmp_path, _artifact(occupied_cells_after=500),
          {"occupied_cells_best": 1000, "regression_reason": "axis registry dropped 3 horizons"})
    assert fence.audit()["verdict"] == "MEASURED"


def test_a_missing_artifact_is_unmeasured_and_never_a_clean_pass(
        monkeypatch: Any, tmp_path: Path) -> None:
    _wire(monkeypatch, tmp_path, None, None)
    doc = fence.audit()
    assert doc["verdict"] == "UNMEASURED" and not doc["failures"]
    assert "L1.28a" in str(doc["why"])


def test_a_fill_with_no_stop_reason_is_unmeasured_not_assumed_finished(
        monkeypatch: Any, tmp_path: Path) -> None:
    art = _artifact()
    art["fill"].pop("stopped_because")
    _wire(monkeypatch, tmp_path, art, {"occupied_cells_best": 900})
    doc = fence.audit()
    assert str(doc["filler_reach"]["verdict"]).startswith("UNMEASURED")
    assert not doc["failures"]


def test_the_organs_own_bound_is_read_from_source_and_must_sit_above_the_grid() -> None:
    """The constant is read from the organ's AST, so a bound cannot be monkeypatched into
    passing and the fence still works on a host that cannot import the desk."""
    assert fence._const("MAX_FILLS_PER_PASS") is not None
    ok = fence.bounds_cannot_bind(60_345)
    assert ok["verdict"] == "MEASURED" and not ok["failures"]
    assert ok["max_fills_per_pass"] >= 60_345


def test_a_bound_below_the_grid_is_reported_as_a_throttle(monkeypatch: Any) -> None:
    monkeypatch.setattr(fence, "_const", lambda _name: 400)
    out = fence.bounds_cannot_bind(60_345)
    assert out["verdict"] == "FAIL"
    assert "throttle on breadth" in " ".join(out["failures"])


def test_the_fence_exits_nonzero_only_on_a_real_failure(
        monkeypatch: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _wire(monkeypatch, tmp_path, _artifact(), {"occupied_cells_best": 900})
    assert fence.main([]) == 0
    _wire(monkeypatch, tmp_path, _artifact(stopped_because="time budget 75s reached after 8 cells"),
          {"occupied_cells_best": 900})
    assert fence.main([]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_the_fence_rides_the_law_gate_battery() -> None:
    src = (_ROOT / "scripts" / "run_law_gate.py").read_text(encoding="utf-8")
    assert '("check_grid_occupancy.py", ())' in src
