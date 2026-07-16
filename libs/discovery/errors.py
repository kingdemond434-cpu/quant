"""Discovery-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class DiscoveryError(QuantPlatformError):
    """Invalid discovery inputs or configuration."""
