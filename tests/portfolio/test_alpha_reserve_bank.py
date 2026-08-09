"""THE RESERVE BANK'S TESTS — the bench must not be allowed to flatter itself.

Three defects would make this module worse than nothing, because each one produces a confident
number that is wrong in the reassuring direction:

  1. counting a bench of clones by HEADCOUNT, so eight momentum variants read as eight replacements
  2. counting a candidate that does not yet clear the bar, so a promise reads as a reserve
  3. counting same-mechanism cover against a mechanism-level death, so the thing that just died
     is offered as the cure for its own death

Each has a test below whose failure means the bank is lying.
"""

from __future__ import annotations

import pytest

from libs.portfolio.alpha_reserve_bank import (
    LAYERS,
    ReserveCandidate,
    alpha_reserve_ratio,
    bench_effective_count,
    replacement_coverage,
    replacement_latency,
    summarise,
    switch_verdict,
)


def _live(sid: str, elog: float, mech: str = "carry") -> ReserveCandidate:
    return ReserveCandidate(strategy_id=sid, layer="LIVE_CORE", mechanism=mech,
                            forward_elog=elog, live_weight=0.25)


def _ready(sid: str, elog: float, mech: str = "flow", rho: float = 0.0) -> ReserveCandidate:
    return ReserveCandidate(strategy_id=sid, layer="INCUBATION", mechanism=mech,
                            forward_elog=elog, meets_evidence_bar=True, bench_correlation=rho)


class TestLayers:
    def test_unknown_layer_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown layer"):
            ReserveCandidate(strategy_id="x", layer="SOMEWHERE_ELSE")

    def test_every_layer_constructs(self) -> None:
        for ly in LAYERS:
            assert ReserveCandidate(strategy_id="x", layer=ly).layer == ly

    def test_dormant_is_bench_and_retired_is_not(self) -> None:
        """Retirement is a capital decision, deletion an information one. Only RETIRED deletes."""
        assert ReserveCandidate(strategy_id="d", layer="DORMANT_MONITORED").is_bench
        assert not ReserveCandidate(strategy_id="r", layer="RETIRED").is_bench

    def test_unmeasured_candidate_is_never_eligible(self) -> None:
        c = ReserveCandidate(strategy_id="u", layer="INCUBATION", meets_evidence_bar=True)
        assert not c.eligible_now, "a candidate with no forward estimate is not a reserve"

    def test_shrunk_elog_never_credits_a_negative(self) -> None:
        c = ReserveCandidate(strategy_id="w", layer="INCUBATION",
                             forward_elog=0.01, forward_elog_sigma=0.05)
        assert c.shrunk_elog == 0.0


class TestBenchIndependence:
    def test_empty_bench_is_unmeasured_not_zero(self) -> None:
        n, why = bench_effective_count([])
        assert n == 0.0
        assert "unknown" in why

    def test_single_member(self) -> None:
        n, why = bench_effective_count([_ready("a", 0.01)])
        assert n == 1.0
        assert "not yet a question" in why

    def test_CLONES_COLLAPSE_TO_ONE(self) -> None:
        """THE TEST THAT MATTERS. Eight perfectly correlated variants are one replacement."""
        bench = [_ready(f"m{i}", 0.01, mech="momentum", rho=1.0) for i in range(8)]
        n, why = bench_effective_count(bench)
        assert n == pytest.approx(1.0), "correlated clones must not be counted by headcount"
        assert "duplicates" in why

    def test_independent_bench_keeps_its_headcount(self) -> None:
        bench = [_ready(f"i{i}", 0.01, rho=0.0) for i in range(5)]
        n, why = bench_effective_count(bench)
        assert n == pytest.approx(5.0)
        assert "roughly honest" in why


