"""Self-improvement (Stage 13) exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class SelfImprovementError(QuantPlatformError):
    """Invalid self-improvement inputs or configuration."""


class GovernanceError(SelfImprovementError):
    """A governance rule was violated (e.g. deploying an unvalidated learned policy, or
    Stage 13 attempting to change production weights without Portfolio Engine approval)."""
