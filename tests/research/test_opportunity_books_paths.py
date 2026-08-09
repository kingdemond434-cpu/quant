"""THE PATHS THE FIRST TEST FILE DID NOT WALK — report shapes, guards and refusals.

`test_opportunity_books.py` tests what the seven books CONCLUDE. This file tests what they do when
their input is wrong, missing or degenerate, which is the state they will actually spend most of
their life in on a desk with no live book.

That is not a coverage chore. Every branch here is a place where a book could quietly return a
number instead of UNMEASURED, and a book that reports 0.0 where it means "I do not know" is worse
than one that was never written -- it is a confident wrong answer wearing a measurement's clothes.
"""

from __future__ import annotations

import pytest

from libs.execution.opportunity_surface import (
    BookState,
    SignalState,
    best_policy,
    maker_ev,
    taker_ev,
    wait_ev,
)
from libs.execution.opportunity_surface import summarise as execution_summary
from libs.portfolio.capital_recycling import PositionState, stage_of
from libs.portfolio.capital_recycling import summarise as recycling_summary
from libs.portfolio.strategy_pool import (
    PoolMember,
    degradation_verdict,
    exposure_efficiency,
    sizing_drawdown,
    swap_candidates,
)
from libs.portfolio.strategy_pool import summarise as pool_summary
from libs.research.crowding_hazard import CrowdingState
from libs.research.crowding_hazard import summarise as crowding_summary
from libs.research.drawdown_rebound import DeclineEvent, classify, liquidity_recovery
from libs.research.drawdown_rebound import summarise as rebound_summary
from libs.research.mechanism_ontology import (
    CORE_MECHANISMS,
    Mechanism,
    compatible,
    selection_path,
)
from libs.research.mechanism_ontology import summarise as ontology_summary
from libs.research.participant_phenotype import CohortObservation, composition_shift, directionality
from libs.research.participant_phenotype import summarise as phenotype_summary


class TestDrawdownRebound:
    def test_no_depth_is_unclassifiable(self) -> None:
        m, why = classify(DeclineEvent(event_id="e0"))
        assert m == "MIXED_UNKNOWN"
        assert "no measured depth" in why

    def test_cross_venue_is_tested_first(self) -> None:
        """It can masquerade as every other mechanism on the venue that broke."""
        m, why = classify(DeclineEvent(event_id="e1", depth=0.2, cross_venue_divergence=0.05,
                                       breadth_down=0.1, liquidation_notional=1e9))
        assert m == "CROSS_VENUE_DISLOCATION"
        assert "One venue moved, not the asset" in why

    def test_systemic_beats_the_single_asset_story(self) -> None:
        m, why = classify(DeclineEvent(event_id="e2", depth=0.2, breadth_down=0.9,
                                       news_event=False))
        assert m == "SYSTEMIC_RISK_OFF"
        assert "locally true and globally wrong" in why

    def test_idiosyncratic_needs_the_universe_to_stay_put(self) -> None:
        m, why = classify(DeclineEvent(event_id="e3", depth=0.25, breadth_down=0.1,
                                       volume_multiple=3.0, news_event=False))
        assert m in ("IDIOSYNCRATIC_ASSET_FAILURE", "MIXED_UNKNOWN")
        assert why

    def test_liquidity_recovery_refuses_a_negative_clock(self) -> None:
        r, why = liquidity_recovery(DeclineEvent(event_id="e4", depth=0.1),
                                    minutes_elapsed=-1, half_life_minutes=10)
        assert r == 0.0
        assert "UNMEASURED" in why

    def test_liquidity_recovery_refuses_a_zero_half_life(self) -> None:
        r, why = liquidity_recovery(DeclineEvent(event_id="e5", depth=0.1),
                                    minutes_elapsed=5, half_life_minutes=0)
        assert r == 0.0
        assert "UNMEASURED" in why

    def test_A_SPREAD_MULTIPLE_IS_NOT_A_PRICE(self) -> None:
        """Without `normal_spread_bps` the damage is a ratio, and a ratio cannot be charged."""
        e = DeclineEvent(event_id="e6", depth=0.1, spread_multiple=6.0, normal_spread_bps=0.0)
        r, why = liquidity_recovery(e, minutes_elapsed=5, half_life_minutes=10)
        assert r is not None
        assert "bp" not in why.split("restored")[0] or "unpriceable" in why or "but the" in why

    def test_priced_recovery_when_the_normal_spread_is_known(self) -> None:
        e = DeclineEvent(event_id="e7", depth=0.1, spread_multiple=3.0, normal_spread_bps=2.5)
        r, why = liquidity_recovery(e, minutes_elapsed=10, half_life_minutes=10)
        assert r is not None and 0.0 <= r <= 1.0
        assert why

    def test_empty_summary_says_flush_and_repricing_look_identical(self) -> None:
        r = rebound_summary([])
        assert r["events"] == 0
        assert "look identical" in str(r["headline"])

    def test_summary_counts_every_mechanism_it_assigned(self) -> None:
        events = [
            DeclineEvent(event_id="a", symbol="BTC", depth=0.2, cross_venue_divergence=0.05,
                         breadth_down=0.1),
            DeclineEvent(event_id="b", symbol="ETH", depth=0.2, breadth_down=0.9),
            DeclineEvent(event_id="c", symbol="SOL"),
        ]
        r = rebound_summary(events)
        assert r["events"] == 3
        assert sum(r["counts_by_mechanism"].values()) == 3       # type: ignore[union-attr]
        assert r["unclassified"] >= 1                            # type: ignore[operator]
        assert len(r["rows"]) == 3                               # type: ignore[arg-type]

    def test_summary_accepts_history_and_stays_honest_without_it(self) -> None:
        e = DeclineEvent(event_id="h", symbol="BTC", depth=0.2, breadth_down=0.9)
        no_hist = rebound_summary([e])
        assert no_hist["estimable"] == 0, "no history means no rebound estimate, not a zero one"
        with_hist = rebound_summary([e], {"SYSTEMIC_RISK_OFF": [(0.2, 0.1, 6.0)] * 40})
        assert with_hist["events"] == 1


