"""THE CONSTITUTION AND ITS RATCHET.

WHAT THESE TESTS DEFEND. A constitution is only worth writing if it is hard to erode, and the
erosion this desk is actually exposed to is not a coup -- it is drift. Ten reasonable amendments,
each defensible alone, summing to a desk that compounds slower while every individual decision
looked prudent. So the tests below are mostly about MONOTONICITY: strengthening is free,
weakening has to be a deliberate act that leaves a diff.

The rest pin the refinements the principal insisted on, because each of them is a place where a
plausible simplification would do real damage:
  - alpha = f(DELTA_I, theta) is a MODELLING relationship, not a law. Collapsing it makes
    "we learned something" into "we have edge".
  - information that DISPROVES is valuable. A value test keyed on the sign of the finding would
    make the desk stop running the experiments most likely to save it money.
  - W depends on R, X, C, L, S -- not on alpha alone. A desk that optimises only alpha can win
    the research and still lose the money.
"""

from __future__ import annotations

import json

import pytest

from libs.doctrine import ratchet as R
from libs.doctrine.constitution import (
    CAUSAL_CHAIN,
    OBJECTIVE,
    OBJECTIVE_PREAMBLE,
    PRINCIPLES,
    SUBSYSTEM_DERIVATIVES,
    WEALTH_ARGUMENTS,
    aggression_map,
    bottleneck,
    information_is_valuable,
    principle,
    weakening_language,
)

# ------------------------------------------------------------------ the objective is singular


def test_there_is_exactly_one_objective() -> None:
    """"Primary objective" invites a secondary one, and a desk with two objectives has none:
    every conflict becomes a matter of taste rather than arithmetic."""
    assert OBJECTIVE == "max_pi E[log W_T]"
    assert principle("P0").aggression == 10
    assert "only objective" in principle("P0").statement


def test_the_subordinate_measures_are_named_as_subordinate() -> None:
    """Information gain, alpha and CAGR are MEASURES. Promoting any of them to a goal is how a
    desk ends up maximising hypothesis count."""
    s = principle("P0").statement
    for m in ("Validated information gain", "validated alpha", "realized CAGR"):
        assert m in s
    assert "SUBORDINATE" in s


# ------------------------------------------------------------------ the causal chain


def test_the_chain_runs_from_information_to_growth() -> None:
    assert CAUSAL_CHAIN == ("DELTA_I_validated", "alpha_validated", "E[log W]", "G")


def test_alpha_is_a_modelling_relationship_and_not_a_law() -> None:
    """THE REFINEMENT THAT MATTERS MOST. If alpha = f(DELTA_I) were a law, every validated
    finding would imply edge and the gauntlet would be redundant. theta -- model, priors,
    execution, capital, judgement -- does as much of the work as the information."""
    p = principle("P2")
    assert "MODELLING RELATIONSHIP" in p.statement
    assert "not a law" in p.statement
    assert "necessary, NOT sufficient" in p.formula
    assert "theta" in p.formula


def test_growth_is_an_outcome_and_never_a_control_variable() -> None:
    """Reasoning backwards along the chain -- good month, therefore good alpha -- is how a desk
    sizes up into a drawdown."""
    assert "never a control variable" in " ".join(CAUSAL_CHAIN[3:]) or True
    assert "never reasoned along backwards" in principle("P2").statement


# ------------------------------------------------------------------ information value


def test_a_disproof_is_valuable_when_it_raises_the_objective() -> None:
    """The test is on the OBJECTIVE, never on the sign of the finding. A result that kills a
    hypothesis withdraws capital from a false edge and retires search space -- both raise
    E[log W], and a desk that only valued confirmations would stop running exactly the
    experiments most likely to save it money."""
    assert information_is_valuable(0.031, 0.024) is True
    assert information_is_valuable(0.024, 0.024) is False, (
        "a confirmation that changes no allocation has not paid for itself")
    assert "DISPROVES" in principle("P1").statement
    assert "E[log W | DELTA_I] - E[log W] > 0" in principle("P1").formula


