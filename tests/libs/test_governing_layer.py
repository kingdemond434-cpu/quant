"""THE GOVERNING LAYER -- estimates, allocation, and the portfolio law.

WHAT THESE DEFEND. The directive is written in the language of derivatives: retire when
ΔÊ[log W] < 0, allocate to argmax ΔÊ[log W]/ΔR, suspend a law that fails to contribute. Read
literally those are arithmetic on observable quantities. They are not -- every one is a posterior
estimate from a handful of observations -- and a system that implements them literally will
retire useful modules on noise, churn its allocation every cycle toward whatever got lucky, and
report precision it does not have.

So the load-bearing tests below are about REFUSING TO DECIDE when the evidence cannot support a
decision, and about the two places where that refusal must NOT apply:

  * idle capacity with positive-return work waiting is a failure, not prudence;
  * a subsystem ranked fourth forever is being permanently deprived by a rule that believes it is
    merely ordering, and no single cycle's argmax can see that about itself.
"""

from __future__ import annotations

import pytest

from libs.doctrine.allocate import (
    STARVATION_CYCLES,
    Action,
    Ledger,
    allocate,
    bottleneck_expansion,
    elasticity_shift,
    meta_learning_rate,
)
from libs.doctrine.estimate import (
    LAMBDA_MAX,
    LAMBDA_MIN,
    MIN_N_FOR_ACTION,
    Estimate,
    adjusted,
    better,
    retirement_verdict,
    uncertainty_penalty,
)
from libs.doctrine.portfolio_law import (
    coexistence_verdict,
    concentration_cap,
    deploy_or_wait,
    dynamic_risk_budget,
    marginal_contribution,
    portfolio_entropy,
    robust_kelly,
    significance_gate,
)

# ============================================================ estimates: the hat


def test_a_module_is_not_retired_on_a_point_estimate_below_zero() -> None:
    """THE DIRECTIVE'S OWN AMENDMENT. Roughly half of everything neutral reads negative on any
    given cycle; a desk retiring on that churns through its own infrastructure while believing
    it is optimising."""
    v = retirement_verdict(Estimate(-0.01, se=0.02, n=20, label="fence"))
    assert v["verdict"] == "KEEP"
    assert "SIGNIFICANT evidence against" in v["action"]


def test_a_significantly_negative_module_is_retired() -> None:
    assert retirement_verdict(Estimate(-0.10, se=0.02, n=20))["verdict"] == "RETIRE"


def test_insufficient_evidence_is_a_third_verdict_not_a_default_keep() -> None:
    """Collapsing it into KEEP or RETIRE loses the one fact that should drive the next action:
    go and measure it."""
    v = retirement_verdict(Estimate(-0.5, se=0.4, n=MIN_N_FOR_ACTION - 1))
    assert v["verdict"] == "INSUFFICIENT-EVIDENCE"
    assert "instrument it" in v["action"]


def test_two_indistinguishable_options_return_no_winner() -> None:
    """Forcing a winner between statistically identical options is how a desk churns: it
    reallocates every cycle on noise and books the churn as responsiveness."""
    assert better(Estimate(0.05, 0.03, 20), Estimate(0.06, 0.03, 20)) is None


def test_a_precise_smaller_edge_beats_a_noisy_larger_one() -> None:
    """THE REORDERING A POINT-ESTIMATE RANKING GETS EXACTLY WRONG, in two steps.

    0.05 +- 0.005 against 0.09 +- 0.06: the raw difference is 0.04 against a joint standard
    error of 0.06, so `better` correctly refuses to call it -- the larger number is NOT
    significantly larger, and a ranker that handed it the budget would be acting on noise. The
    uncertainty-adjusted scores are what the tie-break then reads, and they prefer the bankable
    one. Both halves matter: refusing to decide on the difference, and still having an ordering
    when a decision has to be made anyway."""
    a, b = Estimate(0.05, 0.005, 30), Estimate(0.09, 0.06, 30)
    assert better(a, b) is None, "0.04 apart with 0.06 of joint noise is not a winner"
    assert adjusted(a, brier=0.1) > adjusted(b, brier=0.1)
    assert better(Estimate(0.20, 0.005, 30), b) is not None, (
        "an edge that IS significantly larger must still be callable")


