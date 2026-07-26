"""§42: the cross-venue funding screen must point at the THIN tail and refuse its own bad data.

The properties that decide whether this screen is useful rather than a daily source of noise:
it looks where a small book has an advantage, it reports the capacity of the BINDING leg, and an
implausible spread is flagged rather than ranked first -- because the biggest number in a noisy
cross-venue panel is the likeliest artifact, and a screen that sorts on magnitude surfaces its own
worst data every single day."""

from __future__ import annotations

import pytest

from libs.research.tail_funding import (
    MAX_CREDIBLE_ANNUAL,
    Divergence,
    VenueQuote,
    annualise,
    divergences,
    tail_universe,
)


def _q(sym: str, venue: str, rate: float, oi: float = 1e6) -> VenueQuote:
    return VenueQuote(symbol=sym, venue=venue, funding_rate=rate, open_interest_usd=oi)


class TestAnnualise:
    def test_eight_hourly_compounds_to_1095_intervals(self) -> None:
        assert annualise(0.0001) == pytest.approx(0.0001 * 3 * 365)

    def test_sign_is_preserved(self) -> None:
        assert annualise(-0.001) < 0


class TestTailUniverse:
    def test_it_selects_the_thin_end(self) -> None:
        qs = [_q("THIN", "a", 0.0, 10_000), _q("MID", "a", 0.0, 500_000),
              _q("FAT", "a", 0.0, 50_000_000)]
        assert "THIN" in tail_universe(qs)
        assert "FAT" not in tail_universe(qs)

    def test_no_oi_data_screens_everything_rather_than_nothing(self) -> None:
        # a screen that silently returns empty when a field is missing is worse than a noisy one
        qs = [_q("A", "a", 0.0, 0.0), _q("B", "a", 0.0, 0.0)]
        assert tail_universe(qs) == {"A", "B"}

    def test_empty_input_is_empty_not_a_crash(self) -> None:
        assert tail_universe([]) == set()


class TestDivergences:
    def test_a_single_venue_is_not_a_spread(self) -> None:
        assert divergences([_q("X", "binance", 0.01, 1_000)]) == []

    def test_a_real_gap_on_a_thin_name_is_found(self) -> None:
        qs = [_q("THIN", "binance", 0.0010, 10_000), _q("THIN", "bybit", 0.0001, 12_000),
              _q("FAT", "binance", 0.0001, 9e7), _q("FAT", "bybit", 0.0001, 9e7)]
        got = divergences(qs)
        assert [d.symbol for d in got] == ["THIN"]
        assert got[0].short_venue == "binance" and got[0].long_venue == "bybit"

    def test_capacity_is_the_BINDING_leg(self) -> None:
        # a pair is only as big as its thinner side; taking the fatter leg overstates it
        qs = [_q("T", "binance", 0.0010, 10_000), _q("T", "bybit", 0.0001, 900_000)]
        assert divergences(qs)[0].min_oi_usd == 10_000

    def test_a_gap_below_the_bar_is_not_reported(self) -> None:
        qs = [_q("T", "binance", 0.00002, 1_000), _q("T", "bybit", 0.00001, 1_000)]
        assert divergences(qs) == []

    def test_an_implausible_spread_is_flagged_not_ranked_first(self) -> None:
        qs = [_q("SANE", "binance", 0.0004, 1_000), _q("SANE", "bybit", 0.0000, 1_000),
              _q("ABSURD", "binance", 0.9000, 1_000), _q("ABSURD", "bybit", 0.0000, 1_000)]
        got = divergences(qs)
        assert got[0].symbol == "SANE", "an artifact outranked a real gap"
        absurd = next(d for d in got if d.symbol == "ABSURD")
        assert absurd.credible is False and "stale quote" in absurd.note

    def test_the_credibility_ceiling_is_where_it_says_it_is(self) -> None:
        just_under = MAX_CREDIBLE_ANNUAL * 0.9 / (3 * 365)
        qs = [_q("T", "binance", just_under, 1_000), _q("T", "bybit", 0.0, 1_000)]
        assert divergences(qs)[0].credible is True

    def test_tail_only_can_be_turned_off(self) -> None:
        qs = [_q("FAT", "binance", 0.0010, 9e7), _q("FAT", "bybit", 0.0001, 9e7),
              _q("THIN", "binance", 0.0, 1_000), _q("THIN", "bybit", 0.0, 1_000)]
        assert divergences(qs, tail_only=False) != []
        assert divergences(qs, tail_only=True) == []

    def test_result_is_deterministic(self) -> None:
        qs = [_q("A", "binance", 0.0010, 1_000), _q("A", "bybit", 0.0001, 1_000),
              _q("B", "binance", 0.0020, 900), _q("B", "bybit", 0.0001, 900)]
        assert divergences(qs) == divergences(qs)

    def test_a_divergence_is_frozen(self) -> None:
        import pydantic
        import pytest
        d = Divergence(symbol="X", long_venue="a", short_venue="b", spread_annual=0.5,
                       min_oi_usd=1.0, credible=True)
        with pytest.raises(pydantic.ValidationError):
            d.spread_annual = 9.0    # type: ignore[misc]
