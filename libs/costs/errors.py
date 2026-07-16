"""Cost-model exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class CostError(QuantPlatformError):
    """Invalid cost inputs or missing cost parameters."""
