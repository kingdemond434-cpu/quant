"""Safe retry helper.

Retries are only safe because every order carries an idempotency key — a retry after an
ambiguous failure cannot place a duplicate. Ambiguous timeouts are deliberately *not* retried
blindly here; the engine reconciles instead.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from libs.execution.errors import TransientBrokerError

T = TypeVar("T")
Sleeper = Callable[[float], None]


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff: float = 0.0,
    retry_on: tuple[type[Exception], ...] = (TransientBrokerError,),
    sleeper: Sleeper = time.sleep,
) -> T:
    """Call ``fn`` up to ``attempts`` times, retrying on ``retry_on`` exceptions."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retry_on as exc:
            last_exc = exc
            if attempt < attempts and backoff > 0:
                sleeper(backoff * attempt)
    assert last_exc is not None
    raise last_exc
