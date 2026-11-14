"""Every instrument with a spread column gets a surface, whatever the proposal grid's budget.

Measured 2026-10-29: the surface was written inside the alphabetical grid loop, so instruments
past the budget (NOK*, NZD*, SGD*) had none and 2,989 execution_state builds failed by name.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research import microstructure_miner as mm  # noqa: E402

SYMS = ["AUDCAD", "EURUSD", "NOKSEK", "NZDSGD", "SGDJPY"]


def _bars(_sym):
    idx = pd.date_range("2024-01-01", periods=24 * 260, freq="h")
    rng = np.random.default_rng(0)
    return pd.DataFrame({"close": 1 + rng.normal(0, 1e-3, len(idx)).cumsum(),
                         "spread": rng.integers(1, 9, len(idx))}, index=idx)


@pytest.fixture
def miner(tmp_path, monkeypatch):
    uni = tmp_path / "uni"
    uni.mkdir()
    for s in SYMS:
        (uni / f"{s}_H1.parquet").write_bytes(b"")
    grid: list[str] = []
    monkeypatch.setattr(mm.pc, "UNI", uni)
    monkeypatch.setattr(mm.pc, "bars", _bars)
    monkeypatch.setattr(mm.pc, "universe_meta", lambda: {})
    monkeypatch.setattr(mm.pc, "cost_frac", lambda sym, meta, close: grid.append(sym))  # None
    monkeypatch.setattr(mm, "SURFACES", tmp_path / "MICROSTRUCTURE_SURFACES.json")
    monkeypatch.setattr(mm, "REPORT", tmp_path / "microstructure_miner.json")
    return grid


def _surfaces() -> dict:
    return json.loads(mm.SURFACES.read_text("utf-8"))["symbols"]


def test_an_exhausted_grid_budget_still_writes_every_surface(miner) -> None:
    rep = mm.run(budget_s=-1.0)
    assert sorted(_surfaces()) == SYMS
    assert miner == [] and rep["grid_next"] == "AUDCAD"
    assert all(v == "grid budget exhausted (surface written)" for v in rep["skipped"].values())


def test_the_grid_resumes_where_the_last_run_stopped(miner) -> None:
    mm.REPORT.write_text(json.dumps({"grid_next": "NZDSGD"}), "utf-8")
    rep = mm.run(budget_s=1e9)
    assert miner == ["NZDSGD", "SGDJPY", "AUDCAD", "EURUSD", "NOKSEK"]
    assert rep["grid_next"] is None
    assert sorted(_surfaces()) == SYMS


def test_an_unknown_resume_point_starts_at_the_top() -> None:
    assert mm._grid_order(["A", "B"], {"grid_next": "Z"}) == ["A", "B"]
    assert mm._grid_order(["A", "B"], {}) == ["A", "B"]


def test_a_refused_rename_falls_back_to_writing_in_place(miner, monkeypatch) -> None:
    def refuse(self, target):
        raise PermissionError(13, "in use")

    monkeypatch.setattr(type(mm.SURFACES), "replace", refuse)
    monkeypatch.setattr(mm.time, "sleep", lambda _s: None)
    mm._write_surfaces({"symbols": {"X": {}}})
    assert json.loads(mm.SURFACES.read_text("utf-8")) == {"symbols": {"X": {}}}
    assert not mm.SURFACES.with_name(f"{mm.SURFACES.name}.tmp").exists()