def test_poor_calibration_raises_the_uncertainty_penalty() -> None:
    """Not a safety margin bolted on -- the correct posterior response to knowing your own
    estimator is bad."""
    assert uncertainty_penalty(0.02) < uncertainty_penalty(0.20)


def test_unmeasured_calibration_is_penalised_at_the_maximum() -> None:
    """Absence of evidence about your own reliability is not evidence of reliability, and it is
    the one input the desk cannot retroactively fake."""
    assert uncertainty_penalty(None) == LAMBDA_MAX


def test_the_penalty_is_bounded_at_both_ends() -> None:
    """Zero would size as though the point estimate were the truth. Unbounded means never acting,
    and a guaranteed zero growth rate is the WORST outcome under a log objective, not the safest."""
    assert uncertainty_penalty(0.0) == LAMBDA_MIN
    assert uncertainty_penalty(1.0) == LAMBDA_MAX


# ============================================================ allocation: VIP, no starvation


def _act(name, val, se, cost, ig=0.0):
    return Action(name, Estimate(val, se, 30), cost=cost, information_gain=ig)


def test_the_global_optimum_enters_first_and_it_is_ranked_by_density() -> None:
    """ΔÊ[log W]/ΔR, not total contribution: a large action that eats the whole budget for a
    mediocre rate loses to several efficient ones."""
    r = allocate([_act("big", 0.10, 0.01, 100), _act("eff", 0.04, 0.005, 10)], budget=110)
    assert r["vip"] == "eff"
    assert set(r["funded"]) == {"eff", "big"}


def test_everyone_else_expands_into_the_residual_rather_than_waiting() -> None:
    """The half of the VIP rule that usually gets dropped. Priority decides order; after the
    global optimum is secured nobody waits unnecessarily."""
    acts = [_act(f"s{i}", 0.05 - i * 0.005, 0.002, 10) for i in range(5)]
    r = allocate(acts, budget=50)
    assert len(r["funded"]) == 5
    assert r["residual_budget"] == 0


def test_idle_capacity_with_work_waiting_is_reported_as_a_failure() -> None:
    """Under-utilisation is not prudence. Nothing bad visibly happens when it occurs, which is
    exactly why it has to be reported rather than noticed."""
    r = allocate([_act("cheap", 0.05, 0.002, 10), _act("huge", 0.9, 0.01, 1000)], budget=100)
    assert r["residual_budget"] == 90
    assert "IDLE CAPACITY" in r["failure"]


def test_a_perpetually_fourth_ranked_subsystem_is_eventually_promoted() -> None:
    """THE ONE A PURE ARGMAX CANNOT SEE ABOUT ITSELF: every individual cycle looked correct while
    the same positive contributor was never once funded."""
    led = Ledger()
    acts = [_act("winner", 0.20, 0.001, 10), _act("neglected", 0.01, 0.001, 10)]
    for _ in range(STARVATION_CYCLES):
        allocate(acts, budget=10, ledger=led)
    assert "neglected" in led.starved()
    r = allocate(acts, budget=10, ledger=led)
    assert r["vip"] == "neglected"
    assert "STARVED" in r["starvation_alert"]


def test_a_deferred_action_is_named_as_deferred_not_defunded() -> None:
    r = allocate([_act("a", 0.2, 0.01, 10), _act("b", 0.1, 0.01, 10)], budget=10)
    assert r["deferred"][0]["name"] == "b"
    assert "DEFERRED, not defunded" in r["deferred"][0]["reason"]


def test_non_positive_contributions_are_rejected_rather_than_ranked_last() -> None:
    r = allocate([_act("dead", -0.01, 0.001, 1)], budget=100)
    assert r["funded"] == [] and r["rejected"][0]["name"] == "dead"


# ============================================================ bottleneck expansion


def test_a_backlog_expands_conversion_and_never_throttles_discovery() -> None:
    """An unconverted hypothesis costs storage; a hypothesis never generated costs whatever it
    would have been worth, permanently. Only one of those shows up on a chart."""
    r = bottleneck_expansion(discovery_rate=1000, conversion_rate=40)
    assert r["bottleneck"] == "conversion"
    assert "EXPAND CONVERSION" in r["target"]
    assert "throttling discovery" in r["forbidden"]


