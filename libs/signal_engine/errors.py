"""Stage 13.5 signal-engine errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class SignalEngineError(QuantPlatformError):
    """Base error for the signal intelligence engine."""


class SignalGovernanceError(SignalEngineError):
    """Raised when a signal would bypass a mandatory governance gate."""
