"""WHEN DID THE GATEWAY LAST PASS, IN UTC -- read from a stamp that was written in broker time.

THE DEFECT (ledger row L3, 2026-10-13). `gateway.main` stamps `st["placement_pass"]` from
`pd.Timestamp(tick.time, unit="s", tz="UTC")`. MetaTrader's `tick.time` is the BROKER's wall clock
counted as seconds, not a UTC epoch, so the stamp carries broker time under a `+00:00` label: at
15:20 UTC it read 18:20 "UTC" (Fusion runs EET/EEST, +3 in summer, +2 in winter). Every reader
that subtracted it from `datetime.now(UTC)` got an age three hours too YOUNG -- a gateway that had
stopped two hours ago still read as passing "in the future" -- and a role check that took the
newest stamp kept calling a cold host the trading host for three hours longer.

THE CURE IS AT THE SOURCE and is a money-path change (desktop spec
`docs/desktop_pass/recovery_drills/gateway_broker_clock_stamp.md`): the gateway writes real UTC and
marks it `placement_pass_clock: "utc"`. Until that lands, and for every legacy file after it, this
is the one place a reader turns the stamp into UTC:

  * `placement_pass_clock == "utc"`  -> the stamp is UTC already, taken as written;
  * otherwise (legacy, broker time)  -> `libs.regime.session_clock.server_to_utc`, the desk's one
    conversion of the venue clock (New York wall time + 7 h, so +3 while New York is on daylight
    time and +2 otherwise, DST dates included).

WHY NOT `session_phase.broker_utc_offset_h()` (audit of #328, 2026-10-13). It answers 0 on every
host: `h1_source.broker_utc_offset_hours` is pinned to 0.0 and `data/broker_clock.json` records 0,
so subtracting it was a no-op that left every reader three hours wrong. The venue clock is a
calendar rule measured on the desk's own bars, so it needs no live terminal to answer.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

UTC_MARK = "utc"


def _parse(value: Any) -> datetime | None:
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def broker_stamp_to_utc(ts: datetime) -> datetime:
    """A venue-clock stamp (naive or UTC-labelled) as the true UTC instant."""
    from libs.regime.session_clock import server_to_utc
    out: datetime = server_to_utc([ts.astimezone(UTC).replace(tzinfo=None)])[0].to_pydatetime()
    return out


def placement_pass_utc(state: Any) -> datetime | None:
    """`gateway_state.json`'s last placement pass as a real UTC instant, or None (UNMEASURED)."""
    if not isinstance(state, dict):
        return None
    ts = _parse(state.get("placement_pass"))
    if ts is None:
        return None
    if str(state.get("placement_pass_clock") or "").lower() == UTC_MARK:
        return ts.astimezone(UTC)
    # Only a "+00:00" (or naive) label is the broker clock in disguise. A stamp that carries a real
    # non-zero offset already says which instant it is; shifting it again would move it twice.
    if ts.utcoffset() not in (None, timedelta(0)):
        return ts.astimezone(UTC)
    return broker_stamp_to_utc(ts)
