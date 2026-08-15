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
