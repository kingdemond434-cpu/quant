"""The seed sweep rotates inside the slice it is given, so a slow head never starves the tail."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "side_channels"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import seed_miners  # noqa: E402


class _Killed(BaseException):
    """The caller's hard timeout landing mid-miner: not an Exception, so nothing catches it."""


@pytest.fixture
def sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(seed_miners, "STATE", tmp_path / "seed_miners_state.json")
    monkeypatch.setattr(seed_miners, "INTEL", tmp_path)
    monkeypatch.setattr(seed_miners, "SOURCE_WALLS", {})
    from libs.research import proposer_seat
    asked: list[str] = []
    monkeypatch.setattr(proposer_seat, "ask",
                        lambda *a, **k: asked.append("seat") or (_ for _ in ()).throw(OSError()))
    joined: list[str] = []
    monkeypatch.setitem(sys.modules, "cohort_and_identity",
                        types.SimpleNamespace(run_and_save=lambda: joined.append("join")))
    clock = {"t": 0.0}
    monkeypatch.setattr(seed_miners.time, "monotonic", lambda: clock["t"])
    calls: list[str] = []

    def miner(name: str, cost: float):
        def fn() -> list[dict]:
            calls.append(name)
            clock["t"] += cost
            return [seed_miners.row(name, "repo", f"{name} row")]
        return fn

    monkeypatch.setattr(seed_miners, "MINERS", {
        "heavy_a": miner("heavy_a", 20), "heavy_b": miner("heavy_b", 20),
        "light_c": miner("light_c", 1), "new_d": miner("new_d", 1)})
    return {"calls": calls, "asked": asked, "joined": joined, "tmp": tmp_path}


def _state(tmp: Path) -> dict[str, Any]:
    return json.loads((tmp / "seed_miners_state.json").read_text())


def test_every_miner_is_reached_within_a_few_tight_passes(sweep: dict[str, Any]) -> None:
    for _ in range(3):
        seed_miners.run_and_save(budget_s=30)
    assert set(sweep["calls"]) == {"heavy_a", "heavy_b", "light_c", "new_d"}
    st = _state(sweep["tmp"])
    assert st["miner_seconds"]["heavy_a"] == 20 and st["sweep_last"]["budget_s"] == 30
    assert st["sweep_last"]["deferred"] or st["sweep_last"]["ran"]


def test_the_cursor_moves_before_a_miner_runs_so_a_killed_one_is_passed_over(
        sweep: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    def killed() -> list[dict]:
        raise _Killed
    monkeypatch.setitem(seed_miners.MINERS, "heavy_a", killed)
    with pytest.raises(_Killed):
        seed_miners.run_and_save(budget_s=30)
    assert _state(sweep["tmp"])["sweep_cursor"] == 1    # next pass starts AFTER the killed one
    with pytest.raises(_Killed):                        # it comes round again, LAST
        seed_miners.run_and_save(budget_s=30)
    assert sweep["calls"] == ["heavy_b", "light_c", "new_d"]


def test_a_spent_slice_defers_the_optional_seat_and_join_but_still_records(
        sweep: dict[str, Any]) -> None:
    seed_miners.run_and_save(budget_s=30)
    assert sweep["asked"] == [] and sweep["joined"] == []
    assert _state(sweep["tmp"])["sweep_last"]["deferred"]


def test_without_a_budget_the_whole_sweep_runs_as_before(sweep: dict[str, Any]) -> None:
    seed_miners.run_and_save()
    assert sweep["calls"] == ["heavy_a", "heavy_b", "light_c", "new_d"]
    assert sweep["joined"] == ["join"] and sweep["asked"] == ["seat"]
    assert _state(sweep["tmp"])["sweep_last"]["deferred"] == []


def test_the_swarm_hands_the_sweep_its_slice() -> None:
    sys.path.insert(0, str(DESK / "research"))
    import scout_swarm as sw
    organ = "desks/mt5/side_channels/seed_miners.py"
    assert "--budget-s" in sw.organ_flags(organ)
    args, _ = sw.steer_args(organ, [], 42.0)
    assert args == ["--budget-s", "42"]
