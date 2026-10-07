"""The certified book re-solves on the pass that sees its inputs move (principal 2026-10-07:
"wby isnt it every minute or compute"). A fill reaches a re-solve within ONE allocator-trigger
tick; an unchanged state never re-solves; a change inside the gap is deferred, never dropped."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import allocator_trigger as at  # noqa: E402
import book_trigger as bt  # noqa: E402


@pytest.fixture()
def desk(tmp_path, monkeypatch):
    data, reports = tmp_path / "data", tmp_path / "reports"
    data.mkdir()
    reports.mkdir()
    for name, path in (("GATEWAY_STATE", data / "gateway_state.json"),
                       ("ACCOUNT", data / "account_state.json"),
                       ("E8_GOLD", reports / "E8_GOLD.json"),
                       ("CERT_STORE", reports / "UNIVERSAL_SURVIVORS.json"),
                       ("CERT_CANON", data / "canon.json"),
                       ("SLEEVE_REGISTRY", data / "sleeve_registry.json"),
                       ("QUOTES", data / "cost_truth_quotes.json"),
                       ("ALLOCATION", reports / "pf_allocation_book.json"),
                       ("WORLDS", data / "worlds.npz"),
                       ("KELLY", reports / "KELLY_SURVIVAL.json")):
        monkeypatch.setattr(bt, name, path)
    for name in ("STATE", "LOG", "OUT", "ALLOCATION", "RESOLVE_REQUEST", "LOCK"):
        monkeypatch.setattr(at, name, tmp_path / f"at_{name.lower()}")
    monkeypatch.setattr(at, "sources", lambda: [])          # the allocator stage stays quiet
    (data / "gateway_state.json").write_text(json.dumps(
        {"equity": 583.0, "position": {}, "brackets": {}, "lot": 0.01}), encoding="utf-8")
    (reports / "KELLY_SURVIVAL.json").write_text(json.dumps(
        {"book": {"fusion": {"heat": {"EURZAR_overnight_gap_decay_asia": 0.098}}}}),
        encoding="utf-8")
    (data / "cost_truth_quotes.json").write_text(json.dumps({"symbols": {
        "EURZAR": {"live_spread_pts": 426, "swap_long": -465.16, "swap_short": -35.64}}}),
        encoding="utf-8")
    calls: list[float] = []

    def solver(budget_s: float) -> dict:
        calls.append(budget_s)
        return {"rc": 0, "wall_s": 0.1}
    return data, calls, solver


def _tick(state, t, solver):
    return at.poll(state=state, write=False, now=t, solver=lambda *_: {"rc": 0},
                   book_solver=solver)


def test_a_fill_re_solves_the_book_within_one_tick(desk):
    data, calls, solver = desk
    r = _tick(None, 1000.0, solver)
    assert r["book"]["event"] == "baseline" and not calls
    st = r["state"]
    assert _tick(st, 1020.0, solver)["book"]["event"] == "unchanged" and not calls
    gs = json.loads((data / "gateway_state.json").read_text("utf-8"))
    gs["position"] = {"EURZAR": {"volume": 0.01, "type": 0}}           # a fill lands
    (data / "gateway_state.json").write_text(json.dumps(gs), encoding="utf-8")
    r = _tick(st, 1040.0, solver)                                         # the very next tick
    assert r["book"]["event"] == "solved" and r["book"]["moved"] == ["fill"]
    assert len(calls) == 1
    assert _tick(st, 1060.0, solver)["book"]["event"] == "unchanged" and len(calls) == 1


def test_equity_swap_and_gap_rules(desk):
    data, calls, solver = desk
    st = _tick(None, 1000.0, solver)["state"]
    gs = json.loads((data / "gateway_state.json").read_text("utf-8"))
    gs["equity"] = 583.5                                   # under 1%: same bucket, no solve
    (data / "gateway_state.json").write_text(json.dumps(gs), encoding="utf-8")
    assert _tick(st, 1020.0, solver)["book"]["event"] == "unchanged"
    gs["equity"] = 600.0                                   # +3%: re-solve
    (data / "gateway_state.json").write_text(json.dumps(gs), encoding="utf-8")
    assert _tick(st, 1040.0, solver)["book"]["moved"] == ["equity"] and len(calls) == 1
    q = {"symbols": {"EURZAR": {"live_spread_pts": 426, "swap_long": 12.0, "swap_short": -35.64}}}
    (data / "cost_truth_quotes.json").write_text(json.dumps(q), encoding="utf-8")
    r = _tick(st, 1050.0, solver)                          # swap flipped, but inside the gap
    assert r["book"]["event"] == "deferred" and len(calls) == 1
    r = _tick(st, 1101.0, solver)                          # served after the gap, not dropped
    assert r["book"]["event"] == "solved" and len(calls) == 2


def test_a_failed_solve_is_retried_not_marked_solved(desk):
    data, calls, _ = desk
    st = _tick(None, 1000.0, lambda b: {"rc": 0})["state"]
    (data / "sleeve_registry.json").write_text(json.dumps({"sleeves": ["new"]}), encoding="utf-8")
    assert _tick(st, 1010.0, lambda b: {"rc": 1})["book"]["event"] == "solve_failed"
    assert _tick(st, 1080.0, lambda b: {"rc": 0})["book"]["event"] == "solved"