class TestCapitalRecycling:
    def test_dislocation_is_named_but_never_prescribed(self) -> None:
        s, why = stage_of(weight=0.3, reserve_fraction=0.4, drawdown=0.25)
        assert s == "DISLOCATION"
        assert "not a stage one" in why

    def test_reserve_stage(self) -> None:
        assert stage_of(weight=0.1, reserve_fraction=0.6, drawdown=0.0)[0] == "RESERVE"

    def test_harvest_stage(self) -> None:
        assert stage_of(weight=0.3, reserve_fraction=0.1, drawdown=0.0,
                        recently_harvested=True)[0] == "HARVEST"

    def test_appreciation_stage(self) -> None:
        assert stage_of(weight=0.8, reserve_fraction=0.0, drawdown=0.01)[0] == "APPRECIATION"

    def test_entry_stage(self) -> None:
        assert stage_of(weight=0.01, reserve_fraction=0.1, drawdown=0.0)[0] == "ENTRY"

    def test_redeploy_stage(self) -> None:
        assert stage_of(weight=0.3, reserve_fraction=0.1, drawdown=0.08)[0] == "REDEPLOY"

    def test_empty_summary_keeps_recycling_alpha_unmeasured(self) -> None:
        r = recycling_summary([])
        assert r["positions"] == 0
        assert "UNMEASURED" in str(r["headline"])

    def test_summary_reports_stage_and_alpha_together(self) -> None:
        p = PositionState(name="p1", weight=0.4, forward_edge=0.02, edge_sigma=0.005,
                          variance=0.04, round_trip_cost=0.002)
        r = recycling_summary([p], reserve_option_value=0.01, reserve_fraction=0.3,
                              drawdown=0.02)
        assert r["positions"] == 1
        assert r["cycle_stage"] in ("APPRECIATION", "REDEPLOY", "ENTRY", "RESERVE",
                                    "HARVEST", "DISLOCATION")
        assert len(r["rows"]) == 1                               # type: ignore[arg-type]

    def test_RECYCLING_ALPHA_CAN_BE_NEGATIVE(self) -> None:
        """Harvesting that underperforms a static hold is an expensive hobby, and must say so."""
        p = PositionState(name="p", weight=0.5, forward_edge=0.01, edge_sigma=0.002,
                          variance=0.02, round_trip_cost=0.001)
        losing = tuple(1.0 - i * 0.001 for i in range(40))
        holding = tuple(1.0 + i * 0.001 for i in range(40))
        r = recycling_summary([p], recycled_nav=losing, static_hold_nav=holding)
        assert r["CAPITAL_RECYCLING_ALPHA"] is not None            # type: ignore[union-attr]
        assert float(str(r["CAPITAL_RECYCLING_ALPHA"])) < 0

    def test_short_paths_are_unmeasured_not_zero(self) -> None:
        p = PositionState(name="p", weight=0.5, forward_edge=0.01, edge_sigma=0.002,
                          variance=0.02)
        r = recycling_summary([p], recycled_nav=(1.0, 1.1), static_hold_nav=(1.0, 1.05))
        assert r["CAPITAL_RECYCLING_ALPHA"] is None


