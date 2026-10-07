"""Receding-horizon planning: decay, forecasts, later opportunities and the value of holding.

What `multiperiod.py` could not express (2026-10-06): trade now versus partially versus wait,
priced on the desk's own worlds with real stage lengths. Each test pins one economic behaviour.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.multiperiod_worlds import forward_path, plan_receding
from libs.portfolio.robust_elog import Worlds


def _worlds(mu: list[float], sd: float = 0.02, n_w: int = 32, n_t: int = 64,
            seed: int = 0) -> Worlds:
    rng = np.random.default_rng(seed)
    n = len(mu)
    m = np.asarray(mu, dtype=float)
    r = (m[None, None, :] + rng.normal(0, sd, size=(n_w, n_t, n))).astype(np.float32)
    names = tuple(f"s{i}" for i in range(n))
    return Worlds(r=r, names=names, crisis=np.zeros(n_w, bool),
                  mu_draws=np.repeat(m[None, :], n_w, axis=0))


def test_overlapping_forecasts_are_one_path_not_two_profits() -> None:
    # +0.2R over 1h and +0.5R over 4h is +0.2 then +0.3, never +0.7.
    stages = [1 / 24, 3 / 24]
    fwd = forward_path([(1 / 24, {"a": 0.2}), (4 / 24, {"a": 0.5})], stages, ["a"])
    total = float((fwd[:, 0] * np.asarray(stages)).sum())
    assert total == pytest.approx(0.5)
    assert fwd[0, 0] * stages[0] == pytest.approx(0.2)
    # Past the longest horizon the forecast says nothing.
    fwd2 = forward_path([(1 / 24, {"a": 0.2})], [1 / 24, 1.0], ["a"])
    assert fwd2[1, 0] == 0.0


def test_hold_is_kept_when_switching_buys_nothing() -> None:
    w = _worlds([0.004, 0.004])
    held = {"s0": 0.05, "s1": 0.05}
    out = plan_receding(w, held, cap=0.10, upper={"s0": 0.05, "s1": 0.05},
                        cost_one_way=0.03)
    assert out["h_now"] == pytest.approx(held, abs=1e-4)
    assert out["vs_hold"]["benefit"] == pytest.approx(0.0, abs=1e-8)


def test_a_better_sleeve_is_rotated_into_when_it_pays_net_of_cost() -> None:
    w = _worlds([0.0005, 0.02], sd=0.01)
    out = plan_receding(w, {"s0": 0.05}, cap=0.05, cost_one_way=0.0005)
    assert out["h_now"]["s1"] > out["h_now"]["s0"]
    assert out["vs_hold"]["benefit"] > 0
    assert out["actions"]["s0"]["action"] in {"REDUCE_NOW", "CLOSE", "REDUCE_PARTIAL"}


def test_perishable_edge_is_front_loaded_and_durable_is_not_rushed() -> None:
    w = _worlds([0.01, 0.01], sd=0.01)
    out = plan_receding(w, {}, cap=0.10, upper={"s0": 0.10, "s1": 0.10},
                        half_life_days={"s0": 0.2}, cost_one_way=0.0)
    path_s0 = [out["h_now"]["s0"]]
    assert path_s0[0] > 0.0
    assert out["path_total_heat"][0] == pytest.approx(0.10, abs=1e-3)
    # By the last stage the perishable sleeve has given its budget back to the durable one.
    assert out["actions"]["s1"]["end"] > out["actions"]["s0"]["end"]


def test_a_later_opportunity_is_waited_for_not_churned() -> None:
    w = _worlds([0.002, 0.03], sd=0.01)
    out = plan_receding(w, {}, cap=0.05, available_from={"s1": 2}, cost_one_way=0.01)
    assert out["h_now"]["s1"] == 0.0
    assert out["actions"]["s1"]["action"] == "WAIT"


def test_margin_reserved_by_a_stage_cap_is_respected() -> None:
    w = _worlds([0.01, 0.01], sd=0.01)
    out = plan_receding(w, {}, cap=[0.10, 0.10, 0.02, 0.10], cost_one_way=0.0)
    assert out["path_total_heat"][2] <= 0.02 + 1e-9


def test_solution_carries_an_optimality_certificate() -> None:
    w = _worlds([0.004, 0.006, 0.002], sd=0.02)
    out = plan_receding(w, {"s0": 0.02}, cap=0.08, iterations=600)
    assert out["optimality_gap"] >= 0.0
    assert out["converged"] == (out["optimality_gap"] <= out["gap_tolerance"])


def test_five_day_rule_is_checked_per_opportunity() -> None:
    # A short-lived forecast: the five-day filter would credit five days of a one-hour edge.
    w = _worlds([0.0, 0.0], sd=0.005)
    out = plan_receding(w, {}, cap=0.05, cost_one_way=0.0002,
                        forecasts=[(1 / 24, {"s0": 0.3})])
    chk = out["no_trade_horizon_check"]
    assert chk["rule_days"] == 5.0
    if "s0" in out["actions"]:
        a = out["actions"]["s0"]
        assert a["persistence_days"] == pytest.approx(1 / 24, abs=1e-4)
