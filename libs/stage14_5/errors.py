"""Stage 14.5 hedging / exposure-management errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage14_5Error(QuantPlatformError):
    """Base error for Stage 14.5 portfolio hedging and exposure management."""


class HedgeGovernanceError(Stage14_5Error):
    """Raised when a hedge violates Stage 14.5 governance (fail-closed)."""
