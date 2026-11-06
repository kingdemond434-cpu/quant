"""Broker bar stamps -> true UTC, for anything compared against the wall clock.

MetaTrader returns bar times as epoch seconds on the BROKER's clock: New York wall time shifted
+7 h, so UTC+2 in the northern winter and UTC+3 while New York is on daylight time. `h1_frame`
and `scalp_exec.frame_from_rates` label those seconds UTC, which is right for counting bars and
wrong for any instant later compared with `datetime.now(UTC)`. A family or scalp time exit built
from such a stamp fired two to three hours after the replay's exit (2026-10-13).

The replay counts BARS, so a deadline is the entry bar's true UTC instant plus N real bar
lengths -- convert the stamp first, then add. Adding first and converting the sum is an hour off
across a US daylight-time change, where the broker clock itself skips or repeats an hour.

ONE CONVERSION ON THE DESK. This is the scalar form of `libs.regime.session_clock.server_to_utc`
and calls it, so the money path, the research tables and the trade autopsy cannot disagree about
what a broker stamp means. Its rules, for the two hours a year they matter:
  * spring-forward gap (a stamp New York never showed): shifted forward to the first real
    instant, so a deadline built on it is never earlier than the replay's;
  * autumn repeat hour (a stamp New York showed twice): read as the FIRST (daylight) occurrence,
    the earlier instant. A time exit built on it fires at most one hour early, never late, and a
    reader comparing a close against it can be at most one hour strict, never lenient.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def broker_to_utc(stamp: Any) -> pd.Timestamp:
    """The true UTC instant of one broker-stamped time (naive, or labelled UTC). A stamp that
    carries a real non-zero offset is already an instant and is taken as written, as
    `libs.ops.gateway_clock` does: shifting it again would move it seven hours."""
    ts = pd.Timestamp(stamp)
    off = ts.utcoffset()
    if off is not None and off.total_seconds() != 0:
        return ts.tz_convert("UTC")
    # Imported here, as the other money-path modules import libs: the repo root is on the path
    # wherever the gateway runs, and a module that merely imports this one pays nothing.
    from libs.regime.session_clock import server_to_utc
    return pd.Timestamp(server_to_utc([ts])[0])


def broker_epoch_to_utc(sec: Any) -> pd.Timestamp | None:
    """The true UTC instant of broker epoch seconds (`symbol_info().time`, `tick.time`); None
    for a missing or non-positive stamp."""
    try:
        s = int(sec)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    return broker_to_utc(pd.Timestamp(s, unit="s"))
