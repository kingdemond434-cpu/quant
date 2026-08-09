"""CROWDING ON OUR OWN NAMES -- the residual measure, not the market one.

THE DISTINCTION THIS MODULE EXISTS FOR, because the desk already has the other one. The incumbent
organ `scripts/run_carry_crowding.py` measures the top-20 AVERAGE funding rate against its own
backtest 25th percentile. That answers "is carry as an asset class compressing?" -- a real question
with a market-wide answer. It cannot answer the adversary's question:

    if a competitor finds OUR carry names, the tell arrives before the P&L does.

A competitor compresses the names they found, not the universe. In a top-20 average our names are
one input among twenty, so a targeted compression is diluted ~4:1 -- and worse, the same average is
serving as the benchmark, so part of our own signal is subtracted from itself. A market-wide
compression and a competitor sitting on our book produce the SAME number there. The two are only
separable in the RESIDUAL: our rate minus the cross-section at the same instant.

This is the identical discipline `libs/validation/event_study.abnormal_returns` applies to event
studies -- "without this an event study measures BETA, not edge" -- carried over to funding. The
level is the market; the residual is ours.

WHY A PERCENTILE AND A RESIDUAL, BOTH. They fail in different directions and the pair is cheap:
  * the RESIDUAL (rate minus universe median) keeps P&L units, so a compression can be priced in
    bps against the round-trip cost that has to be earned back;
  * the PERCENTILE RANK is unit-free and survives a universe-wide level shift that would move
    every residual at once -- a funding regime change is not a competitor.
A tell that shows in only one of the two is reported as exactly that, never promoted to both.

WHAT THIS DELIBERATELY DOES NOT DO. It does not resize, denylist, or touch an order. Crowding is
evidence about CAPACITY, and capacity evidence routes to a fence and a review (§42 capacity parity),
never to an autonomous sizing change from a single new signal -- the same root-cause discipline the
incumbent organ states in its own action note.

THE STATISTIC IS A t, NOT A THRESHOLD. Compression is tested with
`libs/research/evidence_clock.sufficient()` on the per-symbol residual drift, so a held name that
has existed for three days cannot raise an alarm and a fast-accruing book is not made to wait for a
calendar (L1.48). The demeaning caveat is priced: subtracting the universe median over ~850 symbols
induces a cross-name residual correlation of order -1/(N-1) ~ -0.001, far below anything that would
manufacture the effect (the desk's `cohort_independence.demeaning_floor` lesson, at a universe
width where the floor is negligible rather than load-bearing).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from libs.research.evidence_clock import MIN_OBS, sufficient

#: Held-symbol residual samples below this cannot support a drift test at all. Distinct from
#: evidence_clock.MIN_OBS, which governs the t: this governs whether a SERIES exists to take a t of.
MIN_SNAPSHOTS = 8

#: A residual compression smaller than this is not economically actionable whatever its t-stat --
#: it is inside the noise of a single round trip at the desk's measured median cost. Stated in bps
#: per settlement so it can be compared directly against `data/cost_model.json`.
MATERIAL_BPS = 1.0


@dataclass(frozen=True)
class SymbolCrowding:
    """One held name's crowding evidence over its own holding window."""

    symbol: str
    n_snapshots: int
    #: Funding minus the universe median at the same instant, in bps, early window.
    residual_bps_early: float
    residual_bps_late: float
    #: Negative = our name compressed relative to the cross-section. The tell.
    residual_drift_bps: float
    #: Cross-sectional percentile of our rate, 0-1. Unit-free cross-check on the residual.
    percentile_early: float
    percentile_late: float
    percentile_drift: float
    t_stat: float
    sufficient: bool
    reason: str


def percentile_of(rate: float, universe: list[float]) -> float:
    """Share of the cross-section at or below ``rate`` -- unit-free position in the distribution.

    Ties count as at-or-below deliberately: with hundreds of perps pinned at the same base rate, a
    strict inequality would read a name sitting exactly at the mode as being at the bottom of it.
    """
    if not universe:
        return float("nan")
    return sum(1 for u in universe if u <= rate) / len(universe)


def residual_bps(rate: float, universe: list[float]) -> float:
    """Our rate minus the cross-section MEDIAN, in bps -- the abnormal component.

    Median rather than mean because perp funding is fat-tailed in both directions; a handful of
    squeezed names would drag a mean benchmark and manufacture a residual out of arithmetic.
    """
    if not universe:
        return float("nan")
    return (rate - statistics.median(universe)) * 1e4


def _split(values: list[float]) -> tuple[list[float], list[float]]:
    """Early/late halves. Odd counts give the extra observation to the LATE half, which is the
    conservative direction: a compression tell is easier to REFUTE with more recent evidence."""
    half = len(values) // 2
    return values[:half], values[half:]


