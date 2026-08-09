"""BEHAVIORAL tests for the Maximum Economic Frontier.

Six properties, each pinned to the specific failure it prevents:

    1  opportunity cost enters ONCE, through the shadow prices
    2  uncertainty has a price -- a loud guess cannot outrank a calibrated estimate
    3  feasibility is a FILTER, so no estimate can outbid the risk kernel
    4  a bundle can beat the greedy single
    5  frontier regret is measured against what was KNOWN, not hindsight
    6  a proposer cannot improve its priority by improving its own estimate
"""

from __future__ import annotations

import pytest

from libs.research.frontier import (
    INFEASIBLE_REASONS,
    REGRET_CATEGORIES,
    RESOURCES,
    Action,
    Bundle,
    ResourcePrices,
    best_bundle,
    calibration,
    economic_surplus,
    feasible,
    frontier_regret,
    rank,
    risk_adjusted,
    summarise,
)

PRICES = ResourcePrices({"capital": 0.01, "compute": 0.001, "engineering_time": 0.002})


def _a(**kw) -> Action:
    base: dict[str, object] = {"action_id": "a", "category": "research",
                               "elogw_mean": 0.05, "elogw_sigma": 0.01, "p_success": 1.0}
    base.update(kw)
    return Action(**base)  # type: ignore[arg-type]


# ======================================================= 3. feasibility is a filter, not a score

def test_an_infeasible_action_is_removed_before_optimisation() -> None:
    """THE PROPERTY THE RISK KERNEL DEPENDS ON. A sufficiently optimistic estimate must never be
    able to outbid a survival constraint, and it cannot outbid something it never competes with."""
    huge = _a(action_id="tempting", elogw_mean=999.0, elogw_sigma=0.001,
              infeasible_reason="SURVIVAL_BREAKING")
    ok, removed = feasible([huge, _a(action_id="ordinary")])
    assert [x.action_id for x in ok] == ["ordinary"]
    assert removed == [{"action_id": "tempting", "reason": "SURVIVAL_BREAKING"}]
    rows = rank([huge, _a(action_id="ordinary")], PRICES)
    assert all(r["action_id"] != "tempting" for r in rows), (
        "an infeasible action received a score and entered the ranking")


def test_an_unknown_infeasibility_reason_cannot_be_recorded() -> None:
    with pytest.raises(ValueError, match="infeasible_reason must be"):
        _a(infeasible_reason="SEEMS_RISKY")
    assert "PRIVILEGE_VIOLATION" in INFEASIBLE_REASONS


def test_an_unknown_resource_cannot_be_consumed() -> None:
    with pytest.raises(ValueError, match="unknown resource"):
        _a(resources={"goodwill": 1.0})
    assert "llm_tokens" in RESOURCES and "engineering_time" in RESOURCES


# ==================================================== 2. uncertainty has a price

def test_a_loud_guess_does_not_outrank_a_calibrated_estimate() -> None:
    """Same shape, different posterior width. If the wide one wins, the module ranks point
    estimates and the loudest guess takes the day."""
    tight = _a(action_id="tight", elogw_mean=0.05, elogw_sigma=0.005)
    loose = _a(action_id="loose", elogw_mean=0.06, elogw_sigma=0.05)
    rows = rank([loose, tight], PRICES)
    assert rows[0]["action_id"] == "tight", rows


def test_a_large_enough_edge_still_wins_despite_uncertainty() -> None:
    """This is NOT conservatism. An uncertain action with a big enough edge must still be able to
    win, or the frontier becomes a machine for doing nothing."""
    bold = _a(action_id="bold", elogw_mean=0.40, elogw_sigma=0.10)
    safe = _a(action_id="safe", elogw_mean=0.05, elogw_sigma=0.005)
    rows = rank([bold, safe], PRICES)
    assert rows[0]["action_id"] == "bold"


def test_an_estimate_with_no_posterior_width_cannot_be_ranked() -> None:
    v, why = risk_adjusted(_a(elogw_sigma=0.0))
    assert v is None
    assert "UNMEASURED" in why and "the loudest guess wins the day" in why


def test_unmeasured_actions_sort_last() -> None:
    rows = rank([_a(action_id="guess", elogw_sigma=0.0),
                 _a(action_id="known", elogw_mean=0.001, elogw_sigma=0.0001)], PRICES)
    assert rows[0]["action_id"] == "known"