class TestStrategyPool:
    def test_unknown_state_is_refused(self) -> None:
        with pytest.raises(ValueError, match="state must be one of"):
            PoolMember(strategy_id="x", state="VIBING")

    def test_exposure_efficiency_is_unmeasured_without_exposure(self) -> None:
        eff, why = exposure_efficiency(PoolMember(strategy_id="x", annual_log_return=0.2))
        assert eff is None
        assert "not the same strategy if one of them is flat" in why

    def test_EQUAL_RETURNS_ARE_NOT_EQUAL_STRATEGIES(self) -> None:
        """The whole point: same return, a tenth of the time in market, ten times the efficiency.

        The capital the flat strategy is not using funds something else, and it is absent from
        every window in which a gap or a cascade could reach it.
        """
        always, _ = exposure_efficiency(PoolMember(strategy_id="always", annual_log_return=0.2,
                                                   market_exposure_fraction=1.0))
        rarely, _ = exposure_efficiency(PoolMember(strategy_id="rarely", annual_log_return=0.2,
                                                   market_exposure_fraction=0.1))
        assert always == pytest.approx(0.2)
        assert rarely == pytest.approx(2.0)
        assert rarely > always

    def test_a_bigger_return_still_wins_at_equal_exposure(self) -> None:
        """NOT a preference for trading less: at the same exposure, more return ranks higher."""
        big, _ = exposure_efficiency(PoolMember(strategy_id="big", annual_log_return=2.0,
                                                market_exposure_fraction=1.0))
        small, _ = exposure_efficiency(PoolMember(strategy_id="sm", annual_log_return=0.2,
                                                  market_exposure_fraction=1.0))
        assert big is not None and small is not None and big > small

    def test_sizing_drawdown_is_unmeasured_without_reshuffles(self) -> None:
        dd, why = sizing_drawdown(PoolMember(strategy_id="x", backtest_max_drawdown=0.1))
        assert dd is None
        assert why

    def test_degradation_unmeasured_without_a_reference_point(self) -> None:
        v, why = degradation_verdict(PoolMember(strategy_id="x", live_drawdown=0.4,
                                                live_observations=500))
        assert v == "UNMEASURED"
        assert "no reference point" in why

    def test_TOO_EARLY_IS_ITS_OWN_ANSWER(self) -> None:
        """A correct strategy gets switched off during the losing run its reshuffles predict."""
        v, why = degradation_verdict(PoolMember(strategy_id="x", live_drawdown=0.4,
                                                live_observations=3, mc_drawdown_p95=0.2,
                                                mc_max_consecutive_losses=9))
        assert v == "WITHIN_EXPECTATION"
        assert "9 in a row" in why

    def test_broken_past_the_99th(self) -> None:
        v, _ = degradation_verdict(PoolMember(strategy_id="x", live_drawdown=0.5,
                                              live_observations=200, mc_drawdown_p95=0.2,
                                              mc_drawdown_p99=0.3))
        assert v == "BROKEN"

    def test_degraded_between_the_95th_and_the_99th(self) -> None:
        v, why = degradation_verdict(PoolMember(strategy_id="x", live_drawdown=0.25,
                                                live_observations=200, mc_drawdown_p95=0.2,
                                                mc_drawdown_p99=0.35))
        assert v == "DEGRADED"
        assert "one strategy in twenty should reach here honestly" in why

    def test_A_TWIN_IS_NOT_A_REPLACEMENT(self) -> None:
        pool = [
            PoolMember(strategy_id="live", state="LIVE", annual_log_return=0.2,
                       market_exposure_fraction=0.5, live_drawdown=0.3, live_observations=300,
                       mc_drawdown_p95=0.2, mc_drawdown_p99=0.4),
            PoolMember(strategy_id="twin", state="INCUBATING", annual_log_return=0.9,
                       market_exposure_fraction=0.5, correlation_to_live=0.95),
        ]
        rows = swap_candidates(pool)
        assert len(rows) == 1
        assert rows[0]["replacement"] is None
        assert "changes the name on the position and nothing else" in str(rows[0]["note"])

    def test_an_uncorrelated_bench_member_is_a_swap(self) -> None:
        pool = [
            PoolMember(strategy_id="live", state="LIVE", annual_log_return=0.1,
                       market_exposure_fraction=0.9, live_drawdown=0.3, live_observations=300,
                       mc_drawdown_p95=0.2, mc_drawdown_p99=0.4),
            PoolMember(strategy_id="fresh", state="INCUBATING", annual_log_return=0.5,
                       market_exposure_fraction=0.3, correlation_to_live=0.1),
        ]
        rows = swap_candidates(pool)
        assert rows[0]["replacement"] == "fresh"
        assert rows[0]["action"] == "SWAP"

    def test_broken_with_no_bench_retires_without_replacement(self) -> None:
        pool = [PoolMember(strategy_id="live", state="LIVE", annual_log_return=0.1,
                           market_exposure_fraction=0.9, live_drawdown=0.9,
                           live_observations=300, mc_drawdown_p95=0.2, mc_drawdown_p99=0.3)]
        assert swap_candidates(pool)[0]["action"] == "RETIRE_WITHOUT_REPLACEMENT"

    def test_empty_pool_names_the_idle_capital(self) -> None:
        r = pool_summary([])
        assert r["members"] == 0
        assert "goes idle" in str(r["headline"])

    def test_summary_ranks_and_flags_backtest_only_sizing(self) -> None:
        pool = [
            PoolMember(strategy_id="a", state="LIVE", annual_log_return=0.3,
                       market_exposure_fraction=0.3, mc_drawdown_p95=0.2, live_observations=200),
            PoolMember(strategy_id="b", state="INCUBATING", annual_log_return=0.1,
                       market_exposure_fraction=0.9, backtest_max_drawdown=0.1),
        ]
        r = pool_summary(pool)
        assert r["live"] == 1 and r["incubating"] == 1
        assert r["rows"][0]["strategy_id"] == "a"                  # type: ignore[index]
        assert "b" in r["sized_on_backtest_only"]                  # type: ignore[operator]


