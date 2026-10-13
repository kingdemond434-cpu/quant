"""PRODUCER HEALTH (principal 2026-10-13): every lane LIVE/STALE and WIRED/UNWIRED, its yield
against its peers, an additive upgrade for the bottom quartile, and a fence that fails on drift.

Every input is synthetic and redirected into `tmp_path`; nothing reads or writes box state.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT), str(_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_producer_health as fence  # noqa: E402

from research import producer_health as ph  # noqa: E402


def _row(key: str, *, clock: str | None = "hourly_cycle:x", emitted: float = 0.0,
         unique: float = 0.0, judged: float = 0.0, compute: float = 0.0,
         orth: float = 0.0, declared: dict | None = None) -> dict[str, Any]:
    r = {"producer": key, "key": key, "clock": clock, "compute_hours_window7d": compute,
         "cells_emitted_per_hour": emitted, "unique_cells_per_hour": unique,
         "cells_to_judge_per_hour": judged, "orthogonality_added": orth}
    if declared:
        r["declared"] = declared
    return r


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rows = [
        _row("winner_a", emitted=100, unique=90, judged=90, compute=7, orth=0.5),
        _row("winner_b", emitted=80, unique=70, judged=70, compute=7, orth=0.3),
        _row("mid", emitted=20, unique=18, judged=18, compute=7, orth=0.1),
        _row("collapser", emitted=50, unique=2, judged=2, compute=7, orth=0.01),
        _row("flat", emitted=5, unique=5, judged=5, compute=7, orth=0.0),
        _row("seatonly", clock="crontab:x"),
        _row("stale_on_clock"),
        _row("never_clocked", clock=None, emitted=3, unique=3, judged=3),
        _row("math:lab", clock=None, compute=1.0,
             declared={"kind": "EXEMPTION", "produces": "x", "consumer": "y"}),
    ]
    py = {"generated_utc": "2026-10-13T00:00:00+00:00",
          "producers": [{"producer": "seatonly", "rows_in_window": 40, "verdict": "PRODUCING"}],
          "cells_owed": {"producers": rows}}
    (tmp_path / "PY.json").write_text(json.dumps(py))
    (tmp_path / "dead.json").write_text(json.dumps({"organs": {}}))
    (tmp_path / "prov.json").write_text(json.dumps({"records": {
        "c1": {"producer": "winner_a"}, "c2": {"producer": "miner:winner_a"},
        "c3": {"producer": "winner_b"}}}))
    monkeypatch.setattr(ph, "PRODUCER_YIELD", tmp_path / "PY.json")
    monkeypatch.setattr(ph, "DEAD_ARCH", tmp_path / "dead.json")
    monkeypatch.setattr(ph, "PROVENANCE", tmp_path / "prov.json")
    monkeypatch.setattr(ph, "OUT", tmp_path / "PRODUCER_HEALTH.json")
    return tmp_path


def _lane(doc: dict[str, Any], name: str) -> dict[str, str]:
    return next(r for r in doc["lane_states"] if r["lane"] == name)


def test_live_stale_wired_unwired(world: Path) -> None:
    doc = ph.build(previous={})
    assert doc["verdict"] == "MEASURED" and doc["counts"]["lanes"] == 9
    assert _lane(doc, "winner_a") == {"lane": "winner_a", "live": "LIVE", "wired": "WIRED"}
    assert _lane(doc, "seatonly") == {"lane": "seatonly", "live": "LIVE", "wired": "WIRED"}
    assert _lane(doc, "stale_on_clock")["live"] == "STALE"
    assert _lane(doc, "stale_on_clock")["wired"] == "UNWIRED"
    assert _lane(doc, "never_clocked") == {"lane": "never_clocked", "live": "LIVE",
                                           "wired": "UNWIRED"}
    assert _lane(doc, "math:lab")["live"] == "LIVE"                 # exemption that ran
    assert doc["counts"]["clocked_stale"] == 1


def test_yield_against_peers_and_additive_upgrades(world: Path) -> None:
    doc = ph.build(previous={})
    lanes = {ln["lane"]: ln for ln in doc["lanes"]}
    assert lanes["winner_a"]["certificates"] == 2                   # miner: prefix folds in
    assert lanes["winner_a"]["keff_per_compute_hour"] == pytest.approx(0.5)
    assert lanes["winner_a"]["yield_score"] > lanes["flat"]["yield_score"]
    assert isinstance(doc["peer_medians"]["unique_cells_per_hour"], float)
    bottom = {b["lane"] for b in doc["bottom_quartile"]}
    assert bottom and "winner_a" not in bottom
    acts = {a["lane"]: a for a in doc["actions"]}
    assert acts["stale_on_clock"]["action"] == "REPAIR"
    assert all(a["never_cut"] for a in doc["actions"])
    kinds = {ph._action(ph.classify(_row("c", emitted=50, unique=2, judged=2, compute=7,
                                         orth=0.1), None, {}, 0), {})["action"],
             ph._action(ph.classify(_row("w", emitted=5, unique=5, judged=5, compute=7),
                                    None, {}, 0), {})["action"],
             ph._action(ph.classify(_row("s"), 40, {}, 0), {})["action"]}
    assert kinds == {"MUTATE", "WIDEN", "CONVERT"}
    shift = ph._action(ph.classify(_row("x:y", emitted=5, unique=5, judged=5, compute=7,
                                        orth=0.1), None, {}, 0), {"x": "x:winner"})
    assert shift["action"] == "BUDGET_SHIFT" and shift["raise_winner"] == "x:winner"


def test_regressions_and_the_ratchet_fail_the_fence(world: Path) -> None:
    first = ph.build(previous={})
    path = ph.write(first)
    assert fence.judge(path)["verdict"] == "OK"
    # winner_b stops producing; a new clocked lane appears stale.
    py = json.loads((world / "PY.json").read_text())
    for r in py["cells_owed"]["producers"]:
        if r["key"] == "winner_b":
            r.update(cells_emitted_per_hour=0, unique_cells_per_hour=0,
                     cells_to_judge_per_hour=0)
    (world / "PY.json").write_text(json.dumps(py))
    second = ph.build()                                             # reads `first` as previous
    path = ph.write(second)
    out = fence.judge(path)
    assert out["verdict"] == "FAIL"
    assert any("REGRESSION winner_b: LIVE->STALE" in f for f in out["failures"])
    assert any("RATCHET clocked_stale" in f for f in out["failures"])
    assert second["ratchet"]["clocked_stale"] == 1                  # falls only


def test_fence_portable_and_box_modes(tmp_path: Path, world: Path) -> None:
    absent = tmp_path / "none.json"
    assert fence.judge(absent)["verdict"] == "UNMEASURED"
    assert fence.main(["--report", str(absent)]) == 0
    assert fence.judge(absent, require_state=True)["verdict"] == "FAIL"
    doc = ph.build(previous={})
    doc["generated_utc"] = (datetime.now(UTC) - timedelta(hours=9)).isoformat()
    p = ph.write(doc, tmp_path / "old.json")
    assert fence.judge(p)["verdict"] == "OK"
    assert fence.judge(p, require_state=True)["verdict"] == "FAIL"


def test_unmeasured_without_the_yield_roster(world: Path) -> None:
    (world / "PY.json").write_text("{}")
    assert ph.build(previous={})["verdict"] == "UNMEASURED"


def test_actions_reach_the_ceo_and_everything_is_scheduled(world: Path) -> None:
    ph.write(ph.build(previous={}))
    props = ph.proposals()
    assert props and all(p["id"].startswith("producer_health:") for p in props)
    assert "_health_proposals" in (_DESK / "research" / "frontier_ceo.py").read_text("utf-8")
    hc = importlib.import_module("research.hourly_cycle")
    from libs.research.layers import LEG_LAYER
    assert "producer_health" in hc.CORE_LEGS and hc.department_of("producer_health") == "meta"
    assert LEG_LAYER["producer_health"] == "meta" and hc.LEG_BUDGET_SEC["producer_health"] >= 120
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert src.index('_costed("producer_breadth"') < src.index('_costed("producer_health"')
    lg = importlib.import_module("run_law_gate")
    assert ("check_producer_health.py", ()) in lg._LAW_FENCES
    assert ("check_producer_health.py", ("--require-state",)) in lg._STATE_FENCES
