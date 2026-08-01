"""Refuse new entries inside a scheduled high-impact event window.

WHY THIS AND NOT MORE GATES. Today's audit found the desk over-conservative at the DISCOVERY
stage, and the correct response there was to remove a redundant correction. This is the opposite
kind of control and the distinction matters: it costs ZERO statistical power because it never
judges whether an edge is real. It declines to open a position during a known window in which
price is about to be repriced by an announcement nobody at this desk can forecast. A rejected
entry here is deferred, not killed -- the edge is still there five minutes later.

THE FAILURE IT ADDRESSES is one the source material describes first-hand rather than
hypothetically: "I lost 60% of one of my portfolios just straight away ... there was something
unforeseen, I hadn't made a rule for it", and separately "I lost a whole massive portion because
my drawdown rules didn't execute". Both are the same shape -- a position opened into a window
where the stop is meaningless because the gap jumps straight through it. A stop is a promise the
book cannot keep across a scheduled repricing.

WHY A CALENDAR AND NOT A VOLATILITY TRIGGER. Realised volatility tells you the repricing already
happened. FOMC, CPI and NFP dates are published months ahead, so this is the rare risk that is
knowable in advance and therefore avoidable for free.

*** THE CALENDAR IS DELIBERATELY NOT SHIPPED POPULATED, AND THAT IS THE POINT. ***

I will not hardcode event dates I cannot verify. A guard carrying invented dates is worse than no
guard: it would decline good entries on days nothing happens and wave trades through on days
something does, while reporting healthy. The Federal Reserve publishes its calendar years ahead
and the BLS publishes CPI/NFP release dates annually; those are the sources. Until this file's
JSON is populated from one of them, the guard reports STALE and BLOCKS, loudly -- which is the
desk's own rule that an ambiguous branch must never be the permissive one, and it makes the empty
calendar impossible to ignore rather than silently inert.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

#: Where the verified calendar lives. Schema:
#:   {"valid_through": "2026-12-31",
#:    "source": "federalreserve.gov/monetarypolicy/fomccalendars.htm",
#:    "events": [{"utc": "2026-09-17T18:00:00Z", "name": "FOMC decision", "impact": "high"}, ...]}
CALENDAR = Path("data/event_calendar.json")

#: Minutes before a scheduled release during which no NEW entry may open. Positioning ahead of a
#: binary event is a bet on the announcement, not on the desk's edge.
BEFORE_MIN = 30
#: Minutes after. The first prints are where spreads blow out and stops fill far from their level,
#: so this is an EXECUTION-quality window as much as a directional one.
AFTER_MIN = 15


class EventVerdict(NamedTuple):
    allowed: bool
    state: str
    """CLEAR | BLACKOUT | STALE | EMPTY -- distinct so an audit can tell 'no event' from
    'no calendar'. Collapsing those two is how a guard becomes decorative."""
    why: str


def _parse(ts: str) -> datetime | None:
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def check(now: datetime | None = None, *, calendar: Path | None = None,
          before_min: int = BEFORE_MIN, after_min: int = AFTER_MIN) -> EventVerdict:
    """May a NEW position open right now?

    Blocks on STALE and EMPTY as well as on a real BLACKOUT. That is deliberate and it is the
    desk's standing rule: a guard whose ambiguous branch allows the action is the defect class
    that costs money. Here the cost of a false block is one deferred entry; the cost of a false
    allow is a position opened into a gap that jumps its stop.
    """
    now = (now or datetime.now(tz=UTC)).astimezone(UTC)
    path = calendar or CALENDAR
    try:
        doc: dict[str, Any] = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return EventVerdict(False, "EMPTY",
                            f"no readable event calendar at {path} ({type(exc).__name__}) -- "
                            "BLOCKING new entries. Populate it from "
                            "federalreserve.gov/monetarypolicy/fomccalendars.htm (FOMC) and the "
                            "BLS release schedule (CPI/NFP). This is not a data problem to work "
                            "around; an unknown event window must never read as a clear one")
    through = _parse(str(doc.get("valid_through", "")) + "T23:59:59Z"
                     if "T" not in str(doc.get("valid_through", "")) else
                     str(doc.get("valid_through", "")))
    if through is None or now > through:
        return EventVerdict(False, "STALE",
                            f"calendar valid_through={doc.get('valid_through')!r} but now is "
                            f"{now:%Y-%m-%d} -- BLOCKING. A calendar that has run out cannot "
                            "distinguish a quiet day from an FOMC day, and the permissive "
                            "reading of that ambiguity is the expensive one")
    events = doc.get("events") or []
    if not events:
        return EventVerdict(False, "EMPTY",
                            "calendar present but carries no events -- BLOCKING. An empty list "
                            "is indistinguishable from an unpopulated file, so it is not "
                            "evidence that the window is clear")
    for ev in events:
        when = _parse(str(ev.get("utc", "")))
        if when is None or str(ev.get("impact", "high")).lower() != "high":
            continue
        if when - timedelta(minutes=before_min) <= now <= when + timedelta(minutes=after_min):
            return EventVerdict(
                False, "BLACKOUT",
                f"{ev.get('name', 'scheduled event')} at {when:%Y-%m-%d %H:%MZ} -- inside the "
                f"-{before_min}/+{after_min} minute window. A stop is a promise the book cannot "
                "keep across a scheduled repricing, so the entry is DEFERRED, not cancelled")
    nxt = min((w for w in (_parse(str(e.get("utc", ""))) for e in events)
               if w is not None and w > now), default=None)
    return EventVerdict(True, "CLEAR",
                        f"no high-impact event within -{before_min}/+{after_min} min"
                        + (f"; next is {nxt:%Y-%m-%d %H:%MZ}" if nxt else "; none scheduled ahead"))