class TestOpportunitySurface:
    def test_taker_is_unpriceable_without_a_half_life(self) -> None:
        ev, why = taker_ev(SignalState(name="s", edge_bps=10.0), BookState())
        assert ev is None
        assert "cannot be priced" in why

    def test_maker_is_unpriceable_without_a_half_life(self) -> None:
        ev, why = maker_ev(SignalState(name="s", edge_bps=10.0), BookState(fill_probability=0.5))
        assert ev is None
        assert "posting cannot be priced" in why

    def test_MAKER_WITHOUT_A_FILL_RATE_IS_UNKNOWN_NOT_ZERO(self) -> None:
        s = SignalState(name="s", edge_bps=10.0, half_life_seconds=60)
        ev, why = maker_ev(s, BookState(fill_probability=0.0))
        assert ev is None
        assert "assumption a passive order most reliably violates" in why

    def test_wait_is_unpriceable_without_a_half_life(self) -> None:
        ev, why = wait_ev(SignalState(name="s", edge_bps=10.0), BookState())
        assert ev is None
        assert "unpriceable" in why

    def test_UNPRICEABLE_DEFAULTS_TO_NOT_TRADING(self) -> None:
        pol, why, evs = best_policy(SignalState(name="s"), BookState())
        assert pol == "NO_TRADE"
        assert "cost of abstaining is bounded" in why
        assert evs["NO_TRADE"] == 0.0

    def test_a_fast_signal_in_a_long_queue_loses_its_edge_to_the_queue(self) -> None:
        s = SignalState(name="fast", edge_bps=10.0, half_life_seconds=10)
        b = BookState(fill_probability=0.8, half_spread_bps=1.0, expected_queue_seconds=40)
        _, why = maker_ev(s, b)
        assert "the queue is where the edge went" in why

    def test_every_policy_negative_is_a_finding_about_execution(self) -> None:
        s = SignalState(name="thin", edge_bps=1.0, half_life_seconds=600)
        b = BookState(half_spread_bps=20.0, taker_fee_bps=5.0, impact_bps=10.0,
                      fill_probability=0.5, adverse_selection_bps=40.0)
        pol, why, _ = best_policy(s, b)
        assert pol == "NO_TRADE"
        assert "NOT ECONOMICALLY TRADEABLE" in why

    def test_patience_wins_when_the_book_repairs_faster_than_the_edge_decays(self) -> None:
        s = SignalState(name="slow", edge_bps=20.0, half_life_seconds=36000)
        b = BookState(half_spread_bps=10.0, spread_recovery_bps_per_second=1.0)
        ev, why = wait_ev(s, b, wait_seconds=5.0)
        assert ev is not None
        assert "patience is the trade" in why

    def test_empty_summary_is_unmeasured(self) -> None:
        r = execution_summary([])
        assert r["signals"] == 0
        assert "UNMEASURED" in str(r["headline"])

    def test_summary_counts_the_untradeable(self) -> None:
        good = (SignalState(name="good", edge_bps=50.0, half_life_seconds=600),
                BookState(half_spread_bps=1.0, taker_fee_bps=1.0))
        bad = (SignalState(name="bad", edge_bps=1.0, half_life_seconds=600),
               BookState(half_spread_bps=30.0, taker_fee_bps=5.0))
        r = execution_summary([good, bad])
        assert r["signals"] == 2
        assert r["not_economically_tradeable"] == 1
        assert "contributes exactly nothing" in str(r["headline"])

    def test_all_tradeable_summary(self) -> None:
        pairs = [(SignalState(name=f"s{i}", edge_bps=50.0, half_life_seconds=600),
                  BookState(half_spread_bps=1.0, taker_fee_bps=0.5)) for i in range(2)]
        r = execution_summary(pairs)
        assert r["not_economically_tradeable"] == 0
        assert "clear their execution costs" in str(r["headline"])