def test_success_probability_is_separate_from_magnitude() -> None:
    lottery = _a(action_id="lottery", elogw_mean=1.0, elogw_sigma=0.05, p_success=0.02)
    steady = _a(action_id="steady", elogw_mean=0.05, elogw_sigma=0.005, p_success=1.0)
    rows = rank([lottery, steady], PRICES)
    assert rows[0]["action_id"] == "steady"


# ==================================================== 1. opportunity cost enters once

def test_resource_use_is_charged_through_shadow_prices_only() -> None:
    """Charging a separate generic opportunity cost on top would double-count and would
    systematically kill cheap high-value actions in favour of ones nobody priced."""
    a = _a(resources={"capital": 2.0}, direct_cost=0.001)
    s, why = economic_surplus(a, PRICES)
    assert s is not None
    # (0.05 - 0.01) * 1 * 1 - (2.0 * 0.01) - 0.001
    assert s == pytest.approx(0.04 - 0.02 - 0.001)
    assert "shadow-priced resources" in why


def test_an_unpriced_resource_is_named_rather_than_treated_as_free() -> None:
    a = _a(resources={"llm_tokens": 1e6})
    _, why = economic_surplus(a, PRICES)
    assert "UNPRICED resources consumed" in why
    assert "look free here and are not" in why
    assert "llm_tokens" in str(summarise([a], PRICES)["headline"]) or \
        "llm_tokens" in str(summarise([a], PRICES)["unpriced_resources"])


def test_a_zero_price_means_the_resource_is_currently_abundant_not_ignored() -> None:
    """Idle CPU during a research bottleneck is a different economic object from idle CPU when no
    useful experiment exists, and only the shadow price can tell them apart."""
    scarce = ResourcePrices({"compute": 0.01})
    abundant = ResourcePrices({"compute": 0.0})
    a = _a(resources={"compute": 100.0})
    assert economic_surplus(a, abundant)[0] > economic_surplus(a, scarce)[0]   # type: ignore[operator]


# ==================================================== opportunity decay / urgency

def test_an_opportunity_that_expires_before_delivery_is_a_loss_not_a_slow_win() -> None:
    fast = _a(action_id="fast", time_to_value_days=1.0, opportunity_half_life_days=10.0)
    slow = _a(action_id="slow", time_to_value_days=40.0, opportunity_half_life_days=5.0)
    rows = rank([slow, fast], PRICES)
    assert rows[0]["action_id"] == "fast"
    _, why = risk_adjusted(slow)
    assert "MOST OF THIS OPPORTUNITY EXPIRES BEFORE DELIVERY" in why


def test_information_value_counts_even_with_no_immediate_pnl() -> None:
    """An action can be worth doing purely because it turns an UNMEASURED into a number."""
    plain = _a(action_id="plain")
    informative = _a(action_id="informative", information_value=0.02)
    rows = rank([plain, informative], PRICES)
    assert rows[0]["action_id"] == "informative"


# ==================================================== 4. bundles beat greedy singles

def test_a_bundle_can_beat_the_single_best_action() -> None:
    """Buy the dataset / build the feature / run the experiment each look weak alone."""
    a = _a(action_id="dataset", elogw_mean=0.011, elogw_sigma=0.01)
    b = _a(action_id="feature", elogw_mean=0.011, elogw_sigma=0.01)
    sel = best_bundle([a, b], [Bundle("combo", ("dataset", "feature"), synergy=0.05,
                                      rationale="the feature is useless without the dataset")],
                      PRICES)
    assert sel["selected"]["bundle_id"] == "combo"       # type: ignore[index]
    assert sel["bundle_beats_greedy"] is True


def test_a_greedy_single_is_evaluated_as_a_one_element_bundle() -> None:
    """So the selection can only ever match or beat a greedy pick, never lose to it."""
    a = _a(action_id="strong", elogw_mean=0.5, elogw_sigma=0.01)
    b = _a(action_id="weak", elogw_mean=0.001, elogw_sigma=0.0005)
    sel = best_bundle([a, b], [Bundle("combo", ("strong", "weak"), synergy=-0.4)], PRICES)
    assert sel["selected"]["bundle_id"] == "single::strong"   # type: ignore[index]
    assert sel["bundle_beats_greedy"] is False