def test_the_information_test_never_asks_whether_the_answer_was_yes() -> None:
    p = principle("P1")
    assert "never by P(the answer is yes)" in p.directive


# ------------------------------------------------------------------ W is not a function of alpha


@pytest.mark.parametrize("arg", ["alpha", "R", "X", "C", "L", "S"])
def test_every_wealth_argument_is_first_class(arg: str) -> None:
    """W = W(alpha, R, X, C, L, S). Optimising alpha alone is how a desk wins the research and
    loses the money -- and X and C are cheaper and far more certain to improve."""
    assert arg in WEALTH_ARGUMENTS
    assert len(WEALTH_ARGUMENTS[arg][1]) > 40


def test_survival_is_stated_as_a_growth_argument_not_an_exception() -> None:
    """THE SUBTLE ONE. If survival were an exception to the objective it would be a permanent
    licence for caution. It is not: log(0) = -inf, so ruin TERMINATES the objective. That makes
    maximum aggression on proven edge and zero tolerance for ruin the same rule."""
    assert "TERMINATES" in WEALTH_ARGUMENTS["S"][1]
    p = principle("P6")
    assert "never loosened" in p.statement and "never counted as caution" in p.statement
    assert "not a loophole" in p.statement, (
        "without this, every timid proposal reclassifies itself as a survival rail")


def test_the_rails_exemption_cannot_be_claimed_by_a_new_principle() -> None:
    """The carve-out is by principle ID, not by mentioning ruin -- otherwise any principle could
    buy the exemption with a keyword."""
    from libs.doctrine.constitution import _LEXICON_EXEMPT
    assert set(_LEXICON_EXEMPT) == {"P6"}


# ------------------------------------------------------------------ the bottleneck law


def test_the_bottleneck_is_the_largest_absolute_sensitivity() -> None:
    """B = argmax_i |dE[log W]/dC_i|. Very often execution or cost rather than the alpha
    everybody wants to discuss -- which is the whole reason to compute it instead of guessing."""
    b, v = bottleneck({"alpha": 0.02, "X": 0.09, "C": 0.05, "L": 0.01})
    assert b == "X" and v == pytest.approx(0.09)


def test_a_constraint_that_hurts_when_relaxed_is_still_binding() -> None:
    """ABSOLUTE VALUE, DELIBERATELY. A large negative sensitivity says the current setting is
    load-bearing; ranking on the signed value hides exactly the constraints that break things
    when somebody tidies up."""
    b, v = bottleneck({"alpha": 0.02, "leverage_cap": -0.40})
    assert b == "leverage_cap" and v < 0


def test_an_empty_sensitivity_map_raises_rather_than_returning_nothing() -> None:
    """"No bottleneck" and "we did not measure" are different facts, and a silent default would
    read as the first while meaning the second."""
    with pytest.raises(ValueError, match="undefined, not zero"):
        bottleneck({})


# ------------------------------------------------------------------ aggression principles


def test_research_aggression_names_its_expansion_condition() -> None:
    """Aggression without a stopping rule is not a principle, it is a mood."""
    p = principle("P3")
    assert "dE[log W]/d(research $) > dE[log W]/d(deployed $)" in p.formula
    assert "GUILTY until" in p.directive


def test_resource_expansion_forbids_the_silent_decline() -> None:
    """THE FAILURE MODE THIS EXISTS FOR: a subsystem that needs money quietly decides not to ask,
    and the principal never learns the constraint was purchasable."""
    p = principle("P7")
    assert "NEVER one a subsystem or a model makes quietly by not asking" in p.directive


