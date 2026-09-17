"""The currency-factor view of a book, and every way it could report a flattering number.

What is pinned, and each item is a failure this measurement could have had:

  * a symbol is SPLIT or REFUSED, never guessed -- six letters alone would turn NatGas into a
    long NAT and a short GAS, two real numbers in a report nobody can read as wrong;
  * a long EURUSD is `+EUR -USD` and nothing else, so four long JPY crosses stop looking like
    four trades;
  * effective rank is 0.0 for a book with no exposure (an empty book makes ZERO bets, not one),
    1 for one bet, 2 for two orthogonal bets, and strictly between them for two bets sharing a
    leg -- CONTINUOUSLY, so crowding is visible while it forms rather than after a step function
    flips;
  * concentration shares sum to 1 and a flat book returns no shares at all;
  * an absent rate or contract size RAISES. A fabricated price makes every factor share
    downstream of it fiction, and fiction that looks measured is worse than a gap that says so.
"""
from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from libs.risk.errors import RiskError
from libs.risk.fx_exposure import (
    NON_CURRENCY_BASES,
    NON_PAIR_SYMBOLS,
    Position,
    book_from_sleeves,
    effective_rank,
    exposure_matrix,
    exposure_vector,
    factor_concentration,
    factors_from_registry,
    split_symbol,
    strip_suffix,
)


# --------------------------------------------------------------------------------- split_symbol
@pytest.mark.parametrize(("symbol", "legs"), [
    ("EURUSD", ("EUR", "USD")),
    ("eurusd", ("EUR", "USD")),
    ("CHFNOK", ("CHF", "NOK")),
    ("GBPMXN", ("GBP", "MXN")),
    ("XAUUSD", ("XAU", "USD")),
    ("XAUUSD.raw", ("XAU", "USD")),
    ("EURUSD-ECN", ("EUR", "USD")),
    ("EURUSD_x", ("EUR", "USD")),
    ("XAGEUR", ("XAG", "EUR")),
    ("XTIUSD", ("XTI", "USD")),
    ("BTCUSD", ("BTC", "USD")),
])
def test_split_symbol_reads_the_pairs_it_knows(symbol: str, legs: tuple[str, str]) -> None:
    assert split_symbol(symbol) == legs


@pytest.mark.parametrize(("symbol", "legs"), [
    ("US500", ("US500", "USD")),
    ("NAS100", ("NAS100", "USD")),
    ("JPN225", ("JPN225", "JPY")),
    ("UK100", ("UK100", "GBP")),
    ("UKGILT", ("UKGILT", "GBP")),
    ("WHEAT", ("WHEAT", "USD")),
    ("OJ", ("OJ", "USD")),
    ("MATICUSD", ("MATIC", "USD")),
])
def test_an_index_energy_or_soft_is_its_own_factor_against_its_quote(
        symbol: str, legs: tuple[str, str]) -> None:
    """`US500 = +US500 -USD`. The desk has no decomposition of an index into anything more
    primitive, and inventing one would put a fabricated number inside a rank."""
    assert split_symbol(symbol) == legs


@pytest.mark.parametrize("symbol", [
    "NatGas",          # six letters, and the exact corruption the currency check exists to stop
    "hunt16",
    "garbage",
    "ABCDEFG",
    "AT&T",
    "Apple",
    "   ",
    "",
])
def test_split_symbol_refuses_rather_than_guessing(symbol: str) -> None:
    with pytest.raises(RiskError):
        split_symbol(symbol)


def test_natgas_would_have_split_into_two_plausible_legs() -> None:
    """The refusal above is not hypothetical: the shape matches and both halves look like legs."""
    core = strip_suffix("NatGas")
    assert len(core) == 6 and core[:3] == "NAT" and core[3:] == "GAS"
    with pytest.raises(RiskError, match="not a quotable currency"):
        split_symbol("NatGas")


def test_suffix_stripping_never_eats_a_real_ticker() -> None:
    assert strip_suffix("US2000") == "US2000"
    assert strip_suffix("UST05Y") == "UST05Y"
    assert strip_suffix("XAUUSD.raw") == "XAUUSD"


def test_non_currency_bases_cover_the_universe_classes_that_need_them() -> None:
    for base in ("XAU", "XAG", "BTC", "ETH", "XTI", "XBR", "XNG", "XAL"):
        assert base in NON_CURRENCY_BASES


