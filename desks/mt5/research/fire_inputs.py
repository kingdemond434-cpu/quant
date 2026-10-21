"""Can this cell's family fire on the inputs the judge would hand it? Asked of the family itself.

    from research.fire_inputs import probe; probe("EURCZK", "cot_positioning")   # a library

WHY (coordinator queue row 176 follow-up, 2026-10-20). The last sweep wrote 9,854 never_fires
verdicts. On the four largest families, measured on this tree with the judge's own build path
(`external_gauntlet.build_cell`), two of them never fire for want of an INPUT, not because the
spec is wrong:

  * `event_reaction`: the judge hands the family every calendar event, and the family places each
    one on the bar clock with `libs.research.bar_clock.to_bar_time`. With no measured bar clock
    (`desks/mt5/reports/BAR_CLOCK.json`, written by `research/futures_lead_lag.py`, or the
    release-spike reading `libs/research/bar_clock_release.py` takes from the desk's own calendar
    and bars) every event is dropped. In a shoulder month (16 Sep - 30 Nov, 16 Feb - 30 Apr)
    every event of a calendar that holds only recent weeks is dropped too. Either way the family
    returns [] on any bars.
  * `cot_positioning`: `orthogonal_sweep._cot_frame(sym)` serves a series only for the symbols
    `scripts/refresh_cot_zcache.py` maps (11) or from the legacy JSON files. Every other symbol
    gets `cot=None`, and the family returns [] on its first line.

A never_fires verdict for those cells names a missing input as scarcity of signals. This module
names the input instead, so `judge_coverage` can park the cell as NEEDS_DATA with the exact
input, hand it to the converter, and re-admit it the moment the input appears.

EXACT, OR SILENT. A probe answers NEEDS_DATA only when the family's OWN code, given the very
inputs `build_cell` would give it, provably returns no signal on any bars:

  * cot: the family is called with `df=None` and the frame `_cot_frame` returns. Its input guard
    runs before it reads a bar, so an empty list can only come from that guard. With a valid
    frame the call reaches `_h1(None)` and raises, and the probe answers PRESENT.
  * event: the family's own `_event_times` is called with the events `build_cell` builds
    (`events_for_symbol(_event_index(), sym)`, `clock="utc"`). The family returns [] whenever
    that list is empty, before any signal is made.

No threshold is copied from any family. Any exception, an unprobed family, or a family the judge
would not resolve to the function probed here answers UNMEASURED, and an UNMEASURED cell is
judged exactly as before (fail open toward judging).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
ROOT = DESK.parent.parent

PRESENT = "PRESENT"
NEEDS_DATA = "NEEDS_DATA"
UNMEASURED = "UNMEASURED"

#: The families this module can probe exactly. Every other family is UNMEASURED.
PROBED = ("cot_positioning", "event_reaction")


def _paths() -> None:
    for p in (str(DESK), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)


def _resolved(family: str) -> Any:
    """The function `external_gauntlet.build_cell` would call for `family`, by its own lookup."""
    from mt5desk import families
    fn = getattr(families, f"family_{family}", None)
    if fn is None:
        from mt5desk import families_orthogonal as fo
        fn = fo.ORTHOGONAL_FAMILIES.get(family)
    return fn


def _probe_cot(sym: str) -> dict[str, Any]:
    from mt5desk.families_orthogonal import family_cot_positioning

    from research import orthogonal_sweep as inputs

    fn = _resolved("cot_positioning")
    if fn is not family_cot_positioning:
        return {"status": UNMEASURED, "why": "the judge resolves cot_positioning elsewhere"}
    frame = inputs._cot_frame(sym)
    # THE JUDGE'S OWN CALL SHAPE: `build_cell` tries `side=1` and, on TypeError, calls again
    # without it. Any other exception means the guard passed and the family reached the bars.
    try:
        try:
            got = fn(None, side=1, cot=frame)
        except TypeError:
            got = fn(None, cot=frame)
    except Exception:
        return {"status": PRESENT, "input": f"cot_series:{sym}"}
    if isinstance(got, list) and not got:
        return {"status": NEEDS_DATA, "missing_input": f"cot_series:{sym}",
                "why": (f"orthogonal_sweep._cot_frame({sym!r}) serves no positioning series "
                        "(data/cot_zcache.parquet has no column for it and no legacy COT JSON "
                        "is on disk), so family_cot_positioning returns [] on its input guard"),
                "stamp": "absent"}
    return {"status": UNMEASURED, "why": "the family answered without reading a bar"}


def _probe_event(sym: str) -> dict[str, Any]:
    from mt5desk.family_event_reaction import _event_times, family_event_reaction
    from mt5desk.family_inputs import events_for_symbol

    from libs.research import bar_clock
    from research import orthogonal_sweep as inputs

    fn = _resolved("event_reaction")
    if fn is not family_event_reaction:
        return {"status": UNMEASURED, "why": "the judge resolves event_reaction elsewhere"}
    events = inputs._event_index()
    if events is None or len(events) == 0:
        # `build_cell` refuses this BY NAME (NOT_RUN build_failed), so it is not a never-fires
        # cell and nothing here claims it.
        return {"status": UNMEASURED, "why": "no calendar: the judge names this a build failure"}
    from mt5desk import family_event_reaction as fer
    _seen = dict(fer._DROPPED)            # the family's counters are not this probe's to move
    _seen_c = dict(fer._CONVERTED)
    fer._DROPPED.clear()
    fer._CONVERTED.clear()
    try:
        times = _event_times(events_for_symbol(events, sym), sym, clock="utc")
        dropped = dict(fer._DROPPED)      # THIS call's drops, by the family's own reason
        placed = dict(fer._CONVERTED)     # and which clock placed the rest
    finally:
        fer._DROPPED.clear()
        fer._DROPPED.update(_seen)
        fer._CONVERTED.clear()
        fer._CONVERTED.update(_seen_c)
    if times:
        return {"status": PRESENT, "input": "event_calendar", "placeable_events": len(times),
                "clock": placed, "dropped": dropped}
    # THE LABEL IS THE FAMILY'S OWN DROP REASON (audit of c72ecfc53). Keying it off "is there any
    # offset at all" called a missing SEASON offset `event_calendar_history`; the input that is
    # missing there is the bar clock. Only events dropped as shoulder-month, with every event's
    # season measured, are a calendar-history gap.
    n_unmeasured = int(dropped.get(bar_clock.UNMEASURED, 0))
    n_shoulder = int(dropped.get(bar_clock.SHOULDER, 0))
    if n_unmeasured:
        missing, why = "bar_clock", (
            f"{n_unmeasured} of {len(events)} calendar events fall in a season with no measured "
            "bar-clock offset (desks/mt5/reports/BAR_CLOCK.json, written by "
            "research/futures_lead_lag.py, does not answer it, and the release-spike reading of "
            "libs/research/bar_clock_release.py does not resolve it): to_bar_time drops them, and "
            f"{n_shoulder} more fall in a shoulder month, so family_event_reaction returns [] on "
            "any bars")
    else:
        missing, why = "event_calendar_history", (
            f"all {n_shoulder} of the {len(events)} calendar events fall in a shoulder month, "
            "where to_bar_time refuses a conversion; the calendar holds no event inside a "
            "measured season, so family_event_reaction returns [] on any bars")
    return {"status": NEEDS_DATA, "missing_input": missing, "why": why,
            "dropped": dropped,
            "stamp": (f"{len(events)}|{sorted(bar_clock.offsets().items())}"
                      f"|{sorted(bar_clock.release_offsets().items())}")}


def probe(sym: str, family: str, params: dict[str, Any] | None = None,
          memo: dict[tuple[str, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    """PRESENT, NEEDS_DATA (with `missing_input`) or UNMEASURED for one cell. Never raises.

    Neither probe reads `params`: `build_cell` replaces the input keys of both families with the
    loaded inputs, so the answer is per (family, symbol) and `memo` may hold it for one pass.
    """
    family, sym = str(family or ""), str(sym or "")
    if family not in PROBED or not sym:
        return {"status": UNMEASURED, "why": "family not probed"}
    key = (family, sym)
    if memo is not None and key in memo:
        return memo[key]
    try:
        _paths()
        out = _probe_cot(sym) if family == "cot_positioning" else _probe_event(sym)
    except Exception as exc:
        out = {"status": UNMEASURED, "why": f"{type(exc).__name__}: {str(exc)[:160]}"}
    if memo is not None:
        memo[key] = out
    return out
