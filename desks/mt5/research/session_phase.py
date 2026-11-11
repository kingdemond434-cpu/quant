"""Which session phase a timestamp falls in, and a sleeve's returns inside the current one.

WHAT THIS EXISTS FOR. `pf_allocator` solves the book from daily series and regime probabilities.
Measured 2026-09-03 it contained ZERO references to hour-of-day or session phase, so 08:00 London
open and 22:00 thin-liquidity roll were the same observation to it and produced the same
allocation from identical inputs. An edge that lives in the London expansion and dies in the roll
carried one mean into every hour of the day.

This module supplies the missing half: the phase label for now, and each sleeve's own realised R
inside that phase, which `robust_elog._posterior_mu` shrinks as the narrowest level of the
hierarchy it already runs (state -> sleeve -> family -> no edge).

IT DECIDES NOTHING. No capital, no eligibility, no veto. It reports what the sleeve did at this
hour and hands that to the optimiser that was already the desk's only allocation authority.

STAMP-HOURS, NOT UTC. The desk measured its own feed (mt5desk/families.py `_h1`, 2026-08-29):
"7-16 broker EET is 04:00-13:00 UTC in summer -- it opens three hours before London does and
closes three hours before it does." The broker offset is therefore an explicit argument with no
default. A wrong constant here does not raise; it silently mislabels every hour, which is worse
than failing, and it would mislabel it in the direction of a confident wrong conditional mean.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parent.parent


def broker_utc_offset_h(at: datetime | None = None) -> tuple[int | None, str]:
    """The feed's offset from UTC, and where the answer came from. `None` means UNKNOWN.

    ONE RULE, EVERY CONSUMER. This resolution used to live inside `pf_allocator._live_state`, and
    the state-vector builder needed exactly the same answer. Two implementations of "what time
    does this broker think it is" is precisely the drift that produces a certificate earned in one
    clock and traded in another, so there is one, here, next to the phases it defines.

    THE VENUE CLOCK, THEN THE RECORDED MEASUREMENT, THEN THE BARS, THEN NOTHING. `at` is the
    UTC instant the offset is wanted for (default now): the venue clock moves with US DST, so a
    trade from January and one from July do not share an offset.
    `data/broker_clock.json` is a measurement the desk made when it last had a terminal, which is
    a far better answer than UTC. `data/broker_clock_measured.json` is an INFERENCE from this
    desk's own H1 volume profile -- worse than a measurement, enormously better than None -- and
    it was added (2026-09-07) because the tier above it names the gateway as its only writer and
    had never fired, which left `session` unjudgeable by `state_admission` on a desk whose entire
    mechanism vocabulary is sessions. Absent all three the answer is None and every caller must
    degrade rather than assume: a hardcoded 0 does not raise, it silently mislabels every hour by
    three hours in summer, in the direction of a confident wrong conditional mean.

    THE INFERENCE CORROBORATES THIS MODULE'S OWN EARLIER READING. The docstring above records
    "7-16 broker EET is 04:00-13:00 UTC in summer", i.e. +3 in summer and +2 in winter. Ten
    majors' volume troughs place it at +2 against the winter rollover with the overlap peak at
    +3 -- the same clock, measured a second way, years later, from different data.
    """
    # FIRST: THE VENUE'S MEASURED CLOCK, NEW YORK + 7 H (2026-09-30). Every non-holiday EURUSD
    # week 2018-2026 opens Monday 00:00 stamp = Sunday 17:00 New York, the US/EU DST-split weeks
    # included (pinned by tests/regime/test_session_clock.py), so the offset is a function of the
    # instant: +3 under US daylight time, +2 otherwise. It replaces the "live terminal" tier,
    # which read `h1_source.broker_utc_offset_hours` -- a function that returns 0.0 by
    # construction -- and recorded that 0 into broker_clock.json on 2026-09-11, so every session
    # phase on every host has been labelled three hours off all summer.
    try:
        return _ny_plus_7_offset(at), "venue_clock_ny_plus_7"
    except Exception:
        pass
    try:
        rec = json.loads(BROKER_CLOCK.read_text("utf-8"))
        return round(float(rec["utc_offset_hours"])), "recorded_broker_clock"
    except Exception:
        pass
    # THIRD AND LAST: THE OFFSET MEASURED FROM THE DESK'S OWN BARS. A separate file, deliberately
    # -- `broker_clock.json` belongs to the live-terminal writer above, and an inference must
    # never race or overwrite a measurement. `research/measure_broker_clock.py` finds the daily
    # rollover trough in the H1 volume profile and cross-checks it against the London/New York
    # overlap peak; on this desk's bars seven majors agree unanimously on +2 with the trough at
    # 8-14% of the median hour.
    #
    # THIS TIER EXISTS BECAUSE THE ONE ABOVE IT HAS NEVER FIRED. `broker_clock.json` names the
    # gateway as its only writer and has never been written, so `session` -- the state dimension
    # this desk's entire mechanism vocabulary is built from -- has never been judged by
    # `state_admission`, which left conditional allocation running on `weekday` ("no measurable
    # improvement") and `event` ("only 1 bucket"). An inference from bars is a worse answer than
    # a terminal and an enormously better one than None.
    try:
        rec = json.loads(BROKER_CLOCK_MEASURED.read_text("utf-8"))
        if str(rec.get("status")) == "MEASURED":
            return round(float(rec["utc_offset_hours"])), "measured_from_bars"
    except Exception:
        pass
    return None, "unknown"


def _ny_plus_7_offset(at: datetime | None) -> int:
    import sys
    root = str(_DESK.parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from libs.regime.session_clock import utc_offset_h
    return int(utc_offset_h(at))


BROKER_CLOCK = _DESK / "data" / "broker_clock.json"
#: The offset INFERRED from this desk's own H1 volume profile (`research/measure_broker_clock.py`).
#: A separate path on purpose: `BROKER_CLOCK` belongs to the live-terminal writer, and an
#: inference must never race or overwrite a measurement. Read only as the third and last tier.
BROKER_CLOCK_MEASURED = _DESK / "data" / "broker_clock_measured.json"
#: A recorded offset older than this is re-measured: the broker moves its clock with DST twice a
#: year, and a record that survived the switch would label every hour wrong by one in the
#: direction of a confident wrong conditional mean.
RECORD_MAX_AGE_S = 24 * 3600


def _record_broker_clock(off: int) -> None:
    """Persist the live measurement so every host without a terminal inherits it. Never raises.

    THE ONLY WRITER. Until this existed `broker_clock.json` had a reader and no producer: the
    opportunity curve, the state vector and the allocator all degraded to 'unknown' on every box
    except the one with a terminal, and that box never wrote the number down. Written once per
    day or on change, from the process that has the terminal (the gateway, on its first pass).
    """
    try:
        from datetime import UTC, datetime
        now = datetime.now(tz=UTC)
        try:
            rec = json.loads(BROKER_CLOCK.read_text("utf-8"))
            same = round(float(rec.get("utc_offset_hours"))) == off
            age = (now - datetime.fromisoformat(str(rec.get("measured_at")))).total_seconds()
            if same and age < RECORD_MAX_AGE_S:
                return
        except Exception:
            pass
        BROKER_CLOCK.parent.mkdir(parents=True, exist_ok=True)
        BROKER_CLOCK.write_text(json.dumps({"utc_offset_hours": off, "measured_at":
                                            now.isoformat(), "source": "live_terminal"},
                                           indent=1), "utf-8")
    except Exception as exc:
        # LOUD, NOT SILENT (2026-09-23 swallowed-write audit). An unwritten broker clock leaves
        # every session-phase decision on the LAST measured offset with nothing saying so.
        print(f"session_phase: broker clock NOT written ({type(exc).__name__}: {exc})",
              flush=True)
        return

#: Session phases in broker stamp-hours as [start, end) over a 24h clock. Deliberately finer than
#: the desk's asia/london_am/afternoon sleeve names: the London OPEN expansion and the London MID
#: grind are one label in a sleeve name and two different worlds for a breakout. Whole hours only
#: -- a finer grid buys resolution the evidence cannot support, and the k=40 shrinkage in
#: `_posterior_mu` would discard it anyway.
PHASES: tuple[tuple[str, int, int], ...] = (
    ("ASIA_OPEN", 0, 2),
    ("ASIA_MID", 2, 5),
    ("ASIA_CLOSE", 5, 7),
    ("LONDON_OPEN", 7, 9),
    ("LONDON_MID", 9, 12),
    ("LONDON_NY_OVERLAP", 12, 15),
    ("NY_MID", 15, 18),
    ("NY_CLOSE", 18, 20),
    ("ROLL_THIN", 20, 24),
)


def phase_for_hour(stamp_hour: int) -> str:
    """The phase containing this broker stamp-hour. Total over 0-23 by construction."""
    h = int(stamp_hour) % 24
    for name, start, end in PHASES:
        if start <= h < end:
            return name
    raise ValueError(f"no phase covers stamp-hour {h}; PHASES no longer tiles 0-23")


def phase_at(ts: datetime, *, broker_utc_offset_h: int) -> str:
    """The phase for a UTC instant, on the broker's stamp clock.

    The offset is REQUIRED and has no default, because the desk's own feed is not on UTC and a
    guessed constant mislabels every bucket without ever raising.
    """
    return phase_for_hour((ts.hour + int(broker_utc_offset_h)) % 24)


def _entry_hour(row: Mapping) -> int | None:
    """Broker stamp-hour of a ledger row's entry, or None when it cannot be read.

    None rather than a fallback hour: a row whose time cannot be parsed must be DROPPED from the
    conditional bucket, not quietly assigned to midnight, which would build a phantom edge at
    whatever hour the parser failed toward.
    """
    for key in ("entry_time", "time", "ts"):
        raw = row.get(key)
        if raw is None:
            continue
        text = str(raw)
        # "2026-08-18 08:00:00+00:00" and the ISO 'T' form both appear in this desk's ledgers.
        for sep in (" ", "T"):
            if sep in text:
                clock = text.split(sep, 1)[1]
                if len(clock) >= 2 and clock[:2].isdigit():
                    return int(clock[:2])
    return None


def _venue_offset_at(at: datetime) -> int | None:
    """The venue clock's offset in force at `at`, or None when the clock cannot be read."""
    try:
        return _ny_plus_7_offset(at)
    except Exception:
        return None


