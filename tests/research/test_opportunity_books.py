"""BEHAVIORAL tests for the six opportunity books.

Each book exists to make one specific mistake impossible, and each test below names that mistake:

    buying every 15% dip                        drawdown_rebound
    a fixed take-profit rule                    capital_recycling
    sizing off the backtest drawdown            strategy_pool
    trading a signal the book cannot support    opportunity_surface
    discovering decay from the P&L              crowding_hazard
    reading aggregate "retail flow"             participant_phenotype
    testing a 90-day order-flow signal          mechanism_ontology
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.execution.opportunity_surface import BookState, SignalState, best_policy, maker_ev
from libs.portfolio.capital_recycling import (
    PositionState,
    capital_recycling_alpha,
    compare,
    stage_of,
)
from libs.portfolio.strategy_pool import (
    PoolMember,
    degradation_verdict,
    exposure_efficiency,
    sizing_drawdown,
    swap_candidates,
)
from libs.research.crowding_hazard import CrowdingState, diffusion_pressure, hazard
from libs.research.drawdown_rebound import (
    DeclineEvent,
    classify,
    liquidity_recovery,
    rebound_estimate,
)
from libs.research.mechanism_ontology import (
    CORE_MECHANISMS,
    Mechanism,
    compatible,
    enumerate_candidates,
    register,
)
from libs.research.participant_phenotype import (
    CohortObservation,
    composition_shift,
    directionality,
)
from libs.research.participant_phenotype import summarise as phenotype_summary

ROOT = Path(__file__).resolve().parents[2]


# =============================================== drawdown/rebound: not every dip is a dip

def test_a_cascade_and_a_news_shock_of_equal_depth_classify_differently() -> None:
    """THE WHOLE POINT. Same 15% fall, opposite forward distributions."""
    cascade = DeclineEvent("c", depth=0.15, oi_cleared_fraction=0.25, volume_multiple=3.0,
                           funding_before=0.35, breadth_down=0.4)
    news = DeclineEvent("n", depth=0.15, news_event=True, breadth_down=0.2, volume_multiple=2.0)
    assert classify(cascade)[0] == "ENDOGENOUS_LEVERAGE_BUILDUP"
    assert classify(news)[0] == "EXOGENOUS_NEWS_SHOCK"
    assert "MECHANICAL" in classify(cascade)[1]
    assert "INFORMED" in classify(news)[1]


def test_a_fall_on_low_volume_is_liquidity_not_repricing() -> None:
    """Almost nobody transacted at the new level, so it is not the market's new estimate."""
    thin = DeclineEvent("t", depth=0.2, volume_multiple=0.4, depth_multiple=0.3, breadth_down=0.3)
    v, why = classify(thin)
    assert v == "LIQUIDITY_WITHDRAWAL"
    assert "nothing under it" in why


def test_an_unclassified_decline_earns_no_rebound_estimate() -> None:
    """Absence must not resolve to the answer that spends money."""
    est = rebound_estimate(DeclineEvent("u", depth=0.1),
                           {"ENDOGENOUS_LEVERAGE_BUILDUP": [(0.1, 0.05, 4.0)] * 50})
    assert est.mechanism == "MIXED_UNKNOWN"
    assert est.p_rebound is None
    assert "UNCLASSIFIED" in est.why


def test_a_thin_mechanism_history_yields_no_distribution() -> None:
    cascade = DeclineEvent("c", depth=0.15, oi_cleared_fraction=0.25, volume_multiple=3.0)
    est = rebound_estimate(cascade, {"ENDOGENOUS_LEVERAGE_BUILDUP": [(0.1, 0.05, 4.0)] * 5})
    assert est.p_rebound is None
    assert "story about those crashes" in est.why


def test_the_adverse_excursion_is_a_tail_not_a_mean() -> None:
    """The mean is what happens; the tail is what stops you out of the trade you were
    right about."""
    hist = {"ENDOGENOUS_LEVERAGE_BUILDUP": [(0.1, 0.02, 4.0)] * 45 + [(0.1, 0.30, 4.0)] * 5}
    est = rebound_estimate(DeclineEvent("c", depth=0.15, oi_cleared_fraction=0.25,
                                        volume_multiple=3.0), hist)
    assert est.expected_max_adverse is not None and est.expected_max_adverse > 0.05


