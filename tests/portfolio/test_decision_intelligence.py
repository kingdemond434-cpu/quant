from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio.decision_intelligence import (
    alpha_retention,
    capital_inventory_policy,
    dependence_preserving_monte_carlo,
    effective_breadth,
    execution_opportunity,
    exit_reallocation_decision,
    momentum_rebound_surface,
    monetisation_latency,
    path_drawdown_state,
    regime_conditional_allocation,
    regime_model_selection,
    return_attribution,
    transition_posterior,
    transition_surprise,
    trigger_collision_control,
    xsec_momentum_book,
)


def test_joint_bootstrap_and_effective_breadth_preserve_dependence() -> None:
    rng = np.random.default_rng(4)
    base = rng.normal(0.001, 0.01, 120)
    duplicate = np.column_stack([base, base])
    breadth = effective_breadth(duplicate)
    assert breadth["effective_sleeves"] == pytest.approx(1.0)
    report = dependence_preserving_monte_carlo(
        duplicate, [0.25, 0.25], n_paths=40, mean_block=5, seed=7
    )
    assert report["status"] == "MEASURED"
    assert report["paths"] == 40
    assert report["ruin_probability"] == 0.0
    assert "jointly" in report["dependence_preserved"]


def test_bad_portfolio_inputs_are_refused() -> None:
    with pytest.raises(ValueError):
        effective_breadth([[1.0]])
    with pytest.raises(ValueError):
        dependence_preserving_monte_carlo([[0.1], [0.2]], [1.0, 2.0])
    with pytest.raises(ValueError):
        dependence_preserving_monte_carlo([[0.1], [0.2]], [1.0], n_paths=0)


def test_transition_posterior_duration_and_surprise() -> None:
    report = transition_posterior(["risk-on", "risk-on", "risk-off", "risk-off", "risk-on"])
    assert report["status"] == "MEASURED"
    assert report["posterior"]["risk-on"]["risk-off"] > 0
    surprise = transition_surprise("risk-on", "unknown", report["posterior"])
    assert surprise["route_to_hypothesis_factory"] is True
    assert transition_posterior(["only"])["status"] == "UNMEASURED"


def test_drawdown_inventory_and_collision_controls() -> None:
    drawdown = path_drawdown_state([0.01, -0.08, -0.02, 0.03])
    assert drawdown["status"] == "MEASURED"
    assert drawdown["max_drawdown"] > 0.08
    assert path_drawdown_state([0.1])["status"] == "UNMEASURED"
    inv = capital_inventory_policy(
        deployable=100, dry_powder=80, opportunity_score=3, future_option_score=1
    )
    assert inv["deploy_now"] == 60
    assert inv["tranches"] == 6
    with pytest.raises(ValueError):
        capital_inventory_policy(
            deployable=-1, dry_powder=1, opportunity_score=1, future_option_score=1
        )
    x = np.column_stack([np.arange(30), np.arange(30), np.arange(30)[::-1]])
    collision = trigger_collision_control(x)
    assert collision["effective_sleeves"] < 2
    assert collision["sizing_multiplier"] < 1


def test_momentum_competing_sleeves_and_conditional_surface() -> None:
    prices = np.vstack(
        [np.linspace(100, 130, 25), np.linspace(100, 90, 25), np.linspace(100, 105, 25)]
    ).T
    book = xsec_momentum_book(prices, lookback=20)
    assert book["status"] == "MEASURED"
    assert sum(book["continuation_weights"]) == pytest.approx(0.0)
    assert (
        np.asarray(book["continuation_weights"]) @ np.asarray(book["crowded_reversal_weights"]) < 0
    )
    assert xsec_momentum_book(prices, lookback=30)["status"] == "UNMEASURED"
    surface = momentum_rebound_surface(
        list(range(24)), [0.2] * 12 + [0.5] * 12, [0.01] * 12 + [0.03] * 12
    )
    assert surface["status"] == "MEASURED"
    assert len(surface["cells"]) == 4


def test_exit_execution_retention_and_attribution() -> None:
    exit_report = exit_reallocation_decision([0.01, 0.02], [0.03, 0.04], switching_cost=0.001)
    assert exit_report["decision"] == "REALLOCATE"
    assert exit_reallocation_decision([], [0.1])["status"] == "UNMEASURED"
    execution = execution_opportunity(
        gross_edge_bps=8,
        order_size=10,
        queue_ahead=5,
        through_volume=15,
        taker_cost_bps=10,
        adverse_selection_bps=1,
    )
    assert execution["maker_fill_probability"] == 1.0
    assert execution["eligible"] is True
    retention = alpha_retention(
        intended_pnl=100, realised_pnl=70, leaks={"fees": 10, "latency": 15}
    )
    assert retention["retention_ratio"] == 0.7
    assert retention["unattributed_leak"] == 5
    assert alpha_retention(intended_pnl=0, realised_pnl=0)["status"] == "UNMEASURED"
    market = np.array([0.01, -0.02, 0.03, 0.01])
    strategy = 2 * market + 0.001
    attr = return_attribution(strategy, market, execution_costs=[0.0001] * 4)
    assert attr["beta"] == pytest.approx(2.0)
    assert attr["execution_pnl"] == pytest.approx(-0.0004)


def test_latency_regime_allocation_and_model_selection() -> None:
    latency = monetisation_latency(
        {"discovered": 0, "tested": 10, "validated": 20, "fill": 100},
        edge_bps=20,
        half_life_seconds=100,
    )
    assert latency["edge_retained"] == pytest.approx(0.5)
    assert latency["latency_regret_bps"] == pytest.approx(10)
    assert (
        monetisation_latency({"fill": 1}, edge_bps=1, half_life_seconds=1)["status"] == "UNMEASURED"
    )
    alloc = regime_conditional_allocation(
        {"on": 0.75, "off": 0.25},
        {"carry": {"on": 0.03, "off": -0.01}, "cash": {"on": 0.0, "off": 0.0}},
    )
    assert alloc["weights"]["carry"] == 1.0
    assert regime_conditional_allocation({"on": 0.7}, {})["status"] == "UNMEASURED"
    selected = regime_model_selection(
        {
            "markov": {"oos_elog": 0.05, "parameters": 5},
            "hsmm": {"oos_elog": 0.052, "parameters": 20},
        }
    )
    assert selected["selected"] == "markov"
    assert regime_model_selection({})["status"] == "UNMEASURED"
