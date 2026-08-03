"""DATA DECAY -- is a source dying, and is it dying by going DARK or by going USELESS?

Triage item #97, whose stated blocker ("needs dataset-usefulness history; nothing to trend yet")
expired once `canary_history.jsonl` and `acquisition_history.jsonl` began accumulating.

TWO DECAYS, AND CONFLATING THEM IS THE WHOLE TRAP. A source can stop being reachable, and a source
can stay perfectly reachable while the information it carries stops being worth anything. They
have opposite remedies -- the first needs a new endpoint, the second needs the source retired --
and a single "health" number averages them into something that recommends neither. They are
measured separately here and never summed.

THE HARDER PROBLEM IS TELLING DECAY FROM ABSENCE OF MEASUREMENT. Three states produce a low or
missing recent reading and only one of them is decay:

  NEVER-WORKED   the source has never once succeeded. Not decay: nothing declined. Filing it as
                 decay would credit the desk with having HAD something it never had.
  UNDERPOWERED   too few independent readings, or too short a span, to distinguish a trend from
                 noise. This is the reading the desk's own history says gets mislabelled: a
                 detector that reports "not measured" as "measured and fine" is how a dead source
                 stays on the books, and reporting it as "decaying" is how a live one gets killed.
  DECAYING       enough independent readings across enough time, and the trend is down.

AN OBSERVATION COUNT IS NOT A SAMPLE SIZE, and this module is built around that specifically
because the live inputs demonstrate it: `instrumentation_coverage.jsonl` holds 164 rows written
within a few seconds of each other, all carrying the identical value. Treating those as 164
observations would give a decay estimate with a beautiful standard error and no content at all.
Readings are therefore collapsed to ONE PER BUCKET (an hour by default) and the sample size is the
number of distinct buckets -- so writing the same value a thousand times in a minute buys exactly
one observation, which is what it is worth.

Pure numpy/stdlib. No I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

__all__ = [
    "MIN_BUCKETS",
    "MIN_SPAN_HOURS",
    "SourceDecay",
    "bucket",
    "classify_decay",
]

#: Distinct time buckets required before a trend is judged at all. Below this the answer is
#: UNDERPOWERED regardless of how many rows were written.
MIN_BUCKETS = 6

#: Span required alongside the bucket count. Six readings inside one hour describe one moment.
MIN_SPAN_HOURS = 24.0

#: Readings closer together than this are the same observation. One hour is chosen because every
#: producer feeding this runs at most hourly; a tighter bucket would only re-admit the burst-write
#: problem it exists to remove.
BUCKET_HOURS = 1.0


@dataclass(frozen=True)
class SourceDecay:
    """One source's decay verdict, with the evidence that produced it."""

    source: str
    kind: str                      # "availability" or "usefulness"
    n_rows: int                    # raw readings seen
    n_buckets: int                 # INDEPENDENT observations -- the real sample size
    span_hours: float
    first_value: float
    last_value: float
    slope_per_day: float
    t_stat: float
    verdict: str
    why: str

    @property
    def decaying(self) -> bool:
        return self.verdict == "DECAYING"


