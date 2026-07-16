"""Operational-resilience errors."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class OpsError(QuantPlatformError):
    """Base error for backup/restore/watchdog/safe-halt operations."""
