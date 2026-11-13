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

THE SOURCE FIX (2026-10-29). `gateway.main` now writes `placement_pass` as the real UTC instant of
the pass with `placement_pass_clock: "utc"`, keeps the raw venue stamp as the naive
`placement_tick_broker`, and judges its stale-tick guard ("never trade a closed market") on the
tick's true UTC instant (`mt5desk.broker_clock`, the scalar form of `server_to_utc`) -- before,
a dead terminal mid-week read 2-3 h younger than it was and the pass traded on it.
`clock_verdict` is the RED check the placement-interlock fence reads: a new-format state without
the mark, or a pass stamped more than `FUTURE_TOLERANCE_S` ahead of the
real clock, is the defect coming back.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

UTC_MARK = "utc"
#: A pass stamp further than this AHEAD of the real clock is not skew, it is a mislabelled clock:
#: the venue runs two or three hours ahead, so a broker stamp under a UTC mark lands far past it.
FUTURE_TOLERANCE_S = 300.0
#: Keys only the post-fix gateway writes. Their presence marks a state as NEW-FORMAT, where a
#: missing UTC mark is a regression rather than a legacy file.
NEW_FORMAT_KEYS = ("placement_tick_broker", "placement_tick_utc", "broker_utc_offset_h")


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


#: THE OFFSET REGIME (audit of #518, 2026-11-13). An offset measured off a fresh tick is the
#: venue's offset NOW; it names a past deal's offset only while no clock change lies between the
#: deal and now. A Friday-open/Monday-close across a US or EU change, or a history backfill, would
#: otherwise be stamped one hour wrong, and that hour flows into the R, hold-time and session
#: attribution the allocator reads. DERIVATION of the 24 h bound: no zone changes its clock twice
#: inside 24 h, so comparing the zone's UTC offset at the two ends of the span sees every
#: transition inside it; past 24 h that endpoint comparison could miss a there-and-back pair.
REGIME_MAX_AGE_S = 24 * 3600
#: Fusion's server clock is New York + 7 h (`libs.regime.session_clock`), so New York's clock
#: changes are the only ones that move it.
FUSION_REGIME_ZONES: tuple[str, ...] = ("America/New_York",)
#: FTMO's server clock is not the Fusion calendar and which DST rule it follows is not measured
#: here (its servers are documented as GMT+2/+3, the European pattern; some MT5 venues follow the
#: US dates instead). A clock change in EITHER zone therefore ends the regime: the stamp stays
#: unconverted (UNMEASURED) rather than risk being an hour wrong.
FTMO_REGIME_ZONES: tuple[str, ...] = ("Europe/Prague", "America/New_York")


def _zone_offset(at: datetime, zone: str) -> timedelta | None:
    import pandas as pd
    out = pd.Timestamp(at).tz_convert(zone).utcoffset()
    return None if out is None else timedelta(seconds=out.total_seconds())


def same_offset_regime(deal_utc: datetime, now_utc: datetime,
                       zones: tuple[str, ...]) -> bool:
    """True when an offset measured at `now_utc` also held at `deal_utc`: the deal is no more than
    REGIME_MAX_AGE_S old (and not more than LEDGER_CLOCK_TOL_S in the future), and no clock change
    in any of `zones` lies between the two instants."""
    if deal_utc.tzinfo is None:
        deal_utc = deal_utc.replace(tzinfo=UTC)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    age = (now_utc - deal_utc).total_seconds()
    if age > REGIME_MAX_AGE_S or age < -LEDGER_CLOCK_TOL_S:
        return False
    try:
        return all(_zone_offset(deal_utc, z) == _zone_offset(now_utc, z) for z in zones)
    except Exception:
        return False


