"""Core enumerations shared across the platform.

These are the single source of truth for environment, run-mode, and log-level vocabularies.
They are plain ``str`` enums so they serialize cleanly to YAML/JSON and SQLite.
"""

from __future__ import annotations

from enum import StrEnum


class Environment(StrEnum):
    """Deployment environment. Selects which ``config/<env>.yaml`` overlay is loaded."""

    DEV = "dev"
    LIVE = "live"
    TEST = "test"


class RunMode(StrEnum):
    """The three run modes of the single codebase (Architecture v1.0)."""

    RESEARCH = "research"
    TRADE = "trade"
    OPS = "ops"


class LogLevel(StrEnum):
    """Logging verbosity levels, mirroring the stdlib level names."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def numeric(self) -> int:
        """Return the stdlib numeric level for this name."""
        import logging

        return int(getattr(logging, self.value))
