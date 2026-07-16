"""Data-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class DataError(QuantPlatformError):
    """Generic data-pipeline error (bad schema, bad timezone, lake I/O)."""


class MT5Error(DataError):
    """The MetaTrader 5 terminal could not be reached or returned no data."""
