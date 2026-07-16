"""Exception hierarchy for the core layer.

Every error the platform raises deliberately descends from :class:`QuantPlatformError`
so callers can catch the whole family at a boundary without swallowing unrelated bugs.
"""

from __future__ import annotations


class QuantPlatformError(Exception):
    """Base class for all platform errors."""


class ConfigError(QuantPlatformError):
    """Configuration could not be loaded, merged, or validated."""


class TimezoneError(QuantPlatformError):
    """A datetime violated the UTC-only contract (naive, or non-UTC tz)."""


class GitError(QuantPlatformError):
    """Git metadata could not be obtained (not a repo, no commits, git missing)."""


class ReproducibilityError(QuantPlatformError):
    """A reproducibility stamp failed verification, or could not be created."""


class SecretsError(QuantPlatformError):
    """A requested secret was missing or could not be retrieved."""
