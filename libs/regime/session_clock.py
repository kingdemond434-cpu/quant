"""The venue's stamp clock, converted to real time, and the market sessions in real time.

THE BARS ARE BROKER STAMPS WEARING A UTC LABEL. Every MT5 bar and tick this desk stores carries
the venue's own wall clock under a `tz="UTC"` label. That clock is NEW YORK + 7 HOURS: the FX day
ends at 17:00 New York, which the venue stamps 00:00, so it is UTC+3 while New York is on daylight
time and UTC+2 otherwise. MEASURED on this desk's own bars (2026-09-30): across 2018-2026 every
week of EURUSD H1 opens on a Monday 00:00 stamp, INCLUDING the weeks between the US and the EU
clock changes (e.g. 2026-03-09, -16, -23), when an EET/EEST clock would have stamped the 17:00
New York open 23:00 Sunday. So `index.hour` is a SERVER hour, and
`index.tz_convert("Europe/London")` shifts a server stamp as if it were UTC and lands two or
three hours early.

WHAT IT COST (Tier S, 2026-09-30). Research tables wrote their sessions in UTC ("asia 0-7",
"london 7-13", "ny 13-21") and compared them with those server hours, so a hypothesis about the
London open was tested on 04:00-10:00 UTC in summer -- the Frankfurt pre-open -- and a "New York"
cell on the London afternoon. Every such trial was charged to the family-wise budget and tested
a mechanism nobody proposed.

ONE CONVERSION, HERE. `server_to_utc` reads the stamp as New York wall time + 7 h and returns
the true UTC instant, DST included. `in_session` answers "was this bar inside the market's own
session" in the market's own local clock, so London and New York follow their own DST weeks.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

#: The venue's stamp clock: New York wall time shifted +7 h (see module docstring), so it follows
#: US daylight-time dates, not the EU's.
SERVER_TZ = "America/New_York"
SERVER_SHIFT_H = 7

#: Each market's session in ITS OWN local clock: (tz, start hour, end hour), [start, end).
MARKET_SESSIONS: dict[str, tuple[str, int, int]] = {
    "asia": ("Asia/Tokyo", 8, 16),
    "london": ("Europe/London", 8, 16),
    "ny": ("America/New_York", 8, 16),
}
SESSION_ALIAS = {"tokyo": "asia", "asian": "asia", "newyork": "ny", "new_york": "ny",
                 "us": "ny", "europe": "london", "eu": "london"}


def server_to_utc(index: Any) -> pd.DatetimeIndex:
    """The true UTC instants of broker-stamped times (a DatetimeIndex, naive or UTC-labelled):
    the stamp minus seven hours, read as New York wall time.

    A stamp in the spring-forward gap is shifted forward; one in the autumn repeat hour is read
    as the first (summer) occurrence. Both are one hour a year and never raise.
    """
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    idx = idx - pd.Timedelta(hours=SERVER_SHIFT_H)
    local = idx.tz_localize(SERVER_TZ, ambiguous=np.ones(len(idx), dtype=bool),
                            nonexistent="shift_forward")
    return local.tz_convert("UTC")


def utc_offset_h(at: Any = None) -> int:
    """The venue stamp's offset from UTC, in hours, at the UTC instant `at` (default now): 3 while
    New York is on daylight time, 2 otherwise. A constant is right for half the year only."""
    ts = pd.Timestamp.now(tz="UTC") if at is None else pd.Timestamp(at)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    local = ts.tz_convert(SERVER_TZ)
    stamp = local.tz_localize(None) + pd.Timedelta(hours=SERVER_SHIFT_H)
    hours: float = (stamp - ts.tz_localize(None)) / pd.Timedelta(hours=1)
    return round(hours)


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


# ------------------------------------------------------------------------------ anchor clocks
#
# ANCHOR-CLOCKED FAMILIES KEEP THEIR ANCHOR (principal/coordinator decision, 2026-10-06). A family
# whose signal is DEFINED by a market's open, close, gap or the daily rollover fires at that
# anchor, which for the FX day is the venue's 00:00 stamp (17:00 New York) -- outside every
# market's 08:00-16:00 local window. Filtering such a family by `in_session` would leave its
# `asia` cell with no signals at all (overnight_gap_decay fires at server 00 only). For these
# families a session means ANCHORED TO THAT MARKET: from the prior close (the venue's day
# boundary, server 00:00) through the market's own session end (16:00 local), DST included.
# That window always contains both the market session and the old server-hour windows
# (asia 0-8, london 8-16, ny 14-22), so no anchored cell can lose a signal it had.

#: Families whose signal is defined by an open, a close, a gap or the rollover, by name.
ANCHOR_FAMILIES = frozenset({"overnight_gap_decay", "session_range_breakout", "opening_range",
                             "carry"})
#: ...and any family whose NAME says the same.
_ANCHOR_NAME = re.compile(r"(^|_)(gap|overnight|opening|rollover)(_|$)|(^|_)session_range(_|$)")
#: The name rule as text, for readers that version a cache by it (`family_firing.clock_settings`).
ANCHOR_NAME_RULE = _ANCHOR_NAME.pattern


def anchor_clocked(family: Any, params: dict[str, Any] | None = None) -> bool:
    """Is this family's signal defined by a market's open, close, gap or the rollover?

    BY NAME ONLY -- THE JUDGE'S RULE (2026-10-07). The sealed judge filters a replay with
    `family_call.session_filter(sigs, session)` and no family, so each signal's own `tag` (the
    family's name) is all it can read; `cell_modifiers.apply` does the same for a `selector`.
    The oracle (`family_firing`), the forward clock and the executor must call the same window
    on the same cell, so `params` never decide. A spec-parameter rule did, and it disagreed with
    the judge on parameters that are not clocks: `pin_bar_reversal`'s `anchor` is a PRICE
    reference (open or mid of the bar), `htf_anchor_trend`'s `anchor_mult` a lookback, and
    `hedging_demand_close`'s `close_hour` the hour it fires, which the judge filters on the
    market's own session. The oracle then folded session variants the judge scores apart.
    `params` stays in the signature for callers that pass it."""
    del params
    name = str(family or "").strip().lower().removeprefix("family_")
    if not name:
        return False
    return name in ANCHOR_FAMILIES or bool(_ANCHOR_NAME.search(name))


def in_anchored_session(index: Any, session: str) -> np.ndarray | None:
    """Per stamp, whether it lies between the prior close (the venue's 00:00 stamp of its own
    day) and the end of that market's session (16:00 local) -- the window an anchor-clocked family
    is judged in. None for a session this table does not know, as `in_session`."""
    key = SESSION_ALIAS.get(str(session).strip().lower(), str(session).strip().lower())
    spec = MARKET_SESSIONS.get(key)
    if spec is None:
        return None
    tz, _lo, hi = spec
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    if len(idx) == 0:
        return np.zeros(0, dtype=bool)
    start = server_to_utc(idx.normalize()).tz_convert(tz)     # the prior close, local
    day = start.tz_localize(None).normalize()
    end_wall = day + pd.Timedelta(hours=hi)
    later = np.asarray(start.tz_localize(None) >= end_wall)    # the session ends the next day
    end_wall = end_wall + pd.to_timedelta(later.astype(int), unit="D")
    end = end_wall.tz_localize(tz, ambiguous=np.ones(len(idx), dtype=bool),
                               nonexistent="shift_forward")
    local = server_to_utc(idx).tz_convert(tz)
    return np.asarray(local < end)


def filter_mask(index: Any, session: str, *, anchored: bool = False) -> np.ndarray | None:
    """The shared session filter's own answer per stamp: the market's session, or for an
    anchor-clocked family the anchored window."""
    return in_anchored_session(index, session) if anchored else in_session(index, session)
