"""Canonical bar schema and validation.

Every bar frame in the platform uses these columns with a timezone-aware UTC ``timestamp``.
Validation is strict: missing columns, naive/non-UTC timestamps, or NaNs in OHLC are bugs.
"""

from __future__ import annotations

import pandas as pd

from libs.data.errors import DataError

TIMESTAMP = "timestamp"
OHLC = ("open", "high", "low", "close")
VOLUME = "volume"
BAR_COLUMNS: tuple[str, ...] = (TIMESTAMP, *OHLC, VOLUME)


def empty_bars() -> pd.DataFrame:
    """Return an empty, correctly-typed bar frame."""
    frame = pd.DataFrame(
        {
            TIMESTAMP: pd.Series([], dtype="datetime64[ns, UTC]"),
            "open": pd.Series([], dtype="float64"),
            "high": pd.Series([], dtype="float64"),
            "low": pd.Series([], dtype="float64"),
            "close": pd.Series([], dtype="float64"),
            VOLUME: pd.Series([], dtype="float64"),
        }
    )
    return frame


def is_utc_series(series: pd.Series) -> bool:
    """Return whether a datetime series is timezone-aware UTC."""
    tz = getattr(series.dt, "tz", None)
    return tz is not None and str(tz) == "UTC"


def validate_bars(df: pd.DataFrame, *, require_sorted: bool = False) -> pd.DataFrame:
    """Validate a bar frame against the canonical schema; return it unchanged.

    Raises:
        DataError: on missing columns, non-UTC timestamps, OHLC NaNs, or (optionally)
            unsorted timestamps.
    """
    missing = [c for c in BAR_COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"bar frame missing columns: {missing}")
    if len(df) and not is_utc_series(df[TIMESTAMP]):
        raise DataError("timestamp column must be timezone-aware UTC")
    if df[list(OHLC)].isna().any().any():
        raise DataError("OHLC columns must not contain NaNs")
    if require_sorted and not df[TIMESTAMP].is_monotonic_increasing:
        raise DataError("timestamps must be sorted ascending")
    return df
