"""Bar timeframes."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

_MINUTES: dict[str, int] = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "H1": 60,
    "H4": 240,
    "H8": 480,
    "D1": 1440,
}


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    H8 = "H8"  # crypto perp funding settles every 8h -- native frequency for funding signals
    D1 = "D1"

    @property
    def minutes(self) -> int:
        return _MINUTES[self.value]

    @property
    def timedelta(self) -> timedelta:
        return timedelta(minutes=self.minutes)

    @property
    def pandas_freq(self) -> str:
        """A pandas offset alias (pandas >= 2.2 spelling)."""
        return "1D" if self is Timeframe.D1 else f"{self.minutes}min"
