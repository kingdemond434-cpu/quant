"""THE EVENT-DENSITY CLOCK -- evidence accrues per EVENT, and events are not all worth one each.

WHAT THIS FIXES. `evidence_clock.sufficient()` already replaced "wait N days" with "is there enough
evidence yet". It answers the question correctly and it reaches almost nothing: measured
2026-08-05, exactly one file on the promotion path imports it. The other clocks -- five identical
ninety-day shadow verdicts, a thirty-day gate that scales DEPLOYABLE CAPITAL, `_MIN_DAYS
= 40` in three more -- still ask the calendar. For an edge whose evidence arrives in discrete
events (a funding settlement three times a day, a liquidation cascade, an ETF flow print) the
calendar under-credits by exactly the event rate, and the desk waits out a clock it has already
earned.

THE TRAP THIS MODULE EXISTS TO NOT FALL INTO, stated first because it is the whole difficulty.
"Funding settles 3x a day, so 28 days is 84 observations" is FALSE and would loosen every
downstream bar by sqrt(3) while looking like an improvement. Successive funding rates are strongly
serially correlated: 84 settlements are nowhere near 84 independent draws, and crediting them as
such inflates every t-statistic computed from them. That is the axis_screen n_eff inflation defect
(a 4,314-bar series reporting n_eff = 1,236,384) one layer up the stack, and it is the single most
expensive mistake available here -- a bar loosened by arithmetic nobody re-reads.

So the currency is EFFECTIVE observations, never raw ones:

    n_eff = n * (1 - rho) / (1 + rho)        clamped to (0, n]

the standard AR(1) correction for the variance of a mean. rho = 0 gives back n; rho = 0.5 costs
two thirds of it; rho -> 1 says a hundred events carried one event's worth of news. THE CLAMP AT n
IS LOAD-BEARING AND ONE-DIRECTIONAL: negative serial correlation genuinely does reduce the variance
of a mean, but crediting MORE evidence than events observed is the exact shape of every n_eff bug
this desk has paid for, so the arithmetic is allowed to take observations away and never to invent
them.

WHAT "FASTER WITHOUT WEAKER" MEANS HERE, precisely. The bar does not move: `min_t` and `MIN_OBS`
are IMPORTED from evidence_clock rather than restated, so this module has no vocabulary in which to
lower them. What changes is the unit the clock counts in. A genuinely event-dense mechanism whose
events carry independent news reaches the SAME t on the SAME bar in fewer calendar days. One whose
events are autocorrelated is discounted and correctly takes longer than its raw count suggests --
this module makes some clocks SLOWER, and that is evidence of it working, not a defect in it.

THE RATE IS MEASURED, NEVER CONFIGURED (L1.46). Event rate comes from the observed stamps, so a
mechanism that claims 3 events a day and delivers 1.2 is credited 1.2. A configured constant is not
evidence of a cadence -- the desk has a live finding (R0117) built on exactly that mistake.

AND THE SHORTFALL IS REPORTED IN EVENTS, WITH A DERIVED ETA. "You need 31 more settlements; at your
measured 2.4/day that is ~13 days" is actionable in a way "come back in 90 days" is not: a caller
told the first can open more slots, widen the universe or shorten holds to get them sooner. That
difference is the entire point of L1.48.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from libs.research.evidence_clock import MIN_OBS, MIN_T, Sufficiency, sufficient

#: Below this, a lag-1 autocorrelation estimate is noise. We then assume rho = 0 rather than trust
#: a noisy estimate -- but a sample this small cannot clear MIN_OBS anyway, so the assumption never
#: decides a promotion. It exists so the number reported is honest, not so a gate passes.
MIN_FOR_RHO = 8

#: Trading periods per year for annualising a per-observation Sharpe. Daily convention, matching
#: the shadow runners' own `sqrt(_PPY)`.
DAILY_PPY = 252.0


@dataclass(frozen=True)
class EventClock:
    """What a mechanism's evidence is actually worth, and how fast it is arriving."""

    mechanism: str
    n_events: int
    #: Calendar span the events arrived over. REPORTED, never gated on.
    span_days: float
    #: MEASURED events per day, from the stamps. Zero when stamps were not supplied.
    events_per_day: float
    #: Lag-1 serial correlation of the per-event outcomes -- the independence discount.
    autocorr: float
    #: The currency. Raw events discounted for serial dependence, never exceeding n_events.
    n_effective: float
    t_stat: float
    sufficient: bool
    #: EFFECTIVE observations still needed at the current effect size.
    obs_short: float
    #: Events still needed -- obs_short grossed back up through the discount, because the caller
    #: generates EVENTS, not effective observations.
    events_short: int
    #: Days to reach the bar at the MEASURED rate. None when the rate is unknown or the effect is
    #: non-positive (more data will not fix a wrong sign).
    eta_days: float | None
    reason: str

    @property
    def discount(self) -> float:
        """n_effective / n_events -- what one event is actually worth. 1.0 = fully independent."""
        return self.n_effective / self.n_events if self.n_events else 0.0


