"""Broker bar stamps -> true UTC, for anything compared against the wall clock.

MetaTrader returns bar times as epoch seconds on the BROKER's clock: New York wall time shifted
+7 h, so UTC+2 in the northern winter and UTC+3 while New York is on daylight time. `h1_frame`
and `scalp_exec.frame_from_rates` label those seconds UTC, which is right for counting bars and
wrong for any instant later compared with `datetime.now(UTC)`. A family or scalp time exit built
from such a stamp fired two to three hours after the replay's exit (2026-10-13).

The replay counts BARS, so a deadline is the entry bar's true UTC instant plus N real bar
lengths -- convert the stamp first, then add. Adding first and converting the sum is an hour off
across a US daylight-time change, where the broker clock itself skips or repeats an hour.

Mirrors `libs.regime.session_clock.server_to_utc` without importing `libs` (the money path does
not); a test pins the two together.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

SERVER_TZ = "America/New_York"
SERVER_SHIFT_H = 7


def broker_to_utc(stamp: Any) -> pd.Timestamp:
    """The true UTC instant of one broker-stamped time (naive, or labelled UTC). A stamp in the
    spring-forward gap is shifted forward; one in the autumn repeat hour is read as the first
    (daylight) occurrence -- `server_to_utc`'s rules exactly."""
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    wall = ts - pd.Timedelta(hours=SERVER_SHIFT_H)
    return wall.tz_localize(SERVER_TZ, ambiguous=True, nonexistent="shift_forward").tz_convert(
        "UTC")
