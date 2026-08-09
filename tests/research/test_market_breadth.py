"""BREADTH VS DEPTH — the comparison this desk was never making.

The claim the module rests on is falsifiable and worth pinning: a new market adds independent
occurrences of the state a mechanism needs, and a parameter search adds none. If
`breadth_versus_depth` recommends BREADTH regardless of whether the expression clears its costs,
the module is a slogan with a function signature. `test_UNPROFITABLE_BREADTH_LOSES_TO_DEPTH` is the
test that stops it being one.
"""

from __future__ import annotations

import pytest

from libs.research.market_breadth import (
    INSTRUMENTS,
    Expression,
    breadth_versus_depth,
    effective_independent_occurrences,
    feasible,
    marginal_breadth_elog,
    rank_expressions,
    summarise,
)


def _good(eid: str = "e1", rho: float = 0.0, **kw: object) -> Expression:
    base: dict[str, object] = {
        "expression_id": eid, "mechanism": "funding_carry", "asset": "SOL", "venue": "bybit",
        "instrument": "perp", "state_occurrences_per_year": 200.0,
        "edge_bps_per_occurrence": 12.0, "execution_cost_bps": 4.0, "capacity_fraction": 0.05,
        "annual_carrying_cost": 0.001, "state_correlation_to_held": rho}
    base.update(kw)
    return Expression(**base)                                     # type: ignore[arg-type]


class TestExpression:
    def test_unknown_instrument_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown instrument"):
            Expression(expression_id="x", mechanism="m", instrument="scratch_card")

    def test_every_declared_instrument_constructs(self) -> None:
        for i in INSTRUMENTS:
            assert Expression(expression_id="x", mechanism="m", instrument=i).instrument == i

    def test_net_bps_is_after_execution(self) -> None:
        assert _good().net_bps == pytest.approx(8.0)

    def test_unmeasured_without_occurrences_or_edge(self) -> None:
        assert not Expression(expression_id="x", mechanism="m",
                              edge_bps_per_occurrence=5.0).measured
        assert not Expression(expression_id="x", mechanism="m",
                              state_occurrences_per_year=10.0).measured


class TestFeasibility:
    def test_reachable(self) -> None:
        ok, why = feasible(_good())
        assert ok is True
        assert "reachable" in why

    @pytest.mark.parametrize(("field", "blocker"), [
        ("data_available", "no data"),
        ("venue_accessible", "venue not accessible"),
        ("above_minimum_size", "below venue minimum size"),
    ])
    def test_each_blocker_is_named(self, field: str, blocker: str) -> None:
        ok, why = feasible(_good(**{field: False}))
        assert ok is False
        assert blocker in why

    def test_FEASIBILITY_IS_A_FILTER_NOT_A_SCORE(self) -> None:
        """An infeasible expression must be removed, never given a low rank it could win from."""
        blocked = _good("blocked", venue_accessible=False,
                        state_occurrences_per_year=100_000.0,
                        edge_bps_per_occurrence=10_000.0)
        rows = rank_expressions([_good("ok"), blocked])
        top = rows[0]
        assert top["expression_id"] == "ok", (
            "an enormous but unreachable expression must not out-rank a modest reachable one")
        assert next(r for r in rows if r["expression_id"] == "blocked")["feasible"] is False


class TestMarginalElog:
    def test_unmeasured_is_unknown_not_zero(self) -> None:
        v, why = marginal_breadth_elog(Expression(expression_id="u", mechanism="m"))
        assert v is None
        assert "an assumption, not breadth" in why

    def test_a_profitable_expression_is_positive(self) -> None:
        v, why = marginal_breadth_elog(_good())
        assert v is not None and v > 0
        assert "MARGINAL_BREADTH_ELOG" in why

    def test_A_CORRELATED_EXPRESSION_IS_WORTH_LESS(self) -> None:
        """Firing at the same times as something already held is notional, not breadth."""
        fresh, _ = marginal_breadth_elog(_good("fresh", rho=0.0))
        twin, _ = marginal_breadth_elog(_good("twin", rho=0.9))
        assert fresh is not None and twin is not None
        assert twin < fresh

    def test_a_perfectly_correlated_expression_only_costs(self) -> None:
        v, why = marginal_breadth_elog(_good(rho=1.0))
        assert v is not None and v < 0
        assert "subscription, not an edge" in why

    def test_carrying_cost_can_sink_a_real_edge(self) -> None:
        v, why = marginal_breadth_elog(_good(annual_carrying_cost=5.0))
        assert v is not None and v < 0
        assert "subscription, not an edge" in why

    def test_a_catastrophic_carrying_cost_does_not_raise(self) -> None:
        """log1p of <= -1 must be handled, not thrown: an absurd input is still a report."""
        v, _ = marginal_breadth_elog(_good(annual_carrying_cost=500.0))
        assert v == float("-inf")