def lag1_autocorr(values: Sequence[float]) -> float:
    """Lag-1 serial correlation, 0.0 when it cannot be estimated.

    Returns 0.0 rather than a guess on a degenerate input: a constant series has no defined
    autocorrelation, and defaulting it to 1.0 would zero out a legitimate sample while defaulting
    it to -1.0 would double it. Zero is the only neutral answer, and it is paired with the clamp in
    `effective_n` so a bad estimate can never manufacture evidence.
    """
    x = [float(v) for v in values if v == v]
    n = len(x)
    if n < MIN_FOR_RHO:
        return 0.0
    mean = statistics.fmean(x)
    denom = sum((v - mean) ** 2 for v in x)
    if denom <= 0.0:
        return 0.0
    num = sum((x[i] - mean) * (x[i + 1] - mean) for i in range(n - 1))
    rho = num / denom
    # A |rho| at or beyond 1 is an arithmetic artifact of a near-degenerate series, not a
    # measurement. Bound it so the discount stays finite.
    return max(-0.99, min(0.99, rho))


def effective_n(n: int, rho: float) -> float:
    """AR(1) effective sample size: n * (1-rho)/(1+rho), clamped to (0, n].

    THE UPPER CLAMP IS THE POINT. Negative serial correlation does reduce the variance of a mean,
    so the unclamped formula would return more than n -- and an n_eff above the observations
    actually seen is the precise shape of the inflation bug that made a 4,314-row screen report
    over a million effective rows. This arithmetic may remove evidence and may never invent it.
    """
    if n <= 0:
        return 0.0
    r = max(-0.99, min(0.99, float(rho)))
    return max(min(float(n), n * (1.0 - r) / (1.0 + r)), 1.0)


def t_from_annual_sharpe(sharpe_ann: float, n_obs: float,
                         *, periods_per_year: float = DAILY_PPY) -> float:
    """t-statistic implied by an ANNUALISED Sharpe over ``n_obs`` observations.

    The conversion the desk's capital gate was missing entirely. An annualised Sharpe is a RATE and
    carries no sample size, so a bare `sharpe > 0` test cannot tell 0.6 on twelve observations from
    0.6 on six hundred -- which is exactly how a hot streak buys size it has not earned. Since
    SR_ann = SR_per_period * sqrt(ppy) and t = SR_per_period * sqrt(n), t = SR_ann * sqrt(n/ppy).
    """
    if n_obs <= 0 or periods_per_year <= 0 or not math.isfinite(sharpe_ann):
        return 0.0
    return float(sharpe_ann) * math.sqrt(float(n_obs) / float(periods_per_year))


def _span_and_rate(stamps: Sequence[float] | None, n: int) -> tuple[float, float]:
    """Calendar span in days and MEASURED events/day. (0.0, 0.0) when stamps are absent."""
    if not stamps or len(stamps) < 2:
        return 0.0, 0.0
    s = sorted(float(x) for x in stamps)
    span_days = (s[-1] - s[0]) / 86400.0
    if span_days <= 0.0:
        return 0.0, 0.0
    # n-1 intervals over the span: the rate at which NEW events arrive, not a fencepost count.
    return span_days, (n - 1) / span_days


def event_clock(outcomes: Sequence[float], stamps: Sequence[float] | None = None, *,
                mechanism: str, min_t: float = MIN_T, min_obs: int = MIN_OBS) -> EventClock:
    """Is this mechanism's evidence sufficient YET -- counted in events, discounted for dependence.

    ``outcomes[i]`` is the per-EVENT outcome (a return, a spread captured, an abnormal move) and
    ``stamps[i]`` its epoch-second timestamp. Stamps are optional and used only to MEASURE the
    arrival rate for the ETA; the verdict never depends on them, so a mechanism that cannot supply
    them is judged on identical terms and simply gets no ETA.
    """
    vals = [float(v) for v in outcomes if v == v]
    n = len(vals)
    if n == 0:
        return EventClock(mechanism, 0, 0.0, 0.0, 0.0, 0.0, 0.0, False, float(min_obs), min_obs,
                          None, "no events observed -- unmeasured, which is not the same as zero")

    rho = lag1_autocorr(vals)
    n_eff = effective_n(n, rho)
    span_days, rate = _span_and_rate(stamps, n)

    mean = statistics.fmean(vals)
    sd = statistics.stdev(vals) if n > 1 else 0.0
    # The t is taken on the EFFECTIVE count, which is the whole discipline: the same returns
    # judged at their real information content rather than their row count.
    suf: Sufficiency = sufficient(mean, sd, round(n_eff), min_obs=min_obs, min_t=min_t)

    disc = n_eff / n
    events_short = math.ceil(suf.obs_short / disc) if disc > 0 else 0
    eta = None
    if events_short > 0 and rate > 0 and suf.t_stat > 0:
        eta = round(events_short / rate, 1)
    elif events_short == 0 and suf.sufficient:
        eta = 0.0

    return EventClock(
        mechanism=mechanism, n_events=n, span_days=round(span_days, 2),
        events_per_day=round(rate, 3), autocorr=round(rho, 4), n_effective=round(n_eff, 1),
        t_stat=round(suf.t_stat, 3), sufficient=suf.sufficient,
        obs_short=float(suf.obs_short), events_short=events_short, eta_days=eta,
        reason=suf.reason,
    )


