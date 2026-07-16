"""Stage 14 portfolio construction errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class Stage14Error(QuantPlatformError):
    """Base error for the Stage 14 compounding / portfolio construction engine."""


class PortfolioGovernanceError(Stage14Error):
    """Raised when a portfolio action violates Stage 14 governance (fail-closed)."""
