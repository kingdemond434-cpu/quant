"""SHORTEN DISCOVERY -> LIVE: small capital early, Bayesian allocation, honest about the two traps.

THE PRINCIPAL'S POSITION (2026-08-07), AND IT IS RIGHT: *live as soon as possible with little
capital; if profitable keep and increase, if not retire, and allocate dynamically.* Backtests are
cheap and endlessly arguable; forward live results are neither. Going live small converts an
unfalsifiable argument into evidence, and at small size the tuition is cheap. A desk that waits for
certainty before trading buys nothing with the delay, because certainty is not what waiting
produces.

**TRAP ONE: A MONTH OF SMALL LIVE TRADING IS NOT AN EXPERIMENT, IT IS AN ANECDOTE.** At Sharpe 1.0
the annual signal-to-noise is 1.0, so one month carries t ~ 0.29. Retiring on a losing month and
scaling on a winning one is, at that horizon, close to a coin flip -- it retires good strategies and
promotes lucky ones at almost the same rate, and it does so while FEELING like decisiveness. So
this module reports the power of the decision it is being asked to make, and returns UNDERPOWERED
rather than a verdict when the evidence cannot support one. Keeping a strategy small for longer
than intuition suggests is not timidity; it is the only honest reading of a short record.

**TRAP TWO, AND IT IS THE ONE THAT SURPRISES PEOPLE: SMALL SIZE HAS WORSE NET ECONOMICS THAN FULL
SIZE.** Fees are proportional but minimum notionals, tick rounding and the spread crossed on every
entry are not. A strategy trading $100 clips can pay several times the basis-point cost of the same
strategy trading $10,000 clips, so a genuinely profitable edge can post losses live at tiny size
FOR REASONS THAT VANISH WHEN IT SCALES. Retiring it would be the exactly wrong conclusion drawn
from real data. `size_cost_penalty()` estimates that drag so a live result can be compared against
the right benchmark rather than against zero.

WHAT THIS MODULE DOES NOT DO. It places no orders, sizes no live position, and touches no rail.
Arming live trading is the principal's act, and the Tier-3 dead-man switch is never modified
autonomously. This computes a RECOMMENDATION from a record; every number it returns is inert.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "MIN_OBS_FOR_A_VERDICT",
    "LadderVerdict",
    "LiveRecord",
    "allocate",
    "decide",
    "posterior",
    "size_cost_penalty",
]

#: Below this many completed round trips, no verdict is issued at any effect size. Not a
#: statistical constant -- a floor below which the posterior is essentially the prior, so the
#: "decision" would be reporting the desk's own assumption back to itself.
MIN_OBS_FOR_A_VERDICT: int = 30

#: Fraction of the Kelly optimum actually allocated. Quarter-Kelly is the standing convention for a
#: reason that matters more here than usual: Kelly is optimal only if the edge estimate is CORRECT,
#: and on a young live record it is a posterior mean with a wide interval. Full Kelly on an
#: uncertain edge is a reliable route to ruin, and this ladder's whole premise is young records.
KELLY_FRACTION: float = 0.25

#: Ceiling on any single strategy's share of capital, however good the posterior looks. A ladder
#: with no cap will, given one lucky record, recommend concentration -- and the objective is
#: geometric growth, which concentration damages through variance drag long before it fails.
MAX_ALLOCATION: float = 0.20


@dataclass(frozen=True)
class LiveRecord:
    """A strategy's forward record. `mean_bps`/`sd_bps` are PER ROUND TRIP, net of realised cost."""

    name: str
    n_trades: int
    mean_bps: float
    sd_bps: float
    days_live: float = 0.0
    #: Typical clip in quote currency -- the input to the small-size cost penalty.
    clip_notional: float = 0.0


@dataclass(frozen=True)
class LadderVerdict:
    """A recommendation. Inert: nothing here places, sizes or arms anything."""

    name: str
    decision: str            # SCALE_UP | HOLD_SMALL | RETIRE | UNDERPOWERED
    allocation: float        # fraction of research capital, 0.0-MAX_ALLOCATION
    post_mean_bps: float
    post_sd_bps: float
    t_stat: float
    power_note: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def posterior(rec: LiveRecord, *, prior_mean_bps: float = 0.0,
              prior_sd_bps: float = 5.0) -> tuple[float, float]:
    """Normal-Normal conjugate update on the per-trade edge. Returns (mean, sd).

    THE PRIOR IS CENTRED ON ZERO AND THAT IS THE LOAD-BEARING CHOICE. The desk's own base rate is
    the argument: 434 screened candidates produced zero survivors, and WS-006's strongest measured
    signal netted -0.656 bp/bar. A prior centred on the backtest's estimate would let an overfit
    backtest pre-load the live verdict -- which is precisely the contamination going live was meant
    to escape. Live evidence must be allowed to speak against the research that produced it.
    """
    n = max(0, rec.n_trades)
    if n == 0 or rec.sd_bps <= 0:
        return prior_mean_bps, prior_sd_bps
    tau0 = 1.0 / (prior_sd_bps ** 2)
    tau_d = n / (rec.sd_bps ** 2)
    post_var = 1.0 / (tau0 + tau_d)
    post_mean = post_var * (tau0 * prior_mean_bps + tau_d * rec.mean_bps)
    return post_mean, math.sqrt(post_var)