def bucket(points: Iterable[tuple[float, float]],
           bucket_hours: float = BUCKET_HOURS) -> list[tuple[float, float]]:
    """Collapse (timestamp_seconds, value) readings to one MEAN value per time bucket.

    THIS IS THE SAMPLE-SIZE FIX, not a smoothing convenience. 164 rows written inside five seconds
    are one observation of one moment; counting them as 164 produces a standard error that reports
    high confidence in a number nobody measured twice.
    """
    width = max(bucket_hours, 1e-9) * 3600.0
    acc: dict[int, list[float]] = {}
    for ts, val in points:
        if not (np.isfinite(ts) and np.isfinite(val)):
            continue
        acc.setdefault(int(ts // width), []).append(float(val))
    return [(k * width, float(np.mean(v))) for k, v in sorted(acc.items())]


def classify_decay(source: str, points: Sequence[tuple[float, float]], *, kind: str,
                   min_buckets: int = MIN_BUCKETS, min_span_hours: float = MIN_SPAN_HOURS,
                   dead_below: float = 1e-12) -> SourceDecay:
    """Classify one source's trend. `points` is (timestamp_seconds, metric) in any order.

    The metric is "higher is better" for both kinds: availability is a success rate in [0,1],
    usefulness is a score. A falling trend is decay in either case.
    """
    raw = [(float(t), float(v)) for t, v in points
           if np.isfinite(t) and np.isfinite(v)]
    n_rows = len(raw)
    buckets = bucket(raw)
    n = len(buckets)

    def _mk(verdict: str, why: str, slope: float = 0.0, t: float = 0.0) -> SourceDecay:
        span = ((buckets[-1][0] - buckets[0][0]) / 3600.0) if n >= 2 else 0.0
        return SourceDecay(
            source=source, kind=kind, n_rows=n_rows, n_buckets=n, span_hours=span,
            first_value=buckets[0][1] if n else float("nan"),
            last_value=buckets[-1][1] if n else float("nan"),
            slope_per_day=slope, t_stat=t, verdict=verdict, why=why)

    if n == 0:
        return _mk("NO-DATA", "no readings at all -- the producer has never written for this "
                              "source, which is a gap in instrumentation, not a decay measurement")

    vals = np.array([v for _, v in buckets], dtype="float64")
    times = np.array([t for t, _ in buckets], dtype="float64")

    # NEVER-WORKED IS NOT DECAY. A source that has never once succeeded did not decline; recording
    # it as decayed would credit the desk with having HAD something it never had, and would send
    # somebody to repair a connection that was never made.
    if float(vals.max()) <= dead_below:
        return _mk("NEVER-WORKED",
                   f"every one of {n} reading(s) is zero -- this source has never succeeded. That "
                   "is an acquisition failure, not decay: nothing declined.")

    span_h = float((times[-1] - times[0]) / 3600.0)
    if n < min_buckets or span_h < min_span_hours:
        return _mk("UNDERPOWERED",
                   f"{n} independent reading(s) over {span_h:.1f}h (bar {min_buckets} over "
                   f"{min_span_hours:.0f}h) from {n_rows} raw row(s). Not a finding of health and "
                   "not a finding of decay -- the sample cannot separate them. Readings written "
                   "in bursts collapse to one per hour, so a high row count buys nothing.")

    if float(vals[-1]) <= dead_below:
        return _mk("DEAD",
                   f"last reading is zero after a peak of {float(vals.max()):.4g} over {n} "
                   f"readings -- this source worked and has stopped. Distinct from NEVER-WORKED "
                   "because there is something to restore.", 0.0, 0.0)

    days = (times - times[0]) / 86400.0
    if float(days.std()) <= 0 or float(vals.std()) <= 0:
        return _mk("STABLE",
                   f"{n} readings over {span_h:.1f}h with zero dispersion -- flat, and the sample "
                   "is wide enough to say so.", 0.0, 0.0)

    slope, intercept = np.polyfit(days, vals, 1)
    resid = vals - (slope * days + intercept)
    dof = n - 2
    # Standard error of the slope. With dof <= 0 the fit is exact and says nothing.
    if dof <= 0:
        return _mk("UNDERPOWERED", f"{n} readings cannot support a trend and its error", 0.0, 0.0)
    s_err = float(np.sqrt((resid @ resid) / dof) / np.sqrt(((days - days.mean()) ** 2).sum()))
    t = float(slope / s_err) if s_err > 0 else 0.0

    if t <= -2.0:
        return _mk("DECAYING",
                   f"{float(vals[0]):.4g} -> {float(vals[-1]):.4g} over {span_h / 24:.1f}d, slope "
                   f"{slope:+.4g}/day (t={t:.2f}). The decline is larger than this sample's noise.",
                   float(slope), t)
    if t >= 2.0:
        return _mk("IMPROVING",
                   f"{float(vals[0]):.4g} -> {float(vals[-1]):.4g}, slope {slope:+.4g}/day "
                   f"(t={t:.2f}) -- reported because a source that is getting BETTER is a reason "
                   "to lean on it harder, and only tracking decline throws that away.",
                   float(slope), t)
    return _mk("STABLE",
               f"slope {slope:+.4g}/day (t={t:.2f}) over {n} readings spanning {span_h / 24:.1f}d "
               "-- not distinguishable from flat, and the sample is wide enough for that to mean "
               "something.", float(slope), t)
