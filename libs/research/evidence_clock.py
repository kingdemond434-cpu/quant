"""THE EVIDENCE CLOCK — calendar time is not evidence, and treating it as evidence costs money.

THE DEFECT. A lifecycle that says "20 trading days of shadow" or "3 months before capital" is
measuring the wrong quantity. A strategy that trades 500 times in five days can accumulate more
usable forward evidence than one that trades 8 times in three months; waiting the same interval for
both is simultaneously too slow for the first and too fast for the second. The waiting has a price
and nothing on this desk has ever charged it: an edge that is real for twenty days and spends
fifteen of them in a calendar gate has had most of its economic life thrown away by its own
validator.

SO THE CLOCK COUNTS INFORMATION, NOT DAYS. And the number it counts is EFFECTIVE INDEPENDENT
OBSERVATIONS, which is the only version of the count that cannot be gamed by a busy afternoon:

    500 trades inside one BTC impulse are ONE event observed 500 times

That inflation is the same defect as GAP #85 -- `n` counting readings of the world rather than
events in it -- pointed at the promotion decision, which is the most expensive place on the desk to
get it wrong. Four deflators apply and each is measured rather than assumed: serial correlation,
event clustering, regime concentration, and cross-symbol dependence.

**THE CLOCK IS SYMMETRIC AND THAT IS DELIBERATE.** It accelerates a high-information strategy AND
it refuses to let a burst of correlated fills masquerade as months of evidence. A rule that only
sped things up would be a lowered bar wearing a stopwatch.

WHAT IT DOES NOT DO. It sets no threshold and grants no promotion. It answers "how much independent
evidence exists" and hands the number to the ladder, which owns what that buys. A module that both
measured the evidence and decided what it earned would be marking its own homework.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MIN_EFFECTIVE",
    "MIN_OBS",
    "MIN_T",
    "EvidenceState",
    "Sufficiency",
    "annualised_information_rate",
    "effective_n",
    "regime_penalty",
    "render",
    "sufficiency",
    "sufficient",
    "t_stat",
    "waiting_cost",
]

#: Below this, an effective count is too small for any forward claim regardless of raw trades.
#: Not a promotion threshold -- the ladder owns those -- but the floor under which the clock
#: reports that it has measured nothing worth reporting.
MIN_EFFECTIVE: float = 30.0


@dataclass(frozen=True)
class EvidenceState:
    """How much INDEPENDENT forward evidence a candidate has actually accumulated."""

    raw_observations: int
    #: Lag-1 autocorrelation of the per-trade return series. 0.0 when unmeasured, and the caller
    #: must say which -- see `measured`.
    autocorrelation: float = 0.0
    #: Distinct market events the observations fall under. 0 = unmeasured.
    distinct_events: int = 0
    #: Distinct regimes covered. One regime is not a sample of the world.
    distinct_regimes: int = 0
    #: Distinct symbols. Cross-symbol fills during one factor move are not independent.
    distinct_symbols: int = 1
    #: Mean pairwise correlation across symbols, when measured.
    cross_symbol_rho: float = 0.0
    measured: bool = True

    @property
    def calendar_days(self) -> float:
        """Deliberately absent from every calculation. Present so a caller can REPORT elapsed time
        without any code path being able to promote on it."""
        return 0.0


def _serial_deflator(rho: float) -> float:
    """Kish-style deflator for serial correlation: n_eff = n * (1-rho)/(1+rho).

    Clamped at rho>=0 because NEGATIVE autocorrelation genuinely carries more information per
    observation, and crediting it would let a mean-reverting strategy claim more evidence than it
    has trades -- an inflation in the one direction nobody would question.
    """
    r = max(0.0, min(0.99, rho))
    return (1.0 - r) / (1.0 + r)


def regime_penalty(distinct_regimes: int) -> float:
    """Evidence from ONE regime is evidence about one regime.

    Not a hard gate -- a single-regime strategy can be real -- but its forward claim covers the
    world it was observed in, and the count should say so rather than the promotion discovering it
    later. Two regimes is the first point at which "works generally" is even a candidate claim.
    """
    if distinct_regimes <= 0:
        return 0.5   # unmeasured: treated as concentrated, because that is the untested case
    if distinct_regimes == 1:
        return 0.5
    if distinct_regimes == 2:
        return 0.8
    return 1.0


def effective_n(state: EvidenceState) -> float:
    """Effective INDEPENDENT observations. Never larger than the raw count.

    THE EVENT DEFLATOR IS THE ONE THAT MATTERS MOST and it is the one a trade count hides
    completely: 500 fills inside a single liquidation cascade are one observation of one cascade.
    When `distinct_events` is recorded it caps the count outright, because no amount of serial
    independence within an event makes the event happen twice.
    """
    n = float(max(0, state.raw_observations))
    if n <= 0:
        return 0.0
    n *= _serial_deflator(state.autocorrelation)
    if state.distinct_events > 0:
        n = min(n, float(state.distinct_events))
    if state.distinct_symbols > 1:
        # Correlated symbols contribute a fraction of a fresh observation each. At rho=1 the
        # cohort is one instrument wearing several tickers.
        rho = max(0.0, min(1.0, state.cross_symbol_rho))
        n *= (1.0 + (state.distinct_symbols - 1) * (1.0 - rho)) / state.distinct_symbols
    return max(0.0, n * regime_penalty(state.distinct_regimes))


def sufficiency(state: EvidenceState, *, required: float) -> tuple[str, str]:
    """(verdict, why). SUFFICIENT | ACCUMULATING | UNMEASURED — and never a promotion.

    `required` is supplied by the caller because how much evidence a candidate owes depends on the
    candidate: a deep-liquidity high-frequency signal with a simple mechanism and a rare-event
    exploit alpha do not owe the same number, and hard-coding one here would recreate the calendar
    gate in a new unit.
    """
    if not state.measured:
        return "UNMEASURED", (
            "no forward record has been instrumented, so there is no evidence to count. That is "
            "an absence of measurement, never an absence of edge, and it is also never a reason "
            "to wait a fixed interval -- start the record")
    eff = effective_n(state)
    if eff < MIN_EFFECTIVE:
        return "ACCUMULATING", (
            f"{eff:.1f} effective observations from {state.raw_observations} raw -- below the "
            f"{MIN_EFFECTIVE:.0f} floor. The gap between the two numbers IS the finding: "
            "correlated fills, one event or one regime")
    if eff >= required:
        return "SUFFICIENT", (
            f"{eff:.1f} effective observations of {required:.0f} required, from "
            f"{state.raw_observations} raw. Elapsed time did not enter this calculation")
    return "ACCUMULATING", (
        f"{eff:.1f} of {required:.0f} effective observations. Deflated from "
        f"{state.raw_observations} raw by serial correlation "
        f"{state.autocorrelation:.2f}, {state.distinct_events or 'unmeasured'} distinct event(s), "
        f"{state.distinct_regimes or 'unmeasured'} regime(s)")


def waiting_cost(expected_edge_bps: float, effective_rate_per_day: float,
                 days_waited: float) -> tuple[float, str]:
    """Economic cost of the delay itself, in bps of forgone edge. THE NUMBER NOBODY CHARGES.

    A validator that delays a real edge is spending money, and until this is computed the spend is
    invisible -- so caution always looks free and speed always looks reckless. Reporting it does
    not license shortening any gate; it makes the trade-off visible to the allocator, which is the
    only thing that can weigh it against a false discovery.
    """
    if expected_edge_bps <= 0 or days_waited <= 0:
        return 0.0, ("no waiting cost: the edge is not positive in expectation, so delay costs "
                     "nothing and caution is free here")
    cost = expected_edge_bps * effective_rate_per_day * days_waited
    return cost, (
        f"{cost:.1f} bp of expected edge forgone over {days_waited:.1f} day(s) of waiting at "
        f"{effective_rate_per_day:.1f} effective observations/day. This is what the delay COST, "
        "not an argument that it was wrong -- a false discovery reaching capital costs more, and "
        "the allocator is what weighs the two")


def annualised_information_rate(state: EvidenceState, days: float) -> float | None:
    """Effective observations per day. None when unmeasurable -- the input to a fast-track decision.

    A candidate producing many independent observations per day can clear a real bar in days; one
    producing a fraction of an observation per day cannot, and no process change alters that. This
    is what makes the track ENDOGENOUS to the strategy rather than a category somebody assigned.
    """
    if days <= 0 or not state.measured:
        return None
    return effective_n(state) / days


def render(state: EvidenceState, *, required: float) -> str:
    verdict, why = sufficiency(state, required=required)
    eff = effective_n(state)
    ratio = f"{eff / state.raw_observations:.1%}" if state.raw_observations else "n/a"
    return (f"[{verdict}] {eff:.1f} effective / {state.raw_observations} raw ({ratio} survive "
            f"deflation)\n    {why}")


# ----------------------------------------------------------------------------------------------
# THE t-TEST CLOCK (f4066f8). RESTORED VERBATIM 2026-08-09, and the restoration is deliberate.
#
# `sufficiency()` above replaced this API, and the replacement is better: it deflates the raw
# count for autocorrelation, so correlated fills stop reading as independent evidence. But the
# rewrite removed MIN_OBS / MIN_T / Sufficiency / sufficient() while THREE modules still imported
# them -- libs/research/event_density.py, libs/research/crowding.py, libs/risk/vol_headroom.py --
# and those three have been raising ImportError at import time ever since. Verified by import,
# not inferred: all three fail on the unified frontier branch today.
#
# WHY RESTORED RATHER THAN MIGRATED. The two are not the same statistic. This one takes
# (mean, sd, n) and tests a t against min_t; the new one takes an EvidenceState and tests an
# EFFECTIVE n against a caller-supplied requirement. Rewriting three callers onto the new clock
# during a merge would silently change what they compute, and a wrong answer that runs is worse
# than an ImportError that does not. So the old function comes back UNCHANGED, and migrating the
# three callers onto the effective-n clock is owed work with its own review, not merge cleanup.
#
# NEW CALLERS SHOULD USE `sufficiency()`. This exists to keep three existing modules honest, not
# to offer a choice.
# ----------------------------------------------------------------------------------------------

#: Minimum observations before a t-statistic is trustworthy at all. Below this the estimate's own
#: standard error is too wide for the t to mean much, whatever it reads.
MIN_OBS = 20

#: Default confidence bar. 2.0 is roughly p<0.05 two-sided and is the bar for ADMITTING an effect,
#: not for betting the book on it -- callers sizing capital should ask for more (the sleeve ladder
#: asks 2.5 at STRONG and 3.5 at DURABLE).
MIN_T = 2.0

@dataclass(frozen=True)
class Sufficiency:
    sufficient: bool
    t_stat: float
    n_obs: int
    reason: str
    #: Observations still needed at the CURRENT effect size. This is the number that replaces "come
    #: back in N days": it tells a caller how much more evidence to GENERATE, which it can often
    #: accelerate, rather than how long to wait, which it cannot.
    obs_short: int


def t_stat(mean: float, stdev: float, n_obs: int) -> float:
    """t = sqrt(n) * mean/stdev. Zero when undefined -- never a confident default."""
    if n_obs < 2 or not (stdev > 0) or not math.isfinite(mean) or not math.isfinite(stdev):
        return 0.0
    return math.sqrt(n_obs) * mean / stdev


def sufficient(mean: float, stdev: float, n_obs: int, *,
               min_obs: int = MIN_OBS, min_t: float = MIN_T) -> Sufficiency:
    """Is there enough evidence YET -- regardless of how long it took to gather?

    Returns the shortfall in OBSERVATIONS rather than days. A caller told "you need 40 more closes"
    can open more slots, shorten holds, or widen the universe to get them today; a caller told
    "wait 60 days" can only wait. That difference is the whole point.
    """
    t = t_stat(mean, stdev, n_obs)
    if n_obs < min_obs:
        return Sufficiency(False, t, n_obs,
                           f"{n_obs}/{min_obs} observations -- too few for the t to be trusted",
                           min_obs - n_obs)
    if t < min_t:
        # n needed scales with the SQUARE of the t shortfall, because t grows as sqrt(n).
        need = math.ceil(n_obs * (min_t / t) ** 2) if t > 0 else 0
        short = max(0, need - n_obs) if need else -1
        return Sufficiency(False, t, n_obs,
                           f"t={t:.2f} < {min_t} at n={n_obs}" +
                           (f" -- needs ~{short} more observations at this effect size"
                            if short >= 0
                            else " -- effect is non-positive, more data will not fix it"),
                           short if short >= 0 else 0)
    return Sufficiency(True, t, n_obs, f"t={t:.2f} >= {min_t} on {n_obs} observations", 0)
