"""THE BROKER'S UTC OFFSET, MEASURED FROM THE BARS -- so a host with no terminal still knows it.

WHAT IS DARK WITHOUT IT, and it is the desk's most important state dimension. `state_admission`
judges which market states may condition capital, and its report says:

    "gaps": {"session": "no labeller: this dimension cannot be reconstructed from a timestamp
              alone, or its input (e.g. the broker clock) is unavailable here"}

`build_labeller("session")` asks `session_phase.broker_utc_offset_h()`, which tries a live
MetaTrader5 terminal, then `data/broker_clock.json`, then gives up. There is no terminal off the
box and THE FILE HAS NEVER BEEN WRITTEN -- its docstring names the gateway as "the only writer,
from the process that has the terminal", and that write has not happened. So session has never
been judged, and state-conditioned allocation runs on the two dimensions that remain:

    weekday   RETAIN_SHRUNK   "no measurable improvement; kept only by the shrinkage"
    event     UNJUDGED        "only 1 bucket ever had 15 training trades"

Which is to say it is not running. On a desk whose entire mechanism vocabulary is sessions --
asia range, london_am, afternoon -- the one state that obviously conditions the edge is the one
state nobody can label.

THE OFFSET DOES NOT NEED A TERMINAL. It is written into the bars the desk already holds, twice:

  THE ROLLOVER TROUGH. Every FX venue's thinnest hour is the daily rollover at the New York
  17:00 cutoff -- 21:00 UTC in summer, 22:00 in winter. It is the sharpest, most reliable
  feature of the intraday volume profile and it does not depend on any venue's own habits.

  THE OVERLAP PEAK. The busiest hour is the London/New York overlap, 12:00-16:00 UTC, centred
  on 14:00. Less sharp than the trough, which is why it is the CHECK and not the estimate.

    offset = (argmin(volume by stamp hour) - 22) mod 24        <- the estimate
    check  = (argmax(volume by stamp hour) - 14) mod 24        <- must agree within TOLERANCE

Measured on this desk's own H1 parquets, EURUSD: the volume minimum sits at stamp hour 00 (0.10
of peak) and the maximum at 17. Trough gives +2, peak gives +3, and both are right -- the broker
is on EET/EEST and the eight-year median straddles the DST switch. That is exactly why the
estimate runs on a TRAILING WINDOW: the desk needs the offset in force TODAY, not its average
since 2018.

WHY THE ANSWER IS NOT SIMPLY "UTC, SO ZERO". The parquets carry a tz-aware UTC index, and it is
mislabelled: a genuine UTC feed from any FX venue puts the Tokyo open at hour 00 and the rollover
at 21-22. This one puts its QUIETEST hour at 00 and its busiest at 17. Reading those stamps as UTC
puts London's open in the calmest part of the day and the Tokyo open at the daily minimum, which
is not how the foreign exchange market works. There are no Sunday bars and the week is a perfect
Monday-00:00 to Friday-23:00 rectangle -- the signature of a venue's own EET stamp clock, not of a
UTC conversion, which would carry Sunday 22:00 bars every week.

THREE REFUSALS, because a wrong clock is worse than no clock -- it mislabels every bucket without
ever raising, and produces a confident wrong conditional mean:

  * too few bars in the window                        -> UNMEASURED
  * the trough is not a trough (flat or noisy profile) -> UNMEASURED
  * trough and peak disagree by more than TOLERANCE    -> UNMEASURED, both reported

NOTHING HERE SIZES, LABELS OR TRADES. It publishes a number and its evidence. `session_phase`
stays the one resolver every consumer asks, and this is a third source BELOW the live terminal
and the recorded measurement -- a terminal that can answer is always believed over an inference
from bars.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

__all__ = [
    "MIN_BARS",
    "MIN_TROUGH_DEPTH",
    "OVERLAP_PEAK_UTC",
    "ROLLOVER_TROUGH_UTC",
    "TOLERANCE_H",
    "estimate_offset",
    "hour_profile",
]

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"

#: The UTC hour of the daily rollover trough. 21:00 UTC in summer and 22:00 in winter (the New
#: York 17:00 cutoff); 22 is used because the desk's trailing window is measured against the
#: venue's own stamp clock and a one-hour DST ambiguity is inside TOLERANCE_H either way.
ROLLOVER_TROUGH_UTC = 22

#: The UTC hour at the centre of the London/New York overlap. The CHECK, never the estimate: the
#: overlap is a four-hour plateau and its argmax wanders inside it, while the rollover trough is
#: one sharp hour.
OVERLAP_PEAK_UTC = 14

#: Hours the two anchors may disagree by before the reading is refused. Two, because DST moves
#: them independently across a trailing window that can straddle a switch.
TOLERANCE_H = 2

#: Bars the trailing window needs. 20 trading days x 24 hours; below this a single quiet week
#: moves the argmin.
MIN_BARS = 480

#: How much shallower than the median hour the trough must be before it counts as a trough. A
#: flat profile has no rollover to find, and taking its argmin would return noise wearing an
#: offset. 0.6 means the quietest hour carries under 60% of the median hour's volume -- on this
#: desk's majors it carries 20-30%, so the bar is not close.
MIN_TROUGH_DEPTH = 0.6


def hour_profile(hours: Sequence[int], volume: Sequence[float]) -> np.ndarray | None:
    """Median volume per stamp-hour, normalised by the profile's own median. None if unusable.

    MEDIAN, NOT MEAN, at both levels. One news day at 10x volume moves a mean profile's argmax
    into the hour that news happened to land in; the median is what the hour usually looks like,
    which is the quantity that carries the venue's clock.
    """
    h = np.asarray(hours, dtype="int64")
    v = np.asarray(volume, dtype="float64")
    if h.size != v.size or h.size < MIN_BARS:
        return None
    ok = np.isfinite(v) & (v > 0)
    if int(ok.sum()) < MIN_BARS:
        return None
    h, v = h[ok] % 24, v[ok]
    prof = np.full(24, np.nan)
    for k in range(24):
        sel = v[h == k]
        if sel.size:
            prof[k] = float(np.median(sel))
    if not np.all(np.isfinite(prof)):
        return None                       # a missing hour means the clock cannot be read
    med = float(np.median(prof))
    return prof / med if med > 0 else None


def estimate_offset(profiles: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    """The venue's UTC offset from one or more 24-hour volume profiles, with its evidence.

    `profiles` maps symbol -> a 24-vector from `hour_profile`. Several symbols are better than
    one and the disagreement between them is reported: a venue has ONE clock, so symbols that
    disagree are evidence the estimator is reading something else.
    """
    per: dict[str, Any] = {}
    votes: list[int] = []
    for sym, p in sorted(profiles.items()):
        arr = np.asarray(p, dtype="float64")
        if arr.shape != (24,) or not np.all(np.isfinite(arr)):
            per[sym] = {"status": UNMEASURED, "why": "profile is not a finite 24-vector"}
            continue
        lo, hi = int(np.argmin(arr)), int(np.argmax(arr))
        depth = float(arr[lo] / np.median(arr)) if np.median(arr) > 0 else 1.0
        if depth > MIN_TROUGH_DEPTH:
            per[sym] = {"status": UNMEASURED, "trough_hour": lo, "trough_depth": round(depth, 3),
                        "why": (f"the quietest stamp-hour carries {depth:.0%} of the median "
                                f"hour, above the {MIN_TROUGH_DEPTH:.0%} bar -- this profile has "
                                "no rollover trough to find, so its argmin is noise")}
            continue
        by_trough = (lo - ROLLOVER_TROUGH_UTC) % 24
        by_peak = (hi - OVERLAP_PEAK_UTC) % 24
        gap = min((by_trough - by_peak) % 24, (by_peak - by_trough) % 24)
        row = {"trough_hour": lo, "peak_hour": hi, "trough_depth": round(depth, 3),
               "offset_by_trough": by_trough, "offset_by_peak": by_peak, "disagreement_h": gap}
        if gap > TOLERANCE_H:
            per[sym] = {**row, "status": UNMEASURED,
                        "why": (f"the rollover trough says {by_trough:+d}h and the overlap peak "
                                f"says {by_peak:+d}h -- {gap}h apart, above the {TOLERANCE_H}h "
                                "tolerance. Two anchors that disagree are not one measurement.")}
            continue
        per[sym] = {**row, "status": MEASURED}
        votes.append(int(by_trough))
    if not votes:
        return {"status": UNMEASURED, "utc_offset_hours": None, "per_symbol": per,
                "why": ("no symbol produced a usable rollover trough; the offset stays UNKNOWN "
                        "and every consumer must degrade rather than assume. A hardcoded 0 does "
                        "not raise -- it mislabels every hour and produces a confident wrong "
                        "conditional mean.")}
    # CIRCULAR MEDIAN, because 23 and 1 are two hours apart and their arithmetic mean is 12.
    ang = np.array(votes, dtype="float64") * (2.0 * math.pi / 24.0)
    mean_ang = math.atan2(float(np.sin(ang).mean()), float(np.cos(ang).mean()))
    off = int(round((mean_ang * 24.0 / (2.0 * math.pi)) % 24.0)) % 24
    if off > 12:
        off -= 24                                     # report as a signed offset, not 0..23
    spread = sorted({v if v <= 12 else v - 24 for v in votes})
    return {
        "status": MEASURED, "utc_offset_hours": int(off),
        "n_symbols": len(votes), "votes": spread, "per_symbol": per,
        "agreement": (max(spread) - min(spread)) if spread else 0,
        "why": (f"{len(votes)} symbol(s) place the daily volume trough {off:+d}h from the "
                f"{ROLLOVER_TROUGH_UTC:02d}:00 UTC rollover, cross-checked against the "
                f"{OVERLAP_PEAK_UTC:02d}:00 UTC overlap peak. Measured from bars, so a host with "
                "no terminal has the venue's clock."),
    }
