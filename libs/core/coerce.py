"""Strict boundary coercion for untrusted JSON-shaped values.

The research control plane consumes durable JSON and externally mined records.  Keep conversion
rules in one place so malformed or adversarial values cannot obtain numeric or collection meaning
through permissive Python constructors.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def finite_float(value: object, default: float = 0.0) -> float:
    """Return a finite real number, otherwise the fail-closed default."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return result if math.isfinite(result) else default


def integer(value: object, default: int = 0) -> int:
    """Return an integer from a real integral value, otherwise the default."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    result = float(value)
    return int(result) if math.isfinite(result) and result.is_integer() else default


def object_mapping(value: object) -> Mapping[str, object]:
    """Narrow an object to a string-keyed mapping without casting unchecked content."""
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        return {}
    return value


def object_sequence(value: object) -> Sequence[object]:
    """Narrow an object to a non-text sequence."""
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else ()


__all__ = ["finite_float", "integer", "object_mapping", "object_sequence"]
