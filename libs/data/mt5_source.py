"""MT5 ingestion (read path) and timezone normalization.

MT5 returns bar times as a Unix epoch in the *broker server's* wall clock, which is the
classic source of session/seasonal bugs. :func:`load_mt5_bars` therefore reads raw bars as
naive server time and converts to true UTC via :func:`normalize_timezone`, which is DST-aware
(it uses the IANA zone, not a fixed offset).
"""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

import pandas as pd

from libs.data.errors import MT5Error
from libs.data.instruments import get_spec
from libs.data.schema import BAR_COLUMNS, validate_bars
from libs.data.timeframe import Timeframe

# Raw columns expected from a bar source (MT5 ``copy_rates_range`` shape).
_RAW_TIME = "time"
_RAW_VOLUME = "tick_volume"


@runtime_checkable
class BarSource(Protocol):
    """Supplies raw bars: a frame with ``time`` (epoch seconds) + OHLC + ``tick_volume``."""

    def fetch_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame: ...


class MT5BarSource:  # pragma: no cover - requires a live Windows MT5 terminal
    """Real bar source backed by the ``MetaTrader5`` package."""

    _TF_MAP: ClassVar[dict[Timeframe, str]] = {
        Timeframe.M1: "TIMEFRAME_M1",
        Timeframe.M5: "TIMEFRAME_M5",
        Timeframe.M15: "TIMEFRAME_M15",
        Timeframe.H1: "TIMEFRAME_H1",
        Timeframe.H4: "TIMEFRAME_H4",
        Timeframe.D1: "TIMEFRAME_D1",
    }

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise MT5Error("the MetaTrader5 package is not installed") from exc
        self._mt5 = mt5
        if not mt5.initialize():
            raise MT5Error(f"MT5 initialize() failed: {mt5.last_error()}")

    def fetch_bars(
        self, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> pd.DataFrame:
        tf_const = getattr(self._mt5, self._TF_MAP[timeframe])
        rates = self._mt5.copy_rates_range(symbol, tf_const, start, end)
        if rates is None or len(rates) == 0:
            raise MT5Error(f"no rates returned for {symbol} {timeframe}")
        return pd.DataFrame(rates)

    def shutdown(self) -> None:
        self._mt5.shutdown()


def normalize_timezone(
    df: pd.DataFrame, *, input_tz: str = "UTC", timestamp_col: str = "timestamp"
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``timestamp_col`` as timezone-aware UTC.

    Naive timestamps are interpreted in ``input_tz`` (DST-aware via the IANA database) and
    converted to UTC; already-aware timestamps are converted to UTC directly.
    """
    out = df.copy()
    series = out[timestamp_col]
    if getattr(series.dt, "tz", None) is None:
        series = series.dt.tz_localize(input_tz)
    out[timestamp_col] = series.dt.tz_convert("UTC")
    return out


def load_mt5_bars(
    symbol: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    *,
    source: BarSource,
    server_tz: str = "UTC",
) -> pd.DataFrame:
    """Load bars from a :class:`BarSource` into the canonical UTC schema.

    Args:
        symbol: a supported instrument.
        timeframe: bar timeframe.
        start, end: inclusive request bounds.
        source: the bar source (injected for testability).
        server_tz: IANA zone of the broker server clock (used to convert to true UTC).
    """
    get_spec(symbol)  # validate the instrument is supported
    raw = source.fetch_bars(symbol, timeframe, start, end)
    if _RAW_TIME not in raw.columns:
        raise MT5Error(f"raw bars missing '{_RAW_TIME}' column")

    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw[_RAW_TIME], unit="s"),  # naive server time
            "open": raw["open"].astype("float64"),
            "high": raw["high"].astype("float64"),
            "low": raw["low"].astype("float64"),
            "close": raw["close"].astype("float64"),
            "volume": raw[_RAW_VOLUME].astype("float64"),
        }
    )
    frame = normalize_timezone(frame, input_tz=server_tz)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return validate_bars(frame[list(BAR_COLUMNS)], require_sorted=True)