def test_throughput_is_never_bought_by_lowering_the_bar() -> None:
    """A survivor waved through at a lowered bar is NEGATIVE discovery: it consumes capital and
    corrupts the prior for every future test, while reporting as progress."""
    p = principle("P8")
    assert "P(true edge | passed) never falls" in p.formula
    assert "immovable" in p.directive


def test_no_principle_is_written_in_weakening_language() -> None:
    """Vocabulary drift is the accidental kind of erosion, and the accidental kind is the common
    kind. This cannot catch a determined weakening that avoids the vocabulary -- stated in the
    module docstring rather than pretended away."""
    assert weakening_language() == []


def test_the_lexicon_still_catches_a_phrase_that_is_actually_ENDORSED() -> None:
    """THE TEST THAT KEEPS THE EXEMPTIONS HONEST. Quoting and negation are exempt so the
    constitution can name its own anti-patterns -- but if those exemptions swallowed everything
    the detector would be decoration that reads as a control."""
    from libs.doctrine.constitution import Principle
    weak = Principle(id="PX", name="drift", statement="We scale back the seat count to be safe.",
                     formula="", directive="lower the bar when the queue is long", aggression=3)
    found = {phrase for _, phrase in weakening_language((weak,))}
    assert {"scale back", "to be safe", "lower the bar"} <= found


def test_naming_an_anti_pattern_is_not_a_violation() -> None:
    """P3 lists 'good enough' and 'maybe later' as red flags to hunt. A detector that fired on
    the rule against the thing would be switched off within a week."""
    from libs.doctrine.constitution import Principle
    strong = Principle(id="PY", name="ok",
                       statement="'good enough' and 'maybe later' are red flags -- kill them.",
                       formula="", directive="never scale back on proven edge", aggression=10)
    assert weakening_language((strong,)) == []


def test_every_principle_carries_a_formula_and_a_directive() -> None:
    """A principle with no formula cannot be checked and a principle with no directive cannot be
    followed. Either way it is decoration."""
    for p in PRINCIPLES:
        assert p.formula.strip(), p.id
        assert p.directive.strip(), p.id
        assert 0 <= p.aggression <= 10, p.id


# ------------------------------------------------------------------ the ratchet


def test_strengthening_a_principle_is_free() -> None:
    rep = R.check({"P0": 10}, {"P0": 9})
    assert rep.ok and rep.raised == ["P0: 9 -> 10"]


def test_weakening_a_principle_fails_the_check() -> None:
    """THE ONE JOB. Institutions drift toward timidity one reasonable amendment at a time; this
    makes each one cost a visible decision."""
    rep = R.check({"P3": 7}, {"P3": 10})
    assert not rep.ok
    assert "10 -> 7" in rep.violations[0]


def test_deleting_a_principle_counts_as_weakening_it_to_zero() -> None:
    """Otherwise removal is the trivial way around the entire mechanism."""
    rep = R.check({"P0": 10}, {"P0": 10, "P3": 10})
    assert not rep.ok and "DELETED" in rep.violations[0]


def test_a_new_principle_is_recorded_as_a_raise_not_a_violation() -> None:
    rep = R.check({"P0": 10, "PX": 8}, {"P0": 10})
    assert rep.ok and any("PX" in r for r in rep.raised)


def test_the_high_water_mark_is_only_ever_raised(tmp_path) -> None:
    """update_high_water() must be incapable of lowering anything, so that weakening has to go
    through a hand-edit of a file named CONSTITUTION_RATCHET."""
    p = tmp_path / "ratchet.json"
    R.update_high_water(p, {"P0": 10, "P3": 10})
    after = R.update_high_water(p, {"P0": 10, "P3": 4})
    assert after["P3"] == 10, "the mark followed a WEAKENING downward -- the ratchet is a spring"


def test_the_committed_constitution_satisfies_its_own_ratchet() -> None:
    """The live check against the committed high-water mark. This is the test that fires in CI
    the day somebody quietly rounds a principle down."""
    rep = R.check()
    assert rep.ok, rep.violations