class TestReserveRatio:
    def test_no_live_book_is_unmeasured(self) -> None:
        r, why = alpha_reserve_ratio([_ready("a", 0.02)])
        assert r is None
        assert "not a ratio of zero" in why

    def test_non_positive_live_value_reframes_the_question(self) -> None:
        book = [ReserveCandidate(strategy_id="l", layer="LIVE_CORE",
                                 forward_elog=0.01, forward_elog_sigma=0.5)]
        r, why = alpha_reserve_ratio(book)
        assert r is None
        assert "the live book is the thing that needs replacing" in why

    def test_full_cover_reads_at_or_above_one(self) -> None:
        book = [_live("L1", 0.02), _ready("B1", 0.02, mech="flow"),
                _ready("B2", 0.02, mech="basis")]
        r, why = alpha_reserve_ratio(book)
        assert r is not None and r >= 1.0
        assert "rebuild the book" in why

    def test_thin_bench_reads_below_one(self) -> None:
        book = [_live("L1", 0.10), _ready("B1", 0.01)]
        r, why = alpha_reserve_ratio(book)
        assert r is not None and r < 0.5
        assert "goes idle" in why or "without one" in why

    def test_a_promise_is_not_a_reserve(self) -> None:
        """A candidate three weeks from the bar contributes ZERO to the ratio, by design."""
        promise = ReserveCandidate(strategy_id="P", layer="INCUBATION", mechanism="flow",
                                   forward_elog=1.0, meets_evidence_bar=False, days_to_bar=21)
        r, _ = alpha_reserve_ratio([_live("L1", 0.02), promise])
        assert r == 0.0


class TestReplacementCoverage:
    def test_fraction_must_be_a_fraction(self) -> None:
        with pytest.raises(ValueError, match="fraction"):
            replacement_coverage([_live("L", 0.01)], fraction=1.5)

    def test_no_live_book_is_unmeasured_not_covered(self) -> None:
        cov, why = replacement_coverage([_ready("a", 0.01)], fraction=0.5)
        assert cov is None
        assert "UNMEASURED, not fully covered" in why

    def test_non_positive_live_total_is_undefined(self) -> None:
        book = [ReserveCandidate(strategy_id="l", layer="LIVE_CORE",
                                 forward_elog=0.01, forward_elog_sigma=1.0)]
        cov, why = replacement_coverage(book, fraction=0.5)
        assert cov is None
        assert "undefined" in why

    def test_THE_SHOCK_TAKES_THE_BIGGEST_FIRST(self) -> None:
        """Edges do not die in order of unimportance. A 25% shock must kill the largest engine."""
        book = [_live("BIG", 0.10), _live("small", 0.01),
                _ready("B", 0.02, mech="flow")]
        cov, why = replacement_coverage(book, fraction=0.25)
        assert cov is not None and cov < 1.0
        assert "1 largest live contributor" in why

    def test_SAME_MECHANISM_IS_NOT_COVER(self) -> None:
        """The defect this argument exists for: funding-carry cannot replace funding-carry."""
        book = [_live("L", 0.02, mech="carry"), _ready("B", 0.05, mech="carry")]
        with_cover, _ = replacement_coverage(book, fraction=1.0)
        without, why = replacement_coverage(book, fraction=1.0, dead_mechanisms=("carry",))
        assert with_cover == pytest.approx(1.0)
        assert without == 0.0, "a dead mechanism's own clones are not a reserve against it"
        assert "EXCLUDED" in why and "same-mechanism cover is not cover" in why

    def test_full_cover_says_so_without_touching_the_bar(self) -> None:
        book = [_live("L", 0.01), _ready("B", 0.05, mech="flow")]
        cov, why = replacement_coverage(book, fraction=1.0)
        assert cov == pytest.approx(1.0)
        assert "without touching the evidence standard" in why


class TestReplacementLatency:
    def test_unmeasured_without_a_live_book(self) -> None:
        lat, why = replacement_latency([_ready("a", 0.01)])
        assert lat is None
        assert "UNMEASURED" in why

    def test_zero_when_already_covered(self) -> None:
        lat, why = replacement_latency([_live("L", 0.01), _ready("B", 0.05, mech="flow")])
        assert lat == 0.0
        assert "0 days" in why

    def test_UNBOUNDED_IS_WORSE_THAN_LONG(self) -> None:
        """A bench with no dated path does not have a long latency. It has no evidence of one."""
        undated = ReserveCandidate(strategy_id="U", layer="INCUBATION", mechanism="flow",
                                   forward_elog=0.5, meets_evidence_bar=False, days_to_bar=0)
        lat, why = replacement_latency([_live("L", 0.10), undated])
        assert lat is None
        assert "UNBOUNDED, not long" in why

    def test_dated_pipeline_reports_the_crossing_day(self) -> None:
        soon = ReserveCandidate(strategy_id="SOON", layer="INCUBATION", mechanism="flow",
                                forward_elog=0.10, meets_evidence_bar=False, days_to_bar=14)
        lat, why = replacement_latency([_live("L", 0.10), soon])
        assert lat == 14
        assert "forfeits" in why

    def test_an_undersized_bench_is_named_as_undersized(self) -> None:
        tiny = ReserveCandidate(strategy_id="T", layer="INCUBATION", mechanism="flow",
                                forward_elog=0.001, meets_evidence_bar=False, days_to_bar=30)
        lat, why = replacement_latency([_live("L", 1.0), tiny])
        assert lat is None
        assert "too small" in why