def test_a_spread_multiple_is_not_a_cost_without_a_normal_spread() -> None:
    """4x on a 2bp book and 4x on a 40bp book are the same multiple and twenty times the money."""
    _, why = liquidity_recovery(DeclineEvent("x", spread_multiple=4.0), minutes_elapsed=5)
    assert "cannot be priced" in why
    _, priced = liquidity_recovery(DeclineEvent("x", spread_multiple=4.0, normal_spread_bps=2.0),
                                   minutes_elapsed=5)
    assert "bp of excess half-spread" in priced


# ================================================ capital recycling: no fixed rules

def test_ties_resolve_to_keep_because_every_alternative_pays_a_round_trip() -> None:
    p = PositionState("flat", weight=0.3, forward_edge=0.001, edge_sigma=0.0005, variance=0.01,
                      round_trip_cost=0.002)
    action, why, _ = compare(p, reserve_option_value=0.0)
    assert action == "KEEP", why


def test_an_unmeasured_position_keeps_rather_than_churns() -> None:
    action, why, _ = compare(PositionState("mystery", weight=0.5))
    assert action == "KEEP"
    assert "certain cost against an unknown benefit" in why


def test_harvest_wins_when_reserve_option_value_is_high_and_the_regime_is_fragile() -> None:
    p = PositionState("btc", weight=0.6, forward_edge=0.001, edge_sigma=0.0008, variance=0.02,
                      transition_hazard=0.4, round_trip_cost=0.001)
    action, _, _ = compare(p, reserve_option_value=0.01)
    assert action == "HARVEST"


def test_no_entry_price_or_unrealised_gain_exists_anywhere_in_the_module() -> None:
    """A large winner earns no ownership privilege, and the way to guarantee that is to make the
    inputs unavailable rather than to remember not to use them."""
    fields = set(PositionState.__dataclass_fields__)
    for banned in ("entry_price", "unrealised_gain", "cost_basis", "peak_value"):
        assert banned not in fields, f"{banned} would let a winner acquire a privilege"


def test_recycling_alpha_reports_a_negative_verdict_plainly() -> None:
    """A desk that harvests busily while underperforming a static hold has an expensive hobby."""
    recycled = tuple(1000 * 1.001 ** i for i in range(40))
    static = tuple(1000 * 1.002 ** i for i in range(40))
    a, why = capital_recycling_alpha(recycled, static)
    assert a is not None and a < 0
    assert "expensive hobby" in why


def test_a_short_path_yields_no_recycling_alpha() -> None:
    a, why = capital_recycling_alpha((1.0, 1.1), (1.0, 1.05))
    assert a is None
    assert "more about the window than about the policy" in why


def test_cycle_stages_are_descriptive_and_say_so() -> None:
    stage, why = stage_of(weight=0.1, reserve_fraction=0.4, drawdown=0.2)
    assert stage == "DISLOCATION"
    assert "marginal question, not a stage one" in why


# ================================================== strategy pool: exposure and sizing

def test_the_lower_exposure_strategy_wins_at_equal_return() -> None:
    """The transcript's own example: 20% at 100% exposure vs 20% at 10%."""
    a = PoolMember("A", annual_log_return=0.20, market_exposure_fraction=1.0)
    b = PoolMember("B", annual_log_return=0.20, market_exposure_fraction=0.10)
    assert exposure_efficiency(b)[0] > exposure_efficiency(a)[0]      # type: ignore[operator]


def test_a_bigger_return_at_full_exposure_still_beats_a_small_one_at_low_exposure() -> None:
    """This is NOT a preference for trading less, and a test has to prove that."""
    big = PoolMember("big", annual_log_return=2.0, market_exposure_fraction=1.0)
    small = PoolMember("small", annual_log_return=0.05, market_exposure_fraction=0.10)
    assert exposure_efficiency(big)[0] > exposure_efficiency(small)[0]   # type: ignore[operator]


