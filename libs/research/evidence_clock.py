"""EVIDENCE, NOT CALENDAR: the one gate every "wait N days" check on this desk should call.

THE HABIT BEING KILLED (principal 2026-08-01: "fix every grandma time habit"). The desk gates
promotion on elapsed days in at least eight places -- `if days < 90` in four shadow runners,
`fwd_days >= 30` in the capital plan, `_MIN_DAYS = 40` in axis shadows and stage-B capacity,
`DESIGN_CLOCK_DAYS = 90`, `live_days >= 60` in kelly_shrink. Every one of them asks the wrong
question.

Calendar time is not evidence. It is a PROXY for evidence that happens to be right only when
observation rate is fixed, and this desk's rate is not fixed -- it varies by sleeve, by symbol and
by how many slots are open. Two consequences, both bad, both currently live:

  * A FAST book is punished for being fast. A sleeve producing 3 closes a day has more evidence at
    day 20 than a slow one has at day 90, and the day-gate holds it back anyway. That is foregone
    compounding bought with nothing.
  * A SLOW book is promoted on a technicality. Ninety days of near-inactivity clears `days >= 90`
    while carrying a handful of observations and a t-stat under 1. The gate reads green on a claim
    no statistician would sign.

What confidence actually depends on is sample size and the t-statistic of the measured effect. The
t-stat is the axis rather than the Sharpe because a Sharpe of 2.0 on 20 observations and the same
2.0 on 400 are different claims, and a Sharpe bar cannot tell them apart -- which is exactly how a
hot streak buys size it has not earned.

WHERE CALENDAR GATES REMAIN LEGITIMATE, and this module must not be used to remove them:
  * physical and venue reality -- funding stamps, rate limits, maker rest times, release lags;
  * an explicit principal law, e.g. the 7-day Gate 0 soak floor, which exists to prove the desk
    RUNS UNATTENDED. That one is not a proxy for statistical evidence, it measures a different
    thing entirely, and swapping it for a t-stat would be a category error;
  * data-window definitions such as an out-of-sample split boundary.
The test is simple: if the number is standing in for "enough evidence", replace it. If it encodes
a physical fact or a distinct claim, keep it.

ADAPTIVE BY CONSTRUCTION. There is no schedule here. A caller asks whether the evidence in hand is
sufficient, gets an answer now, and gets a different answer the moment the evidence changes -- in
either direction. Sufficiency is recomputed, never latched, so decay withdraws eligibility as fast
as accumulation grants it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

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