def forward_verdict(n_obs: int, fwd_sharpe: float, bt_sharpe: float, *,
                    min_t: float = MIN_T, min_obs: int = MIN_OBS,
                    periods_per_year: float = DAILY_PPY,
                    on_track_action: str = "eligible for TINY live on human approval "
                                           "(governance gate)",
                    kill_action: str = "kill candidate",
                    accruing_tail: str = "") -> str:
    """The Stage-B shadow verdict, gated on EVIDENCE instead of elapsed days.

    ONE FUNCTION, FIVE CALLERS, BY DESIGN. The ninety-day literal was copy-pasted verbatim into five
    shadow runners, which is how this desk ends up fixing a bar in one caller's comment while the
    next caller hits it from scratch. A shared function cannot drift; five literals always do.

    THE BAR IS UNCHANGED AND THE DIRECTION CUTS BOTH WAYS, which is how you can tell it is not a
    loosening. A sleeve accruing fast enough to reach t >= min_t in forty observations is promoted
    at forty instead of waiting out ninety it has already earned; a sleeve that reaches day ninety
    carrying t = 0.4 no longer clears on the technicality of having existed for a quarter. The
    second case is the one the calendar was silently passing.
    """
    t = t_from_annual_sharpe(fwd_sharpe, n_obs, periods_per_year=periods_per_year)
    if fwd_sharpe < 0:
        return (f"FAILING FORWARD -> {kill_action} (Sharpe {fwd_sharpe:.2f} on {n_obs} "
                f"observations, t={t:.2f})")
    if n_obs < min_obs:
        return (f"ACCUMULATING ({n_obs}/{min_obs} observations -- too few for the t to be "
                f"trusted, whatever it reads){accruing_tail}")
    if t < min_t:
        # Observations needed scale with the SQUARE of the t shortfall, because t grows as sqrt(n).
        need = math.ceil(n_obs * (min_t / t) ** 2) - n_obs if t > 0 else 0
        return (f"ACCUMULATING (t={t:.2f}/{min_t} on {n_obs} observations"
                + (f" -- needs ~{need} more at this effect size)" if need > 0 else
                   " -- effect is non-positive, more data will not fix it)") + accruing_tail)
    if fwd_sharpe >= 0.5 and fwd_sharpe >= 0.5 * bt_sharpe:
        return (f"ON TRACK -> {on_track_action}; t={t:.2f} >= {min_t} on {n_obs} observations")
    return (f"WEAK forward -> continue shadow, do not deploy (t={t:.2f} clears {min_t} but "
            f"Sharpe {fwd_sharpe:.2f} is below 0.5 or half the backtest {bt_sharpe:.2f})")


def verdict_line(clock: EventClock) -> str:
    """One line a shadow runner can publish in place of "ACCUMULATING (n/90+ days)".

    States the shortfall in EVENTS and, where the rate is measured, the ETA that follows from it --
    never a bare calendar target, which tells a caller nothing it can act on.
    """
    density = (f"{clock.n_events} events over {clock.span_days:g}d "
               f"({clock.events_per_day:g}/day)" if clock.events_per_day
               else f"{clock.n_events} events")
    worth = (f"worth {clock.n_effective:g} effective "
             f"(rho={clock.autocorr:+.2f}, {clock.discount:.0%} of raw)")
    if clock.sufficient:
        return f"SUFFICIENT: {density}, {worth}; t={clock.t_stat:.2f}. {clock.reason}"
    eta = f", ~{clock.eta_days:g}d at the measured rate" if clock.eta_days else ""
    return (f"ACCRUING: {density}, {worth}; t={clock.t_stat:.2f}. "
            f"Needs ~{clock.events_short} more event(s){eta} -- {clock.reason}")
