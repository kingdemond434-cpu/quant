"""FORCED FLOW -- trade the minutes in which somebody HAS to transact (blueprint item 10).

WHAT MAKES THIS A MECHANISM AND NOT A TIME-OF-DAY PATTERN

Every other calendar family on this desk fires on a date because the date has historically been
kind to it. This one fires on a date because a NAMED PARTICIPANT IS UNDER AN OBLIGATION, and the
claim is only admissible when all three parts of it can be written down before the window opens:

    1. a known FORCED PARTICIPANT      who must transact regardless of price
    2. a known TIME WINDOW             fixed by a rule, a mandate or a contract
    3. an observable CONSTRAINT        why they cannot simply wait for a better price

`research/forced_flow_calendar.py` supplies all three per event -- `forced_actor`, the UTC
window, and `mechanism` -- computed from rules years ahead. This module is the engine that turns
one of those rows into ordinary `Signal` objects, so the existing gauntlet judges a forced-flow
hypothesis exactly as harshly as a price one. A flow lane must not become a gentler standard.

THE TWO CLAIMS, KEPT SEPARATE ON PURPOSE

    pre_flow          the flow is ANTICIPATED. Dealers who know the fix is coming position ahead
                      of it, so the drift into the window continues through it. Enters in the
                      window BEFORE the event, along the prior three bars' drift.
    post_flow_fade    the flow is AN IMPACT, not information. Price was pushed by somebody who
                      had no choice, so it reverts once the obligation is discharged. Enters
                      AFTER the window closes, against the move the window made.

They are opposite bets on the same minutes and both are economically real, which is exactly the
sort of thing that must be measured rather than assumed. Keeping them as one parameter (rather
than picking whichever fits after seeing the data) means the docket pays for both trials, which
is the honest price.

WHY USING A FUTURE-DATED CALENDAR IS NOT LOOKAHEAD, and the line that separates it from one

An event's window is KNOWN BY RULE. The last business day of March 2026, the third Friday of
June, the Thursday before it, the 09:55 Tokyo fix -- all of them were computable in 2019, from
nothing but a calendar. A backtest that uses them is reproducible live, which is the only test
that matters: the live gateway computes the same window from the same rule at the same moment.

What WOULD be lookahead, and is not done here:

  * reading any PRICE at or after the decision bar. Every signal at bar t is a function of bars
    with index <= t only. `pre_flow` reads the three closes ending at t; `post_flow_fade` reads
    closes inside the event window, which has already ENDED before its first eligible bar.
  * letting the realised bar sequence decide which bar is "the last of the month". That is the
    exact defect `family_turn_of_month` was repaired for -- it built its month-end from
    `month_ends != month_ends.shift(-1)`, which asks whether the market TURNED OUT to be open.
    Here the date comes from the rule and the bars are only asked whether they fall inside it.
  * the central-bank table. Those dates follow no rule and are published roughly a year ahead, so
    a 2026 FOMC date used in a 2019 backtest WOULD be lookahead. The calendar carries no
    pre-publication years at all -- a year with no table produces no rows, and that absence is
    recorded rather than filled in.

THE BAR CLOCK IS NOT UTC, AND THIS FAMILY IS THE KIND THAT CARES. The calendar is genuinely UTC;
the desk's bar index is broker time carrying a UTC tzinfo (+2 winter, +3 summer, measured by
`research/futures_lead_lag`). `clock="utc"` converts the windows into the bars' frame through
`libs.research.bar_clock`; `clock="bars"` -- the default, for the same reason
`family_event_reaction` defaults that way -- assumes the caller's frames already agree. Getting
this wrong does not merely mistime the entry: it puts a "London fix" window on the Frankfurt
lunch hour, and gate 1 judges the mechanism by its name.

UNIVERSE MANDATE. Price-only, MT5/Fusion instruments only. The calendar names no single-name
equity (they are routed to the news/earnings lane) and no crypto-exchange-native venue.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from mt5desk.families import Signal, _atr, _h1, bar_minutes

from libs.research.bar_clock import to_bar_time

BASE = Path(__file__).resolve().parent.parent
CALENDAR_PATH = BASE / "data" / "forced_flow_calendar.json"

#: The two claims. Kept as an explicit tuple so an unrecognised mode REFUSES rather than falling
#: through to whichever branch happens to be written first.
MODES = ("pre_flow", "post_flow_fade")

#: Which clock the calendar's stamps must be read on. Identical in meaning to
#: `family_event_reaction.CLOCKS`, and deliberately the same word, so a reader who has met one
#: has met both.
CLOCKS = ("bars", "utc")

#: How many closes the anticipation claim reads. Three is the blueprint's number; it is a
#: CONSTANT rather than a swept parameter because the claim is "the drift into the window", not
#: "whichever lookback fits".
DRIFT_BARS = 3

#: Every parameter this family takes, at its default. Published so the registering session, the
#: sweep and a certificate all read the same defaults from one place instead of three copies.
FORCED_FLOW_DEFAULTS: dict[str, Any] = {
    "event_kind": "month_end",
    "window_before_min": 60,
    "window_after_min": 90,
    "mode": "pre_flow",
    "stop_atr": 1.0,
    "target_atr": 1.5,
    "atr_n": 14,
    "ttl_bars": 12,
    "symbol": "",
    "clock": "bars",
}


def describe() -> str:
    """The mechanism, in the three parts a forced-flow claim has to have.

    Gate 1 judges a candidate on whether a mechanism was stated BEFORE the evidence. This is that
    statement, and it is deliberately the same text for every parameterisation: if a particular
    `event_kind` needs a different story to sound plausible, that is a second hypothesis and it
    owes its own trial.
    """
    return (
        "FORCED FLOW. "
        "FORCED PARTICIPANT: somebody who must transact regardless of price -- a fund benchmarked "
        "to the WMR 4pm London fix, a tracker that must hold new index weights from the effective "
        "open, a financial holder of a COMEX contract who cannot take delivery of the metal, a "
        "primary dealer contractually obliged to bid an auction, an option market maker hedging "
        "the delta its book acquires mechanically. "
        "TIME WINDOW: fixed by a rule, a mandate or a contract and therefore computable years "
        "ahead -- the last business day of the month, the third Friday of a quarter, first notice "
        "day, 09:55 in Tokyo. `research/forced_flow_calendar.py` derives each one and stores it "
        "in UTC. "
        "OBSERVABLE CONSTRAINT: the participant cannot wait for a better price without breaching "
        "the thing that forces them -- tracking error against a benchmark they are measured on, "
        "physical delivery they cannot take, a dealership obligation, a hedge ratio set by "
        "someone else's published number. "
        "THE TRADE: `pre_flow` claims the flow is anticipated and positions along the drift into "
        "the window; `post_flow_fade` claims the flow is impact rather than information and "
        "fades the move the window made, once the obligation has been discharged."
    )


# ---------------------------------------------------------------------------------- the calendar

def _calendar_module() -> Any:
    """`research.forced_flow_calendar`, under whichever spelling this process can resolve.

    The desk runs modules with `desks/mt5` on sys.path and sometimes with `desks/mt5/research`,
    and a single-form import works in whichever context its author tested and raises in the other
    (`survivor_publication` carries the same note for the same reason).
    """
    try:
        from research import forced_flow_calendar
    except ImportError:                              # pragma: no cover - import-context dependent
        try:
            sys.path.insert(0, str(BASE / "research"))
            import forced_flow_calendar  # type: ignore[no-redef]
        except ImportError:
            return None
    return forced_flow_calendar


def _rows_from_disk(kind: str, lo: date, hi: date) -> list[dict[str, Any]] | None:
    """Calendar rows of `kind` dated in [lo, hi] from the artifact, or None if unreadable."""
    try:
        doc = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = doc.get("events") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("kind", "")) != kind:
            continue
        try:
            when = date.fromisoformat(str(row.get("date", "")))
        except ValueError:
            continue
        if lo <= when <= hi:
            out.append(row)
    return out


def _rows_computed(kind: str, lo: date, hi: date) -> list[dict[str, Any]]:
    module = _calendar_module()
    if module is None:
        return []
    try:
        rows = module.events(lo, hi)
    except (ValueError, TypeError):                  # pragma: no cover - defensive
        return []
    return [e.to_json() for e in rows if e.kind == kind]


def calendar_windows(kind: str, lo: date, hi: date) -> list[tuple[pd.Timestamp, pd.Timestamp,
                                                                 tuple[str, ...]]]:
    """(window_start, window_end, instruments) in UTC for every `kind` event dated in [lo, hi].

    THE ARTIFACT IS PREFERRED AND THE RULE IS THE FALLBACK, not the other way round, because the
    artifact is what a scheduled leg regenerates and what a later audit can diff. When it is
    absent the rules produce the same rows from nothing -- which is the whole reason the calendar
    is computed rather than fetched -- so a missing file costs reproducibility, not signals.
    """
    rows = _rows_from_disk(kind, lo, hi)
    if not rows:
        rows = _rows_computed(kind, lo, hi)
    out: list[tuple[pd.Timestamp, pd.Timestamp, tuple[str, ...]]] = []
    for row in rows:
        try:
            start = pd.Timestamp(str(row["window_start_utc"]))
            end = pd.Timestamp(str(row["window_end_utc"]))
        except (KeyError, TypeError, ValueError):
            continue
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        if end.tzinfo is None:
            end = end.tz_localize("UTC")
        if end <= start:
            continue
        names = row.get("instruments")
        syms = tuple(str(s).upper() for s in names) if isinstance(names, list) else ()
        out.append((start, end, syms))
    return sorted(out)


def _to_bar_clock(ts: pd.Timestamp, clock: str) -> pd.Timestamp | None:
    """The stamp a bar label would carry for this UTC instant, or None when it is not knowable.

    An unconvertible stamp is DROPPED rather than used raw: raw is not a conservative fallback,
    it is the two-to-three-hour error `libs/research/bar_clock` exists to refuse.
    """
    if clock == "bars":
        return ts
    moved, _status, _why = to_bar_time(ts.to_pydatetime())
    return None if moved is None else pd.Timestamp(moved)


# ------------------------------------------------------------------------------------ the family

def family_forced_flow(
    bars: pd.DataFrame,
    side: int = 1,
    *,
    event_kind: str = "month_end",
    window_before_min: int = 60,
    window_after_min: int = 90,
    mode: str = "pre_flow",
    stop_atr: float = 1.0,
    target_atr: float = 1.5,
    atr_n: int = 14,
    ttl_bars: int = 12,
    symbol: str = "",
    clock: str = "bars",
) -> list[Signal]:
    """Signals inside the window around a dated forced-flow event. Price-only, next-open entries.

    `bars` is the desk's usual frame: a tz-aware (or localisable) DatetimeIndex with open/high/
    low/close and optionally volume, on whatever chart the caller handed in -- `_h1` normalises
    the index and leaves the bar clock alone.

    `side` IS A POLARITY, NOT A DIRECTION. The mechanism decides which way to trade -- the prior
    drift for `pre_flow`, the opposite of the window's move for `post_flow_fade` -- and `side`
    says whether the cell is testing that claim (+1) or its mirror (-1), exactly as `side` works
    in `family_event_reaction`. It is the second positional parameter and carries a default
    because `mt5desk.family_call.signals` passes `side=-1` for a short cell and OMITS it
    entirely for a long one; a keyword-only or defaultless `side` would break one of those two
    call shapes, and that asymmetry is load-bearing for every clock already running.

    `symbol` narrows the calendar to events that name it. Left empty, every event of the kind is
    used: a caller who does not say which instrument the bars are cannot be told which events
    bear on it, and silently dropping all of them would read as "this mechanism never fires".

    Entries are at the NEXT OPEN (`trigger=None, wait_bars=1`), the convention every family in
    `families_orthogonal` uses. No cooldown is applied: `engine` holds one position at a time and
    skips signals inside a live trade, so a second discipline here would double-count it.
    """
    if mode not in MODES or clock not in CLOCKS or int(side) not in (1, -1):
        return []
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        return []
    d = _h1(bars)
    if len(d) < max(int(atr_n), DRIFT_BARS) + 3:
        return []

    index = d.index
    step = bar_minutes(d) or 60
    # A window can straddle midnight either side of the bars' own span, so the calendar is asked
    # for a day more than the frame covers. Cheap, and it stops the first and last event of a
    # sample being silently absent.
    lo = (index[0] - pd.Timedelta(minutes=window_before_min + step)).date() - timedelta(days=1)
    hi = (index[-1] + pd.Timedelta(minutes=window_after_min + step)).date() + timedelta(days=1)
    windows = calendar_windows(str(event_kind), lo, hi)
    if not windows:
        return []

    want = str(symbol).strip().upper()
    atr = _atr(d, int(atr_n)).to_numpy()
    close = d["close"].astype(float).to_numpy()
    first = max(int(atr_n), DRIFT_BARS)
    polarity = 1 if int(side) > 0 else -1
    signals: list[Signal] = []

    for start_utc, end_utc, instruments in windows:
        if want and instruments and want not in instruments:
            continue
        start = _to_bar_clock(start_utc, clock)
        end = _to_bar_clock(end_utc, clock)
        if start is None or end is None:
            continue                       # unconvertible stamp: dropped, never used raw

        fade_direction: int | None = None
        if mode == "pre_flow":
            active_lo = int(index.searchsorted(start - pd.Timedelta(minutes=window_before_min),
                                               side="left"))
            active_hi = int(index.searchsorted(start, side="left"))
        else:
            active_lo = int(index.searchsorted(end, side="right"))
            active_hi = int(index.searchsorted(end + pd.Timedelta(minutes=window_after_min),
                                               side="right"))
            # THE MOVE THE FORCED PARTICIPANT MADE, measured from the last close before the
            # window to the last close inside it. Both are bars the market had already printed
            # when the first eligible bar opens, so nothing here can see the future.
            win_lo = int(index.searchsorted(start, side="left"))
            win_hi = int(index.searchsorted(end, side="right"))
            if win_lo < 1 or win_hi - win_lo < 1:
                continue                   # no measurable window move: UNMEASURED, so no trade
            base_move = float(close[win_hi - 1] - close[win_lo - 1])
            if not np.isfinite(base_move) or base_move == 0.0:
                continue
            fade_direction = polarity * (-1 if base_move > 0 else 1)

        for i in range(max(active_lo, first), min(active_hi, len(d) - 1)):
            a = float(atr[i])
            if not np.isfinite(a) or a <= 0:
                continue
            if fade_direction is None:
                drift = float(close[i] - close[i - DRIFT_BARS])
                if not np.isfinite(drift) or drift == 0.0:
                    continue
                direction = polarity * (1 if drift > 0 else -1)
            else:
                direction = fade_direction
            px = float(close[i])
            if not np.isfinite(px):
                continue
            signals.append(Signal(
                time=index[i], side=direction,
                stop=px - direction * float(stop_atr) * a,
                target=px + direction * float(target_atr) * a,
                ttl_bars=int(ttl_bars), tag=f"forced_flow.{event_kind}.{mode}",
                trigger=None, wait_bars=1))
    return signals
