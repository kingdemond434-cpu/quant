"""The desk's own hurdle. The property that matters is what it does with an UNKNOWN cost:
a burn rate that silently omits the largest line item yields a confident hurdle somebody would
plan against, which is strictly worse than reporting nothing."""

from __future__ import annotations

from libs.research.desk_economics import (
    assess,
    capital_for_hurdle,
    hurdle,
    parse_costs,
    runway_months,
)

FULL = {"monthly_usd": {"vps": 12.0, "llm_subscription": 200.0, "llm_api": 30.0,
                        "market_data": 0, "proxies": 0, "domains_misc": 2.0},
        "policy": {"max_acceptable_annual_hurdle_pct": 10.0}}


class TestUnknownsAreNeverZero:
    def test_a_null_cost_is_unknown_not_free(self) -> None:
        c = parse_costs({"monthly_usd": {"vps": None, "llm": 100.0}})
        assert c.unknown == ("vps",) and c.known == {"llm": 100.0}
        assert not c.is_complete

    def test_an_explicit_zero_IS_free(self) -> None:
        """`0` and `null` must not collapse to the same thing -- one is a measurement."""
        c = parse_costs({"monthly_usd": {"market_data": 0}})
        assert c.is_complete and c.monthly_usd == 0.0

    def test_an_unparseable_cost_is_unknown_not_zero(self) -> None:
        c = parse_costs({"monthly_usd": {"vps": "about twelve dollars"}})
        assert c.unknown == ("vps",)

    def test_an_incomplete_base_labels_the_hurdle_a_floor(self) -> None:
        a = assess(10_000.0, {"monthly_usd": {"vps": None, "llm": 100.0}})
        assert a["cost_base_complete"] is False
        assert "at least" in a["verdict"]
        assert a["undeclared_line_items"] == ["vps"]

    def test_a_complete_base_states_the_hurdle_flatly(self) -> None:
        assert "at least" not in assess(10_000.0, FULL)["verdict"]

    def test_a_missing_section_does_not_raise(self) -> None:
        c = parse_costs({})
        assert c.monthly_usd == 0.0 and c.is_complete


class TestHurdleArithmetic:
    def test_the_annual_hurdle_compounds_rather_than_multiplying_by_twelve(self) -> None:
        """The desk's doctrine is geometric growth; an arithmetic hurdle understates what
        compounding actually has to deliver."""
        h = hurdle(12_000.0, parse_costs({"monthly_usd": {"x": 120.0}}))
        assert h.monthly_pct == 1.0
        assert h.annual_pct is not None
        assert 12.6 < h.annual_pct < 12.8       # 1.01^12 - 1, not 12%

    def test_zero_equity_has_no_defined_hurdle(self) -> None:
        h = hurdle(0.0, parse_costs({"monthly_usd": {"x": 100.0}}))
        assert h.monthly_pct is None and h.annual_pct is None
        assert "undefined" in h.verdict

    def test_a_bigger_book_lowers_the_hurdle(self) -> None:
        c = parse_costs(FULL)
        small = hurdle(10_000.0, c).annual_pct
        large = hurdle(100_000.0, c).annual_pct
        assert small is not None and large is not None and large < small

    def test_the_largest_cost_is_surfaced(self) -> None:
        assert parse_costs(FULL).largest == ("llm_subscription", 200.0)

    def test_no_costs_means_no_largest(self) -> None:
        assert parse_costs({"monthly_usd": {}}).largest is None


class TestInverseQuestion:
    def test_capital_needed_to_make_the_hurdle_acceptable(self) -> None:
        need = capital_for_hurdle(parse_costs(FULL), 10.0)
        assert need is not None
        # at that equity the hurdle should land at (or just under) the target
        assert hurdle(need, parse_costs(FULL)).annual_pct == 10.0

    def test_zero_costs_need_no_capital(self) -> None:
        assert capital_for_hurdle(parse_costs({"monthly_usd": {"x": 0}}), 10.0) is None

    def test_a_nonsense_target_is_uncomputable_rather_than_infinite(self) -> None:
        assert capital_for_hurdle(parse_costs(FULL), 0.0) is None
        assert capital_for_hurdle(parse_costs(FULL), -5.0) is None


class TestRunway:
    def test_runway_is_cash_over_burn(self) -> None:
        assert runway_months(1200.0, parse_costs({"monthly_usd": {"x": 100.0}})) == 12.0

    def test_no_burn_means_no_finite_runway(self) -> None:
        assert runway_months(1000.0, parse_costs({"monthly_usd": {"x": 0}})) is None

    def test_negative_cash_floors_at_zero(self) -> None:
        assert runway_months(-500.0, parse_costs({"monthly_usd": {"x": 100.0}})) == 0.0


class TestPolicyVerdict:
    def test_a_small_book_fails_the_policy_bar(self) -> None:
        a = assess(14_628.0, FULL)
        assert a["hurdle_acceptable"] is False
        assert a["capital_needed_for_acceptable_hurdle_usd"] > 14_628.0

    def test_a_large_book_passes(self) -> None:
        assert assess(250_000.0, FULL)["hurdle_acceptable"] is True

    def test_a_malformed_policy_falls_back_to_the_default_bar(self) -> None:
        cfg = {**FULL, "policy": {"max_acceptable_annual_hurdle_pct": "ten percent"}}
        assert assess(50_000.0, cfg)["max_acceptable_annual_hurdle_pct"] == 10.0

    def test_zero_equity_leaves_acceptability_undecided_not_false(self) -> None:
        """Unknown is not the same as failing -- reporting False here would read as a verdict
        about a cost base against a book that does not exist yet."""
        assert assess(0.0, FULL)["hurdle_acceptable"] is None
