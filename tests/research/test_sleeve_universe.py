"""THE UNIVERSE IS DERIVED FROM CAPITAL -- so funding is the only lever needed to widen the book.

Two failures, opposite directions, from the hardcoded six it replaces: publishing more symbols than
capital funds produces refused orders and a book holding a fraction of what it published; holding
fewer than capital funds leaves turnover unbought at identical per-trade edge. These pin both, plus
the claim the count would otherwise imply -- that widening is diversification. It is not.
"""

from __future__ import annotations

import pytest

from libs.research import sleeve_universe as U


def _hist(*syms: str, n: int = 400) -> dict[str, int]:
    return dict.fromkeys(syms, n)


class TestTheCapitalGate:
    def test_it_floors_because_a_leg_below_the_minimum_is_REFUSED_not_small(self) -> None:
        # $100 * 1x * 0.25 / 5 sleeves = $5/sleeve -> exactly one $5 leg, not 1.4 of them.
        assert U.capital_supports(100.0, leverage=1.0, book_frac=0.25,
                                  n_sleeves=5, min_notional=5.0) == 1
        assert U.capital_supports(140.0, leverage=1.0, book_frac=0.25,
                                  n_sleeves=5, min_notional=5.0) == 1

    def test_zero_is_a_real_answer_and_the_one_the_desk_missed(self) -> None:
        # At $193 with a $5 floor, four of five sleeves could not place a leg while every report
        # showed them LIVE. That state must be expressible.
        assert U.capital_supports(50.0, leverage=1.0, book_frac=0.25,
                                  n_sleeves=5, min_notional=5.0) == 0

    def test_leverage_widens_the_universe_proportionally(self) -> None:
        at1 = U.capital_supports(600.0, leverage=1.0, book_frac=0.25,
                                 n_sleeves=5, min_notional=5.0)
        at3 = U.capital_supports(600.0, leverage=3.0, book_frac=0.25,
                                 n_sleeves=5, min_notional=5.0)
        assert at3 == 3 * at1

    def test_degenerate_inputs_return_zero_rather_than_dividing_by_zero(self) -> None:
        assert U.capital_supports(600.0, leverage=1.0, book_frac=0.25,
                                  n_sleeves=0, min_notional=5.0) == 0
        assert U.capital_supports(600.0, leverage=1.0, book_frac=0.25,
                                  n_sleeves=5, min_notional=0.0) == 0


class TestFundingIsTheLever:
    def test_more_equity_widens_the_book_by_itself(self) -> None:
        cands = tuple(f"S{i}USDT" for i in range(24))
        h = _hist(*cands)
        small = U.select(cands, equity_usd=200.0, leverage=1.0, book_frac=0.25,
                         n_sleeves=5, min_notional=5.0, history=h)
        big = U.select(cands, equity_usd=2000.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=h)
        assert big["n_selected"] > small["n_selected"]
        assert small["binding_constraint"] == "CAPITAL"

    def test_it_never_publishes_more_than_capital_funds(self) -> None:
        cands = tuple(f"S{i}USDT" for i in range(24))
        rep = U.select(cands, equity_usd=200.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist(*cands))
        assert rep["n_selected"] <= rep["capital_supports"]
        assert rep["per_leg_usd"] >= 5.0

    def test_no_capital_is_NO_TRADEABLE_UNIVERSE_with_the_number_in_it(self) -> None:
        rep = U.select(("AUSDT",), equity_usd=10.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist("AUSDT"))
        assert rep["state"] == "NO-TRADEABLE-UNIVERSE"
        assert rep["symbols"] == ()
        assert "place NOTHING" in rep["why"]

    def test_data_binds_when_capital_is_ample(self) -> None:
        rep = U.select(("AUSDT", "BUSDT"), equity_usd=100_000.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist("AUSDT", "BUSDT"))
        assert rep["binding_constraint"] == "DATA"
        assert rep["n_selected"] == 2


class TestTheDataGate:
    def test_a_short_series_is_excluded_with_a_reason(self) -> None:
        rep = U.select(("GOODUSDT", "NEWUSDT"), equity_usd=10_000.0, leverage=1.0,
                       book_frac=0.25, n_sleeves=5, min_notional=5.0,
                       history={"GOODUSDT": 400, "NEWUSDT": 30})
        assert rep["symbols"] == ("GOODUSDT",)
        assert "NEWUSDT" in rep["rejected"]

    def test_an_absent_symbol_is_excluded_not_assumed_flat(self) -> None:
        # A generator handed no series returns zeros, and a sleeve reading zeros publishes
        # "no signal" where the truth is "no data".
        rep = U.select(("GOODUSDT", "MISSINGUSDT"), equity_usd=10_000.0, leverage=1.0,
                       book_frac=0.25, n_sleeves=5, min_notional=5.0,
                       history={"GOODUSDT": 400})
        assert rep["symbols"] == ("GOODUSDT",)
        assert "MISSINGUSDT" in rep["rejected"]


class TestLiquidityRanksRatherThanFilters:
    def test_the_deepest_names_are_kept_when_capital_truncates(self) -> None:
        cands = ("THINUSDT", "DEEPUSDT", "MIDUSDT")
        rep = U.select(cands, equity_usd=250.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist(*cands),
                       liquidity={"THINUSDT": 1.0, "MIDUSDT": 50.0, "DEEPUSDT": 900.0})
        assert rep["capital_supports"] == 2
        assert rep["symbols"] == ("DEEPUSDT", "MIDUSDT")

    def test_an_unmeasured_symbol_ranks_last_but_is_not_dropped(self) -> None:
        cands = ("KNOWNUSDT", "UNKNOWNUSDT")
        rep = U.select(cands, equity_usd=10_000.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist(*cands),
                       liquidity={"KNOWNUSDT": 100.0})
        assert rep["symbols"] == ("KNOWNUSDT", "UNKNOWNUSDT")

    def test_the_universe_is_deterministic_on_ties(self) -> None:
        cands = ("BUSDT", "AUSDT", "CUSDT")
        kw = {"equity_usd": 10_000.0, "leverage": 1.0, "book_frac": 0.25,
              "n_sleeves": 5, "min_notional": 5.0, "history": _hist(*cands)}
        assert U.select(cands, **kw)["symbols"] == U.select(cands, **kw)["symbols"]
        assert U.select(cands, **kw)["symbols"] == ("AUSDT", "BUSDT", "CUSDT")


class TestWideningIsNotDiversification:
    """The count invites the wrong conclusion, so the honest number is published beside it."""

    def test_tripling_the_symbol_count_barely_moves_k_eff(self) -> None:
        g = U.breadth_gain(6, 18)
        assert g["count_ratio"] == pytest.approx(3.0)
        assert g["breadth_ratio"] < 1.10, (
            "if widening really tripled breadth, the correlation assumption is wrong -- and the "
            "whole argument for it being a turnover lever rather than a diversification one goes")

    def test_at_zero_correlation_it_WOULD_be_diversification(self) -> None:
        # The contrast is the point: the ceiling comes from co-movement, not from arithmetic.
        assert U.breadth_gain(6, 18, rho=0.0)["breadth_ratio"] == pytest.approx(3.0)

    def test_the_report_carries_the_warning_rather_than_leaving_it_to_the_reader(self) -> None:
        rep = U.select(("AUSDT",), equity_usd=10_000.0, leverage=1.0, book_frac=0.25,
                       n_sleeves=5, min_notional=5.0, history=_hist("AUSDT"))
        assert "NOT DIVERSIFICATION" in rep["breadth_note"]