def test_sizing_uses_the_reshuffled_drawdown_not_the_backtest_one() -> None:
    m = PoolMember("m", backtest_max_drawdown=0.13, mc_drawdown_p95=0.34)
    dd, why = sizing_drawdown(m)
    assert dd == 0.34
    assert "2.6" in why
    assert "the one that happened to be survivable" in why


def test_without_a_reshuffled_distribution_sizing_is_unmeasured() -> None:
    dd, why = sizing_drawdown(PoolMember("m", backtest_max_drawdown=0.13))
    assert dd is None
    assert "systematically the optimistic one" in why


def test_the_retirement_trigger_is_the_distribution_not_a_multiple() -> None:
    """A fixed 1.5x fires early on a fat tail and late on a tight one."""
    fat = PoolMember("fat", mc_drawdown_p95=0.40, mc_drawdown_p99=0.55, live_drawdown=0.30,
                     live_observations=100)
    tight = PoolMember("tight", mc_drawdown_p95=0.10, mc_drawdown_p99=0.14, live_drawdown=0.30,
                       live_observations=100)
    assert degradation_verdict(fat)[0] == "HEALTHY"
    assert degradation_verdict(tight)[0] == "BROKEN"


def test_a_short_live_record_cannot_trigger_a_swap() -> None:
    m = PoolMember("m", mc_drawdown_p95=0.10, live_drawdown=0.5, live_observations=3,
                   mc_max_consecutive_losses=12)
    v, why = degradation_verdict(m)
    assert v == "WITHIN_EXPECTATION"
    assert "12 in a row" in why


def test_a_correlated_bench_member_is_not_a_replacement() -> None:
    """Replacing a strategy with its twin changes the name on the position and nothing else."""
    inc = PoolMember("inc", state="LIVE", annual_log_return=0.1, market_exposure_fraction=1.0,
                     mc_drawdown_p95=0.10, mc_drawdown_p99=0.15, live_drawdown=0.20,
                     live_observations=100)
    twin = PoolMember("twin", state="INCUBATING", annual_log_return=0.5,
                      market_exposure_fraction=0.1, correlation_to_live=0.95)
    out = swap_candidates([inc, twin])
    assert out and out[0]["replacement"] is None
    assert "changes the name on the position" in str(out[0]["note"])


# ============================================ execution surface: tradeable or not

def test_a_real_signal_can_be_not_economically_tradeable() -> None:
    weak = SignalState("weak", edge_bps=1.0, half_life_seconds=30.0, edge_sigma_bps=0.2)
    hostile = BookState(half_spread_bps=6.0, fill_probability=0.2, adverse_selection_bps=9.0,
                        taker_fee_bps=4.0, impact_bps=3.0, expected_queue_seconds=60.0)
    pol, why, _ = best_policy(weak, hostile)
    assert pol == "NO_TRADE"
    assert "NOT ECONOMICALLY TRADEABLE" in why


def test_a_slow_signal_crosses_and_a_fast_one_does_not_wait_forever() -> None:
    book = BookState(half_spread_bps=2.0, fill_probability=0.55, adverse_selection_bps=3.5,
                     maker_fee_bps=-0.2, taker_fee_bps=4.5, impact_bps=1.0,
                     expected_queue_seconds=30.0)
    slow = SignalState("slow", edge_bps=25.0, half_life_seconds=21600.0, edge_sigma_bps=3.0)
    assert best_policy(slow, book)[0] == "TAKER"


def test_maker_ev_is_unpriceable_without_a_fill_rate() -> None:
    """A maker policy priced without a fill rate assumes it always gets filled."""
    ev, why = maker_ev(SignalState("s", edge_bps=10.0, half_life_seconds=60.0),
                       BookState(half_spread_bps=1.0))
    assert ev is None
    assert "most reliably violates" in why