def test_idle_conversion_capacity_expands_discovery() -> None:
    r = bottleneck_expansion(discovery_rate=10, conversion_rate=100)
    assert r["bottleneck"] == "discovery"
    assert "EXPAND DISCOVERY" in r["target"]
    assert r["forbidden"] == ""


def test_every_discovery_ends_somewhere_and_none_is_discarded_for_capacity() -> None:
    assert "never discarded for want of conversion capacity" in bottleneck_expansion(5, 5)["note"]


# ============================================================ elasticity


def test_saturation_shifts_more_resource_never_all_of_it() -> None:
    """Wholesale reallocation drives the receiving subsystem straight into its own saturation
    and destroys the sender's ability to recover. Gradual tracks a moving optimum."""
    r = elasticity_shift({"a": Estimate(0.02, 0.001, 30), "b": Estimate(0.05, 0.001, 30)},
                         {"a": -0.01, "b": 0.0})
    assert r["shift_from"] == ["a"] and r["shift_to"] == ["b"]
    assert "shift MORE, never ALL" in r["note"]


def test_universal_saturation_names_total_resource_as_the_constraint() -> None:
    """When everything is saturating the answer is to acquire more, not to reshuffle -- P7 read
    through the elasticity lens."""
    r = elasticity_shift({"a": Estimate(0.02, 0.001, 30)}, {"a": -0.01})
    assert "TOTAL RESOURCE" in r["blocked"]


# ============================================================ meta-learning rate


def test_the_improvement_rate_is_measured_with_its_own_uncertainty() -> None:
    """A desk at 0.02 improving by 0.001/cycle overtakes one sitting at 0.05 flat."""
    r = meta_learning_rate([0.010, 0.012, 0.014, 0.016, 0.018, 0.020])
    assert r["improving"] and r["rate"] == pytest.approx(0.002, abs=1e-6)


def test_a_flat_desk_is_told_its_capability_is_not_compounding() -> None:
    """A first-order finding about the meta-layer, not a rounding error."""
    r = meta_learning_rate([0.02, 0.019, 0.021, 0.020, 0.0205, 0.0195])
    assert not r["improving"]
    assert "not currently compounding" in r["note"]


def test_a_rate_from_two_points_is_refused() -> None:
    assert meta_learning_rate([0.01, 0.02])["state"] == "INSUFFICIENT-HISTORY"


# ============================================================ portfolio law


def test_kelly_shrinkage_is_multiplicative_across_uncertainty_sources() -> None:
    """An edge measured over a short sample AND in one regime AND through an unproven execution
    path is uncertain three times over; an additive penalty would let two strong factors mask a
    fatal third."""
    r = robust_kelly(1.0, sharpe_ann=2.3, n_days=40,
                     regime_stability=0.8, execution_confidence=0.5, model_confidence=0.9)
    g = r["gammas"]
    assert r["gamma"] == pytest.approx(g["estimation"] * 0.8 * 0.5 * 0.9, rel=1e-3)
    assert r["fraction"] < 0.2


def test_the_binding_uncertainty_is_named_because_it_names_the_work() -> None:
    """If gamma_execution is the binding term the fix is a week of execution work, not more
    backtesting -- a single blended shrink factor hides which week to spend."""
    r = robust_kelly(1.0, sharpe_ann=3.0, n_days=400, execution_confidence=0.3)
    assert r["binding_uncertainty"] == "execution"


def test_shrinkage_is_stated_as_a_growth_argument_not_a_safety_one() -> None:
    """Anyone proposing to remove it is proposing to LOWER expected growth, and the note has to
    say so or it will be argued about as though it were caution."""
    note = robust_kelly(1.0, sharpe_ann=2.0, n_days=100)["note"]
    assert "NOT conservatism" in note and "HIGHER expected log growth" in note


