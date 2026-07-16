"""Alpha-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class AlphaError(QuantPlatformError):
    """Generic alpha-lifecycle error (unknown alpha, bad input)."""


class AlphaStateError(AlphaError):
    """An illegal lifecycle state transition was attempted."""
