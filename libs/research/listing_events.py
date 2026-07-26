"""Turn the listing collector's log into event-study observations -- the acquired->convertible step.

``scripts/run_listing_watch.py`` has been logging every new USDT perp with its funding rate at
detection. That is ACQUISITION. Nothing consumed it, so the day-1 listing dislocation -- the
capacity-tiny, structurally recurring edge §39 calls the desk's niche -- could accumulate evidence
forever without ever being able to earn a promotion. This module is the consumer: it shapes those
rows into ``Event`` observations that ``libs.validation.event_study`` can actually rule on.

PRE-REGISTRATION, AND WHY IT IS A MODULE CONSTANT. The hypothesis is fixed HERE, in code, before
the data is looked at:

    A new perp listing whose day-1 funding is extreme-positive (spec longs, no arb capital yet)
    earns a positive abnormal return to the SHORT side over the following HOLD_HOURS.

Direction, holding period and the funding threshold are constants, not arguments. If they were
tunable the script would sweep them, report the best, and the desk would have data-mined its own
collector -- and the multiplicity correction would be a lie, because the trials would be invisible.
Changing any of them is a NEW hypothesis: bump ``VARIANTS_TRIED`` so the Holm bar rises to match,
which is the only honest way to try a second window.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from libs.validation.event_study import Event, EventStudyResult, event_study

#: Holding period for the pre-registered hypothesis. Fixed, not swept.
HOLD_HOURS = 48.0
#: Day-1 funding above this counts as the extreme-positive regime the hypothesis is about.
#: Binance funding is 8-hourly, so 0.10% per interval is ~110% annualised -- genuinely dislocated,
#: not merely "a bit rich".
FUNDING_THRESHOLD = 0.0010
#: Every distinct (direction, window, threshold) ever tried against this collector. The event
#: study's Holm bar reads this: a second window is a second trial, and pretending otherwise is how
#: a screen becomes a "discovery". RAISE IT when you add a variant; never lower it.
VARIANTS_TRIED = 1

LISTINGS_LOG = Path("data/listings.jsonl")


def listing_rows(path: Path = LISTINGS_LOG) -> list[dict[str, Any]]:
    """Parse the collector's log, keeping only listings (a delisting is a different event)."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue                      # a torn append must not take the whole study down
        if row.get("event") == "listed":
            rows.append(row)
    return rows


def qualifying(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Listings in the extreme-positive-funding regime the hypothesis is actually about."""
    return [r for r in rows
            if float(r.get("funding_at_detect", 0.0) or 0.0) >= FUNDING_THRESHOLD]


def build_events(
    rows: list[dict[str, Any]],
    forward_return: Callable[[str, float], float | None],
    benchmark_return: Callable[[float], float | None] | None = None,
    *,
    hold_hours: float = HOLD_HOURS,
) -> list[Event]:
    """Shape qualifying listings into events, SHORT-side and benchmark-adjusted.

    ``forward_return(symbol, t_start)`` returns the long-side return over the holding window, or
    None when the window is not yet complete -- an incomplete window is DROPPED, never zero-filled,
    because a zero is an observation and a missing bar is not.

    The sign flip is the hypothesis: extreme-positive funding is a crowded long, so the trade is
    the short. Benchmark is subtracted over the SAME window, otherwise a listing panel collected
    through a bear month reports -beta and calls it edge.
    """
    events: list[Event] = []
    for r in qualifying(rows):
        sym = str(r.get("symbol", ""))
        t_start = _epoch(r.get("ts"))
        if not sym or t_start is None:
            continue
        long_ret = forward_return(sym, t_start)
        if long_ret is None:
            continue                      # window still open -- not evidence yet
        bench = benchmark_return(t_start) if benchmark_return is not None else 0.0
        if bench is None:
            continue                      # no benchmark means we would be measuring beta
        # short side, benchmark-adjusted: -(asset - benchmark)
        events.append(Event(event_id=f"{sym}@{t_start:.0f}", t_start=t_start,
                            t_end=t_start + hold_hours * 3600.0,
                            ret=-(long_ret - bench)))
    return events


def study_listings(events: list[Event]) -> EventStudyResult:
    """Run the pre-registered listing hypothesis through the event-study gate."""
    return event_study(events, n_cohort=VARIANTS_TRIED, rank=1)


def _epoch(ts: object) -> float | None:
    from datetime import datetime
    if isinstance(ts, int | float):
        return float(ts)
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return None