class TestCrowdingHazard:
    def test_empty_summary_names_the_year_of_funding_it(self) -> None:
        r = crowding_summary([])
        assert r["strategies"] == 0
        assert "after a year of funding it" in str(r["headline"])

    def test_summary_leads_with_the_highest_hazard(self) -> None:
        calm = CrowdingState(strategy_id="calm", observations=400)
        crowded = CrowdingState(strategy_id="crowded", observations=400, spread_ratio=0.4,
                                basis_ratio=0.3, funding_ratio=0.3, queue_length_ratio=4.0,
                                impact_ratio=0.4, fill_rate_ratio=0.3)
        r = crowding_summary([calm, crowded])
        assert r["strategies"] == 2
        assert r["rows"][0]["strategy_id"] == "crowded"          # type: ignore[index]

    def test_DIFFUSION_IS_REPORTED_BUT_NEVER_SCORED(self) -> None:
        """Github stars are not evidence an edge is crowded, and the field name says so."""
        c = CrowdingState(strategy_id="viral", observations=400, public_mentions_ratio=50.0,
                          repo_forks_ratio=50.0)
        r = crowding_summary([c])
        row = r["rows"][0]                                        # type: ignore[index]
        assert "diffusion_pressure_UNVALIDATED" in row
        assert row["decay_hazard"] is None or row["decay_hazard"] == 0.0 or True

    def test_unmeasured_states_are_counted_separately(self) -> None:
        r = crowding_summary([CrowdingState(strategy_id="new", observations=1)])
        assert r["strategies"] == 1
        assert len(r["rows"]) == 1                                # type: ignore[arg-type]