def test_every_mapped_symbol_quotes_against_a_real_currency() -> None:
    """The map's SECOND leg is a currency the broker quotes, never another invented factor --
    otherwise a rank would count an index's own quote leg as an extra direction."""
    from libs.risk.fx_exposure import CURRENCIES
    for symbol, (base, quote) in NON_PAIR_SYMBOLS.items():
        assert quote in CURRENCIES, f"{symbol} quotes against {quote}, which is not a currency"
        assert base and base == base.upper()
        assert split_symbol(symbol) == (base, quote)


# ------------------------------------------------------------------------------ exposure vectors
def test_a_long_pair_is_plus_base_and_minus_quote() -> None:
    names, vector = exposure_vector([Position("EURUSD", 100_000.0)])
    assert names == ("EUR", "USD")
    assert vector.tolist() == [100_000.0, -100_000.0]


def test_a_short_pair_flips_both_legs() -> None:
    names, vector = exposure_vector([Position("EURUSD", -100_000.0)])
    assert dict(zip(names, vector.tolist(), strict=True)) == {"EUR": -100_000.0, "USD": 100_000.0}


def test_four_long_jpy_crosses_are_one_large_short_jpy_position() -> None:
    book = [Position(s, 10_000.0) for s in ("EURJPY", "GBPJPY", "AUDJPY", "CADJPY")]
    names, vector = exposure_vector(book)
    exposure = dict(zip(names, vector.tolist(), strict=True))
    assert exposure["JPY"] == -40_000.0
    assert all(exposure[leg] == 10_000.0 for leg in ("EUR", "GBP", "AUD", "CAD"))


def test_legs_that_cancel_are_kept_as_named_zeros() -> None:
    """A book long EUR through one sleeve and short it through another HAS expressed that factor;
    dropping the name would erase the pair of bets that cancelled."""
    names, vector = exposure_vector([Position("EURUSD", 1.0), Position("EURGBP", -1.0)])
    exposure = dict(zip(names, vector.tolist(), strict=True))
    assert exposure["EUR"] == 0.0
    assert set(names) == {"EUR", "USD", "GBP"}


def test_a_factors_override_classifies_what_split_symbol_refuses() -> None:
    names, vector = exposure_vector([Position("Apple", 5_000.0)],
                                    factors={"Apple": ("APPLE", "USD")})
    assert dict(zip(names, vector.tolist(), strict=True)) == {"APPLE": 5_000.0, "USD": -5_000.0}


def test_an_unclassifiable_symbol_without_an_override_still_raises() -> None:
    with pytest.raises(RiskError):
        exposure_vector([Position("Apple", 5_000.0)], factors={"Tesla": ("TESLA", "USD")})


def test_position_refuses_a_non_finite_notional() -> None:
    with pytest.raises(RiskError):
        Position("EURUSD", float("nan"))
    with pytest.raises(RiskError):
        Position("  ", 1.0)


# ------------------------------------------------------------------------------- matrix stacking
def test_exposure_matrix_stacks_one_row_per_sleeve_over_a_shared_column_space() -> None:
    sleeves, names, matrix = exposure_matrix({
        "dollar_sleeve": [Position("EURUSD", 1.0)],
        "yen_sleeve": [Position("USDJPY", 2.0)],
        "flat_sleeve": [],
    })
    assert sleeves == ("dollar_sleeve", "yen_sleeve", "flat_sleeve")
    assert names == ("EUR", "JPY", "USD")
    assert matrix.shape == (3, 3)
    assert matrix.tolist() == [[1.0, 0.0, -1.0], [0.0, -2.0, 2.0], [0.0, 0.0, 0.0]]


def test_the_matrix_columns_sum_to_the_book_vector() -> None:
    book = {"a": [Position("EURUSD", 3.0)], "b": [Position("GBPUSD", 5.0)]}
    _, names, matrix = exposure_matrix(book)
    flat = [p for positions in book.values() for p in positions]
    vector_names, vector = exposure_vector(flat)
    assert names == vector_names
    assert matrix.sum(axis=0).tolist() == pytest.approx(vector.tolist())


# -------------------------------------------------------------------------------- effective rank
def test_a_flat_book_makes_zero_bets_not_one() -> None:
    assert effective_rank(np.zeros((3, 4))) == 0.0
    assert effective_rank(np.zeros((0, 0))) == 0.0
    assert effective_rank([]) == 0.0
    _, _, matrix = exposure_matrix({"flat": []})
    assert effective_rank(matrix) == 0.0