class TestIndependentOccurrences:
    def test_nothing_measured_is_unmeasured(self) -> None:
        eff, why = effective_independent_occurrences([Expression(expression_id="u", mechanism="m")])
        assert eff == 0.0
        assert "UNMEASURED, not zero" in why

    def test_FORTY_MARKETS_FIRING_TOGETHER_ARE_NOT_FORTY_OBSERVATIONS(self) -> None:
        herd = [_good(f"h{i}", rho=0.95) for i in range(10)]
        eff, why = effective_independent_occurrences(herd)
        assert eff == pytest.approx(100.0)          # 10 x 200 x 0.05
        assert "notional on an existing bet rather than new evidence" in why

    def test_independent_markets_keep_their_occurrences(self) -> None:
        spread = [_good(f"s{i}", rho=0.0) for i in range(3)]
        eff, why = effective_independent_occurrences(spread)
        assert eff == pytest.approx(600.0)
        assert "breadth genuinely multiplies the evidence" in why


class TestBreadthVersusDepth:
    def test_UNPROFITABLE_BREADTH_LOSES_TO_DEPTH(self) -> None:
        """THE DISCRIMINATOR. If this returns BREADTH the module is a slogan, not a comparison."""
        v, why = breadth_versus_depth([_good("bad", annual_carrying_cost=99.0)],
                                      depth_hypotheses=50)
        assert v == "DEPTH"
        assert "a real answer rather than a failure to find breadth" in why

    def test_infeasible_candidates_are_counted_in_the_depth_verdict(self) -> None:
        v, why = breadth_versus_depth([_good("x", data_available=False)], depth_hypotheses=10)
        assert v == "DEPTH"
        assert "1 were infeasible" in why

    def test_no_candidates_at_all_is_depth(self) -> None:
        assert breadth_versus_depth([], depth_hypotheses=5)[0] == "DEPTH"

    def test_PROFITABLE_BREADTH_NAMES_THE_ZERO(self) -> None:
        v, why = breadth_versus_depth([_good("a"), _good("b")], depth_hypotheses=1000)
        assert v == "BREADTH"
        assert "ZERO new occurrences by construction" in why
        assert "more places to meet the state it works in" in why


class TestSummarise:
    def test_empty_names_why_depth_is_the_default(self) -> None:
        r = summarise([])
        assert r["measured"] is False
        assert "least likely to be right" in str(r["headline"])

    def test_full_report_shape(self) -> None:
        cands = [_good("a"), _good("b", rho=0.8),
                 _good("c", venue_accessible=False),
                 Expression(expression_id="d", mechanism="m")]
        r = summarise(cands, depth_hypotheses=250)
        assert r["measured"] is True
        assert r["candidates"] == 4
        assert r["feasible"] == 3
        assert r["infeasible"] == ["c"]
        assert r["verdict"] in ("BREADTH", "DEPTH")
        assert len(r["rows"]) == 4                                # type: ignore[arg-type]

    def test_ranking_puts_the_best_feasible_first(self) -> None:
        r = summarise([_good("weak", rho=0.95), _good("strong", rho=0.0)])
        assert r["rows"][0]["expression_id"] == "strong"          # type: ignore[index]

    def test_an_all_unmeasured_set_is_not_measured(self) -> None:
        r = summarise([Expression(expression_id="u", mechanism="m")])
        assert r["measured"] is False