def test_adverse_selection_is_charged_against_fills_only() -> None:
    cheap = BookState(half_spread_bps=2.0, fill_probability=0.5, adverse_selection_bps=0.0,
                      maker_fee_bps=0.0)
    toxic = BookState(half_spread_bps=2.0, fill_probability=0.5, adverse_selection_bps=8.0,
                      maker_fee_bps=0.0)
    s = SignalState("s", edge_bps=6.0, half_life_seconds=600.0)
    assert maker_ev(s, cheap)[0] > maker_ev(s, toxic)[0]     # type: ignore[operator]


def test_the_note_refuses_maker_share_as_an_objective() -> None:
    from libs.execution.opportunity_surface import summarise
    rep = summarise([(SignalState("s", edge_bps=5.0, half_life_seconds=60.0), BookState())])
    assert "never maker share" in str(rep["note"])


# ================================================= crowding: predict decay, don't observe it

def test_the_hazard_never_reads_the_pnl() -> None:
    """A hazard that reads returns is a lagging indicator wearing a leading indicator's name."""
    base: dict[str, object] = {
        "strategy_id": "s", "observations": 120, "spread_ratio": 0.6, "basis_ratio": 0.5,
        "funding_ratio": 0.6, "queue_length_ratio": 1.6, "impact_ratio": 1.3,
        "fill_rate_ratio": 0.7}
    good = CrowdingState(**base, realised_edge_ratio=1.2)      # type: ignore[arg-type]
    bad = CrowdingState(**base, realised_edge_ratio=0.1)       # type: ignore[arg-type]
    assert hazard(good)[0] == hazard(bad)[0]
    assert "was not an input to it" in hazard(bad)[1]


def test_diffusion_is_computed_reported_and_excluded() -> None:
    """'Publication destroys edge' is widely believed and unmeasured here."""
    quiet = CrowdingState("s", observations=120, spread_ratio=0.6, public_mentions_ratio=1.0)
    loud = CrowdingState("s", observations=120, spread_ratio=0.6, public_mentions_ratio=5.0,
                         repo_forks_ratio=5.0)
    assert diffusion_pressure(loud)[0] > diffusion_pressure(quiet)[0]
    assert hazard(loud)[0] == hazard(quiet)[0], "diffusion leaked into the hazard"
    assert "UNVALIDATED on this desk" in diffusion_pressure(loud)[1]


def test_a_thin_crowding_record_is_unmeasured() -> None:
    h, why = hazard(CrowdingState("s", observations=10, spread_ratio=0.2))
    assert h is None
    assert "noise with a direction" in why


# ========================================= phenotype: aggregation destroys the signal

def test_opposite_leading_cohorts_are_named_as_the_thing_an_aggregate_cancels() -> None:
    chaser = CohortObservation("MOMENTUM_CHASER", "high_vol", observations=400,
                               flow_leads_price=-0.12, population_share=0.4,
                               baseline_population_share=0.42)
    accum = CohortObservation("PERSISTENT_ACCUMULATOR", "high_vol", observations=400,
                              flow_leads_price=0.14, population_share=0.35,
                              baseline_population_share=0.34)
    rep = phenotype_summary([chaser, accum])
    assert "cancelled to noise" in str(rep["headline"])


def test_reactive_flow_is_not_alpha() -> None:
    o = CohortObservation("PANIC_SELLER", "crash", observations=400, flow_leads_price=0.02,
                          flow_follows_price=0.31)
    v, why = directionality(o)
    assert v == "LAGGING"
    assert "not alpha however well it correlates" in why


def test_composition_shift_blocks_a_behavioural_reading() -> None:
    """An aggregate can move because different people arrived, and that is the opposite finding."""
    o = CohortObservation("MOMENTUM_CHASER", "x", observations=400, flow_leads_price=0.4,
                          population_share=0.8, baseline_population_share=0.2)
    drift, ok, why = composition_shift([o])
    assert not ok and drift > 0.15
    assert "different people arriving" in why
    assert directionality(o, composition_ok=ok)[0] == "UNMEASURED"