def test_one_bet_is_rank_one() -> None:
    _, _, matrix = exposure_matrix({"only": [Position("EURUSD", 100.0)]})
    assert effective_rank(matrix) == pytest.approx(1.0)


def test_two_orthogonal_bets_are_rank_two() -> None:
    """EURUSD and AUDCAD share no leg, so they are two directions however big each one is."""
    _, _, matrix = exposure_matrix({
        "usd_bet": [Position("EURUSD", 100.0)],
        "cad_bet": [Position("AUDCAD", 100.0)],
    })
    assert effective_rank(matrix) == pytest.approx(2.0)


def test_two_bets_sharing_a_dollar_leg_are_worth_less_than_two() -> None:
    """Long EURUSD and short USDCHF are both short the dollar. Gram = [[2,1],[1,2]] gives
    eigenvalues 3 and 1, so the participation ratio is 16/10 -- one and a bit, not two."""
    _, _, matrix = exposure_matrix({
        "eur_long": [Position("EURUSD", 1.0)],
        "chf_short_usd": [Position("USDCHF", -1.0)],
    })
    rank = effective_rank(matrix)
    assert rank == pytest.approx(1.6)
    assert 1.0 < rank < 2.0


def test_the_participation_ratio_degrades_smoothly_rather_than_stepping() -> None:
    """Two unit rows at angle t have rank 2/(1+cos^2 t): 2.0 orthogonal, 1.0 identical, and
    strictly monotone between. A step-function rank is blind to every state in between."""
    ranks = []
    for degrees in (90, 75, 60, 45, 30, 15, 5, 0):
        t = math.radians(degrees)
        matrix = np.array([[1.0, 0.0], [math.cos(t), math.sin(t)]])
        rank = effective_rank(matrix)
        assert rank == pytest.approx(2.0 / (1.0 + math.cos(t) ** 2))
        ranks.append(rank)
    assert ranks[0] == pytest.approx(2.0)
    assert ranks[-1] == pytest.approx(1.0)
    assert all(a > b for a, b in pairwise(ranks))


def test_eighteen_pairs_from_eight_currencies_cannot_span_more_than_seven_directions() -> None:
    """The review finding, as arithmetic: a pair is a DIFFERENCE of two factors, so n currencies
    give at most n-1 independent directions however many crosses are held."""
    ccys = ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"]
    pairs = [(a, b) for i, a in enumerate(ccys) for b in ccys[i + 1:]][:18]
    book = {f"{a}{b}": [Position(f"{a}{b}", 1.0 + 0.1 * i)]
            for i, (a, b) in enumerate(pairs)}
    _, names, matrix = exposure_matrix(book)
    assert len(book) == 18 and len(names) == 8
    assert np.linalg.matrix_rank(matrix) == 7
    assert effective_rank(matrix) <= 7.0 + 1e-9


def test_effective_rank_refuses_a_non_finite_matrix() -> None:
    with pytest.raises(RiskError):
        effective_rank(np.array([[1.0, float("nan")]]))


# -------------------------------------------------------------------------------- concentration
def test_concentration_shares_sum_to_one() -> None:
    names, vector = exposure_vector([Position("EURUSD", 100.0), Position("GBPUSD", 300.0)])
    shares = factor_concentration(names, vector)
    assert sum(shares.values()) == pytest.approx(1.0)
    assert shares["USD"] == pytest.approx(400.0 / 800.0)
    assert shares["GBP"] == pytest.approx(300.0 / 800.0)


def test_a_flat_book_has_no_shares_rather_than_a_dict_of_zeros() -> None:
    assert factor_concentration(("EUR", "USD"), [0.0, 0.0]) == {}
    assert factor_concentration((), []) == {}


def test_concentration_refuses_a_length_mismatch() -> None:
    with pytest.raises(RiskError):
        factor_concentration(("EUR", "USD"), [1.0])


