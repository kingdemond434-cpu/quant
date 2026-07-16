"""Locked holdout — a final out-of-sample slice that may be opened exactly once.

Research happens on the research slice freely; the lockbox is sealed until a single, audited
open. A second open is a protocol violation and raises, because peeking destroys the holdout's
value as independent evidence.
"""

from __future__ import annotations

from typing import Generic, TypeVar, cast

from libs.core.time import to_iso8601, utcnow
from libs.validation.errors import ValidationError

T = TypeVar("T")


class LockedHoldout(Generic[T]):
    """Splits a sliceable dataset into a free research part and a once-openable lockbox."""

    def __init__(self, data: T, *, holdout_fraction: float = 0.3) -> None:
        if not 0.0 < holdout_fraction < 1.0:
            raise ValidationError("holdout_fraction must be in (0, 1)")
        n = len(data)  # type: ignore[arg-type]
        if n < 2:
            raise ValidationError("dataset too small to split")
        self._data = data
        self.split_index = int(n * (1.0 - holdout_fraction))
        self._opened = False
        self._access_log: list[str] = []

    @property
    def is_opened(self) -> bool:
        return self._opened

    @property
    def access_log(self) -> list[str]:
        return list(self._access_log)

    def research(self) -> T:
        """The research portion — always accessible."""
        return cast("T", self._data[: self.split_index])  # type: ignore[index]

    def open_lockbox(self) -> T:
        """The held-out portion — may be opened exactly once."""
        if self._opened:
            raise ValidationError(
                "lockbox already opened once; opening it again invalidates the holdout"
            )
        self._opened = True
        self._access_log.append(to_iso8601(utcnow()))
        return cast("T", self._data[self.split_index :])  # type: ignore[index]
