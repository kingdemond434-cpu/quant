"""Multi-asset support: factor mapping and instrument tiers."""

from __future__ import annotations

import pytest

from libs.risk.errors import RiskError
from libs.risk.instruments import TIER1, TIER2, Factor, get_factor, tier_of


def test_tier1_and_tier2_membership() -> None:
    assert {"XAUUSD", "XAGUSD", "NAS100", "US500", "BTCUSD", "USDJPY"} == TIER1
    assert {"EURUSD", "GBPUSD", "US30", "GER40", "ETHUSD", "USOIL"} == TIER2


@pytest.mark.parametrize(
    ("symbol", "factor"),
    [
        ("XAUUSD", Factor.PRECIOUS_METALS),
        ("XAGUSD", Factor.PRECIOUS_METALS),
        ("EURUSD", Factor.FX),
        ("USDJPY", Factor.FX),
        ("US500", Factor.EQUITY_INDEX),
        ("NAS100", Factor.EQUITY_INDEX),
        ("BTCUSD", Factor.CRYPTO),
        ("ETHUSD", Factor.CRYPTO),
        ("USOIL", Factor.ENERGY),
        ("Copper", Factor.COMMODITY),
    ],
)
def test_factor_mapping(symbol: str, factor: Factor) -> None:
    assert get_factor(symbol) is factor


def test_tiers() -> None:
    assert tier_of("XAUUSD") == 1
    assert tier_of("EURUSD") == 2
    assert tier_of("SOLUSD") == 3


def test_unknown_instrument_raises() -> None:
    with pytest.raises(RiskError):
        get_factor("DOGEUSD")
    with pytest.raises(RiskError):
        tier_of("DOGEUSD")
