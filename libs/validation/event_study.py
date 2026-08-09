"""Event-study validation -- the promotion path for edges that are EVENTS, not time series.

Every gate the desk owns scores a CONTINUOUS DAILY RETURN SERIES: Sharpe, DSR, PBO, walk-forward,
Newey-West. That is the right shape for carry, trend and cross-sectional sleeves. It is the wrong
shape for the edges a small book actually wants (§42): a day-1 listing funding spike is a handful
of hours, happens a few times a week, and is over. Thirty such events are thirty observations --
but strung into a daily series they are ~2 non-zero days in 30 mostly-flat ones, and every
continuous statistic reads that as noise. The result is that the desk could COLLECT the listing
data (run_listing_watch already does) and never be able to PROMOTE what it found: acquired, not
convertible, at the strategy layer.

This module is that missing path. The unit of evidence is the EVENT.

WHY THIS IS FASTER WITHOUT BEING WEAKER -- the point that matters. At 2-4 new perp listings a
week, 30 events is ~10 weeks: comparable to the 40-day forward clock in calendar terms, but far
richer in statistical content, because 30 events are 30 largely-independent draws whereas 40 daily
returns are 40 autocorrelated ones. The clock shortens because the EVIDENCE is denser, not because
the bar moved. Same argument as reconstructed-history backfill, applied to events.

THE TRAP, AND WHY IT IS CHECKED HERE. Overlapping event windows share the same market moves, so
they are not independent draws: a market-wide shock inside two overlapping windows is one
observation counted twice, and the cross-sectional standard error silently shrinks. Overlap is
therefore MEASURED and reported, and the effective N is discounted by it -- the same
effective-vs-raw discipline §31 applies to trial counts, here applied to observations.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from libs.validation.errors import ValidationError

#: Below this an event study says nothing: the cross-sectional t-test needs a usable sample, and
#: crypto event returns are fat-tailed enough that small-N normal approximations mislead badly.
MIN_EVENTS = 20


class Event(BaseModel):
    """One occurrence: when it started, how long it ran, and the return earned across it."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    t_start: float                # epoch seconds
    t_end: float
    ret: float                    # realised return over the window (ABNORMAL if a benchmark
    #                               was subtracted by the caller -- see abnormal_returns)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.t_end - self.t_start)


def abnormal_returns(
    event_rets: np.ndarray, benchmark_rets: np.ndarray | None = None
) -> np.ndarray:
    """Subtract the benchmark earned over each event's own window.

    Without this an event study measures BETA, not edge: a listing study run through a bull month
    reports the market. This is the same error as the video's AI 'beating' a falling S&P by sitting
    in cash -- the number was the benchmark's, not the strategy's.
    """
    r = np.asarray(event_rets, dtype="float64")
    if benchmark_rets is None:
        return r
    b = np.asarray(benchmark_rets, dtype="float64")
    if b.shape != r.shape:
        raise ValidationError("benchmark_rets must align 1:1 with event_rets")
    return np.asarray(r - b, dtype="float64")


def overlap_fraction(events: list[Event]) -> float:
    """Share of events whose window intersects another's -- the independence discount.

    Overlapping windows share market moves, so they are not independent draws. Reported rather
    than silently corrected, because the honest response depends on WHY they overlap.
    """
    if len(events) < 2:
        return 0.0
    ordered = sorted(events, key=lambda e: e.t_start)
    overlapping: set[str] = set()
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.t_start >= a.t_end:
                break                       # sorted: nothing later can overlap a either
            overlapping.add(a.event_id)
            overlapping.add(b.event_id)
    return round(len(overlapping) / len(events), 3)


class EventStudyResult(BaseModel):
    """Cross-sectional verdict over N events."""

    model_config = ConfigDict(frozen=True)

    n_events: int
    n_effective: float            # N discounted for overlapping windows
    mean_ret: float
    std_ret: float
    t_stat: float                 # cross-sectional (Brown-Warner), on effective N
    hit_rate: float               # share of events with a positive return
    boot_lo: float                # 5th pct of the bootstrapped mean -- fat-tail sanity check
    boot_hi: float
    overlap: float
    bar: float                    # multiplicity-corrected t threshold this had to clear
    passed: bool
    verdict: str