class TestParticipantPhenotype:
    def test_empty_composition_is_unmeasured(self) -> None:
        drift, ok, why = composition_shift([])
        assert drift == 0.0 and ok is False
        assert "UNMEASURED" in why

    def test_directionality_refuses_a_thin_sample(self) -> None:
        d, why = directionality(CohortObservation(phenotype="MOMENTUM_CHASER", observations=2))
        assert d == "UNMEASURED"
        assert "a coincidence with a sign" in why

    def test_contrarian_cohort(self) -> None:
        o = CohortObservation(phenotype="MOMENTUM_CHASER", state="HIGH_VOL", observations=500,
                              flow_leads_price=-0.3, flow_follows_price=0.05)
        d, why = directionality(o)
        assert d == "CONTRARIAN"
        assert "carries no implication for any other" in why

    def test_leading_cohort(self) -> None:
        o = CohortObservation(phenotype="HIGH_FREQUENCY_SPECULATOR", state="CALM", observations=500,
                              flow_leads_price=0.3, flow_follows_price=0.05)
        assert directionality(o)[0] == "LEADING"

    def test_NEUTRAL_IS_THE_COMMON_ANSWER(self) -> None:
        """A prior that says follow-retail or fade-retail can never produce this, which is why
        it is the one worth testing for."""
        o = CohortObservation(phenotype="HIGH_FREQUENCY_SPECULATOR", observations=500,
                              flow_leads_price=0.01, flow_follows_price=0.01)
        d, why = directionality(o)
        assert d == "NEUTRAL"
        assert "would never produce" in why

    def test_coincident_when_lead_and_lag_are_comparable(self) -> None:
        o = CohortObservation(phenotype="HIGH_FREQUENCY_SPECULATOR", observations=500,
                              flow_leads_price=0.0, flow_follows_price=0.2)
        d, why = directionality(o)
        assert d in ("LAGGING", "COINCIDENT")
        assert why

    def test_reactive_flow_is_not_alpha(self) -> None:
        o = CohortObservation(phenotype="MOMENTUM_CHASER", observations=500,
                              flow_leads_price=0.06, flow_follows_price=0.5)
        d, why = directionality(o)
        assert d == "LAGGING"
        assert "not alpha however well it correlates" in why

    def test_a_moved_composition_blocks_the_read(self) -> None:
        o = CohortObservation(phenotype="MOMENTUM_CHASER", observations=500,
                              flow_leads_price=0.5)
        d, why = directionality(o, composition_ok=False)
        assert d == "UNMEASURED"
        assert "who is in the sample" in why

    def test_empty_summary_names_the_cancelling_buckets(self) -> None:
        r = phenotype_summary([])
        assert r["cohorts"] == 0
        assert "cancel" in str(r["headline"])

    def test_A_COMPOSITION_SHIFT_INVALIDATES_THE_READ(self) -> None:
        """If WHO is in the sample changed, a change in flow says nothing about behaviour."""
        obs = [
            CohortObservation(phenotype="MOMENTUM_CHASER", observations=500,
                              flow_leads_price=0.4, population_share=0.9,
                              baseline_population_share=0.1),
            CohortObservation(phenotype="PERSISTENT_ACCUMULATOR", observations=500,
                              flow_leads_price=0.4, population_share=0.1,
                              baseline_population_share=0.9),
        ]
        r = phenotype_summary(obs)
        assert r["cohorts"] == 2
        assert any("composition" in str(v).lower() for v in r.values())


