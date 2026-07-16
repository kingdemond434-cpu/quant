"""Deterministic-format identifier helpers.

Ids are opaque, URL-safe, prefixed strings (``<prefix>_<hex>``) so a bare id is
self-describing in logs and the audit trail.
"""

from __future__ import annotations

import uuid


def generate_id(prefix: str) -> str:
    """Return a new unique id of the form ``<prefix>_<32-hex>``.

    Args:
        prefix: Short lowercase tag identifying the id's kind (e.g. ``"run"``).
    """
    if not prefix or not prefix.isidentifier():
        raise ValueError(f"prefix must be a valid identifier, got {prefix!r}")
    return f"{prefix}_{uuid.uuid4().hex}"


def new_run_id() -> str:
    """Return a new research-run id."""
    return generate_id("run")


def new_correlation_id() -> str:
    """Return a new correlation id for threading one decision across log records."""
    return generate_id("corr")


def new_stamp_id() -> str:
    """Return a new reproducibility-stamp id."""
    return generate_id("stamp")
