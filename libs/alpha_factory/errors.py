"""Alpha Factory errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class AlphaFactoryError(QuantPlatformError):
    """Base error for the Alpha Factory research operating system."""


class AlphaFactoryGovernanceError(AlphaFactoryError):
    """Raised when the factory is asked to do something it may not (trade/promote/allocate)."""