def test_an_unaffordable_bundle_is_reported_not_silently_dropped() -> None:
    """'We could not afford it' and 'it was not worth it' are different findings."""
    a = _a(action_id="expensive", elogw_mean=1.0, elogw_sigma=0.01,
           resources={"capital": 1000.0})
    sel = best_bundle([a], [], PRICES, budget={"capital": 10.0})
    cands = sel["candidates"]
    assert isinstance(cands, list)
    assert any(c["over_budget"] for c in cands)
    assert sel["selected"] is None
    assert "different findings" in str(sel["note"])


# ==================================================== 6. anti-Goodhart calibration

def test_a_proposer_with_a_record_of_optimism_is_discounted_by_its_record() -> None:
    hist = {"optimist": (1.0, 0.2), "realist": (1.0, 1.0)}
    m_opt, why = calibration("optimist", hist)
    m_real, _ = calibration("realist", hist)
    assert m_opt == pytest.approx(0.2)
    assert m_real == pytest.approx(1.0)
    assert "requires realised descendants, not better estimates" in why


def test_an_unproven_proposer_is_neutral_rather_than_penalised() -> None:
    m, why = calibration("newcomer", {})
    assert m == 1.0
    assert "freeze the exploration" in why


def test_calibration_actually_changes_the_ranking() -> None:
    hist = {"optimist": (1.0, 0.1)}
    a = _a(action_id="from_optimist", elogw_mean=0.10, elogw_sigma=0.01, proposer="optimist")
    b = _a(action_id="from_nobody", elogw_mean=0.05, elogw_sigma=0.01)
    rows = rank([a, b], PRICES, history=hist)
    assert rows[0]["action_id"] == "from_nobody", (
        "a proposer with a 10x optimism record still won -- calibration is not applied")


# ==================================================== 5. frontier regret

def test_frontier_regret_is_the_gap_from_the_best_KNOWN_set() -> None:
    r = frontier_regret(best_known_surplus=0.08, selected_surplus=0.03,
                        by_category={"CAPITAL_REGRET": 0.04, "LATENCY_REGRET": 0.01})
    assert r["FRONTIER_REGRET"] == pytest.approx(0.05)
    assert "CAPITAL_REGRET" in str(r["headline"])
    assert set(REGRET_CATEGORIES) >= set(r["by_category"])   # type: ignore[arg-type]


def test_regret_is_never_negative_and_zero_is_stated_plainly() -> None:
    r = frontier_regret(best_known_surplus=0.01, selected_surplus=0.05)
    assert r["FRONTIER_REGRET"] == 0.0
    assert "no frontier regret" in str(r["headline"])


def test_regret_is_measured_against_knowledge_not_hindsight() -> None:
    r = frontier_regret(best_known_surplus=0.0, selected_surplus=0.0)
    assert "never against hindsight" in str(r["note"])
    assert "unimprovable and therefore ignored" in str(r["note"])


def test_an_unrecognised_regret_category_is_surfaced_not_silently_dropped() -> None:
    r = frontier_regret(best_known_surplus=1.0, selected_surplus=0.0,
                        by_category={"VIBES_REGRET": 1.0})
    assert r["unrecognised_categories"] == ["VIBES_REGRET"]


# ==================================================== the report

def test_the_worked_example_from_the_mandate_comes_out_right() -> None:
    """'If deploying a validated survivor has greater marginal economic value than building
    another research module: DEPLOY.'"""
    deploy = Action("deploy_survivor", "capital", elogw_mean=0.05, elogw_sigma=0.01,
                    p_success=0.8, resources={"capital": 1.0}, proposer="ladder")
    build = Action("build_module", "research", elogw_mean=0.06, elogw_sigma=0.05,
                   p_success=0.4, resources={"engineering_time": 8.0, "compute": 100.0},
                   time_to_value_days=10, opportunity_half_life_days=5, proposer="claude")
    rows = rank([build, deploy], PRICES)
    assert rows[0]["action_id"] == "deploy_survivor"
    assert float(str(rows[1]["surplus"])) < 0


def test_an_empty_frontier_says_the_day_was_chosen_by_something_else() -> None:
    rep = summarise([], PRICES)
    assert "UNMEASURED" in str(rep["headline"])
    assert "chosen by something other than expected marginal contribution" in str(rep["headline"])


def test_the_note_states_all_three_invariants() -> None:
    rep = summarise([_a()], PRICES)
    note = str(rep["note"])
    assert "FILTER applied before optimisation" in note
    assert "enters ONCE" in note
    assert "realised evidence dominates" in note
