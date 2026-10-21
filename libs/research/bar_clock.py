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
    the caller drops the event. The one other measurement, the release-spike reading of
    `bar_clock_release` (the desk's own UTC-stamped releases against the bars' range spike), is
    used only by a caller that opts in (`fallback=True`), only inside the season instance it was
    measured on, and is named in the status (`CONVERTED_RELEASE_SPIKE`). A constant +2 would be
    right for half the year and silently wrong for the other half, which is the defect
    `broker_clock_measured.json` already has: it records `offset_by_trough: 2` beside
    `offset_by_peak: 3` on all ten symbols, cannot settle the disagreement, and stores one
    scalar.
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
from datetime import UTC, datetime, timedelta
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
#: Converted by the release-spike reading, for a caller that opted in. Never returned otherwise.
OK_RELEASE = "CONVERTED_RELEASE_SPIKE"


def _read(root: Path) -> dict[str, Any]:
    try:
        value = json.loads((root / Path(*CLOCK_REL.split("/"))).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_offsets(root: Path) -> dict[str, int]:
    doc = _read(root)
    out: dict[str, int] = {}
    for name, block in (doc.get("per_season") or {}).items():
        if not isinstance(block, dict):
            continue
        off = block.get("offset_h")
        if isinstance(off, int) and block.get("agrees_across_pairs"):
            out[str(name)] = off
    return out


def _release(root: Path) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    """(season -> offset, season -> measured window) from the release-spike reading."""
    try:
        from libs.research import bar_clock_release
    except ImportError:                                                 # pragma: no cover
        return {}, {}
    try:
        return bar_clock_release.offsets(root), bar_clock_release.windows(root)
    except Exception:                                                   # fail closed: no clock
        return {}, {}


def release_offsets(root: Path | None = None) -> dict[str, int]:
    """The release-spike reading alone (what an opted-in caller may fall back to)."""
    return _release(Path(root or _ROOT))[0]


def sources(root: Path | None = None) -> dict[str, str]:
    """Which measurement answers each season: BAR_CLOCK.json, or the release-spike reading."""
    base = Path(root or _ROOT)
    out = dict.fromkeys(_file_offsets(base), "BAR_CLOCK.json")
    for name in _release(base)[0]:
        out.setdefault(name, "release_spike")
    return out


def offsets(root: Path | None = None, *, fallback: bool = False) -> dict[str, int]:
    """The measured offset per season, or {} when nothing has measured one.

    EMPTY IS A REAL ANSWER. A caller that receives {} must drop the join, not fall back to zero:
    zero is the one value guaranteed wrong, since these bars are on no UTC-equivalent clock in
    either season.

    `BAR_CLOCK.json` (futures_lead_lag, a feed stamped in epoch seconds) is the clock. The
    release-spike reading (`bar_clock_release`) answers ONLY for a caller that opts in with
    `fallback=True`, and `to_bar_time` bounds it to the season instances it was measured on.
    """
    base = Path(root or _ROOT)
    out = _file_offsets(base)
    if fallback:
        for name, off in _release(base)[0].items():
            out.setdefault(name, off)
    return out


def season_instance(when: datetime) -> str:
    """One season in one year: `summer-2026`, `winter-2026` (Dec 2025..Feb 2026), or shoulder.

    Inside one instance there is no daylight-saving changeover by construction (the windows end
    clear of it), so an offset measured on releases of that instance holds for all of it -- and
    for nothing outside it.
    """
    season = season_of(when)
    if season == "winter":
        return f"winter-{when.year + 1 if when.month == 12 else when.year}"
    return f"{season or 'shoulder'}-{when.year}"


def season_of(when: datetime) -> str | None:
    """Which measured season an instant belongs to, or None in the shoulder."""
    mmdd = when.month * 100 + when.day
    for name, (lo, hi) in SEASON_WINDOWS.items():
        inside = (lo <= mmdd <= hi) if lo <= hi else (mmdd >= lo or mmdd <= hi)
        if inside:
            return name
    return None


#: How far either side of the first and last measured release the release-spike clock answers
#: (audit of 0742dcb1b: the whole season instance reached 3.5 months before the first release).
#: The season windows already exclude every changeover; this keeps the claim near its evidence.
RELEASE_MARGIN_DAYS = 14


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def _window_bounds(win: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    try:
        first = _aware(datetime.fromisoformat(str(win.get("first"))))
        last = _aware(datetime.fromisoformat(str(win.get("last"))))
    except (TypeError, ValueError):
        return None, None
    margin = timedelta(days=RELEASE_MARGIN_DAYS)
    return first - margin, last + margin


def to_bar_time(when: datetime, root: Path | None = None, *, fallback: bool = False
                ) -> tuple[datetime | None, str, str]:
    """Convert a genuinely-UTC instant into the stamp the bar index would carry.

    Returns (converted, status, why). `converted` is None whenever the answer is not knowable, and
    the caller must drop the row rather than use `when` unchanged -- an unconverted stamp is not a
    conservative fallback, it is the bug.

    PROVENANCE IS IN THE STATUS (audit of b9d37faaa). `CONVERTED` means `BAR_CLOCK.json`
    answered. `CONVERTED_RELEASE_SPIKE` means the caller opted in (`fallback=True`) and the
    release-spike reading answered, inside the season instance it was measured on AND within
    RELEASE_MARGIN_DAYS of its first and last measured release; the why names that window.
    Outside it the answer is UNMEASURED: a three-week 2026 reading says nothing about 2024. A
    caller that does not opt in sees exactly the old behaviour.
    """
    base = Path(root or _ROOT)
    table = offsets(root)
    rel_off, rel_win = _release(base) if fallback else ({}, {})
    if not table and not rel_off:
        return None, UNMEASURED, (
            "no measured bar clock on disk: run desks/mt5/research/futures_lead_lag.py"
            + (" (and the release-spike reading of libs/research/bar_clock_release.py resolved "
               "no season)" if fallback else "")
            + ". The bars are broker-stamped and no offset is knowable, so the join cannot be "
            "made")
    season = season_of(when)
    if season is None:
        return None, SHOULDER, (
            f"{when.date()} falls between the measured season windows, where the offset depends "
            "on a daylight-saving changeover date nothing here measures. Dropped rather than "
            "converted with a neighbouring season's offset")
    if season in table:
        off = table[season]
        return when + timedelta(hours=off), OK, (
            f"BAR_CLOCK.json: shifted {off:+d}h into the bars' own frame ({season}); the bar "
            "index is broker time carrying a UTC tzinfo, so an unconverted UTC stamp lands on a "
            f"bar that opened {off} hours before the information existed")
    if season in rel_off:
        win = rel_win.get(season) or {}
        inst = season_instance(when)
        span = (f"{', '.join(win.get('instances') or [])} on {win.get('n_releases')} releases "
                f"{str(win.get('first'))[:10]}..{str(win.get('last'))[:10]}")
        lo, hi = _window_bounds(win)
        if inst not in (win.get("instances") or []) or lo is None or hi is None \
                or not (lo <= _aware(when) <= hi):
            return None, UNMEASURED, (
                f"the release-spike clock was measured on {span} (+/-{RELEASE_MARGIN_DAYS} "
                f"days); {when.date()} ({inst}) is outside that window, so no offset is "
                "knowable for it")
        off = rel_off[season]
        return when + timedelta(hours=off), OK_RELEASE, (
            f"release_spike ({span}): shifted {off:+d}h into the bars' own frame ({season})")
    return None, UNMEASURED, f"the {season} offset is not measured"


def convert_many(stamps: list[datetime], root: Path | None = None, *,
                 fallback: bool = False) -> dict[str, Any]:
    """Convert a batch and account for every row, so a shrinking sample is never silent."""
    kept, dropped = [], {UNMEASURED: 0, SHOULDER: 0}
    by_source: dict[str, int] = {}
    why = ""
    for s in stamps:
        got, status, reason = to_bar_time(s, root, fallback=fallback)
        if got is None:
            dropped[status] = dropped.get(status, 0) + 1
            why = why or reason
        else:
            kept.append(got)
            by_source[status] = by_source.get(status, 0) + 1
    return {
        "kept": kept, "n_in": len(stamps), "n_kept": len(kept),
        "dropped": dropped, "kept_by_source": by_source,
        "coverage": (round(len(kept) / len(stamps), 4) if stamps else 0.0),
        "why": why or "every stamp converted",
        "rule": ("an event placed on the wrong bar is a LOOK-AHEAD and not a conservative error: "
                 "it enters on a bar that opened before the information existed. Dropping it "
                 "removes an observation the desk cannot place and changes no size and no live "
                 "trade"),
    }