def size_cost_penalty(clip_notional: float, *, min_notional: float = 20.0,
                      fixed_bp: float = 1.0) -> float:
    """Extra cost in bp that a SMALL clip pays and a full-size one does not.

    Tick rounding, minimum-notional granularity and the spread crossed per entry do not scale down
    with size, so their basis-point impact rises as the clip shrinks. This is the trap that makes
    "go live small and retire it if it loses" dangerous: a real edge can post losses at $100 clips
    for reasons that disappear entirely at $10,000, and the data supporting the wrong conclusion is
    genuine live data.

    Deliberately crude and deliberately CONSERVATIVE (it over-states the penalty at tiny size), and
    it should be replaced by the venue's measured fill data the moment any exists. An estimate
    labelled as one beats an unstated assumption of zero.
    """
    if clip_notional <= 0:
        return 0.0
    return fixed_bp * max(0.0, min_notional / clip_notional)


def _power_note(rec: LiveRecord, post_sd: float) -> tuple[str, bool]:
    """Can this record support a verdict at all? Returns (note, powered)."""
    if rec.n_trades < MIN_OBS_FOR_A_VERDICT:
        return (f"{rec.n_trades} round trip(s) < {MIN_OBS_FOR_A_VERDICT}: the posterior is still "
                "essentially the prior, so a verdict would report the desk's own assumption back "
                "to itself", False)
    if post_sd <= 0:
        return ("posterior sd is degenerate -- not measurable", False)
    return (f"{rec.n_trades} round trip(s); posterior sd {post_sd:.3f}bp", True)


def allocate(post_mean_bps: float, post_sd_bps: float, *, fraction: float = KELLY_FRACTION,
             cap: float = MAX_ALLOCATION) -> float:
    """Fractional-Kelly allocation from the POSTERIOR, not from the point estimate.

    Using the posterior mean and sd rather than the sample mean is what makes the ladder
    self-damping: a young record has a wide posterior, so the recommended size is small no matter
    how good the sample looks, and it grows as evidence accumulates rather than as luck does. A
    negative posterior mean allocates ZERO -- never a short of the strategy, which would be trading
    on the desk's own inability to measure.
    """
    if post_mean_bps <= 0 or post_sd_bps <= 0:
        return 0.0
    kelly = post_mean_bps / (post_sd_bps ** 2)
    return float(min(cap, max(0.0, fraction * kelly)))


def decide(rec: LiveRecord, *, prior_sd_bps: float = 5.0,
           retire_below_bps: float = 0.0) -> LadderVerdict:
    """The ladder's recommendation for one strategy.

    RETIREMENT REQUIRES POWER, NOT JUST A LOSS. A losing month at Sharpe 1.0 carries t ~ 0.29 and
    is what a good strategy does roughly four months a year. Retiring on it is not decisiveness, it
    is a coin flip wearing a decision's clothes -- and the strategies it kills are the ones whose
    edge is real but modest, which are the only kind this desk expects to find.
    """
    post_mean, post_sd = posterior(rec, prior_sd_bps=prior_sd_bps)
    note, powered = _power_note(rec, post_sd)
    t = post_mean / post_sd if post_sd > 0 else 0.0

    notes: list[str] = []
    penalty = size_cost_penalty(rec.clip_notional)
    if penalty > 0:
        notes.append(
            f"small-size cost drag ~{penalty:.2f}bp per round trip at a {rec.clip_notional:.0f} "
            "clip. Compare the live result against THAT, not against zero: a real edge can post "
            "losses at tiny size for reasons that vanish when it scales, and retiring it would be "
            "the wrong conclusion drawn from genuine data.")

    if not powered:
        return LadderVerdict(rec.name, "UNDERPOWERED", 0.0, post_mean, post_sd, t, note,
                             (*notes, "keep it live at the minimum that produces observations -- "
                                      "the record is the point, not the P&L at this size"))

    if post_mean + penalty <= retire_below_bps:
        return LadderVerdict(
            rec.name, "RETIRE", 0.0, post_mean, post_sd, t, note,
            (*notes, f"posterior mean {post_mean:.3f}bp is at or below the retirement line even "
                     f"after crediting the {penalty:.2f}bp small-size drag -- this is not a sizing "
                     "problem"))

    alloc = allocate(post_mean, post_sd)
    if t >= 2.0:
        return LadderVerdict(rec.name, "SCALE_UP", alloc, post_mean, post_sd, t, note,
                             (*notes, f"posterior t={t:.2f}; allocation is quarter-Kelly on the "
                                      "POSTERIOR and rises with evidence, not with luck"))
    # The note has to describe the record it actually has. A negative posterior that survived the
    # retirement line only because the small-size drag was credited is a DIFFERENT situation from a
    # positive one that is merely not yet significant, and calling both "positive but not yet
    # separable" would be the ladder flattering a strategy in the one state where it should not.
    shape = ("positive but not yet separable from zero" if post_mean > 0 else
             f"NEGATIVE ({post_mean:+.3f}bp) and spared only by crediting the {penalty:.2f}bp "
             "small-size drag -- if the drag estimate is wrong, so is this reprieve")
    return LadderVerdict(rec.name, "HOLD_SMALL", min(alloc, 0.02), post_mean, post_sd, t, note,
                         (*notes, f"posterior t={t:.2f} < 2.0: {shape}. Holding small IS the "
                                  "decision -- it buys observations, which is the only thing that "
                                  "moves the posterior."))


def render(v: LadderVerdict) -> str:
    head = (f"{v.name}: {v.decision} -- allocate {v.allocation:.1%} "
            f"(posterior {v.post_mean_bps:+.3f} +/- {v.post_sd_bps:.3f} bp, t={v.t_stat:.2f})")
    return "\n".join([head, f"  power: {v.power_note}", *(f"  - {n}" for n in v.notes)])