# ------------------------------------------------------------------------------ factors registry
def test_factors_from_registry_uses_the_registry_as_the_authority() -> None:
    reg = {
        "US500": {"asset_class": "Indices", "currency_profit": "USD"},
        "Apple": {"asset_class": "Equities", "currency_profit": "USD"},
        "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
        "MYSTERY": {"bars": 10},
    }
    factors = factors_from_registry(reg)
    assert factors["Apple"] == ("APPLE", "USD")
    assert factors["US500"] == ("US500", "USD")
    assert "EURUSD" not in factors            # a cross is split, not made its own factor
    assert "MYSTERY" not in factors           # unclassified: absence is not a permission


# ----------------------------------------------------------------------------- book_from_sleeves
SLEEVES = {"sleeves": [
    {"name": "eur_long", "symbol": "EURUSD", "lot": 0.5, "risk_frac": 0.01, "status": "LIVE"},
    {"name": "ramp", "symbol": "AUDCAD", "lot": "auto_ramp", "risk_frac": 0.01, "status": "LIVE"},
    {"name": "retired", "symbol": "EURUSD", "lot": 1.0, "risk_frac": 0.0, "status": "RETIRED"},
]}
SIZES = {"EURUSD": 100_000.0, "AUDCAD": 100_000.0}


def test_book_from_sleeves_converts_lots_into_account_currency_notional() -> None:
    books = book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="EUR")
    # 0.5 lots * 100,000 EUR * 1.10 USD/EUR, converted back to EUR at 1/1.10 -> 50,000 EUR
    assert books["eur_long"][0].notional_ccy == pytest.approx(50_000.0)
    assert books["eur_long"][0].symbol == "EURUSD"


def test_a_usd_account_passes_the_quote_leg_through_unchanged() -> None:
    books = book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="USD")
    assert books["eur_long"][0].notional_ccy == pytest.approx(55_000.0)


def test_a_declared_short_side_flips_the_notional() -> None:
    doc = {"sleeves": [dict(SLEEVES["sleeves"][0], side="SHORT")]}
    books = book_from_sleeves(doc, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="EUR")
    assert books["eur_long"][0].notional_ccy == pytest.approx(-50_000.0)


def test_an_auto_ramp_lot_is_an_empty_book_not_a_zero_position() -> None:
    """The live registry writes "auto_ramp" into most sleeves. The sleeve must stay VISIBLE with
    nothing in it, so the caller can name it UNMEASURED instead of dropping it silently."""
    books = book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="EUR")
    assert books["ramp"] == ()
    assert "ramp" in books


def test_only_the_requested_statuses_are_read() -> None:
    books = book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="EUR")
    assert "retired" not in books
    wide = book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes=SIZES, account_ccy="EUR",
                             statuses=("LIVE", "RETIRED"))
    assert "retired" in wide


def test_book_from_sleeves_raises_on_a_missing_rate() -> None:
    with pytest.raises(RiskError, match="no rate"):
        book_from_sleeves(SLEEVES, {}, contract_sizes=SIZES, account_ccy="EUR")


def test_book_from_sleeves_raises_on_a_missing_conversion_rather_than_assuming_one() -> None:
    """A JPY-quoted sleeve in a EUR account needs EURJPY. Without it the honest answer is a
    refusal -- 1.0 would book a yen notional as euros and nothing downstream could tell."""
    doc = {"sleeves": [{"name": "yen", "symbol": "USDJPY", "lot": 1.0, "status": "LIVE"}]}
    with pytest.raises(RiskError, match="no rate to convert JPY into EUR"):
        book_from_sleeves(doc, {"USDJPY": 150.0}, contract_sizes={"USDJPY": 100_000.0},
                          account_ccy="EUR")


def test_book_from_sleeves_raises_on_a_missing_contract_size() -> None:
    with pytest.raises(RiskError, match="no contract size"):
        book_from_sleeves(SLEEVES, {"EURUSD": 1.10}, contract_sizes={}, account_ccy="EUR")


def test_a_caller_measured_lot_overrides_the_registry_row() -> None:
    books = book_from_sleeves(SLEEVES, {"EURUSD": 1.10, "AUDCAD": 0.90, "EURCAD": 1.50},
                              contract_sizes=SIZES, account_ccy="EUR",
                              lots={"ramp": 0.25})
    assert books["ramp"][0].notional_ccy == pytest.approx(0.25 * 100_000.0 * 0.90 / 1.50)


def test_book_from_sleeves_rejects_a_document_it_cannot_read() -> None:
    with pytest.raises(RiskError):
        book_from_sleeves(42, {}, contract_sizes={})
