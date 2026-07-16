"""Portfolio-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class PortfolioError(QuantPlatformError):
    """Invalid portfolio inputs or infeasible construction."""
