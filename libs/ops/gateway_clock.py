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


#: THE BROKER-EPOCH CLASS (row 247/239, 2026-10-29). MetaTrader's `deal.time`, `deal.time_msc`
#: and `tick.time` count the BROKER's wall clock, not UTC: deal 217155220 closed at 09:09:01 UTC
#: and carries epoch 12:09:01 (Fusion, UTC+3 while New York is on daylight time). Every writer
#: that did `datetime.fromtimestamp(deal.time, tz=UTC)` stamped broker time under a +00:00 label.
#: A measured offset is accepted only when the tick is this fresh against the wall clock; a stale
#: tick (market closed, weekend) carries no reading of the offset. DERIVATION: the venue offsets
#: are whole hours, so a fresh tick sits within a few seconds of a whole hour; six minutes is one
#: tenth of an hour, far inside the half-hour that would make the rounding ambiguous.
OFFSET_FRESH_TOL_H = 0.1
#: Basis labels written on ledger rows, so a reader knows which instant a stamp names.
BASIS_MEASURED = "utc_from_broker_epoch:measured"
BASIS_CALENDAR = "utc_from_broker_epoch:calendar_ny+7"
BASIS_UNMEASURED = "broker_epoch_unconverted"


def measured_offset_h(tick_epoch: Any, wall_epoch: float) -> int | None:
    """The broker clock's offset from UTC in whole hours, read off one FRESH tick, or None.

    `tick_epoch` is the venue's `tick.time` (broker wall seconds), `wall_epoch` this host's real
    UTC `time.time()` at the same moment. None when the tick is absent, stale, or the offset is not
    a plausible whole hour (|h| <= 14)."""
    try:
        diff_h = (float(tick_epoch) - float(wall_epoch)) / 3600.0
    except (TypeError, ValueError):
        return None
    h = round(diff_h)
    if abs(diff_h - h) > OFFSET_FRESH_TOL_H or abs(h) > 14:
        return None
    return int(h)


def broker_epoch_to_utc(epoch: Any, offset_h: int | None = None, *,
                        calendar: bool = True) -> tuple[str | None, str]:
    """(ISO UTC instant, basis) for a MetaTrader broker-wall epoch in seconds.

    `offset_h` is the offset measured in the writer's OWN session (`measured_offset_h`); it wins.
    Without it, `calendar=True` falls back to the venue calendar rule (New York + 7 h, DST-aware:
    `libs.regime.session_clock`), which is the Fusion server's clock and NOT a rule for any other
    venue -- a writer for another venue passes `calendar=False`, and an unmeasured stamp is then
    returned unconverted with BASIS_UNMEASURED rather than guessed."""
    try:
        e = float(epoch)
    except (TypeError, ValueError):
        return None, BASIS_UNMEASURED
    if e <= 0:
        return None, BASIS_UNMEASURED
    wall = datetime.fromtimestamp(e, tz=UTC)
    if offset_h is not None:
        return (wall - timedelta(hours=offset_h)).isoformat(), BASIS_MEASURED
    if calendar:
        return broker_stamp_to_utc(wall).astimezone(UTC).isoformat(), BASIS_CALENDAR
    return wall.isoformat(), BASIS_UNMEASURED


#: A ledger row's exit stamp may trail its real-UTC write time (a pass that ran late records the
#: close late) but may never LEAD it: a stamp in the future of its own write is the broker clock
#: under a UTC label. DERIVATION: five minutes covers the venue's own clock skew against this host
#: (measured in seconds by e8_gold.venue_clock_skew_ms) with room to spare, and is a twelfth of
#: the smallest offset error (one hour) it exists to catch.
LEDGER_CLOCK_TOL_S = 5 * 60


def ledger_clock_breaches(rows: list[dict[str, Any]]) -> list[str]:
    """Why ledger rows written with a converted basis carry a broker stamp, by row: an exit (or
    entry) stamp more than LEDGER_CLOCK_TOL_S after the row's own real-UTC `time`. Legacy rows
    (basis "broker_deal_epoch") are read through `row_utc` and are not breaches."""
    out: list[str] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if not str(r.get("timestamp_basis") or "").startswith("utc_from_broker_epoch"):
            continue
        wrote = _parse(r.get("time"))
        if wrote is None:
            continue
        for field in ("exit_time", "entry_time"):
            ts = _parse(r.get(field))
            if ts is not None and (ts - wrote).total_seconds() > LEDGER_CLOCK_TOL_S:
                out.append(f"deal {r.get('deal')}: {field} {r.get(field)} is "
                           f"{(ts - wrote).total_seconds() / 3600:.2f}h after its write "
                           f"{r.get('time')} (a broker stamp under a UTC label)")
    return out


def row_utc(row: dict[str, Any], field: str) -> datetime | None:
    """THE CORRECTED VIEW of a ledger stamp, without rewriting the ledger: the true UTC instant of
    `row[field]`. A row written with a `utc_from_broker_epoch:*` basis is taken as written; a
    legacy row (`timestamp_basis == "broker_deal_epoch"`, the pre-2026-10-29 Fusion writer) is
    converted by the venue calendar rule. Anything else returns None -- not guessed."""
    ts = _parse(row.get(field)) if isinstance(row, dict) else None
    if ts is None:
        return None
    basis = str(row.get("timestamp_basis") or "")
    if basis.startswith("utc_from_broker_epoch"):
        return ts.astimezone(UTC)
    if basis == "broker_deal_epoch":
        return broker_stamp_to_utc(ts)
    return None


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
