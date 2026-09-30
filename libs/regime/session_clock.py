"""The venue's stamp clock, converted to real time, and the market sessions in real time.

THE BARS ARE BROKER STAMPS WEARING A UTC LABEL. Every MT5 bar and tick this desk stores carries
the venue's own wall clock, EET/EEST (UTC+2 in winter, UTC+3 in summer: measured on the desk's
own feed 2026-08-29, `mt5desk/families.py` `_h1`, and again from the volume troughs in
`libs/regime/broker_clock.py`), under a `tz="UTC"` label. So `index.hour` is a SERVER hour, and
`index.tz_convert("Europe/London")` shifts a server stamp as if it were UTC and lands two or
three hours early.

WHAT IT COST (Tier S, 2026-09-30). Research tables wrote their sessions in UTC ("asia 0-7",
"london 7-13", "ny 13-21") and compared them with those server hours, so a hypothesis about the
London open was tested on 04:00-10:00 UTC in summer -- the Frankfurt pre-open -- and a "New York"
cell on the London afternoon. Every such trial was charged to the family-wise budget and tested
a mechanism nobody proposed.

ONE CONVERSION, HERE. `server_to_utc` reads the stamp as EET/EEST wall time and returns the true
UTC instant, DST included. `in_session` answers "was this bar inside the market's own session"
in the market's own local clock, so the London and New York windows follow their own DST weeks.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

#: The venue's stamp clock. EU DST rules, the desk's recorded reading (see module docstring).
SERVER_TZ = "Europe/Athens"

#: Each market's session in ITS OWN local clock: (tz, start hour, end hour), [start, end).
MARKET_SESSIONS: dict[str, tuple[str, int, int]] = {
    "asia": ("Asia/Tokyo", 8, 16),
    "london": ("Europe/London", 8, 16),
    "ny": ("America/New_York", 8, 16),
}
SESSION_ALIAS = {"tokyo": "asia", "asian": "asia", "newyork": "ny", "new_york": "ny",
                 "us": "ny", "europe": "london", "eu": "london"}


def server_to_utc(index: Any) -> pd.DatetimeIndex:
    """The true UTC instants of broker-stamped times (a DatetimeIndex, naive or UTC-labelled).

    A stamp in the spring-forward gap is shifted forward; one in the autumn repeat hour is read
    as the first (summer) occurrence. Both are one hour a year and never raise.
    """
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    local = idx.tz_localize(SERVER_TZ, ambiguous=np.ones(len(idx), dtype=bool),
                            nonexistent="shift_forward")
    return local.tz_convert("UTC")


def utc_hours(index: Any) -> np.ndarray:
    """The true UTC hour of each broker-stamped time."""
    return np.asarray(server_to_utc(index).hour, dtype=np.int16)


def in_session(index: Any, session: str) -> np.ndarray | None:
    """Per stamp, whether it falls inside that market's session in its own local clock.

    None for a session this table does not know, so a caller keeps its own fall-through rather
    than receiving an all-False mask that would read as "never in session".
    """
    key = SESSION_ALIAS.get(str(session).strip().lower(), str(session).strip().lower())
    spec = MARKET_SESSIONS.get(key)
    if spec is None:
        return None
    tz, lo, hi = spec
    local = server_to_utc(index).tz_convert(tz)
    return np.asarray((local.hour >= lo) & (local.hour < hi))