def test_an_indistinguishable_edge_is_allocated_zero_not_small() -> None:
    """"Size it small to keep learning" has a real answer: that is what the research clock is
    for, and it does not risk capital on an edge that might be nothing."""
    r = significance_gate(mu=0.01, se=0.02)
    assert r["allocate"] is False
    assert "ZERO, not small" in r["note"]
    assert significance_gate(mu=0.10, se=0.02)["allocate"] is True


def test_the_concentration_cap_tightens_itself_in_an_unstable_regime() -> None:
    assert concentration_cap(1.0) == 0.5
    assert concentration_cap(0.4) == 0.2


def test_a_sleeve_is_judged_by_marginal_contribution_not_standalone_record() -> None:
    """Ranking sleeves by their own Sharpe builds a book of correlated winners, which is one bet
    wearing five names."""
    r = marginal_contribution(Estimate(0.080, 0.004, 60), Estimate(0.060, 0.004, 60),
                              "discretionary")
    assert r["significant_positive"]
    bad = marginal_contribution(Estimate(0.050, 0.002, 60), Estimate(0.070, 0.002, 60), "sleeve3")
    assert bad["significant_negative"]
    assert "orthogonalise before retiring" in bad["note"]


def test_harmful_coexistence_orders_separation_before_retirement() -> None:
    """Retiring a sleeve recovers the interaction loss AND gives up the strategy -- strictly
    worse than separation whenever separation is available."""
    v = coexistence_verdict({"systematic": {"significant_positive": True},
                             "discretionary": {"significant_negative": True}})
    assert v["verdict"] == "COEXISTENCE HARMFUL"
    assert v["remedy_order"][0] == "execution separation"
    assert v["remedy_order"][-1] == "retirement"


def test_non_destructive_coexistence_runs_both_families_at_full_size() -> None:
    v = coexistence_verdict({"systematic": {"significant_positive": True},
                             "discretionary": {"significant_positive": True}})
    assert v["verdict"] == "COEXISTENCE NON-DESTRUCTIVE"
    assert "maximum feasible size" in v["note"]


def test_portfolio_entropy_counts_effective_bets_not_sleeves() -> None:
    """Concentration into one structural regime is the exposure a strong backtest is least able
    to warn about: every sleeve looks different and they all stop working the same morning."""
    even = portfolio_entropy({"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25})
    lopsided = portfolio_entropy({"a": 0.97, "b": 0.01, "c": 0.01, "d": 0.01})
    assert even["effective_bets"] == pytest.approx(4.0, abs=0.01)
    assert lopsided["effective_bets"] < 1.5
    assert lopsided["n_sleeves"] == 4, "four sleeves, barely more than one bet"


def test_the_risk_budget_names_its_binding_component() -> None:
    """A static limit is not the safe choice -- it is the choice that is wrong all the time, in
    whichever direction the world happens to have moved."""
    r = dynamic_risk_budget(calibration_brier=0.05, regime_stability=0.9,
                            portfolio_correlation=0.2, execution_quality=0.35)
    assert r["binding"] == "execution"
    assert 0.0 < r["multiplier"] < 1.0
    assert "never raises anything through a survival rail" in r["note"]


def test_waiting_is_priced_rather_than_treated_as_free() -> None:
    """Holding cash is a short position on every edge the desk owns, and nothing visibly happens
    while waiting -- which is exactly why the cost has to be stated."""
    r = deploy_or_wait(Estimate(0.05, 0.008, 40), Estimate(0.0, 0.0, 40), execution_cost=0.005)
    assert r["deploy"]
    slow = deploy_or_wait(Estimate(0.01, 0.02, 40), Estimate(0.0, 0.0, 40), execution_cost=0.008)
    assert not slow["deploy"]
    assert "book the cost" in slow["note"]


def test_execution_cost_is_subtracted_from_the_deploy_side() -> None:
    """Slippage, impact and capacity limits are real reductions in the edge, not an
    administrative fee bolted on afterwards."""
    cheap = deploy_or_wait(Estimate(0.05, 0.005, 40), Estimate(0.0, 0.0, 40), 0.0)
    dear = deploy_or_wait(Estimate(0.05, 0.005, 40), Estimate(0.0, 0.0, 40), 0.04)
    assert cheap["gap"] > dear["gap"]
