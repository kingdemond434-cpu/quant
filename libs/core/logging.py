"""Structured logging with correlation ids and secret redaction.

Every record carries a UTC timestamp and the current correlation id, so one decision can
be traced tick -> signal -> order -> fill across the codebase. Context values are scrubbed
of secret-like keys before they ever reach a handler (no secrets in logs).

Usage::

    from libs.core.logging import configure_logging, get_logger, correlation_context

    configure_logging(settings)
    log = get_logger(__name__)
    with correlation_context():
        log.info("placing order", extra={"context": {"symbol": "XAUUSD", "qty": 0.1}})
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from libs.core.ids import new_correlation_id
from libs.core.time import to_iso8601, utcnow

if False:  # typing-only import guard avoids a runtime cycle with config
    from libs.core.config import Settings  # pragma: no cover

_correlation_id: ContextVar[str | None] = ContextVar("_correlation_id", default=None)

# Standard LogRecord attributes that are never treated as user context.
_RESERVED = set(
    vars(logging.makeLogRecord({})).keys()
) | {"message", "asctime", "context", "taskName"}

REDACTED = "***REDACTED***"


# --------------------------------------------------------------------------- correlation id


def set_correlation_id(value: str) -> None:
    """Set the correlation id for the current context."""
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    """Return the correlation id for the current context, if any."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Clear the correlation id for the current context."""
    _correlation_id.set(None)


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    """Bind a correlation id for the duration of the ``with`` block.

    Generates a new id when none is supplied; restores the previous value on exit.
    """
    cid = correlation_id or new_correlation_id()
    token = _correlation_id.set(cid)
    try:
        yield cid
    finally:
        _correlation_id.reset(token)


# --------------------------------------------------------------------------- redaction


def _redact(value: Any, redact_keys: frozenset[str]) -> Any:
    """Recursively redact values whose key matches a secret-like name."""
    if isinstance(value, Mapping):
        return {
            k: (REDACTED if str(k).lower() in redact_keys else _redact(v, redact_keys))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item, redact_keys) for item in value]
    return value


# --------------------------------------------------------------------------- formatters


class JsonFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object."""

    def __init__(self, *, redact_keys: frozenset[str], include_caller: bool = False) -> None:
        super().__init__()
        self._redact_keys = redact_keys
        self._include_caller = include_caller

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": to_iso8601(utcnow()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        if cid is not None:
            payload["correlation_id"] = cid

        context = getattr(record, "context", None)
        if isinstance(context, Mapping) and context:
            payload["context"] = _redact(dict(context), self._redact_keys)

        if self._include_caller:
            payload["caller"] = f"{record.pathname}:{record.lineno}"

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


class HumanFormatter(logging.Formatter):
    """Render a readable single line for local development."""

    def __init__(self, *, redact_keys: frozenset[str]) -> None:
        super().__init__()
        self._redact_keys = redact_keys

    def format(self, record: logging.LogRecord) -> str:
        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        cid_part = f" [{cid}]" if cid else ""
        line = (
            f"{to_iso8601(utcnow())} {record.levelname:<8} {record.name}{cid_part}"
            f" :: {record.getMessage()}"
        )
        context = getattr(record, "context", None)
        if isinstance(context, Mapping) and context:
            redacted = _redact(dict(context), self._redact_keys)
            line += f" {json.dumps(redacted, default=str, separators=(',', ':'))}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


# --------------------------------------------------------------------------- configuration

_HANDLER_TAG = "_qp_core_handler"


def configure_logging(settings: Settings) -> None:
    """Install the platform's logging handler on the root logger (idempotent)."""
    redact_keys = frozenset(settings.logging.redact_keys)
    formatter: logging.Formatter
    if settings.logging.emit_json:
        formatter = JsonFormatter(
            redact_keys=redact_keys, include_caller=settings.logging.include_caller
        )
    else:
        formatter = HumanFormatter(redact_keys=redact_keys)

    root = logging.getLogger()
    # Remove any handler we previously installed so re-configuration is clean.
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_TAG, False):
            root.removeHandler(handler)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    setattr(stream_handler, _HANDLER_TAG, True)
    root.addHandler(stream_handler)
    root.setLevel(settings.logging.level.numeric)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)


class _BoundLogger(logging.LoggerAdapter):  # type: ignore[type-arg]
    """A logger adapter that merges bound context into every record's ``context``."""

    def process(self, msg: Any, kwargs: Any) -> tuple[Any, Any]:
        extra = dict(kwargs.get("extra") or {})
        bound = dict(self.extra or {})
        call_context = dict(extra.get("context") or {})
        bound.update(call_context)
        extra["context"] = bound
        kwargs["extra"] = extra
        return msg, kwargs


def bind(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter:  # type: ignore[type-arg]
    """Return a logger that attaches ``context`` to every record it emits."""
    return _BoundLogger(logger, dict(context))