class TestSwitchVerdict:
    def test_unmeasured_either_side_defaults_to_keep(self) -> None:
        v, why = switch_verdict(_live("I", 0.02), ReserveCandidate(strategy_id="C",
                                                                   layer="SHADOW_CHALLENGER"))
        assert v == "UNMEASURED"
        assert "defaults to KEEP" in why

    def test_challenger_below_the_bar_is_refused(self) -> None:
        c = ReserveCandidate(strategy_id="C", layer="SHADOW_CHALLENGER", forward_elog=99.0,
                             meets_evidence_bar=False, days_to_bar=10)
        v, why = switch_verdict(_live("I", 0.02), c)
        assert v == "KEEP"
        assert "10 days from it" in why

    def test_challenger_below_the_bar_with_no_path(self) -> None:
        c = ReserveCandidate(strategy_id="C", layer="SHADOW_CHALLENGER", forward_elog=99.0,
                             meets_evidence_bar=False)
        v, why = switch_verdict(_live("I", 0.02), c)
        assert v == "KEEP"
        assert "no dated path" in why

    def test_DRAWDOWN_IS_NOT_AN_INPUT(self) -> None:
        """A healthy incumbent must survive an identical challenger no matter how far it is down.

        The signature carries no drawdown field at all, which is the strongest possible form of
        this guarantee: the reflex cannot be expressed, not merely discouraged.
        """
        assert "drawdown" not in switch_verdict.__code__.co_varnames
        v, why = switch_verdict(_live("I", 0.02), _ready("C", 0.02, mech="flow"))
        assert v == "KEEP"
        assert "sells the bottom" in why

    def test_switching_costs_can_reverse_a_gross_win(self) -> None:
        v, why = switch_verdict(_live("I", 0.02), _ready("C", 0.03, mech="flow"),
                                switching_cost=0.05)
        assert v == "KEEP"
        assert "better gross but the switch costs more" in why

    def test_a_positive_incumbent_is_DEMOTED_not_retired(self) -> None:
        v, why = switch_verdict(_live("I", 0.01), _ready("C", 0.10, mech="flow"))
        assert v == "DEMOTE_INCUMBENT"
        assert "DORMANT_MONITORED" in why

    def test_a_dead_incumbent_is_replaced(self) -> None:
        dead = ReserveCandidate(strategy_id="I", layer="LIVE_CORE", forward_elog=-0.01)
        v, why = switch_verdict(dead, _ready("C", 0.10, mech="flow"))
        assert v == "REPLACE"
        assert "not a rotation" in why


class TestSummarise:
    def test_empty_bank_is_unmeasured_not_zero_latency(self) -> None:
        r = summarise([])
        assert r["measured"] is False
        assert "UNMEASURED rather than zero" in str(r["headline"])

    def test_full_report_shape(self) -> None:
        book = [_live("L1", 0.03, mech="carry"), _live("L2", 0.02, mech="momentum"),
                _ready("B1", 0.02, mech="flow"), _ready("B2", 0.02, mech="basis"),
                ReserveCandidate(strategy_id="D1", layer="DORMANT_MONITORED", mechanism="carry",
                                 forward_elog=0.01, bench_correlation=0.3)]
        r = summarise(book)
        assert r["measured"] is True
        assert r["live"] == 2
        assert r["bench"] == 3
        assert set(r["shock_coverage"]) == {"25pct", "50pct", "75pct"}       # type: ignore[arg-type]
        assert sum(r["layers"].values()) == len(book)                        # type: ignore[union-attr]
        assert r["alpha_reserve_ratio"] is not None

    def test_unmeasured_book_still_reports_every_field(self) -> None:
        r = summarise([_ready("B1", 0.02)])
        assert r["measured"] is False
        assert "UNMEASURED" in str(r["headline"])
        assert r["shock_coverage"]["50pct"]["coverage"] is None              # type: ignore[index]
