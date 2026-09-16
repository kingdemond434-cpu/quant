"""The breadth ladder: rungs, the measured slope, the exploration floor and the budget factors."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if p not in sys.path:
        sys.path.insert(0, p)

import breadth_ladder as bl  # noqa: E402


def _point(monkeypatch, tmp_path: Path) -> None:
    for name in ("HISTORY", "LATEST", "LEDGER", "AXIS", "OUT"):
        monkeypatch.setattr(bl, name, tmp_path / f"{name}.json")


def _history(tmp_path: Path, values: list[float], hours_apart: float = 1.0) -> None:
    t0 = datetime(2026, 9, 16, 0, 0, tzinfo=UTC)
    rows = [{"at": (t0 + timedelta(hours=i * hours_apart)).isoformat(), "effective_breadth": v,
             "n_clusters_occupied": 8, "n_clusters_empty": 7} for i, v in enumerate(values)]
    (tmp_path / "HISTORY.json").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    ledger = [{"at": (t0 + timedelta(hours=i * hours_apart, minutes=10)).isoformat(),
               "run": "deepen" if i % 2 else "breadth_sweep", "wall_s": 1800}
              for i in range(len(values))]
    (tmp_path / "LEDGER.json").write_text("\n".join(json.dumps(r) for r in ledger),
                                          encoding="utf-8")


def test_rungs():
    assert bl.rung_of(2.0) == (None, 6)
    assert bl.rung_of(6.0) == (6, 10)
    assert bl.rung_of(17.5) == (15, 25)
    assert bl.rung_of(41.0) == (40, None)


def test_unmeasured_when_nothing_exists(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    doc = bl.build()
    assert doc["status"] == "UNMEASURED" and doc["slope"]["status"] == "UNMEASURED"
    assert doc["factors"] == {"exploration": 1.0, "exploitation": 1.0,
                              "why": "slope UNMEASURED: no reallocation"}
    assert bl.budget_factor("deepen", doc) == 1.0 and bl.budget_factor("health", doc) == 1.0
    assert doc["exploration_floor"]["floor"] == bl.FLOOR_BOUNDS[0]


def test_stalled_ladder_moves_budget_to_exploration(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    _history(tmp_path, [2.1, 2.0, 2.05, 2.0])
    doc = bl.build()
    assert doc["slope"]["status"] == "MEASURED" and doc["slope"]["per_hour"] <= 0
    assert bl.budget_factor("breadth_sweep", doc) > 1.0 > bl.budget_factor("deepen", doc)
    assert bl.FACTOR_CLIP[0] <= bl.budget_factor("deepen", doc)
    assert doc["exploration_floor"]["basis"].startswith("effective_breadth.jsonl")
    assert abs(doc["exploration_floor"]["raw"] - 7 / 15) < 1e-3


def test_rising_ladder_pays_exploitation_and_keeps_the_floor(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    _history(tmp_path, [4.0, 5.0, 6.5, 8.0])
    doc = bl.build()
    assert doc["rung_reached"] == 6 and doc["next_target"] == 10
    assert bl.budget_factor("deepen", doc) > 1.0 and bl.budget_factor("breadth_sweep", doc) == 1.0
    assert bl.budget_factor("deepen", doc) <= bl.FACTOR_CLIP[1]


def test_axis_registry_sets_the_floor_and_the_report_is_written(monkeypatch, tmp_path):
    _point(monkeypatch, tmp_path)
    _history(tmp_path, [4.0, 5.0, 6.5])
    (tmp_path / "AXIS.json").write_text(json.dumps({"by_state": {"UNMEASURED": 70, "CERTIFIED": 20,
                                                                 "LIVE": 10}}), encoding="utf-8")
    doc = bl.build()
    assert doc["exploration_floor"]["floor"] == bl.FLOOR_BOUNDS[1]   # 0.7 raw, bounded to 0.6
    assert bl.main([]) == 0 and (tmp_path / "OUT.json").exists()