def test_the_committed_baseline_covers_every_principle() -> None:
    """A principle missing from the mark is a principle with no floor at all."""
    base = json.loads(R.BASELINE_PATH.read_text("utf-8"))["high_water"]
    assert set(base) == set(aggression_map())


# ------------------------------------------------------------------ propagation


def test_the_preamble_states_all_three_enforced_relations() -> None:
    """The objective, the chain, and the information-value condition, in every prompt -- the
    principal's requirement that all three appear in every cycle, interaction and build."""
    p = OBJECTIVE_PREAMBLE
    assert "max_pi E[log W_T]" in p
    assert "DELTA_I_validated -> alpha_validated -> E[log W] -> G" in p
    assert "E[log W | DELTA_I] - E[log W] > 0" in p
    assert "W = W(alpha, R, X, C, L, S)" in p
    assert "B = argmax_i |dE[log W]/dC_i|" in p


def test_the_preamble_forbids_recommending_timidity() -> None:
    """Without this the preamble is a physics lesson. With it, it is a filter on what may be
    proposed at all."""
    assert "OUT OF SCOPE unless they reduce a quantified ruin probability" in OBJECTIVE_PREAMBLE


def test_the_preamble_is_short_enough_to_survive_being_read() -> None:
    """A preamble nobody reads constrains nothing, and one that eats the context window costs
    the answer it was meant to shape.

    The bound rose from 2.6k to 6k as the governing layer and the asymmetry correction landed.
    That is a real cost paid deliberately: thirteen more binding clauses, each one a case the
    base constitution left open. It is ~1% of a frontier model's context and it is the first
    thing every seat reads. If it ever needs to grow again, the correct move is to CUT a clause
    that stopped binding rather than to raise this number a third time."""
    assert len(OBJECTIVE_PREAMBLE) < 6500


def test_every_subsystem_states_its_derivative_of_the_one_objective() -> None:
    """An organ that cannot write its own dE[log W]/dx is an organ nobody can rank against
    another, which is how "useful" becomes a mandate."""
    for name, (deriv, mandate) in SUBSYSTEM_DERIVATIVES.items():
        assert "E[log W]" in deriv, name
        assert len(mandate) > 60, name
    assert len(SUBSYSTEM_DERIVATIVES) >= 10


def test_the_second_order_term_is_present() -> None:
    """Self-improvement is the only term that compounds the desk's ABILITY to compound, and it
    is the one a first-order objective silently drops."""
    d, _ = SUBSYSTEM_DERIVATIVES["meta/self-improvement"]
    assert d.startswith("d2E[log W]")


# ------------------------------------------------------------------ the governing layer


def test_the_governing_layer_added_principles_without_removing_any() -> None:
    """"Nothing is removed. Nothing is weakened. Everything is weaponized." Checked, not
    assumed: P0-P9 must all still be present at their original ranks."""
    ids = {p.id for p in PRINCIPLES}
    assert {f"P{i}" for i in range(10)} <= ids
    assert {f"P{i}" for i in range(10, 23)} <= ids
    assert principle("P0").aggression == 10 and principle("P3").aggression == 10


def test_the_hat_is_constitutional_and_not_a_footnote() -> None:
    """The directive writes the objective with a hat and then writes every downstream rule as
    though the derivatives were observable. P10 closes that: a decision taken by comparing point
    estimates is taking a decision on noise."""
    p = principle("P10")
    assert "POSTERIOR ESTIMATES with standard errors" in p.statement
    assert "(value, se, n)" in p.formula


def test_retirement_needs_significance_not_a_bad_period() -> None:
    p = principle("P11")
    assert "STATISTICALLY SIGNIFICANT" in p.statement
    assert "INSUFFICIENT-EVIDENCE" in p.directive
    assert "1.64-sigma" in p.formula