def _entry_at(row: Mapping) -> datetime | None:
    """The UTC instant of a ledger row's entry (a naive time is read as UTC), or None."""
    from datetime import UTC
    for key in ("entry_time", "time", "ts"):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt
    return None


def stamp_to_utc(stamp: datetime) -> datetime:
    """A naive broker stamp as the true UTC instant, on the venue's DST-aware clock."""
    import pandas as pd
    _ny_plus_7_offset(None)                       # puts the repo root on sys.path
    from libs.regime.session_clock import server_to_utc
    return server_to_utc(pd.DatetimeIndex([stamp]))[0].to_pydatetime()


def returns_in_phase(rows: Iterable[Mapping], phase: str, *,
                     broker_utc_offset_h: int | None,
                     value_key: str = "r_multiple") -> np.ndarray:
    """This sleeve's realised R for trades ENTERED in `phase`.

    Entry time, not exit: the allocation question is "what is this sleeve worth if it opens a
    position now", and the hour it happened to close in is not something the desk knows at
    decision time. Using exit hour would leak the future into the conditional mean.

    `broker_utc_offset_h=None` reads the venue clock AT EACH TRADE'S OWN TIME (2026-09-30): the
    clock moves with US DST, so one offset for every past trade mislabels everything on the far
    side of a clock change. A trade whose time or offset cannot be read is dropped, not guessed.
    """
    out: list[float] = []
    for row in rows:
        hour = _entry_hour(row)
        if hour is None:
            continue
        off = broker_utc_offset_h
        if off is None:
            at = _entry_at(row)
            off = _venue_offset_at(at) if at is not None else None
            if off is None:
                continue
        if phase_for_hour((hour + int(off)) % 24) != phase:
            continue
        try:
            out.append(float(row.get(value_key)))
        except (TypeError, ValueError):
            continue
    return np.asarray(out, dtype=float)
