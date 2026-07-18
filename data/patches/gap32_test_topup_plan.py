"""Tests for `_topup_plan` -- the guarded resize-up sizing (2026-07-19 gap #32 capital-utilization
fix). These pin the SAFE-direction invariants on the risk-path math: fill idle authorized capital
by topping held carries toward target, but never lever past `capital`, never breach the 0.35
per-name concentration rail (the 2026-07-13 failure mode), never size DOWN, and never churn on
immaterial shortfalls.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_cashcarry_executor.py"
_SPEC = importlib.util.spec_from_file_location("run_cashcarry_executor_tp", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

_topup_plan = _MOD._topup_plan
CAP = 4500.0


def _pos(notional: float, funding: float, price: float = 1.0) -> dict:
    q = notional / price
    return {"spot_qty": q, "spot_cost": price, "perp_qty": -q,
            "perp_entry": price, "funding": funding}


def _deployed(pos: dict) -> float:
    return sum(float(p["spot_qty"]) * float(p["spot_cost"]) for p in pos.values())


def test_empty_book_no_plan():
    assert _topup_plan({}, CAP) == {}


def test_tops_up_undersized_carries():
    pos = {f"S{i}": _pos(30.0, 0.01) for i in range(10)}          # 10 frozen $30 carries = $300
    plan = _topup_plan(pos, CAP)
    assert plan, "undersized book must produce top-ups"
    for sym, add in plan.items():
        assert add > 0.0                                          # only adds
        cur = float(pos[sym]["spot_qty"]) * float(pos[sym]["spot_cost"])
        assert cur + add <= 0.35 * CAP + 1e-6                     # concentration rail holds


def test_never_levers_past_capital():
    pos = {f"S{i}": _pos(30.0, 0.01) for i in range(10)}
    plan = _topup_plan(pos, CAP)
    assert _deployed(pos) + sum(plan.values()) <= CAP + 1e-6      # aggregate <= authorized capital


def test_never_sizes_down_when_over_target():
    # one carry already ABOVE the 0.35 cap -> must not appear in the plan (no size-down)
    pos = {"BIG": _pos(2000.0, 0.02), "A": _pos(30.0, 0.01), "B": _pos(30.0, 0.01),
           "C": _pos(30.0, 0.01)}
    plan = _topup_plan(pos, CAP)
    assert "BIG" not in plan


def test_hysteresis_skips_immaterial_shortfall():
    # target ~ CAP/2 = 2250 each but capped at 0.35*CAP=1575; put one carry $10 under its cap
    pos = {"A": _pos(1575.0 - 10.0, 0.01), "B": _pos(1575.0, 0.01)}
    plan = _topup_plan(pos, CAP)
    assert "A" not in plan                                        # < max(0.02*CAP, 20)=90 -> skip


def test_concentration_cap_with_few_names():
    # 2 names: each may reach at most 0.35*CAP; 30% stays idle BY DESIGN (never over-concentrate)
    pos = {"A": _pos(50.0, 0.01), "B": _pos(50.0, 0.01)}
    plan = _topup_plan(pos, CAP)
    for sym, add in plan.items():
        cur = float(pos[sym]["spot_qty"]) * float(pos[sym]["spot_cost"])
        assert cur + add <= 0.35 * CAP + 1e-6


def test_converges_after_repeated_application():
    # applying the plan repeatedly should walk deployment UP toward (but never past) capital
    pos = {f"S{i}": _pos(30.0, 0.01) for i in range(10)}
    for _ in range(5):
        plan = _topup_plan(pos, CAP)
        for sym, add in plan.items():
            price = float(pos[sym]["spot_cost"])
            q = (float(pos[sym]["spot_qty"]) * price + add) / price
            pos[sym]["spot_qty"] = q
            pos[sym]["perp_qty"] = -q
    dep = _deployed(pos)
    assert dep <= CAP + 1e-6
    assert dep >= 0.9 * min(CAP, 10 * 0.35 * CAP)   # 10 names -> full deploy reachable