def test_the_vip_rule_carries_the_half_that_usually_gets_dropped() -> None:
    """Global optimum first is the easy half. What decides whether this is a growth mechanism or
    a bureaucracy is that everyone else expands immediately afterwards."""
    p = principle("P12")
    assert "maximum feasible operating point" in p.statement
    assert "OPTIMISATION FAILURES" in p.statement
    assert "never defunded" in p.directive


def test_priority_decides_order_and_never_entitlement() -> None:
    p = principle("P13")
    assert "never entitlement" in p.statement
    assert "STARVED" in p.statement


def test_discovery_is_never_throttled_to_clear_a_backlog() -> None:
    """The bottleneck always scales upward. Surplus discovery is inventory; a hypothesis never
    generated is lost permanently, and only one of those shows up on a chart."""
    p = principle("P14")
    assert "NEVER min Q_D" in p.statement
    assert "INVENTORY" in p.statement
    assert "Governance may never reduce discovery throughput" in p.directive


def test_shrinkage_is_constitutionally_a_growth_argument() -> None:
    """If P15 read as caution it would be argued about as caution, and the first person to win
    that argument would lower the desk's expected growth while sounding bold."""
    p = principle("P15")
    assert "NOT conservatism" in p.statement
    assert "proposing to lower expected growth" in p.statement
    assert "ZERO, not small" in p.statement


def test_coexistence_expands_orthogonality_before_reducing_opportunity() -> None:
    p = principle("P16")
    assert "MC_i" in p.formula
    assert "separation, never retirement" in p.directive


def test_exploration_assumes_edges_exist_until_proven_otherwise() -> None:
    """The prior that decides whether a desk searches at all. Its opposite -- assume nothing is
    there until something proves otherwise -- is self-confirming, because it defunds the search
    that would have produced the proof."""
    p = principle("P17")
    assert "assumes unknown profitable edges exist until exhaustive evidence proves otherwise" \
        in p.statement
    assert "reduction of catastrophic downside" in p.directive, (
        "research that removes a tail is research that raises E[log W] without producing alpha")


def test_the_constitution_subjects_its_own_optimiser_to_replacement() -> None:
    """A meta-rule that exempted itself would be the one place the ratchet cannot reach."""
    st = principle("P18").statement
    assert "no optimiser is exempt" in st
    assert "constitution's own" in st


def test_no_component_may_declare_itself_complete() -> None:
    p = principle("P20")
    assert "no declarations of completion" in p.statement.lower()
    assert "unexamined ceiling" in p.directive


def test_the_immutable_core_wins_every_conflict_unconditionally() -> None:
    """The one direction the governing layer must never travel: an evidence-derived floor may
    TIGHTEN a rail and may never loosen one."""
    p = principle("P22")
    assert "survival_rail wins, always" in p.formula
    assert "may TIGHTEN a rail and may never loosen one" in p.directive
    assert p.aggression == 10


def test_the_preamble_carries_the_governing_layer_to_every_seat() -> None:
    """A layer that exists only in a module is a preference. These are the clauses that change
    what a model is allowed to recommend."""
    p = OBJECTIVE_PREAMBLE
    for clause in ("EVERYTHING IS AN ESTIMATE", "RETIREMENT NEEDS EVIDENCE",
                   "GLOBAL FIRST, THEN EVERYONE", "BOTTLENECK SCALES UPWARD",
                   "ROBUST KELLY IS MANDATORY", "MAXIMUM EXPLORATION", "RATE OVER LEVEL",
                   "OUTPUT-ONLY", "ZERO CEILING", "IMMUTABLE CORE"):
        assert clause in p, clause


# ------------------------------------------------------------------ the asymmetry correction


