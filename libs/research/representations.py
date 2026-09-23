"""THE REPRESENTATION LIBRARY -- what a raw series can BECOME, as pure typed transforms.

THE PRINCIPAL, 2026-09-17: *representation invention mints new features from ingested series and
tracks their ROI*. A dataset is never one feature. A monthly print is a level, a surprise against
what was expected, a pace against the period elapsed, a z against its own prior dispersion, a
revision between two vintages, and -- crossed with a second dataset -- a ratio or a product that
neither series carries alone. The desk had ingestion and it had families; it had no vocabulary
for the step between them, so every ingested series reached the docket as at most its own level.

WHAT THIS MODULE IS. Pure functions over PIT-stamped points, and nothing else: no I/O, no clock,
no registry, no randomness. `desks/mt5/research/representation_forge.py` is the organ that reads
the desk's series, applies these, stores them and scores their ROI. Keeping the transforms here
means they are testable without a desk, type-checked under `strict`, and callable from the world
model, the forge and any later organ on identical terms.

THE ONE INVARIANT, AND EVERY TRANSFORM IS WRITTEN TO IT: a representation's value stamped
`available_time = t` is computed from input points whose own `available_time <= t`. Never a
trailing window centred on t, never a mean over the whole sample, never a z-score against a
dispersion that includes the future. Expanding statistics are computed on the STRICT prefix, so
the point being transformed never helps decide its own normalisation. That is not a style
preference: a z-score against full-sample dispersion is the single most common way a leak enters
a conditioning variable, and the return series stays spotless while it happens (R0316's class).

THE GRAMMAR. `compose(outer, inner)` makes one transform out of two, which is where invention
actually happens -- `zscore(surprise(x))` is a different claim from either half, and the space of
compositions is far larger than the space of hand-written features. It is budgeted rather than
enumerated: `rank_proposals` orders by novelty (distance to the representation ids that already
exist) times expected value (how often the transform family has produced candidates before), so
the forge spends its hour on the corner of the grammar that has paid and is still unexplored.

IDS ARE THE MEMORY. `repr:<dataset>:<transform>:<params>` is stable across passes, so the same
representation proposed twice is one representation with a second use, and a composition is
`repr:<dataset>:<inner>|<outer>:<params>`. An id nobody can reconstruct is a feature nobody can
credit, and ROI accounting is exactly the act of crediting a feature months later.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left, bisect_right, insort
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Final

__all__ = [
    "FAMILIES",
    "TRANSFORMS",
    "Point",
    "Series",
    "Transform",
    "TransformSpec",
    "apply",
    "as_of",
    "compose",
    "expected_value",
    "novelty",
    "parse_time",
    "rank_proposals",
    "representation_id",
]

#: Points with fewer than this many strict predecessors cannot carry an expanding statistic.
#: Not a tuning knob: below it the "prior dispersion" is one or two numbers and the z-score is
#: noise wearing a statistic's clothes.
MIN_PRIOR: Final[int] = 8
#: Parameter renderings longer than this collapse to a hash, so an id stays a filename.
MAX_PARAM_CHARS: Final[int] = 48
EPS: Final[float] = 1e-12


# ------------------------------------------------------------------------------- the PIT point
@dataclass(frozen=True)
class Point:
    """One observation, carrying BOTH clocks (L1.46).

    `period_time` is what the value describes -- the source's clock. `available_time` is the
    first instant this desk could have read it -- ours. Every transform reads the second and
    every join uses the second; the first exists so a seasonal or pace transform can ask which
    month a number is ABOUT without asking when it arrived.
    """

    available_time: str
    period_time: str
    value: float
    vintage_id: str | None = None

    def with_value(self, value: float) -> Point:
        return replace(self, value=float(value))


@dataclass(frozen=True)
class Series:
    """A PIT series plus the labels the world model attributes explained variance BY.

    `dataset`, `region` and `information_type` are DECLARED by whoever built the series and
    carried through every transform unchanged. A derived feature belongs to the dataset it came
    from -- that is what makes "which dataset explained this residual" answerable at all.
    """

    series_id: str
    points: tuple[Point, ...] = ()
    dataset: str = ""
    region: str = ""
    information_type: str = ""

    def __len__(self) -> int:
        return len(self.points)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(p.value for p in self.points)

    def sorted(self) -> Series:
        """Points in the order the desk could have learned them; ties keep input order."""
        ordered = sorted(self.points, key=lambda p: (p.available_time, p.period_time))
        return replace(self, points=tuple(ordered))

    def relabel(self, series_id: str) -> Series:
        return replace(self, series_id=series_id)


def parse_time(value: str | None) -> datetime | None:
    """A tolerant ISO reader: full stamps, dates, and the `1999-01` month the BIS axis writes.

    Returns None rather than guessing. A stamp nobody can parse is an UNSTAMPED observation and
    the caller must treat it as unusable, not as the epoch.
    """
    raw = str(value or "").strip()
    if not raw:
        return None
    text = raw.replace("Z", "+00:00")
    for attempt in (text, text[:19], text[:10]):
        try:
            parsed = datetime.fromisoformat(attempt)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    if len(raw) == 7 and raw[4] == "-":
        try:
            return datetime(int(raw[:4]), int(raw[5:7]), 1, tzinfo=UTC)
        except ValueError:
            return None
    return None


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _sd(values: Sequence[float]) -> float:
    if len(values) < 2:
        return float("nan")
    mu = _mean(values)
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var) if var > 0 else 0.0


def as_of(series: Series, when: str) -> float | None:
    """The newest value of `series` KNOWABLE at `when` -- the join every consumer makes.

    A later vintage of the same period does not exist yet at `when` and is not returned; this is
    the whole of the anti-lookahead contract in one function, and the world model routes every
    external input through it.
    """
    best: tuple[str, float] | None = None
    for point in series.points:
        if point.available_time > when:
            continue
        if best is None or point.available_time >= best[0]:
            best = (point.available_time, point.value)
    return None if best is None else best[1]


# ------------------------------------------------------------------------------- ids and keys
def _render_params(params: Mapping[str, Any]) -> str:
    if not params:
        return "default"
    parts = [f"{k}={params[k]}" for k in sorted(params)]
    text = ",".join(parts)
    if len(text) <= MAX_PARAM_CHARS:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"h{digest}"


def representation_id(dataset: str, transform: str, params: Mapping[str, Any]) -> str:
    """`repr:<dataset>:<transform>:<params>` -- stable across passes and safe as a filename."""
    safe_dataset = "".join(c if c.isalnum() or c in "-_.@" else "_" for c in (dataset or "any"))
    return f"repr:{safe_dataset}:{transform}:{_render_params(params)}"


def _seasonal_key(point: Point, cycle: str) -> str:
    stamp = parse_time(point.period_time) or parse_time(point.available_time)
    if stamp is None:
        return "unknown"
    if cycle == "month":
        return f"m{stamp.month:02d}"
    if cycle == "weekday":
        return f"d{stamp.weekday()}"
    if cycle == "hour":
        return f"h{stamp.hour:02d}"
    if cycle == "monthday":
        return f"md{stamp.day:02d}"
    if cycle == "quarter":
        return f"q{(stamp.month - 1) // 3 + 1}"
    return "all"


# ------------------------------------------------------------------------------- the transforms
def diff(series: Series, *, lag: int = 1) -> Series:
    """Change over `lag` observations. The first `lag` points have no predecessor and are gone."""
    points = series.sorted().points
    out = [points[i].with_value(points[i].value - points[i - lag].value)
           for i in range(lag, len(points))
           if _finite(points[i].value) and _finite(points[i - lag].value)]
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "diff", {"lag": lag}))


def acceleration(series: Series, *, lag: int = 1) -> Series:
    """The second difference: whether the change itself is speeding up."""
    inner = diff(series, lag=lag)
    out = diff(inner, lag=lag)
    return replace(out, series_id=representation_id(series.dataset, "acceleration", {"lag": lag}))


def zscore(series: Series, *, window: int = 0, min_prior: int = MIN_PRIOR) -> Series:
    """(value - prior mean) / prior sd, against the STRICT prefix only.

    `window = 0` is expanding; a positive window is the trailing window ending one observation
    before the point. Either way the point never enters its own normalisation, which is the
    difference between a z-score and a leak.

    STREAMED, NOT SLICED. The obvious implementation takes `points[:i]` and averages it, which is
    O(n^2): on the desk's real axes (14,000 points per symbol on the BIS series) that is 196
    million steps for one transform and the organ never finishes its hour. Running sums give the
    identical numbers in one pass, and the accumulator is updated AFTER the point is emitted, so
    the causality is exactly as before.
    """
    points = series.sorted().points
    out: list[Point] = []
    values: list[float] = []
    total = total_sq = 0.0
    for point in points:
        count = len(values)
        lo = max(0, count - window) if window > 0 else 0
        n = count - lo
        if window > 0 and lo > 0:
            run = sum(values[lo:count])
            run_sq = sum(v * v for v in values[lo:count])
        else:
            run, run_sq = total, total_sq
        if n >= min_prior and _finite(point.value):
            mean = run / n
            var = (run_sq - n * mean * mean) / (n - 1) if n > 1 else 0.0
            sd = math.sqrt(var) if var > 0 else 0.0
            if sd > EPS:
                out.append(point.with_value((point.value - mean) / sd))
        if _finite(point.value):
            values.append(point.value)
            total += point.value
            total_sq += point.value * point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "zscore",
                                               {"window": window, "min_prior": min_prior}))


def rank_percentile(series: Series, *, window: int = 0, min_prior: int = MIN_PRIOR) -> Series:
    """Where the value sits in its own prior distribution, in [0, 1]. Robust to a fat tail.

    A sorted insert per point (`bisect`) rather than a scan of the whole prefix: the same numbers
    in n log n, for the reason `zscore` records.
    """
    points = series.sorted().points
    out: list[Point] = []
    values: list[float] = []
    order: list[float] = []
    for point in points:
        prior = values[-window:] if window > 0 else values
        if len(prior) >= min_prior and _finite(point.value):
            if window > 0:
                below = sum(1 for v in prior if v < point.value)
                ties = sum(1 for v in prior if v == point.value)
            else:
                left = bisect_left(order, point.value)
                right = bisect_right(order, point.value)
                below, ties = left, right - left
            out.append(point.with_value((below + 0.5 * ties) / len(prior)))
        if _finite(point.value):
            values.append(point.value)
            if window <= 0:
                insort(order, point.value)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "rank_percentile",
                                               {"window": window, "min_prior": min_prior}))


def surprise(series: Series, *, control: str = "weekday", min_prior: int = 3) -> Series:
    """Actual minus expectation, where the expectation is MATCHED on a control key.

    The control is the point of it. A raw month-on-month change confounds the calendar with the
    news; the mean of prior observations sharing the same weekday (or month, or hour) removes the
    part of the number that was a property of the date rather than of the world. Matched strictly
    on the prefix -- one running sum per control key, so the expectation for point i is built from
    points before i only.
    """
    points = series.sorted().points
    history: dict[str, tuple[float, int]] = {}
    out: list[Point] = []
    for point in points:
        key = _seasonal_key(point, control)
        total, count = history.get(key, (0.0, 0))
        if _finite(point.value) and count >= min_prior:
            out.append(point.with_value(point.value - total / count))
        if _finite(point.value):
            history[key] = (total + point.value, count + 1)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "surprise",
                                               {"control": control, "min_prior": min_prior}))


def seasonal_expectation(series: Series, *, cycle: str = "month", min_prior: int = 3) -> Series:
    """What the calendar alone predicts: the prior mean of the matching seasonal cell.

    The expectation itself is a representation, not only a subtrahend -- a carry family wants the
    level the season implies, while a surprise family wants what it failed to imply.
    """
    points = series.sorted().points
    history: dict[str, tuple[float, int]] = {}
    out: list[Point] = []
    for point in points:
        key = _seasonal_key(point, cycle)
        total, count = history.get(key, (0.0, 0))
        if count >= min_prior:
            out.append(point.with_value(total / count))
        if _finite(point.value):
            history[key] = (total + point.value, count + 1)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "seasonal_expectation",
                                               {"cycle": cycle, "min_prior": min_prior}))


def pace(series: Series, *, cycle: str = "month") -> Series:
    """Value per unit of the period ELAPSED -- a run-rate, not a level.

    A cumulative print three days into a month and the same number three weeks in are opposite
    news, and the level cannot tell them apart. The elapsed fraction comes from the point's own
    period stamp, so nothing about the future enters.
    """
    points = series.sorted().points
    out: list[Point] = []
    for point in points:
        stamp = parse_time(point.period_time) or parse_time(point.available_time)
        if stamp is None or not _finite(point.value):
            continue
        if cycle == "month":
            fraction = stamp.day / 31.0
        elif cycle == "year":
            fraction = stamp.timetuple().tm_yday / 366.0
        elif cycle == "quarter":
            fraction = (((stamp.month - 1) % 3) * 31 + stamp.day) / 93.0
        else:
            fraction = 1.0
        out.append(point.with_value(point.value / max(fraction, 1.0 / 366.0)))
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "pace", {"cycle": cycle}))


def lead_lag(series: Series, *, lag: int = 1) -> Series:
    """The value from `lag` observations ago, stamped NOW.

    A LAG only. A lead would stamp a future value at the present instant, which is the leak this
    library exists to make impossible, so a negative lag is refused rather than quietly flipped.
    """
    if lag < 0:
        raise ValueError("lead_lag takes a non-negative lag: a lead is a look-ahead")
    points = series.sorted().points
    out = [replace(points[i], value=points[i - lag].value)
           for i in range(lag, len(points)) if _finite(points[i - lag].value)]
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "lead_lag", {"lag": lag}))


def rolling_volatility(series: Series, *, window: int = 20) -> Series:
    """The sd of prior changes: the state every vol-conditioned family asks about.

    A rolling accumulator over the trailing `window` changes, so the cost is O(n) rather than the
    O(n*window) of rebuilding the window at every point.
    """
    points = series.sorted().points
    out: list[Point] = []
    changes: deque[float] = deque(maxlen=max(2, window))
    total = total_sq = 0.0
    previous: float | None = None
    floor = max(2, MIN_PRIOR // 2)
    for point in points:
        n = len(changes)
        if n >= floor:
            mean = total / n
            var = (total_sq - n * mean * mean) / (n - 1)
            if var >= 0:
                out.append(point.with_value(math.sqrt(var)))
        if _finite(point.value):
            if previous is not None:
                change = point.value - previous
                if len(changes) == changes.maxlen:
                    dropped = changes[0]
                    total -= dropped
                    total_sq -= dropped * dropped
                changes.append(change)
                total += change
                total_sq += change * change
            previous = point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "rolling_volatility",
                                               {"window": window}))


def spectral_state(series: Series, *, window: int = 32) -> Series:
    """How much of the trailing variance is HIGH-frequency: var(differences) / var(levels).

    The cheap spectral statistic, and deliberately the cheap one. A full periodogram over every
    axis every hour is not affordable on this box, and the quantity a regime actually turns on is
    whether the series is currently choppy or smooth -- which this ratio measures with running
    sums and no transform. Near zero the series is trending; large, it is oscillating.
    """
    points = series.sorted().points
    out: list[Point] = []
    levels: deque[float] = deque(maxlen=max(4, window))
    floor = max(4, MIN_PRIOR // 2)
    for point in points:
        n = len(levels)
        if n >= floor:
            prior = list(levels)
            var_levels = _sd(prior) ** 2
            changes = [prior[j] - prior[j - 1] for j in range(1, n)]
            var_changes = _sd(changes) ** 2 if len(changes) >= 2 else float("nan")
            if _finite(var_levels) and _finite(var_changes) and var_levels > EPS:
                out.append(point.with_value(var_changes / var_levels))
        if _finite(point.value):
            levels.append(point.value)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "spectral_state",
                                               {"window": window}))


def vintage_revision(series: Series) -> Series:
    """Final minus flash, per period, stamped at the instant the REVISION became knowable.

    A revision is news about the world and news about the statistician, and it is the one
    representation only a desk that stored its vintages can build at all. A period seen once has
    no revision and produces nothing -- absence, not a zero.
    """
    points = series.sorted().points
    first: dict[str, float] = {}
    out: list[Point] = []
    for point in points:
        if not _finite(point.value):
            continue
        period = point.period_time
        if period in first:
            out.append(point.with_value(point.value - first[period]))
        else:
            first[period] = point.value
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "vintage_revision", {}))


#: Points between refits of the regime bucket cuts. Refitting at every point re-sorts the whole
#: prefix -- O(n^2 log n) -- and the cuts move by nothing between neighbours; the block is still
#: labelled by the cut fitted on everything BEFORE the block began, so causality is unchanged.
REGIME_RECUT = 64


def regime_conditioned(series: Series, regime: Series, *, buckets: int = 3,
                       min_prior: int = MIN_PRIOR) -> Series:
    """The value minus what it usually is IN THE STATE the desk is currently in.

    The regime series is joined point-in-time by a merge scan, bucketed against its own prior
    quantiles, and the subtrahend is the prior mean of the SAME bucket. A value that is ordinary
    for a high-vol world and extraordinary for a calm one reads as extraordinary only in the calm
    one, which is the whole claim of a state-dependent feature.
    """
    points = series.sorted().points
    other = regime.sorted().points
    history: dict[int, tuple[float, int]] = {}
    regime_prior: list[float] = []
    cuts: list[float] = []
    since_recut = 0
    pointer = 0
    state: float | None = None
    out: list[Point] = []
    for point in points:
        while pointer < len(other) and other[pointer].available_time <= point.available_time:
            if _finite(other[pointer].value):
                state = other[pointer].value
            pointer += 1
        if state is None or not _finite(point.value):
            continue
        if len(regime_prior) >= min_prior:
            if not cuts or since_recut >= REGIME_RECUT:
                ordered = sorted(regime_prior)
                cuts = [ordered[int(len(ordered) * k / buckets)] for k in range(1, buckets)]
                since_recut = 0
            since_recut += 1
            bucket = sum(1 for c in cuts if state >= c)
            total, count = history.get(bucket, (0.0, 0))
            if count >= min_prior:
                out.append(point.with_value(point.value - total / count))
            history[bucket] = (total + point.value, count + 1)
        regime_prior.append(state)
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "regime_conditioned",
                                               {"buckets": buckets, "on": regime.dataset or "x"}))


def _pairwise(left: Series, right: Series, op: Callable[[float, float], float | None],
              name: str) -> Series:
    """A MERGE SCAN, not a lookup per point. `as_of` walks the whole right-hand series for every
    left-hand point, so the pair cost was O(n*m) -- on two 14,000-point axes, 196 million steps
    for one interaction. Both series are already sorted by availability; one pointer is enough,
    and the join it produces is identical."""
    lhs = left.sorted()
    rhs = right.sorted()
    out: list[Point] = []
    pointer = 0
    latest: float | None = None
    for point in lhs.points:
        while pointer < len(rhs.points) and rhs.points[pointer].available_time \
                <= point.available_time:
            if _finite(rhs.points[pointer].value):
                latest = rhs.points[pointer].value
            pointer += 1
        if latest is None or not _finite(point.value):
            continue
        value = op(point.value, latest)
        if value is not None and _finite(value):
            out.append(point.with_value(value))
    dataset = f"{left.dataset}x{right.dataset}" if left.dataset and right.dataset else "cross"
    region = left.region if left.region == right.region else f"{left.region}|{right.region}"
    return Series(series_id=representation_id(dataset, name, {"b": right.series_id[-16:]}),
                  points=tuple(out), dataset=dataset, region=region,
                  information_type=left.information_type or right.information_type)


def ratio(left: Series, right: Series) -> Series:
    """A cross-dataset ratio, joined point-in-time. Division by ~0 is dropped, never clipped."""
    return _pairwise(left, right,
                     lambda a, b: None if abs(b) <= EPS else a / b, "ratio")


def product(left: Series, right: Series) -> Series:
    """THE INTERACTION. Two datasets whose product says what neither says alone -- a positioning
    extreme times a funding-stress state is a forced-flow claim; either one alone is not."""
    return _pairwise(left, right, lambda a, b: a * b, "product")


def event_window_aggregate(series: Series, events: Sequence[str], *, window_days: float = 3.0,
                           how: str = "mean") -> Series:
    """One value per EVENT: the series aggregated over the window BEFORE that event.

    Anchored on the event's own instant and reaching backwards only, so the aggregate published
    at the event is computable at the event. An event with nothing in its window produces no
    point: an empty window is UNMEASURED and is not an aggregate of zero.
    """
    ordered = series.sorted().points
    stamps: list[float] = []
    values: list[float] = []
    for point in ordered:
        at = parse_time(point.available_time)
        if at is None or not _finite(point.value):
            continue
        stamps.append(at.timestamp())
        values.append(point.value)
    out: list[Point] = []
    for raw_event in events:
        stamp = parse_time(raw_event)
        if stamp is None:
            continue
        hi = stamp.timestamp()
        lo = hi - window_days * 86400.0
        # Bisect rather than a scan per event: an event calendar and a daily axis are both long,
        # and the product of the two is what makes a "cheap" aggregate cost an hour.
        inside = values[bisect_left(stamps, lo):bisect_right(stamps, hi)]
        if not inside:
            continue
        if how == "sum":
            value = sum(inside)
        elif how == "max":
            value = max(inside)
        elif how == "last":
            value = inside[-1]
        else:
            value = _mean(inside)
        out.append(Point(available_time=stamp.isoformat(), period_time=stamp.isoformat(),
                         value=float(value)))
    return replace(series, points=tuple(out),
                   series_id=representation_id(series.dataset, "event_window_aggregate",
                                               {"days": window_days, "how": how}))


# ------------------------------------------------------- the panel: many members, one clock
def _panel_label(members: Sequence[Series]) -> str:
    """A bounded, deterministic name for a panel, so its representations have stable ids."""
    text = "+".join(m.dataset or m.series_id[-8:] for m in members)
    if len(text) <= MAX_PARAM_CHARS:
        return text
    return "panel" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _panel_region(members: Sequence[Series]) -> str:
    regions = sorted({m.region for m in members if m.region})
    text = "|".join(regions)
    return text if len(text) <= MAX_PARAM_CHARS else f"{len(regions)}regions"


def _panel_scan(members: Sequence[Series]) -> list[tuple[Point, tuple[float, ...]]]:
    """The members joined on the union of their availability stamps, last value carried forward.

    One row per distinct `available_time`, holding each member's newest value whose OWN
    availability is at or before it, and emitted only once every member has published one. That
    is the module's single invariant stated for many series instead of two: no member ever
    contributes a number the desk could not have read at t.

    A merge over the sorted event list, not a lookup per member per stamp -- `_pairwise` records
    why (the pair version of that mistake cost 196 million steps on two real axes).
    """
    events: list[tuple[str, int, int, Point]] = []
    for idx, member in enumerate(members):
        for order, point in enumerate(member.sorted().points):
            if _finite(point.value):
                events.append((point.available_time, idx, order, point))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    latest: list[float | None] = [None] * len(members)
    rows: list[tuple[Point, tuple[float, ...]]] = []
    i = 0
    while i < len(events):
        stamp = events[i][0]
        carrier = events[i][3]
        while i < len(events) and events[i][0] == stamp:
            latest[events[i][1]] = events[i][3].value
            carrier = events[i][3]
            i += 1
        if all(v is not None for v in latest):
            rows.append((Point(available_time=stamp, period_time=carrier.period_time, value=0.0),
                         tuple(float(v) for v in latest if v is not None)))
    return rows


def _difference(a: float, b: float) -> float | None:
    return a - b


def _ratio_op(a: float, b: float) -> float | None:
    return None if abs(b) <= EPS else a / b


def cross_country_spread(left: Series, right: Series, *, mode: str = "difference") -> Series:
    """THE SAME MEASURE IN TWO PLACES, differenced -- and the pairing comes from the data.

    The country is not a list in this file. It is the `region` each series was DECLARED with, so
    a pairing exists exactly when both sides carry a region and the two differ. A hard-coded pair
    table would need editing every time an axis is ingested for a new country, and the pairs
    nobody remembered to add would silently never be built -- the difference between a grammar
    and a lookup table.

    When no pairing can be derived the result is an EMPTY series whose id says `undeclared`:
    UNMEASURED, named in the id, never a zero (L1.28a).
    """
    lhs, rhs = left.region.strip(), right.region.strip()
    pair = f"{lhs}-{rhs}" if lhs and rhs and lhs != rhs else "undeclared"
    label = f"{left.dataset or right.dataset or 'cross'}@{pair}"
    rid = representation_id(label, "cross_country_spread", {"mode": mode})
    if pair == "undeclared":
        return Series(series_id=rid, points=(), dataset=label,
                      region=left.region or right.region,
                      information_type=left.information_type or right.information_type)
    out = _pairwise(left, right, _ratio_op if mode == "ratio" else _difference,
                    "cross_country_spread")
    return replace(out, dataset=label, region=pair, series_id=rid)


def diffusion(*panel: Series, window: int = 12, min_prior: int = MIN_PRIOR) -> Series:
    """THE BREADTH INDEX: the share of the panel currently above its OWN trailing level.

    The question an aggregate cannot answer -- whether a move is the whole panel or one member
    carrying it. Each member is compared to the mean of its own last `window` values STRICTLY
    BEFORE the current row, so members with different units and levels are each judged against
    themselves and nothing is ever compared across members. A member with too short a history
    does not vote, and a row with fewer than two voters produces nothing rather than a 0 or a 1
    manufactured from one series.
    """
    if len(panel) < 2:
        raise ValueError("diffusion needs at least two panel members")
    prior: list[deque[float]] = [deque(maxlen=max(2, window)) for _ in panel]
    out: list[Point] = []
    for carrier, values in _panel_scan(panel):
        voters = above = 0
        for k, value in enumerate(values):
            hist = prior[k]
            if len(hist) >= min_prior:
                voters += 1
                if value > sum(hist) / len(hist):
                    above += 1
        if voters >= 2:
            out.append(carrier.with_value(above / voters))
        for k, value in enumerate(values):
            prior[k].append(value)
    label = _panel_label(panel)
    return Series(series_id=representation_id(label, "diffusion", {"window": window}),
                  points=tuple(out), dataset=label, region=_panel_region(panel),
                  information_type=panel[0].information_type)


def rolling_beta(series: Series, benchmark: Series, *, window: int = 60,
                 min_prior: int = MIN_PRIOR) -> Series:
    """The series' rolling OLS beta to a NAMED benchmark, over the trailing `window` changes.

    ON CHANGES, NEVER ON LEVELS. Two trending levels regress beautifully on each other and the
    slope means nothing; the beta a desk can use is the one between their increments. The
    benchmark is joined point-in-time (its newest value whose own availability is at or before
    the point), and the window ENDS at the current observation -- data the desk has, not data it
    will have. The window is in the id, because a beta whose window nobody recorded cannot be
    reproduced, and the benchmark is in the dataset label for the same reason.
    """
    points = series.sorted().points
    other = benchmark.sorted().points
    xs: deque[float] = deque(maxlen=max(2, window))
    ys: deque[float] = deque(maxlen=max(2, window))
    sx = sy = sxx = sxy = 0.0
    pointer = 0
    state: float | None = None
    prev_x: float | None = None
    prev_y: float | None = None
    floor = max(2, min_prior // 2)
    out: list[Point] = []
    for point in points:
        while pointer < len(other) and other[pointer].available_time <= point.available_time:
            if _finite(other[pointer].value):
                state = other[pointer].value
            pointer += 1
        if state is None or not _finite(point.value):
            continue
        if prev_x is not None and prev_y is not None:
            dx, dy = state - prev_x, point.value - prev_y
            if len(xs) == xs.maxlen:
                old_x, old_y = xs[0], ys[0]
                sx -= old_x
                sy -= old_y
                sxx -= old_x * old_x
                sxy -= old_x * old_y
            xs.append(dx)
            ys.append(dy)
            sx += dx
            sy += dy
            sxx += dx * dx
            sxy += dx * dy
            n = len(xs)
            if n >= floor:
                var = sxx - sx * sx / n
                if var > EPS:
                    out.append(point.with_value((sxy - sx * sy / n) / var))
        prev_x, prev_y = state, point.value
    dataset = f"{series.dataset}x{benchmark.dataset}" if series.dataset and benchmark.dataset \
        else "beta"
    return Series(series_id=representation_id(dataset, "rolling_beta", {"window": window}),
                  points=tuple(out), dataset=dataset, region=series.region,
                  information_type=series.information_type)


#: Rows between refits of the embedding. `regime_conditioned` records the same argument: refitting
#: at every point is quadratic and the loadings do not move between neighbours. The block is
#: projected on loadings fitted STRICTLY BEFORE it began, so causality is unchanged.
EMBED_RECUT: Final[int] = 32
#: Power iterations per component. The panels here are a handful of series; this converges long
#: before it, and a fixed count keeps a fit reproducible byte for byte.
EMBED_ITERS: Final[int] = 48


def _fit_components(rows: Sequence[Sequence[float]], k: int
                    ) -> tuple[list[float], list[float], list[list[float]], list[float], float]:
    """Leading `k` eigenvectors of the panel's covariance, by DEFLATED POWER ITERATION.

    No numpy, no learned weights, no new dependency, and -- the part that matters for a
    representation -- NO RANDOM START: the start vector is fixed and the sign of each component
    is pinned to its first non-zero loading, so the same history always produces the same
    loadings and the same id means the same numbers. Returns (mean, sd, loadings, eigenvalues,
    total variance); the eigenvalue over the total is the explained variance the forge publishes.
    """
    n, m = len(rows), len(rows[0])
    mean = [sum(r[j] for r in rows) / n for j in range(m)]
    sd = [_sd([r[j] for r in rows]) for j in range(m)]
    z = [[(r[j] - mean[j]) / sd[j] if sd[j] > EPS else 0.0 for j in range(m)] for r in rows]
    cov = [[sum(z[i][a] * z[i][b] for i in range(n)) / (n - 1) for b in range(m)]
           for a in range(m)]
    total = sum(cov[j][j] for j in range(m))
    loadings: list[list[float]] = []
    values: list[float] = []
    for _ in range(max(1, min(k, m))):
        vec = [1.0 / math.sqrt(m)] * m
        value = 0.0
        for _ in range(EMBED_ITERS):
            w = [sum(cov[a][b] * vec[b] for b in range(m)) for a in range(m)]
            norm = math.sqrt(sum(x * x for x in w))
            if norm <= EPS:
                break
            vec = [x / norm for x in w]
            value = norm
        for x in vec:
            if abs(x) > EPS:
                if x < 0:
                    vec = [-y for y in vec]
                break
        loadings.append(vec)
        values.append(value)
        cov = [[cov[a][b] - value * vec[a] * vec[b] for b in range(m)] for a in range(m)]
    return mean, sd, loadings, values, total


def _embed(panel: Sequence[Series], window: int, components: int, component: int,
           min_prior: int) -> tuple[list[Point], dict[str, Any]]:
    rows = _panel_scan(panel)
    history: deque[list[float]] = deque(maxlen=max(4, window))
    fit: tuple[list[float], list[float], list[list[float]], list[float], float] | None = None
    explained: list[float] = []
    out: list[Point] = []
    since = 0
    fits = 0
    need = max(min_prior, len(panel) + 1)
    for carrier, values in rows:
        if len(history) >= need:
            if fit is None or since >= EMBED_RECUT:
                fit = _fit_components(list(history), components)
                since = 0
                fits += 1
                total = fit[4]
                explained = [round(v / total, 6) for v in fit[3]] if total > EPS else []
            since += 1
            mean, sd, loadings, _values, _total = fit
            if component < len(loadings):
                z = [(values[j] - mean[j]) / sd[j] if sd[j] > EPS else 0.0
                     for j in range(len(values))]
                score = sum(z[j] * loadings[component][j] for j in range(len(z)))
                if _finite(score):
                    out.append(carrier.with_value(score))
        history.append(list(values))
    status = "measured" if out else "unmeasured"
    why = ("fitted on the trailing window strictly before each row" if out else
           f"fewer than {need} joint rows in the panel, or a component that never converged")
    return out, {"status": status, "why": why, "components": components,
                 "component": component, "fit_window": window, "n_members": len(panel),
                 "n_rows": len(rows), "n_points": len(out), "n_fits": fits,
                 "explained_variance": explained,
                 "explained_variance_total": round(sum(explained), 6),
                 "fitted_on": "the standardized panel history up to, and not including, each row"}


def embedding(*panel: Series, window: int = 120, components: int = 2, component: int = 0,
              min_prior: int = MIN_PRIOR) -> Series:
    """A LEARNED low-dimensional coordinate of the panel: its rolling principal component.

    The one transform here that FITS something, and therefore the one where a look-ahead would
    poison everything downstream: a component fitted on the whole sample and then projected back
    over it is a feature that knows how the sample ended. So the loadings and the standardisation
    at every row come from the trailing `window` rows STRICTLY BEFORE it, refitted every
    `EMBED_RECUT` rows and used only forward. `embedding_fit` publishes the number of components
    and the variance each explains, because an embedding whose explained variance nobody recorded
    is a number with no claim attached.

    No LLM and no new dependency: `_fit_components` is a deflated power iteration in plain
    Python over a matrix whose width is the size of the panel.
    """
    if len(panel) < 2:
        raise ValueError("embedding needs at least two panel members")
    out, _diag = _embed(panel, window, components, component, min_prior)
    label = _panel_label(panel)
    return Series(series_id=representation_id(label, "embedding",
                                              {"window": window, "components": components,
                                               "component": component}),
                  points=tuple(out), dataset=label, region=_panel_region(panel),
                  information_type=panel[0].information_type)


def embedding_fit(*panel: Series, window: int = 120, components: int = 2, component: int = 0,
                  min_prior: int = MIN_PRIOR) -> dict[str, Any]:
    """The embedding's published fit: components, explained variance, window, and how many fits.

    Kept out of the series id on purpose. An id is a NAME -- two passes over the same data must
    produce the same one -- and explained variance is a MEASUREMENT that moves with the data. A
    measurement inside a name would mint a new representation every hour and credit none of them.
    """
    if len(panel) < 2:
        return {"status": "unmeasured", "why": "a panel needs at least two members",
                "components": components, "n_members": len(panel), "explained_variance": []}
    _out, diag = _embed(panel, window, components, component, min_prior)
    return diag


# ------------------------------------------------------------------------------- the registry
@dataclass(frozen=True)
class TransformSpec:
    """One transform: how many series it eats, what family it belongs to, and its defaults."""

    name: str
    family: str
    arity: int
    fn: Callable[..., Series]
    defaults: Mapping[str, Any]
    needs_events: bool = False
    #: A PANEL transform: `arity` is its MINIMUM and every input after the first is a member,
    #: not a second operand. `diffusion` over three series is a three-member breadth index, and
    #: passing only the first two would have measured a different thing silently.
    variadic: bool = False


#: The FAMILY is the unit ROI is tracked by. Two parameterisations of `zscore` are one bet about
#: what normalisation buys; `zscore` and `vintage_revision` are not.
FAMILIES: Final[tuple[str, ...]] = ("normalisation", "surprise", "seasonal", "dynamics",
                                    "interaction", "event", "vintage", "state")

TRANSFORMS: Final[dict[str, TransformSpec]] = {
    "diff": TransformSpec("diff", "dynamics", 1, diff, {"lag": 1}),
    "acceleration": TransformSpec("acceleration", "dynamics", 1, acceleration, {"lag": 1}),
    "lead_lag": TransformSpec("lead_lag", "dynamics", 1, lead_lag, {"lag": 1}),
    "zscore": TransformSpec("zscore", "normalisation", 1, zscore, {"window": 0}),
    "rank_percentile": TransformSpec("rank_percentile", "normalisation", 1, rank_percentile,
                                     {"window": 0}),
    "surprise": TransformSpec("surprise", "surprise", 1, surprise, {"control": "weekday"}),
    "seasonal_expectation": TransformSpec("seasonal_expectation", "seasonal", 1,
                                          seasonal_expectation, {"cycle": "month"}),
    "pace": TransformSpec("pace", "seasonal", 1, pace, {"cycle": "month"}),
    "rolling_volatility": TransformSpec("rolling_volatility", "state", 1, rolling_volatility,
                                        {"window": 20}),
    "spectral_state": TransformSpec("spectral_state", "state", 1, spectral_state, {"window": 32}),
    "vintage_revision": TransformSpec("vintage_revision", "vintage", 1, vintage_revision, {}),
    "regime_conditioned": TransformSpec("regime_conditioned", "state", 2, regime_conditioned,
                                        {"buckets": 3}),
    "ratio": TransformSpec("ratio", "interaction", 2, ratio, {}),
    "product": TransformSpec("product", "interaction", 2, product, {}),
    "cross_country_spread": TransformSpec("cross_country_spread", "interaction", 2,
                                          cross_country_spread, {"mode": "difference"}),
    "rolling_beta": TransformSpec("rolling_beta", "dynamics", 2, rolling_beta, {"window": 60}),
    "diffusion": TransformSpec("diffusion", "state", 2, diffusion, {"window": 12},
                               variadic=True),
    "embedding": TransformSpec("embedding", "interaction", 2, embedding,
                               {"window": 120, "components": 2, "component": 0}, variadic=True),
    "event_window_aggregate": TransformSpec("event_window_aggregate", "event", 1,
                                            event_window_aggregate,
                                            {"window_days": 3.0, "how": "mean"},
                                            needs_events=True),
}


@dataclass(frozen=True)
class Transform:
    """A named transform with its parameters, and optionally an inner transform composed under it.

    The composition is the INVENTION step: `Transform("zscore", inner=Transform("surprise"))` is
    a feature nobody wrote down, minted from two that were.
    """

    name: str
    params: Mapping[str, Any] = ()  # type: ignore[assignment]
    inner: Transform | None = None

    @property
    def chain(self) -> tuple[str, ...]:
        return (*(self.inner.chain if self.inner is not None else ()), self.name)

    @property
    def family(self) -> str:
        spec = TRANSFORMS.get(self.name)
        return spec.family if spec is not None else "unknown"

    @property
    def label(self) -> str:
        return "|".join(self.chain)


def compose(outer: Transform, inner: Transform) -> Transform:
    """`inner` then `outer`, as one transform. Composing onto a two-input transform is refused:
    the second input is a different series, not a stage, and pretending otherwise would silently
    drop it."""
    spec = TRANSFORMS.get(outer.name)
    if spec is None:
        raise KeyError(f"unknown transform {outer.name!r}")
    if spec.arity != 1:
        raise ValueError(f"{outer.name} takes {spec.arity} series: it cannot wrap a chain")
    return Transform(name=outer.name, params=dict(outer.params or {}), inner=inner)


def apply(transform: Transform, *inputs: Series, events: Sequence[str] = ()) -> Series:
    """Run a (possibly composed) transform and stamp the result with its full id.

    The id names the WHOLE chain, so `repr:fred:surprise|zscore:window=0` is recognisably one
    representation built from two steps rather than an anonymous number.
    """
    if not inputs:
        raise ValueError("a transform needs at least one series")
    spec = TRANSFORMS.get(transform.name)
    if spec is None:
        raise KeyError(f"unknown transform {transform.name!r}")
    primary = inputs[0]
    if transform.inner is not None:
        primary = apply(transform.inner, primary, *inputs[1:], events=events)
    params = {**dict(spec.defaults), **dict(transform.params or {})}
    if spec.arity == 2:
        if len(inputs) < 2:
            raise ValueError(f"{transform.name} needs two series")
        # A PANEL TRANSFORM GETS THE WHOLE PANEL. Handing `diffusion` only `inputs[1]` would run
        # silently and measure the breadth of two members while the plan said six.
        out = spec.fn(primary, *inputs[1:], **params) if spec.variadic \
            else spec.fn(primary, inputs[1], **params)
    elif spec.needs_events:
        out = spec.fn(primary, events, **params)
    else:
        out = spec.fn(primary, **params)
    # A TWO-INPUT TRANSFORM KEEPS THE PAIR'S OWN LABELS. Rewriting them to the left operand's
    # would name `a x b` and `a x c` identically, which is not a naming quibble: the store is
    # keyed by id, so the second interaction would overwrite the first and the desk would hold
    # one cross-dataset feature where it had built two.
    if spec.arity == 2:
        return replace(out, series_id=representation_id(out.dataset, transform.label, params))
    dataset = inputs[0].dataset
    return replace(out, dataset=dataset, region=inputs[0].region,
                   information_type=inputs[0].information_type,
                   series_id=representation_id(dataset, transform.label, params))


# ------------------------------------------------------------------------------- the budget
def _id_tokens(rid: str) -> set[str]:
    return {t for t in rid.replace(":", " ").replace(",", " ").replace("|", " ").split() if t}


#: How many existing representations a novelty score is compared against. The grammar offers
#: thousands of proposals a pass and the store grows without bound, so an exhaustive comparison
#: is quadratic in two growing numbers -- measured on the real tree, 3,700 proposals against
#: 3,000 stored ids is eleven million set intersections for a SCORE, which is not what the hour
#: is for. An exact re-proposal is always caught (the id is matched directly); beyond that a
#: deterministic sample of the store is enough to rank, and the sample is the OLDEST-first slice
#: so it is stable across passes rather than drifting with whatever was minted last.
NOVELTY_SAMPLE: Final[int] = 256


def novelty(candidate_id: str, existing: Iterable[str]) -> float:
    """1 - the highest Jaccard similarity to anything that already exists, in [0, 1].

    An id nothing resembles scores 1.0; an exact re-proposal scores 0.0. This is the cheap
    distance, and cheap is the requirement: it is evaluated over the whole grammar every pass.
    """
    mine = _id_tokens(candidate_id)
    if not mine:
        return 0.0
    return round(1.0 - _closest(mine, _token_sets(existing), candidate_id), 6)


def _token_sets(existing: Iterable[str]) -> tuple[tuple[str, frozenset[str]], ...]:
    rows = [(rid, frozenset(_id_tokens(rid))) for rid in existing]
    if len(rows) > NOVELTY_SAMPLE:
        step = len(rows) / NOVELTY_SAMPLE
        rows = [rows[int(i * step)] for i in range(NOVELTY_SAMPLE)]
    return tuple(rows)


def _closest(mine: set[str], rows: tuple[tuple[str, frozenset[str]], ...],
             candidate_id: str) -> float:
    best = 0.0
    for rid, theirs in rows:
        if rid == candidate_id:
            return 1.0
        if not theirs:
            continue
        union = mine | theirs
        best = max(best, len(mine & theirs) / len(union) if union else 0.0)
    return best


def expected_value(family: str, history: Mapping[str, Mapping[str, float]],
                   *, prior_rate: float = 0.25, prior_weight: float = 4.0) -> float:
    """Laplace-smoothed candidates-per-use for a transform family.

    A family nobody has run yet takes the PRIOR, never 1.0 and never 0.0 -- an unmeasured family
    must neither outrank a family measured to convert nor be extinguished before its first trial.
    """
    row = history.get(family) or {}
    uses = float(row.get("used_by_candidates", 0.0)) + float(row.get("uses", 0.0))
    produced = float(row.get("candidates", 0.0)) + float(row.get("survivors", 0.0))
    return round((produced + prior_rate * prior_weight) / (uses + prior_weight), 6)


def rank_proposals(proposals: Sequence[tuple[str, str]], existing: Iterable[str],
                   history: Mapping[str, Mapping[str, float]], *, budget: int = 50
                   ) -> list[dict[str, Any]]:
    """Order `(representation_id, family)` proposals by novelty x expected value, take `budget`.

    Ties break on the id so a pass is reproducible: the same tree and the same history select the
    same representations, which is what makes a ROI series comparable across hours.
    """
    known = list(existing)
    exact = set(known)
    rows = _token_sets(known)
    cache: dict[str, float] = {}
    scored: list[dict[str, Any]] = []
    for rid, family in proposals:
        if rid in exact:
            nov = 0.0
        else:
            tokens = _id_tokens(rid)
            nov = round(1.0 - _closest(tokens, rows, rid), 6) if tokens else 0.0
        if family not in cache:
            cache[family] = expected_value(family, history)
        ev = cache[family]
        scored.append({"id": rid, "family": family, "novelty": nov, "expected_value": ev,
                       "score": round(nov * ev, 6)})
    scored.sort(key=lambda r: (-float(r["score"]), str(r["id"])))
    return scored[:budget]


def to_json(series: Series) -> str:
    """The stored form: the id, the labels, and every point with both clocks."""
    return json.dumps({
        "id": series.series_id, "dataset": series.dataset, "region": series.region,
        "information_type": series.information_type, "n": len(series.points),
        "points": [{"available_time": p.available_time, "period_time": p.period_time,
                    "value": p.value, "vintage_id": p.vintage_id} for p in series.points],
    }, indent=1, default=str)
