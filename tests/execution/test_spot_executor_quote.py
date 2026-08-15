"""Re-quoting the book onto the asset the account may actually trade.

MEASURED 2026-08-15, on the first live placement: every order came back `-2010 This symbol is not
permitted for this account`. Under MiCA, Binance does not permit EEA retail to trade its USDT spot
pairs, and the desk's entire research universe is quoted in USDT because that is what the data lake
holds. Three orders, three rejections, and the reason was in neither the strategy nor the code.

The signal is about the BASE asset. The quote is a settlement detail of the venue.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_SRC = Path("scripts/run_spot_executor.py")


def _mod() -> Any:
    spec = importlib.util.spec_from_file_location("run_spot_executor_undertest", _SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_THE_BASE_ASSET_IS_PRESERVED_AND_ONLY_THE_QUOTE_MOVES() -> None:
    r = _mod().retarget
    assert r("BNBUSDT", "USDC") == "BNBUSDC"
    assert r("LINKUSDT", "USDC") == "LINKUSDC"
    assert r("ADAUSDT", "EUR") == "ADAEUR"


def test_THE_LONGEST_QUOTE_WINS() -> None:
    """A suffix table ordered wrongly would strip 'USDC' out of 'FDUSD'-quoted symbols, or match a
    short quote inside a longer one, and the resulting symbol would silently not exist."""
    r = _mod().retarget
    assert r("BTCFDUSD", "USDC") == "BTCUSDC"
    assert r("ETHTUSD", "USDC") == "ETHUSDC"


def test_STRIPPING_TO_THE_BARE_BASE_IS_HOW_HOLDINGS_ARE_MATCHED() -> None:
    """Balances are keyed by base asset, so the holdings lookup needs the base alone. Getting this
    wrong reads every holding as zero and re-buys a book the account already owns."""
    r = _mod().retarget
    assert r("BNBUSDT", "") == "BNB"
    assert r("ADAUSDC", "") == "ADA"


def test_AN_UNRECOGNISED_QUOTE_APPENDS_RATHER_THAN_MANGLING() -> None:
    """A base-only entry must become a tradeable pair, not a truncated one -- and it must never
    silently drop characters from a symbol the table does not know."""
    r = _mod().retarget
    assert r("SOL", "USDC") == "SOLUSDC"


def test_THE_DEFAULT_IS_UNCHANGED() -> None:
    """USDT stays the default so no existing caller is re-pointed at a different venue leg by an
    upgrade. The EEA account passes --quote explicitly, which makes the constraint visible in the
    command rather than buried in a default."""
    src = _SRC.read_text("utf-8")
    assert '"--quote", default="USDT"' in src
    assert "-2010" in src, "the reason for the flag must travel with it"


def test_AUTO_EQUITY_COUNTS_THE_QUOTE_PLUS_THE_BOOKS_OWN_COINS() -> None:
    """The denominator has to include what the book already holds, or every target shrinks to the
    cash left over and the executor sells the position it just bought."""
    r = _mod()._resolve_equity
    held = {"USDC": 41.06, "BNB": 0.15, "LINK": 3.0}
    eq, why = r("auto", {"BNBUSDT": 0.5, "LINKUSDT": 0.5}, held,
                {"BNBUSDC": 700.0, "LINKUSDC": 17.0}, "USDC")
    assert abs(eq - 197.06) < 0.01
    assert "read from the venue" in why and "BNB" in why


def test_AUTO_EQUITY_IGNORES_COINS_THE_BOOK_DOES_NOT_TARGET() -> None:
    """A balance can hold positions put there for another reason. Sweeping them into the
    denominator sizes this book against committed capital, then sells them to fund the gap."""
    r = _mod()._resolve_equity
    eq, _ = r("auto", {"BNBUSDT": 1.0}, {"USDC": 100.0, "BNB": 0.1, "DOGE": 1_000_000.0},
              {"BNBUSDC": 700.0, "DOGEUSDC": 0.2}, "USDC")
    assert abs(eq - 170.0) < 0.01, "an untargeted holding must not enter the denominator"


def test_AN_UNPRICEABLE_HOLDING_REFUSES_RATHER_THAN_UNDERSTATES() -> None:
    """Counting it as zero would shrink every target and turn a missing price into a sell order --
    UNMEASURED resolving to a number, in the direction that liquidates (L1.28a)."""
    r = _mod()._resolve_equity
    eq, why = r("auto", {"BNBUSDT": 1.0}, {"USDC": 10.0, "BNB": 1.0}, {}, "USDC")
    assert eq == 0.0
    assert "cannot be priced" in why and "trigger sells" in why


def test_A_STATED_NUMBER_STILL_WINS() -> None:
    """An explicit figure is a stated intent. A book being deliberately sized down must not have
    its denominator quietly re-read from the account it is withdrawing from."""
    r = _mod()._resolve_equity
    eq, why = r("198", {}, {"USDC": 5000.0}, {}, "USDC")
    assert eq == 198.0 and "stated by the caller" in why


def test_A_NONSENSE_EQUITY_IS_REFUSED_NOT_COERCED() -> None:
    r = _mod()._resolve_equity
    eq, why = r("lots", {}, {"USDC": 1.0}, {}, "USDC")
    assert eq == 0.0 and "neither a number nor" in why


def _clamp_src() -> str:
    return _SRC.read_text("utf-8")


def test_A_BUY_IS_SIZED_TO_THE_CASH_THAT_EXISTS() -> None:
    """MEASURED 2026-08-15. Targets are computed from EQUITY, which includes coins already held;
    the cash available to buy with is a different and smaller number. The final leg asked for
    $39.96 against $36.21 free, the venue answered `-2010 Account has insufficient balance`, and
    the book sat two-thirds complete. A slightly underweight position is a book; a rejected order
    is a hole."""
    src = _clamp_src()
    assert "quote_free" in src, "the executor does not track spendable cash"
    assert "delta > quote_free" in src, "a buy larger than the free balance is not clamped"
    assert "clamped_from" in src and "shortfall_usd" in src, (
        "a clamped leg must record what it wanted -- otherwise the filled weight reads as the "
        "intended one and the book looks correctly sized when it is not")


def test_THE_CASH_DECREMENTS_AS_LEGS_FILL() -> None:
    """Without this, every leg believes it has the whole balance, and a three-leg book plans to
    spend the same dollars three times -- in the dry run too, where the operator reads the plan."""
    src = _clamp_src()
    assert src.count("quote_free -= delta") >= 2, (
        "both the live and the dry-run branches must decrement, or the printed plan is a fiction")


def test_A_LEG_WITH_LESS_THAN_THE_MINIMUM_REFUSES_RATHER_THAN_CLAMPING() -> None:
    """Clamping below the venue minimum produces an order that cannot be placed. The leg stays
    empty and says so, which is the one outcome an operator can act on."""
    src = _clamp_src()
    assert "quote_free < min_notional" in src
    assert "Nothing placeable" in src


def test_QUOTE_AMOUNTS_FLOOR_TO_THE_CENT_NEVER_ROUND() -> None:
    """THE LAST LEG'S BUG, TWICE. Free balance was 36.20972275 USDC; the order was clamped to
    exactly that and `round(_, 2)` published 36.21 -- $0.00028 more than the account held. The
    venue answered `insufficient balance`, which reads as a sizing error and was a rounding
    direction. Rounding to nearest is safe on every order EXCEPT the one that spends the whole
    balance, and that is precisely the order a rebalance ends on."""
    f = _mod()._floor_2dp
    assert f(36.20972275) == 36.20
    assert f(41.999) == 41.99
    assert f(5.0) == 5.0
    assert f(36.219) == 36.21
    # the property that matters: never more than the input
    for v in (0.001, 1.005, 99.999, 36.20972275):
        assert f(v) <= v


def test_THE_PLACED_AMOUNT_IS_FLOORED_NOT_ROUNDED() -> None:
    src = _SRC.read_text("utf-8")
    assert "_floor_2dp(delta)" in src, "the order amount still rounds to nearest"
    assert 'place_market_quote(sym, "BUY", round(' not in src
