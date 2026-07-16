"""Execution-layer exceptions."""

from __future__ import annotations

from libs.core.errors import QuantPlatformError


class ExecutionError(QuantPlatformError):
    """Generic execution error (missing approval, unknown order, invalid request)."""


class BrokerError(ExecutionError):
    """The broker reported an error."""


class TransientBrokerError(BrokerError):
    """A retryable broker error (requote, momentary disconnect) — no order was placed."""


class BrokerTimeout(BrokerError):
    """An *ambiguous* broker timeout: the order may or may not have been placed.

    Never assume a fill. The caller must reconcile against the broker before acting.
    """


class ReconciliationError(ExecutionError):
    """Internal state diverged from the broker (the source of truth) — fail closed."""