def event_study(
    events: list[Event],
    *,
    n_cohort: int = 1,
    rank: int = 1,
    alpha: float = 0.05,
    min_events: int = MIN_EVENTS,
    n_boot: int = 2000,
    seed: int = 0,
) -> EventStudyResult:
    """Cross-sectional event study with a multiplicity-corrected bar and a bootstrap check.

    ``n_cohort``/``rank`` plug into the desk's existing Holm discipline: an event edge found while
    screening K candidate event-types is one of K, and is deflated exactly as a candidate cohort
    is (``forward_stats.holm_bar``). A single PRE-REGISTERED event hypothesis uses n_cohort=1.

    The bootstrap runs alongside the parametric t on purpose: crypto event returns are strongly
    fat-tailed, and a t-stat that clears on a normal assumption while the bootstrap interval spans
    zero is exactly the false positive this desk exists to refuse.
    """
    from libs.validation.forward_stats import holm_bar

    n = len(events)
    if n < min_events:
        return EventStudyResult(
            n_events=n, n_effective=float(n), mean_ret=0.0, std_ret=0.0, t_stat=0.0,
            hit_rate=0.0, boot_lo=0.0, boot_hi=0.0, overlap=0.0, bar=0.0, passed=False,
            verdict=(f"{n}/{min_events} events -- too few to judge. An event study below ~20 "
                     "observations is a story, not evidence; keep the clock running."),
        )
    r = np.array([e.ret for e in events], dtype="float64")
    ov = overlap_fraction(events)
    # Discount N by overlap: fully-overlapping events are ONE observation, not many. Linear is
    # crude but conservative, and conservative is the correct direction for an independence proxy.
    n_eff = max(1.0, n * (1.0 - ov))
    mean = float(r.mean())
    std = float(r.std(ddof=1)) if n > 1 else 0.0
    # DEGENERATE INPUT. `std == 0.0` is the wrong guard: numpy returns ~3e-19 for identical
    # values, so an exact-equality check never fires and the t-stat explodes (measured: 3e16 for
    # 30 identical returns) -- a constant series would then clear every bar in the module. Real
    # event returns are never constant, so this is a DATA defect (a repeated fill price, a stubbed
    # feed, a join that fanned one row out) and must be refused loudly rather than scored.
    if std <= 1e-12 or not np.isfinite(std):
        return EventStudyResult(
            n_events=n, n_effective=round(n_eff, 1), mean_ret=round(mean, 6), std_ret=0.0,
            t_stat=0.0, hit_rate=round(float((r > 0).mean()), 3), boot_lo=0.0, boot_hi=0.0,
            overlap=ov, bar=0.0, passed=False,
            verdict=(f"DEGENERATE: {n} events with ~zero cross-sectional variance (std={std:.2e}). "
                     "Real event returns are never constant -- this is a data defect (repeated "
                     "price, stubbed feed, fanned-out join), not an edge. Fix the input."),
        )
    t = mean / (std / np.sqrt(n_eff))

    rng = np.random.default_rng(seed)
    boots = rng.choice(r, size=(n_boot, n), replace=True).mean(axis=1)
    lo, hi = (float(np.percentile(boots, 5)), float(np.percentile(boots, 95)))

    bar = holm_bar(max(1, n_cohort), rank, alpha=alpha)
    # BOTH must hold: the corrected t AND a bootstrap interval that excludes zero. Either alone is
    # defeatable -- the t by fat tails, the bootstrap by a lucky resample of a thin sample.
    passed = bool(t >= bar and lo > 0.0)

    if passed:
        verdict = (f"PASS: {n} events (eff {n_eff:.0f}), mean {mean:+.4%}, t={t:.2f} vs bar "
                   f"{bar:.2f}, bootstrap 90% CI [{lo:+.4%}, {hi:+.4%}] excludes zero.")
    elif t >= bar:
        verdict = (f"t={t:.2f} clears the {bar:.2f} bar but the bootstrap CI [{lo:+.4%}, "
                   f"{hi:+.4%}] SPANS ZERO -- fat tails, not edge. Refused.")
    else:
        verdict = (f"t={t:.2f} below the multiplicity-corrected bar {bar:.2f} "
                   f"({n} events, eff {n_eff:.0f}, overlap {ov:.0%}). Keep collecting.")
    return EventStudyResult(
        n_events=n, n_effective=round(n_eff, 1), mean_ret=round(mean, 6),
        std_ret=round(std, 6), t_stat=round(t, 3),
        hit_rate=round(float((r > 0).mean()), 3), boot_lo=round(lo, 6), boot_hi=round(hi, 6),
        overlap=ov, bar=round(bar, 3), passed=passed, verdict=verdict,
    )
