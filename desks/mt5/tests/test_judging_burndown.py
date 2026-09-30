"""The burn-down counts CELLS LEAVING THE BACKLOG, and the sweep's clock is taken apart honestly.

`research/judging_burndown.py` is the number the principal asked for ("the backlog burned down
faster than creation"). A verdict ROW is not a drain -- a re-judge that moves a cell between gates
is a second row for a cell that left the backlog long ago, and an UNKNOWN or NOT_RUN row is no
ruling at all -- so these pin that only a cell's FIRST real verdict counts, that the inflow is the
docket's own `first_seen` clock, and that the sweep anatomy the warmer sizes itself by is read
from the judge's own artifacts without decoding its million-row verdict list.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK / "scripts"), str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import judging_burndown as JB  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def _row(cell: str, hours_ago: float, gate: str = "cpcv", passed: bool = False,
         status: str | None = None) -> str:
    return json.dumps({"at": _at(hours_ago), "cell": cell, "passed": passed,
                       "terminal_gate": gate, "downstream_status": status}) + "\n"


def test_only_a_cells_first_real_verdict_is_a_drain(tmp_path: Path) -> None:
    led = tmp_path / "ledger.jsonl"
    led.write_text("".join([
        _row("old", 400.0),                       # ruled before both windows
        _row("old", 2.0, gate="walk_forward"),    # a re-judge: not a drain
        _row("a", 3.0), _row("b", 30.0, gate="PASSED", passed=True),
        _row("u", 1.0, gate="UNKNOWN"),           # no terminal gate: not a ruling
        _row("n", 1.0, status="NOT_RUN_BUILD_BUDGET_DEFERRED"),
        _row("u", 0.5, gate="deflated_sharpe"),   # u's first REAL ruling
    ]), encoding="utf-8")
    d = JB.drain(NOW, led)
    assert d["first_rulings"] == {"24h": 2, "7d": 3}
    assert d["rows"]["24h"] == {"ruled": 3, "unknown": 1, "not_run": 1}


def test_inflow_is_the_dockets_first_seen_clock(tmp_path: Path) -> None:
    dk = tmp_path / "external_survivors.json"
    dk.write_text(json.dumps([{"symbol": "X", "first_seen": _at(h)} for h in (1, 5, 30, 400)]),
                  encoding="utf-8")
    i = JB.inflow(NOW, dk)
    assert i["created"] == {"24h": 2, "7d": 3}


def test_the_verdict_is_growing_when_creation_outruns_first_rulings() -> None:
    b = {"status": "MEASURED", "unjudged": 1_400_000}
    d = {"status": "MEASURED", "first_rulings_per_hour": {"7d": 220.0, "24h": 220.0}}
    i = {"status": "MEASURED", "created_per_hour": {"7d": 345.0, "24h": 345.0}}
    v = JB.verdict(b, d, i)
    assert v["status"] == "GROWING" and v["net_per_day"] == pytest.approx(-3000.0)
    assert v["needed_first_rulings_per_hour"] == pytest.approx(345.0 + 1_400_000 / 720.0, 0.01)
    d["first_rulings_per_hour"]["7d"] = 3000.0
    assert JB.verdict(b, d, i)["status"] == "DRAINING"
    assert JB.verdict({"status": "UNMEASURED", "why": "x"}, d, i)["status"] == "UNMEASURED"


def _plant_sweep(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, order_at: str,
                 swept_at: str, deferred: int) -> None:
    rep = tmp_path / "universal_gates_external.json"
    verdicts = [{"cell": f"c{i}", "stages": {}, "why": "x" * 50} for i in range(30_000)]
    rep.write_text(json.dumps({"verdicts": verdicts, "swept_at": swept_at,
                               "n_cells_advanced_beyond_economic_prior": 1_000,
                               "n_cells_deferred_build_budget": deferred, "workers": 15,
                               "prewarm": {"workers": 15, "submitted": 900, "warmed": 400,
                                           "hit": 450, "failed": 50, "unreached": 0,
                                           "seconds": 1800.0, "failures": {"X": 1}}},
                              indent=2), encoding="utf-8")
    order = tmp_path / "GAUNTLET_ORDER.json"
    order.write_text(json.dumps({"at": order_at}), encoding="utf-8")
    monkeypatch.setattr(JB, "GATES_REPORT", rep)
    monkeypatch.setattr(JB, "GAUNTLET_ORDER", order)


def test_sweep_anatomy_splits_build_from_gate_without_decoding_the_verdicts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant_sweep(tmp_path, monkeypatch, order_at=_at(1.0), swept_at=_at(0.0), deferred=0)
    s = JB.sweep_anatomy()
    assert s["status"] == "MEASURED"
    assert s["seconds_after_order"] == pytest.approx(3600.0)
    assert s["post_build_seconds"] == pytest.approx(1800.0)
    assert s["post_build_s_per_cell"] == pytest.approx(1.8)
    assert s["prewarm"]["warmed"] == 400.0 and s["prewarm"]["hit"] == 450.0
    assert s["binding_stage"] == "GATE"
    _plant_sweep(tmp_path, monkeypatch, order_at=_at(1.0), swept_at=_at(0.0), deferred=12)
    assert JB.sweep_anatomy()["binding_stage"] == "BUILD"


def test_an_out_of_step_order_and_report_is_unmeasured(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    """A new sweep has ordered but not yet reported: the pair describes two sweeps."""
    _plant_sweep(tmp_path, monkeypatch, order_at=_at(0.0), swept_at=_at(1.0), deferred=0)
    assert JB.sweep_anatomy()["status"] == "UNMEASURED"


def test_the_warmers_gate_room_is_sized_by_the_measured_anatomy(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import warm_gauntlet_cache as W

    jt = tmp_path / "JUDGING_THROUGHPUT.json"
    jt.write_text(json.dumps({"decision": {"task_time_limit_s": 14_400.0,
                                           "fresh_budget_s": 8_640.0}}), encoding="utf-8")
    monkeypatch.setattr(W, "JUDGING_THROUGHPUT", jt)
    room = W.gate_room({"status": "MEASURED", "post_build_s_per_cell": 0.1})
    assert room["status"] == "MEASURED"
    assert room["cells"] == int(W.GATE_SAFETY * (14_400 - 8_640) / 0.1)
    assert W.gate_room({"status": "UNMEASURED", "why": "x"})["cells"] is None, \
        "an unmeasured sweep bounds nothing"


def test_capacity_projects_the_warm_side_and_labels_it(tmp_path: Path) -> None:
    d = {"status": "MEASURED", "first_rulings_per_hour": {"24h": 220.0, "7d": 200.0}}
    w = {"cells_per_min": 10.0, "warmed": 100, "never_judged_warmed": 80}
    c = JB.capacity(d, w, {"binding_stage": "BUILD"})
    assert c["status"] == "PROJECTED"
    assert c["warm_builds_per_day"] == 14_400
    assert c["first_rulings_per_day_from_warm_side"] == round(14_400 * 0.8)
    assert c["measured_first_rulings_per_day"] == pytest.approx(5_280.0)
    assert JB.capacity(d, {}, {})["status"] == "UNMEASURED"
