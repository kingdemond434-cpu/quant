"""ANYTIME MATH LAB (box 2026-11-25): math_lab, physics_lab and expression_factory were killed at
their 720 s / 700 s caps on both 11-25 passes with "0 of N declared artifact(s) moved", on code
unchanged since 11-10. A slow step -- the seat's unbounded free-panel rotation, a registry write
waiting on another writer -- must cost the pass its time and never its artifacts.

Pinned here: the pass budget never reaches past the cycle's cap; a slow fake seat and a slow
panel build under a short cap still publish MATH_LAB.json and the allocation; the registry write
stops at its deadline and carries the rest to the next pass, which writes it first; the free
panel's rotation is bounded by the caller's deadline; the theorem memory reads its tail, not its
file; and every untradeable object lands in a NAMED refusal class.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "tests"), str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_math_lab as TML  # noqa: E402

FAST = TML.FAST
lab = TML.lab                     # the shared fixture: synthetic panels, a tmp registry

from research import math_lab as ML  # noqa: E402


def test_the_pass_budget_never_reaches_past_the_cycle_cap(monkeypatch: pytest.MonkeyPatch):
    assert ML.effective_budget(600.0, "720") == 600.0          # inside the cap: unchanged
    assert ML.effective_budget(600.0, "500") == 440.0          # cap less LEG_MARGIN_S
    assert ML.effective_budget(600.0, "40") == 30.0            # floored, never zero
    assert ML.effective_budget(600.0, "") == 600.0             # no cap known: the request
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "300")
    assert ML.effective_budget(600.0) == 240.0


def test_bounded_returns_the_default_when_the_call_overruns():
    value, status = ML.bounded(lambda: time.sleep(5) or "late", 0.2, "default")
    assert value == "default" and status.startswith("TIMED_OUT")
    assert ML.bounded(lambda: 7, 2.0, None) == (7, "OK")
    assert ML.bounded(lambda: 7, 0.0, None)[1].startswith("SKIPPED")


def test_a_slow_seat_and_a_slow_panel_under_a_short_cap_still_publish(lab, monkeypatch):
    """The fake seat sleeps far past the cap; the pass must finish inside it and write."""
    from libs.research import proposer_seat as ps
    build = ML.build_panels

    def slow_build(max_targets: int = 4) -> Any:
        time.sleep(1.0)
        return build(max_targets)

    def stuck_seat(*a: Any, **k: Any) -> dict:
        time.sleep(120)
        return {}

    monkeypatch.setattr(ML, "build_panels", slow_build)
    monkeypatch.setattr(ps, "names_for", stuck_seat)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "90")              # effective budget 30 s
    t0 = time.monotonic()
    report = ML.run(budget_s=600.0, traditions=list(FAST), permutations=20)
    took = time.monotonic() - t0
    assert took < 60.0, took                                     # inside the 90 s cap, margin kept
    doc = json.loads(ML.OUT.read_text("utf-8"))
    assert not doc.get("partial") and doc["objects"]["admitted"] == report["objects"]["admitted"]
    assert ML.ALLOCATION.exists()
    assert report["objects"]["admitted"] > 0 and lab["donated"]


def test_the_panels_checkpoint_moves_the_artifact_before_the_science(lab, monkeypatch):
    """A kill right after the panels still leaves MATH_LAB.json moved (phase `panels`)."""
    seen: dict[str, Any] = {}

    def stop_at_science(*a: Any, **k: Any) -> Any:
        seen["doc"] = json.loads(ML.OUT.read_text("utf-8"))
        raise KeyboardInterrupt

    monkeypatch.setattr(ML, "department_plan", stop_at_science)
    with pytest.raises(KeyboardInterrupt):
        ML.run(budget_s=30.0, traditions=list(FAST), permutations=20)
    assert seen["doc"]["partial"] is True and seen["doc"]["phase"] == "panels"


def test_the_registry_write_stops_at_its_deadline_and_resumes_next_pass(lab, monkeypatch):
    from libs.moat import registry as R
    objects = _objects(lab)
    pending = ML.state_path(ML.REGISTRY_PENDING_NAME)
    out = ML.record_registry(objects, {}, {}, deadline=time.monotonic() - 1.0)
    assert out["discoveries"] == 0 and out["pending_for_next_pass"] == len(objects) > 0
    carried = json.loads(pending.read_text("utf-8"))["entries"]
    assert len(carried) == len(objects)
    again = ML.record_registry([], {}, {})
    assert again["carried_from_previous_pass"] == len(objects)
    assert again["discoveries"] == len(objects) and again["pending_for_next_pass"] == 0
    assert json.loads(pending.read_text("utf-8"))["entries"] == []
    conn = R.connect()
    try:
        ids = {o.object_id for o in objects}
        rows = conn.execute("SELECT discovery_id, state FROM discoveries").fetchall()
        assert ids <= {r[0] for r in rows}
        assert {r[1] for r in rows if r[0] in ids} == {"QUEUED"}
    finally:
        conn.close()


def _objects(_lab: dict[str, Any]) -> list[Any]:
    from research.mathlab import scientists as S
    panel = ML.build_panels()[0][0]
    out: list[Any] = []
    for t in FAST[:2]:
        res = ML._run_tradition(t, [panel], 5.0, {}, ML._operator_census([]),
                                time.monotonic() + 10.0)
        out.extend(o for o, _v in res.get("objects") or [])
    assert S.REGISTRY
    return out[:6]


def test_the_free_panel_rotation_is_bounded_by_the_callers_deadline(tmp_path, monkeypatch):
    from libs.data import keyed_sources
    from libs.ops import openrouter_guard
    from libs.research import free_panel as FP
    calls: list[float] = []

    def slow_open(req: Any, timeout: float) -> Any:
        calls.append(timeout)
        time.sleep(min(timeout, 0.4))
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(FP, "_load_key", lambda: "k")
    monkeypatch.setattr(FP, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(FP, "PRIORITY", tmp_path / "none.json")
    monkeypatch.setattr(keyed_sources, "keyed_urlopen", slow_open)
    monkeypatch.setattr(openrouter_guard, "check_request", lambda req: None)
    tier = FP.ROLE_TIER["mechanism"]
    assert len(tier) >= 4
    t0 = time.monotonic()
    with pytest.raises(FP.PanelExhausted):
        FP.ask("mechanism", "s", "u", deadline=time.monotonic() + 1.0)
    assert time.monotonic() - t0 < 2.0
    assert len(calls) < len(tier) and all(c <= 1.0 for c in calls)


def test_the_theorem_memory_reads_its_tail_not_its_file(tmp_path, monkeypatch):
    from research.mathlab import institution as I
    monkeypatch.setattr(I, "TAIL_BYTES_PER_ROW", 200)
    mem = I.TheoremMemory(tmp_path)
    for i in range(500):
        mem.append("failed", {"canonical": f"c{i}", "pad": "x" * 20})
    rows = mem.rows("failed", limit=10)
    assert [r["canonical"] for r in rows] == [f"c{i}" for i in range(490, 500)]


def test_every_untradeable_object_lands_in_a_named_refusal_class():
    from research.mathlab import grammar as G
    cases = {"NON_BAR_SERIES": ["z", "esn_readout", 240],
             "NO_TRADE_OPERATOR": ["mul", ["gt", ["z", "vol", 240], 1.28], ["z", "ret", 24]],
             "UNIT_ALGEBRA_OR_DEPTH": ["sub", ["curv", ["sub", ["rmin", "low", 8], "range"], 12],
                                       "vol"]}
    refused = []
    for want, expr in cases.items():
        got, why = G.tradeable(expr)
        assert got is None, expr
        assert ML.refusal_class(why) == want, why
        refused.append({"object_id": want, "why": why})
    assert ML.refusal_classes(refused) == dict.fromkeys(cases, 1)
