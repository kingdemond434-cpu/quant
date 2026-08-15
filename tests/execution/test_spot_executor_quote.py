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