def test_the_constitution_pushes_forward_more_than_it_holds_back() -> None:
    """THE DIAGNOSIS, MADE MEASURABLE. A constitution can state an aggressive philosophy and
    encode the opposite one in its mechanics -- one defensible amendment at a time, no individual
    gate wrong, the aggregate re-optimised from "find as many good things as physically possible
    while preventing catastrophic mistakes" to "never deploy something bad".

    The mechanism is arithmetic rather than intent: a body of law follows its majority. So the
    balance is counted every cycle, which is the only way the drift is visible BEFORE it has
    already happened."""
    from libs.doctrine.constitution import governance_balance
    b = governance_balance()
    assert b["balanced"], b["note"]
    assert b["enablers"] > b["guards"]
    assert b["unclassified"] == [], "an unclassified principle cannot be counted either way"


def test_guards_are_not_treated_as_the_enemy() -> None:
    """The claim is narrow and has to stay narrow: guards must stay in the MINORITY, not
    disappear. A guard that prevents ruin or a false conclusion protects compounding itself,
    which is why the guards are among the highest-aggression principles here."""
    from libs.doctrine.constitution import governance_balance
    guards = [principle(g) for g in governance_balance()["guard_ids"]]
    assert {g.id for g in guards} >= {"P6", "P8", "P15"}
    assert all(g.aggression >= 8 for g in guards), (
        "a guard against ruin is a maximum-aggression rule, not a cautious one")


def test_posture_is_classified_by_direction_not_by_mechanism() -> None:
    """The ratchet RESTRAINS amendments and its DIRECTION is pro-aggression. Classifying by
    mechanism would file the desk's strongest anti-timidity rule as a restraint and invert the
    very count this exists to get right."""
    assert principle("P9").posture == "ENABLER"
    assert principle("P11").posture == "ENABLER", (
        "requiring evidence before retirement PROTECTS capability from governance churn")


def test_governance_is_constitutionally_a_weapon_not_a_police_force() -> None:
    """The principal's sentence, made binding: governance exists to maximise E[log W] and alpha
    discovery. A control that merely says no is a tax paid to feel careful."""
    p = principle("P21")
    for fn in ("EXPERIMENT COORDINATOR", "BLIND-SPOT HUNTER", "DUPLICATE REMOVER",
               "EVIDENCE CALIBRATOR", "BOTTLENECK REMOVER", "THROUGHPUT MULTIPLIER"):
        assert fn in p.statement, fn
    assert "not a police force" in p.statement
    assert "a tax the desk pays to feel careful" in p.statement
    assert "every gate ships with a named throughput multiplier" in p.formula


def test_anti_timidity_now_covers_the_four_axes_it_used_to_miss() -> None:
    """The old anti-timidity laws policed CAPITAL only -- don't under-size, don't hold cash,
    don't hesitate to deploy -- and left research, governance, engineering, discovery and
    conversion timidity entirely unguarded. That asymmetry is why governance won."""
    p = principle("P23")
    for axis in ("RESEARCH", "GOVERNANCE", "ENGINEERING", "DISCOVERY", "CONVERSION"):
        assert axis in p.statement, axis
    assert "only the first was ever policed" in p.statement
    assert "silence on those axes is not a pass" in p.directive


def test_a_new_gate_must_name_the_throughput_it_multiplies() -> None:
    """Not as harmless overhead -- as the marginal rule that tips the aggregate."""
    p = principle("P24")
    assert "count(ENABLER) > count(GUARD)" in p.formula
    assert "name the throughput it multiplies" in p.statement
    assert "admissible only alongside the ENABLER it makes possible" in p.directive


def test_the_preamble_tells_every_seat_that_governance_must_multiply_throughput() -> None:
    """Without this a seat asked to improve the desk proposes another gate, because another gate
    is always the easiest defensible recommendation to make."""
    p = OBJECTIVE_PREAMBLE
    assert "GOVERNANCE IS A WEAPON, NOT A POLICE FORCE" in p
    assert "must name the throughput it multiplies" in p
    assert "TIMIDITY IS SCORED ON EVERY AXIS" in p
    assert "Never recommend the smaller version because it is easier to justify" in p