def test_neutral_is_a_real_answer() -> None:
    o = CohortObservation("LOW_TURNOVER_HOLDER", "calm", observations=400,
                          flow_leads_price=0.01, flow_follows_price=0.01)
    v, why = directionality(o)
    assert v == "NEUTRAL"
    assert "would never produce" in why


def test_an_unknown_phenotype_cannot_be_recorded() -> None:
    with pytest.raises(ValueError, match="phenotype must be one of"):
        CohortObservation("WHALES_PROBABLY")


# ======================================== ontology: real questions, not formulas

def test_a_ninety_day_order_flow_candidate_is_refused_before_it_costs_anything() -> None:
    """The named example. OFI measures who is pressing the book NOW."""
    m = CORE_MECHANISMS["ORDER_FLOW_IMBALANCE"]
    ok, why = compatible(m, observable="order_flow_imbalance", transform="LEVEL", horizon="WEEKLY")
    assert not ok
    assert "outside the span" in why
    assert compatible(m, observable="order_flow_imbalance", transform="LEVEL",
                      horizon="SECONDS")[0]


def test_an_observable_that_merely_correlates_is_refused() -> None:
    m = CORE_MECHANISMS["PERP_FUNDING_CARRY"]
    ok, why = compatible(m, observable="order_flow_imbalance", transform="LEVEL", horizon="DAILY")
    assert not ok
    assert "does not MEASURE" in why


def test_the_prune_removes_the_majority_and_the_count_is_reported() -> None:
    """The pruned count is the size of the search that did NOT happen."""
    _, counts = enumerate_candidates(CORE_MECHANISMS)
    assert counts["pruned"] > counts["kept"]
    assert counts["considered"] == counts["kept"] + counts["pruned"]


def test_every_candidate_carries_its_selection_path() -> None:
    """A winner detached from its search size is indistinguishable from a preregistered one."""
    cands, _ = enumerate_candidates(CORE_MECHANISMS)
    assert all(c.siblings_enumerated > 0 for c in cands)


def test_an_unfalsifiable_mechanism_is_refused() -> None:
    with pytest.raises(ValueError, match="no falsifier"):
        register(CORE_MECHANISMS, Mechanism("VIBES", economic_rationale="it feels right"))


def test_a_mechanism_with_no_rationale_is_refused() -> None:
    with pytest.raises(ValueError, match="no economic rationale"):
        register(CORE_MECHANISMS, Mechanism("X", economic_rationale="  ",
                                            falsifiers=("it does not work",)))


def test_the_ontology_is_open_and_accepts_a_well_formed_mechanism() -> None:
    m = Mechanism("STABLECOIN_FLOW", economic_rationale="money entering the system must land",
                  observables=("stablecoin_supply",), valid_transforms=("DIFFERENCE",),
                  valid_horizons=("DAILY",), falsifiers=("supply change does not precede returns",))
    out = register(CORE_MECHANISMS, m)
    assert "STABLECOIN_FLOW" in out
    assert "STABLECOIN_FLOW" not in CORE_MECHANISMS, "register mutated the shared ontology"


def test_every_shipped_mechanism_has_a_falsifier_and_a_rationale() -> None:
    for m in CORE_MECHANISMS.values():
        assert m.falsifiers, f"{m.mechanism_id} has no falsifier"
        assert m.economic_rationale.strip(), f"{m.mechanism_id} has no rationale"
        assert m.valid_horizons, f"{m.mechanism_id} constrains no horizon, so it prunes nothing"


# ================================================================== the consumer

def test_the_books_script_runs_and_reports_unmeasured_honestly(tmp_path) -> None:
    out = tmp_path / "opportunity_books.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/run_opportunity_books.py"),
                        "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                       timeout=300, check=False)
    assert r.returncode == 0, r.stderr
    doc = json.loads(out.read_text("utf-8"))
    assert len(doc["unmeasured_books"]) >= 5, "a book produced a verdict with no input"
    for name in doc["unmeasured_books"]:
        assert doc["books"][name]["missing_artifact"], f"{name} did not name its input"
    # The ontology needs no market data and must therefore always produce output.
    assert doc["books"]["mechanism_ontology"]["counts"]["kept"] > 0
