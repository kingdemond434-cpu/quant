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


def publication_cadence(n_obs: object, first: object, last: object) -> str | None:
    """The publication cadence a dated series' own span implies, or None when it cannot say.

    Observations per calendar day over [first, last]: about 1 is calendar-daily, about 5/7 is a
    business-day series (weekends and holidays absent), about 1/7 weekly, about 1/30 monthly,
    about 1/91 quarterly. The words are the dataset-usage census's cadence vocabulary, so an
    organ that registers a series can declare the cadence its data actually has.
    """
    from datetime import datetime

    try:
        n = int(n_obs)  # type: ignore[call-overload]
        t0 = datetime.fromisoformat(str(first).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    span_days = (t1 - t0).total_seconds() / 86400.0
    if n < 3 or span_days <= 0:
        return None
    per_day = (n - 1) / span_days
    if per_day >= 12:
        return "hourly"
    if per_day >= 0.9:
        return "daily"
    if per_day >= 0.5:
        return "business_daily"
    if per_day >= 0.1:
        return "weekly"
    if per_day >= 0.025:
        return "monthly"
    if per_day >= 0.008:
        return "quarterly"
    return None
