"""Tests for the instrument registry and timeframes."""

from __future__ import annotations

from datetime import timedelta

import pytest

from libs.data.errors import DataError
from libs.data.instruments import SUPPORTED_SYMBOLS, AssetClass, get_spec, is_supported
from libs.data.timeframe import Timeframe

_REQUIRED = {"XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "US500", "NAS100", "BTCUSD"}


def test_all_required_symbols_supported() -> None:
    assert set(SUPPORTED_SYMBOLS) >= _REQUIRED
    for symbol in _REQUIRED:
        assert is_supported(symbol)


def test_asset_classes_and_weekend_trading() -> None:
    assert get_spec("XAUUSD").asset_class is AssetClass.METAL
    assert get_spec("EURUSD").asset_class is AssetClass.FX
    assert get_spec("US500").asset_class is AssetClass.INDEX
    assert get_spec("BTCUSD").asset_class is AssetClass.CRYPTO
    assert get_spec("BTCUSD").trades_weekends is True
    assert get_spec("XAUUSD").trades_weekends is False


def test_unsupported_symbol_raises() -> None:
    with pytest.raises(DataError):
        get_spec("DOGEUSD")


@pytest.mark.parametrize(
    ("tf", "minutes", "freq"),
    [
        (Timeframe.M1, 1, "1min"),
        (Timeframe.M5, 5, "5min"),
        (Timeframe.H1, 60, "60min"),
        (Timeframe.H4, 240, "240min"),
        (Timeframe.D1, 1440, "1D"),
    ],
)
def test_timeframe_properties(tf: Timeframe, minutes: int, freq: str) -> None:
    assert tf.minutes == minutes
    assert tf.timedelta == timedelta(minutes=minutes)
    assert tf.pandas_freq == freq
