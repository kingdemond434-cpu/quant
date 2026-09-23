"""Currency-leg decomposition: the concentration an asset-class view cannot see."""
from __future__ import annotations

import pytest

from libs.risk.fx_factors import decompose, effective_bets, split_pair


def test_split_pair_rejects_non_crosses() -> None:
    assert split_pair("EURJPY") == ("EUR", "JPY")
    assert split_pair("eurjpy") == ("EUR", "JPY")
    # These must NOT be halved into three-letter legs.
    for bad in ("US500", "NatGas", "hunt16", "XAUUSDm", ""):
        assert split_pair(bad) is None


def test_four_jpy_crosses_are_one_short_jpy_bet() -> None:
    """THE MEASUREMENT THIS MODULE EXISTS FOR.

    Four equal longs in four different JPY crosses look like four positions to a per-symbol
    view and to Factor.FX alike. They are one short-JPY bet of four times the size.
    """
    book = {"CADJPY": 100.0, "EURJPY": 100.0, "USDJPY": 100.0, "GBPJPY": 100.0}
    d = decompose(book)
    assert d.by_currency["JPY"] == pytest.approx(-400.0)
    for leg in ("CAD", "EUR", "USD", "GBP"):
        assert d.by_currency[leg] == pytest.approx(100.0)
    leg, share = d.top_concentration
    assert leg == "JPY"
    assert share == pytest.approx(0.5)          # 400 of 800 gross leg risk
    assert effective_bets(book) == pytest.approx(2.0)


def test_genuinely_diversified_book_scores_higher() -> None:
    spread = {"EURJPY": 100.0, "AUDCAD": 100.0, "GBPSEK": 100.0, "USDMXN": 100.0}
    assert effective_bets(spread) > effective_bets(
        {"CADJPY": 100.0, "EURJPY": 100.0, "USDJPY": 100.0, "GBPJPY": 100.0})


def test_exotics_are_classified_not_raised_on() -> None:
    """libs.risk.instruments.get_factor RAISES on these; a measurement must not."""
    exotics = {"CHFNOK": 50.0, "GBPSEK": 50.0, "USDZAR": 50.0, "GBPMXN": 50.0, "CHFDKK": 50.0}
    d = decompose(exotics)
    assert d.unknown == {}
    assert d.by_currency["CHF"] == pytest.approx(100.0)
    assert set(d.by_currency) >= {"CHF", "NOK", "GBP", "SEK", "USD", "ZAR", "MXN", "DKK"}


def test_metal_is_its_own_factor_and_usd_leg_is_kept() -> None:
    d = decompose({"XAUUSD": 100.0})
    assert d.by_metal["XAU"] == pytest.approx(100.0)
    assert d.by_currency["USD"] == pytest.approx(-100.0)


def test_unknown_symbols_are_reported_never_silently_dropped() -> None:
    """A silent zero would read exactly like genuine diversification (L1.28a)."""
    d = decompose({"EURJPY": 100.0, "hunt16": 100.0, "US500": 50.0})
    assert d.unknown == {"hunt16": 100.0, "US500": 50.0}
    assert "hunt16" not in d.by_currency
    assert d.gross == pytest.approx(200.0)      # unknowns excluded from the total


def test_shorts_net_against_longs_on_the_shared_leg() -> None:
    d = decompose({"EURJPY": 100.0, "EURUSD": -100.0})
    assert d.by_currency["EUR"] == pytest.approx(0.0)
    assert d.by_currency["JPY"] == pytest.approx(-100.0)
    assert d.by_currency["USD"] == pytest.approx(100.0)


def test_empty_book_is_zero_not_an_error() -> None:
    d = decompose({})
    assert d.gross == 0.0
    assert d.top_concentration == ("NONE", 0.0)
    assert effective_bets({}) == 0.0
