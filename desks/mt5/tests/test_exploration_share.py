"""The measured exploration share (N9 item 5): read off the judge's published allocation, set
beside the declared constants, UNMEASURED whenever the reading is not about this hour.

Every allocation is planted; every path is redirected into `tmp_path`. The declared constants are
the desk's real ones, read from source.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import exploration_share as es  # noqa: E402

NOW = datetime(2026, 11, 10, 20, 0, tzinfo=UTC)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(es, "ALLOCATION", tmp_path / "reports" / "RESEARCH_ALLOCATION.json")
    monkeypatch.setattr(es, "REPORT", tmp_path / "reports" / "EXPLORATION_SHARE.json")
    monkeypatch.setattr(es, "HISTORY", tmp_path / "data" / "exploration_share_history.jsonl")
    return tmp_path


def _alloc(*, built: int = 1000, axes: int = 0, ortho: int = 0, strength: float = 1.0,
           fams: dict[str, dict[str, Any]] | None = None, at: datetime = NOW) -> dict[str, Any]:
    return {"generated_utc": at.isoformat(), "strength": strength, "docket_total": 5000,
            "built_this_sweep": built,
            "by_family": fams if fams is not None else {"a": {"share_of_budget": 1.0,
                                                              "built_this_sweep": built}},
            "exploration": {"n_cells_added": axes,
                            "orthogonality_floor": {"added_by_floor": ortho}}}


def _plant(root: Path, doc: dict[str, Any]) -> None:
    path = root / "reports" / "RESEARCH_ALLOCATION.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), "utf-8")


def test_every_declared_constant_is_read_from_source() -> None:
    floors = es.declared()
    assert len(floors) == len(es.DECLARED)
    assert all(v["state"] == "READ" and 0 < v["value"] < 1 for v in floors.values())


def test_a_constant_that_is_not_a_literal_is_unreadable(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text("import os\nX = float(os.environ.get('X', '0.2'))\nY: float = 0.3\n")
    assert es.declared_constant(src, "X") is None
    assert es.declared_constant(src, "Y") == 0.3
    assert es.declared_constant(tmp_path / "absent.py", "Y") is None


def test_appended_cells_are_the_strict_share() -> None:
    m = es.measure(_alloc(built=1000, axes=80, ortho=20))
    assert m["appended_share"] == 0.1 and m["uniform_share"] == 0.0
    assert m["exploration_share"] == 0.1


def test_the_uniform_blend_counts_only_where_a_share_set_the_count() -> None:
    fams = {"a": {"share_of_budget": 0.5, "built_this_sweep": 400},
            "b": {"share_of_budget": 0.5, "built_this_sweep": 400},
            "c": {"share_of_budget": 0.5, "built_this_sweep": 200, "held_by_floor": True}}
    m = es.measure(_alloc(built=1000, strength=0.7, fams=fams))
    # uniform part of each share = 0.3 / 3 = 0.1 of 0.5 -> 20% of a's and b's builds.
    assert m["uniform_blend_cells"] == 160.0
    assert m["uniform_share"] == 0.16


def test_absent_allocation_is_unmeasured_not_zero(desk: Path) -> None:
    rep = es.build(NOW)
    assert rep["verdict"] == "UNMEASURED" and rep["state"] == "ABSENT"
    assert rep["exploration_share"] is None


def test_a_stale_allocation_is_unmeasured_and_keeps_its_reading(desk: Path) -> None:
    _plant(desk, _alloc(axes=300, at=NOW - timedelta(hours=5)))
    rep = es.build(NOW)
    assert rep["verdict"] == "UNMEASURED" and rep["state"] == "STALE"
    assert rep["exploration_share"] is None and rep["measured"]["appended_share"] == 0.3


def test_a_thin_docket_is_below_every_declared_floor(desk: Path) -> None:
    _plant(desk, _alloc(axes=10))
    rep = es.build(NOW)
    assert rep["verdict"] == "BELOW_EVERY_DECLARED_FLOOR"
    assert set(rep["below"]) == set(rep["declared"])


def test_a_middling_share_names_the_floors_it_misses(desk: Path) -> None:
    _plant(desk, _alloc(axes=220))
    rep = es.build(NOW)
    assert rep["verdict"] == "BELOW_SOME_DECLARED_FLOORS"
    assert "search_controller" in rep["below"] and "source_roi" not in rep["below"]


def test_a_rich_share_is_a_fact_never_a_licence(desk: Path) -> None:
    _plant(desk, _alloc(axes=400))
    rep = es.build(NOW)
    assert rep["verdict"] == "AT_OR_ABOVE_EVERY_DECLARED_FLOOR" and rep["below"] == []
    assert "ever recommends exploring less" in rep["rule"]


def test_each_pass_appends_one_history_row(desk: Path) -> None:
    _plant(desk, _alloc(axes=100))
    es.write(es.build(NOW))
    es.write(es.build(NOW))
    rows = (desk / "data" / "exploration_share_history.jsonl").read_text().splitlines()
    assert len(rows) == 2 and json.loads(rows[-1])["exploration_share"] == 0.1


def test_the_leg_is_wired_into_the_hourly_cycle_and_a_layer() -> None:
    import hourly_cycle

    from libs.research import layers

    assert "exploration_share" in hourly_cycle.CORE_LEGS
    assert layers.LEG_LAYER["exploration_share"] == "meta"