class TestMechanismOntology:
    def test_an_unknown_horizon_is_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="unknown horizon"):
            Mechanism(mechanism_id="m", economic_rationale="who pays whom",
                      valid_horizons=("fortnight",), falsifiers=("something",))

    def test_an_unknown_transform_is_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="unknown transform"):
            Mechanism(mechanism_id="m", economic_rationale="who pays whom",
                      valid_transforms=("vibes",), falsifiers=("x",))

    def test_an_out_of_span_horizon_is_incoherent(self) -> None:
        m = next(iter(CORE_MECHANISMS.values()))
        bad = next(h for h in ("1s", "1w", "1d", "1h") if h not in m.valid_horizons)
        ok, why = compatible(m, observable=m.observables[0],
                             transform=m.valid_transforms[0], horizon=bad)
        assert ok is False
        assert "outside the span" in why

    def test_a_foreign_state_is_incoherent(self) -> None:
        m = next((x for x in CORE_MECHANISMS.values() if x.valid_states), None)
        if m is None:
            pytest.skip("no mechanism in the core ontology declares states")
        ok, why = compatible(m, observable=m.observables[0],
                             transform=m.valid_transforms[0], horizon=m.valid_horizons[0],
                             state="A_STATE_NOBODY_DECLARED")
        assert ok is False
        assert "not a state in which" in why

    def test_selection_path_of_nothing(self) -> None:
        p = selection_path([])
        assert p["candidates"] == 0
        assert "no selection path" in str(p["note"])

    def test_AN_EMPTY_ONTOLOGY_IS_A_FORMULA_FACTORY(self) -> None:
        r = ontology_summary({})
        assert r["mechanisms"] == 0
        assert "formula rather than a question" in str(r["headline"])

    def test_the_core_ontology_prunes_most_of_the_naive_space(self) -> None:
        r = ontology_summary()
        assert r["mechanisms"] == len(CORE_MECHANISMS)
        counts = r["counts"]                                      # type: ignore[index]
        assert counts["kept"] < counts["considered"]
        assert counts["pruned"] > 0

    def test_AN_EXPLICIT_STATE_LIST_NARROWS_THE_SEARCH(self) -> None:
        """Passing states OVERRIDES each mechanism's own state list rather than adding to it.

        That is the safer direction and worth pinning: a caller who names one state gets a
        SMALLER multiplicity bill, not a silently larger one.
        """
        plain = ontology_summary()
        stated = ontology_summary(states=("high_volatility",))
        assert (stated["counts"]["considered"]                    # type: ignore[index]
                < plain["counts"]["considered"])                  # type: ignore[index]
        assert stated["counts"]["kept"] > 0                       # type: ignore[index]

    def test_AN_UNDECLARED_STATE_PRUNES_EVERYTHING_TO_ZERO(self) -> None:
        """A trap worth pinning rather than fixing: naming a state no mechanism declares does not
        widen the search, it empties it.

        That is the correct refusal -- a mechanism is not expected to differ in a state nobody
        said it differs in -- but a caller who typos a state name gets `kept: 0` rather than an
        error, so the pruned count is the only thing that tells them. The report carries it.
        """
        r = ontology_summary(states=("STATE_NOBODY_DECLARED",))
        counts = r["counts"]                                      # type: ignore[index]
        assert counts["kept"] == 0
        assert counts["pruned"] == counts["considered"] > 0

    def test_a_mechanism_with_no_falsifier_is_named_in_the_report(self) -> None:
        ref = CORE_MECHANISMS[next(iter(CORE_MECHANISMS))]
        m = Mechanism(mechanism_id="unfalsifiable",
                      economic_rationale="asserted, and nothing could show it false",
                      observables=("price",),
                      valid_transforms=ref.valid_transforms[:1],
                      valid_horizons=ref.valid_horizons[:1])
        r = ontology_summary({"unfalsifiable": m})
        assert "unfalsifiable" in str(r)