def symbol_crowding(symbol: str, rates: list[float], universes: list[list[float]],
                    *, min_snapshots: int = MIN_SNAPSHOTS) -> SymbolCrowding | None:
    """Crowding evidence for one held name across aligned snapshots.

    ``rates[i]`` is our symbol's funding at snapshot ``i``; ``universes[i]`` is the whole
    cross-section at that SAME instant. The alignment is the requirement -- a residual taken
    against a different instant's universe is not a residual, and this returns ``None`` rather
    than compute one from mismatched inputs.
    """
    if len(rates) != len(universes) or len(rates) < min_snapshots:
        return None
    res = [residual_bps(r, u) for r, u in zip(rates, universes, strict=True)]
    pct = [percentile_of(r, u) for r, u in zip(rates, universes, strict=True)]
    res = [x for x in res if x == x]          # drop NaN from empty universes
    pct = [x for x in pct if x == x]
    if len(res) < min_snapshots or len(pct) < min_snapshots:
        return None

    r_early, r_late = _split(res)
    p_early, p_late = _split(pct)
    drift = statistics.mean(r_late) - statistics.mean(r_early)

    # The t is on the LATE window's residual against the EARLY window's mean: "has this name's
    # abnormal funding fallen away from where it was?". Sign is flipped so a POSITIVE t means
    # compression, which keeps `sufficient()` -- which tests a positive effect -- meaningful.
    base = statistics.mean(r_early)
    dev = [base - x for x in r_late]
    sd = statistics.stdev(dev) if len(dev) > 1 else 0.0
    suf = sufficient(statistics.mean(dev), sd, len(dev), min_obs=min(MIN_OBS, min_snapshots))
    return SymbolCrowding(
        symbol=symbol, n_snapshots=len(res),
        residual_bps_early=round(statistics.mean(r_early), 4),
        residual_bps_late=round(statistics.mean(r_late), 4),
        residual_drift_bps=round(drift, 4),
        percentile_early=round(statistics.mean(p_early), 4),
        percentile_late=round(statistics.mean(p_late), 4),
        percentile_drift=round(statistics.mean(p_late) - statistics.mean(p_early), 4),
        t_stat=round(suf.t_stat, 3), sufficient=suf.sufficient, reason=suf.reason,
    )


def assess(per_symbol: list[SymbolCrowding], *, material_bps: float = MATERIAL_BPS
           ) -> dict[str, Any]:
    """Book-level verdict over the held names, with both tells reported separately.

    CONFIRMED requires the residual AND the percentile to agree. Either alone is reported as
    PARTIAL and named as such: a residual-only move is what a universe level-shift looks like from
    inside one name, and a percentile-only move can be a reshuffle among names that all pay the
    same. Promoting either to a book-level alarm on its own is how a regime becomes an adversary.
    """
    if not per_symbol:
        return {"verdict": "NO-HELD-EVIDENCE", "n_symbols": 0, "compressing": [],
                "detail": "no held name has enough aligned snapshots to test"}

    compressing = [s for s in per_symbol
                   if s.sufficient and s.residual_drift_bps <= -material_bps]
    pct_falling = [s for s in per_symbol if s.percentile_drift < 0.0]
    both = [s for s in compressing if s.percentile_drift < 0.0]

    if both:
        verdict = "CROWDING"
        detail = (f"{len(both)}/{len(per_symbol)} held name(s) compressed against the "
                  f"cross-section on BOTH tells: "
                  + ", ".join(f"{s.symbol} {s.residual_drift_bps:+.2f}bps "
                              f"pct {s.percentile_drift:+.3f} t={s.t_stat:.2f}" for s in both))
    elif compressing:
        verdict = "PARTIAL"
        detail = (f"{len(compressing)}/{len(per_symbol)} name(s) show a significant RESIDUAL "
                  f"compression that the percentile does not confirm -- consistent with a "
                  f"universe-wide level shift seen from inside one name, not a competitor")
    elif len(pct_falling) == len(per_symbol) and len(per_symbol) > 1:
        verdict = "PARTIAL"
        detail = (f"all {len(per_symbol)} held name(s) fell in cross-sectional RANK without a "
                  f"significant residual move -- a reshuffle among names paying alike, not yet "
                  f"a priced compression")
    else:
        verdict = "OK"
        detail = (f"{len(per_symbol)} held name(s) tested; no significant residual compression "
                  f"against the cross-section")
    return {"verdict": verdict, "n_symbols": len(per_symbol),
            "compressing": [s.symbol for s in compressing],
            "confirmed_both_tells": [s.symbol for s in both], "detail": detail}
