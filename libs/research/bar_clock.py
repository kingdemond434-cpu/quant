"""ONE PLACE THAT KNOWS WHAT CLOCK THE BARS ARE ON, so no join has to guess.

THE BUG THIS EXISTS TO FIX, and it is live. `mt5desk/family_event_reaction` takes an event's
`knowable_at`, localises a naive stamp to UTC, and calls `searchsorted` against the bar index to
find the first bar opening at or after the news. The bar index is NOT UTC -- it is broker time
carrying a UTC tzinfo, +2 in winter and +3 in summer (`research/futures_lead_lag` measures this
against a feed stamped in epoch seconds, reaching 0.978 correlation at the right offset against
0.10 at zero). So an event at 14:30 genuinely-UTC lands against the bar LABELLED 14:00, which is
really the 11:00-12:00 UTC bar in summer.

THE EVENT LANE HAS THEREFORE BEEN ENTERING TWO TO THREE HOURS BEFORE THE NEWS. Not after -- which
would merely be late -- BEFORE, on bars that opened while the information was still private. Every
backtest of it is a look-ahead, and the effect is largest exactly where the lane is supposed to
work, because the hours before a scheduled release are when the drift into it happens.

WHAT THIS MODULE REFUSES TO DO, and the refusals are the point:

  * IT NEVER GUESSES AN OFFSET. With no measured clock on disk, `to_bar_time` returns None and
    the caller drops the event. A constant +2 would be right for half the year and silently wrong
    for the other half, which is the defect `broker_clock_measured.json` already has: it records
    `offset_by_trough: 2` beside `offset_by_peak: 3` on all ten symbols, cannot settle the
    disagreement, and stores one scalar.
  * IT NEVER CONVERTS A SHOULDER-MONTH INSTANT. March, April, October and November lie between
    the measured season windows, and which offset applies depends on a changeover date nothing
    here measures. An hour of error on a fraction of the year is worse than a gap in the same
    fraction, because a gap is visible.
  * IT NEVER MOVES A BAR. Bars are what the broker sent and are not rewritten; the EVENT is
    converted into the bars' frame. Rewriting an index would silently invalidate every artifact
    keyed on it, and the desk has one clock defect already.

DROPPING AN EVENT IS NOT TIMIDITY. It removes an observation the desk cannot place, which raises
the quality of every observation that remains; it caps nothing, vetoes no live trade and changes
no size. An event placed on the wrong bar is not a conservative error -- it is a look-ahead, and
it makes a backtest better than the strategy.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]

#: Published by `desks/mt5/research/futures_lead_lag.py`, which measures the offset against a feed
#: whose stamps are epoch seconds and therefore UTC by definition.
CLOCK_REL = "desks/mt5/reports/BAR_CLOCK.json"

#: The season windows the offsets were measured on, as (month, day) bounds. Mirrors
#: `futures_lead_lag.SEASONS`; anything outside them is a shoulder period and is refused.
SEASON_WINDOWS: dict[str, tuple[int, int]] = {
    "summer": (501, 915),
    "winter": (1201, 215),
}

UNMEASURED = "UNMEASURED"
SHOULDER = "SHOULDER_MONTH"
OK = "CONVERTED"


def _read(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / Path(*CLOCK_REL.split("/"))).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def offsets(root: Path | None = None) -> dict[str, int]:
    """The measured offset per season, or {} when nothing has measured one.

    EMPTY IS A REAL ANSWER. A caller that receives {} must drop the join, not fall back to zero:
    zero is the one value guaranteed wrong, since these bars are on no UTC-equivalent clock in
    either season.
    """
    doc = _read(Path(root or _ROOT))
    out: dict[str, int] = {}
    for name, block in (doc.get("per_season") or {}).items():
        if not isinstance(block, dict):
            continue
        off = block.get("offset_h")
        if isinstance(off, int) and block.get("agrees_across_pairs"):
            out[str(name)] = off
    return out


def season_of(when: datetime) -> str | None:
    """Which measured season an instant belongs to, or None in the shoulder."""
    mmdd = when.month * 100 + when.day
    for name, (lo, hi) in SEASON_WINDOWS.items():
        inside = (lo <= mmdd <= hi) if lo <= hi else (mmdd >= lo or mmdd <= hi)
        if inside:
            return name
    return None


def to_bar_time(when: datetime, root: Path | None = None
                ) -> tuple[datetime | None, str, str]:
    """Convert a genuinely-UTC instant into the stamp the bar index would carry.

    Returns (converted, status, why). `converted` is None whenever the answer is not knowable, and
    the caller must drop the row rather than use `when` unchanged -- an unconverted stamp is not a
    conservative fallback, it is the bug.
    """
    table = offsets(root)
    if not table:
        return None, UNMEASURED, (
            "no measured bar clock on disk: run desks/mt5/research/futures_lead_lag.py. The bars "
            "are broker-stamped and no offset is knowable, so the join cannot be made")
    season = season_of(when)
    if season is None:
        return None, SHOULDER, (
            f"{when.date()} falls between the measured season windows, where the offset depends "
            "on a daylight-saving changeover date nothing here measures. Dropped rather than "
            "converted with a neighbouring season's offset")
    if season not in table:
        return None, UNMEASURED, f"the {season} offset is not measured"
    off = table[season]
    return when + timedelta(hours=off), OK, (
        f"shifted {off:+d}h into the bars' own frame ({season}); the bar index is broker time "
        "carrying a UTC tzinfo, so an unconverted UTC stamp lands on a bar that opened "
        f"{off} hours before the information existed")


def convert_many(stamps: list[datetime], root: Path | None = None) -> dict[str, Any]:
    """Convert a batch and account for every row, so a shrinking sample is never silent."""
    kept, dropped = [], {UNMEASURED: 0, SHOULDER: 0}
    why = ""
    for s in stamps:
        got, status, reason = to_bar_time(s, root)
        if got is None:
            dropped[status] = dropped.get(status, 0) + 1
            why = why or reason
        else:
            kept.append(got)
    return {
        "kept": kept, "n_in": len(stamps), "n_kept": len(kept),
        "dropped": dropped,
        "coverage": (round(len(kept) / len(stamps), 4) if stamps else 0.0),
        "why": why or "every stamp converted",
        "rule": ("an event placed on the wrong bar is a LOOK-AHEAD and not a conservative error: "
                 "it enters on a bar that opened before the information existed. Dropping it "
                 "removes an observation the desk cannot place and changes no size and no live "
                 "trade"),
    }
