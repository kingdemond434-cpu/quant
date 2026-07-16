"""Autonomous research-lab errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class AutoDiscoveryError(QuantPlatformError):
    """Base error for the autonomous research lab."""
