"""Validation-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class ValidationError(QuantPlatformError):
    """Invalid validation inputs, or a guarded resource (lockbox) misused."""