def fusion_epoch_to_utc(epoch: Any, measured_h: int | None,
                        now_epoch: float) -> dict[str, Any]:
    """A Fusion broker-wall epoch as UTC, converted by the calendar rule AT THE DEAL'S OWN INSTANT
    (New York + 7 h, DST-aware), with the offset measured now as a CROSS-CHECK only.

    Returns `utc` (ISO or None), `basis`, `offset_h` (the calendar offset at the deal),
    `measured_h` (the fresh-tick offset now, or None) and `mismatch`: True when the deal lies in
    the measured offset's own regime (`same_offset_regime`) and the two offsets disagree, False
    when they agree there, None when the cross-check could not be made (no fresh tick, or the deal
    is outside the regime -- an older deal's offset is the calendar's alone)."""
    out: dict[str, Any] = {"utc": None, "basis": BASIS_UNMEASURED, "offset_h": None,
                           "measured_h": measured_h, "mismatch": None}
    try:
        e = float(epoch)
    except (TypeError, ValueError):
        return out
    if e <= 0:
        return out
    wall = datetime.fromtimestamp(e, tz=UTC)
    now = datetime.fromtimestamp(float(now_epoch), tz=UTC)
    try:
        utc = broker_stamp_to_utc(wall).astimezone(UTC)
    except Exception:
        utc = None
    if utc is None:
        # The calendar could not answer: the measured offset is used only inside its own regime.
        if measured_h is not None:
            guess = wall - timedelta(hours=measured_h)
            if same_offset_regime(guess, now, FUSION_REGIME_ZONES):
                out.update(utc=guess.isoformat(), basis=BASIS_MEASURED, offset_h=measured_h)
        return out
    cal_h = round((wall - utc).total_seconds() / 3600.0)
    out.update(utc=utc.isoformat(), basis=BASIS_CALENDAR, offset_h=int(cal_h))
    if measured_h is not None and same_offset_regime(utc, now, FUSION_REGIME_ZONES):
        out["mismatch"] = int(cal_h) != int(measured_h)
    return out


def regime_epoch_to_utc(epoch: Any, measured_h: int | None, now_epoch: float,
                        zones: tuple[str, ...] = FTMO_REGIME_ZONES) -> tuple[str | None, str]:
    """(ISO, basis) for a broker-wall epoch on a venue WITHOUT a calendar rule (FTMO): the offset
    measured now is applied only when the deal lies in the same offset regime
    (`same_offset_regime`); otherwise the stamp is returned unconverted with BASIS_UNMEASURED."""
    try:
        e = float(epoch)
    except (TypeError, ValueError):
        return None, BASIS_UNMEASURED
    if e <= 0:
        return None, BASIS_UNMEASURED
    wall = datetime.fromtimestamp(e, tz=UTC)
    if measured_h is not None:
        guess = wall - timedelta(hours=measured_h)
        if same_offset_regime(guess, datetime.fromtimestamp(float(now_epoch), tz=UTC), zones):
            return guess.isoformat(), BASIS_MEASURED
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


def clock_verdict(state: Any, now: datetime | None = None) -> dict[str, Any]:
    """Is `gateway_state.json`'s pass stamp on the right clock? OK, LEGACY, RED or UNMEASURED.

    RED when a NEW-FORMAT state (one carrying `NEW_FORMAT_KEYS`) lacks the `utc` mark, or when the
    pass -- read through `placement_pass_utc` -- sits more than `FUTURE_TOLERANCE_S` in the
    future. LEGACY is an unmarked stamp from a gateway that predates the fix: converted, not red.
    Freshness is not judged here; an old stamp is somebody else's verdict.
    """
    t_now = datetime.now(tz=UTC) if now is None else now
    if not isinstance(state, dict) or not state.get("placement_pass"):
        return {"verdict": "UNMEASURED", "why": "no placement_pass in the gateway state"}
    marked = str(state.get("placement_pass_clock") or "").lower() == UTC_MARK
    new_format = any(k in state for k in NEW_FORMAT_KEYS)
    at = placement_pass_utc(state)
    out: dict[str, Any] = {"placement_pass": state.get("placement_pass"),
                           "placement_pass_clock": state.get("placement_pass_clock"),
                           "new_format": new_format,
                           "pass_utc": at.isoformat(timespec="seconds") if at else None}
    if at is None:
        return {**out, "verdict": "UNMEASURED", "why": "placement_pass is unreadable"}
    ahead = (at - t_now).total_seconds()
    out["ahead_s"] = round(ahead, 1)
    if new_format and not marked:
        return {**out, "verdict": "RED",
                "why": ("new-format gateway state without placement_pass_clock='utc': the pass "
                        "stamp's clock is unknown, the L3 broker-clock defect is back")}
    if ahead > FUTURE_TOLERANCE_S:
        return {**out, "verdict": "RED",
                "why": (f"placement_pass is {ahead / 60:.0f} min in the future (limit "
                        f"{FUTURE_TOLERANCE_S / 60:.0f} min): a broker stamp wearing a UTC label")}
    if not marked:
        return {**out, "verdict": "LEGACY",
                "why": "unmarked broker-clock stamp from a pre-fix gateway; read converted"}
    return {**out, "verdict": "OK", "why": "real UTC, marked"}


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
