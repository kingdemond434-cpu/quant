"""SIGNAL CADENCE vs ALPHA HALF-LIFE — a scheduler slower than the edge it is watching.

A DIFFERENT QUESTION FROM `cadence_roi`, and the two are easy to confuse. `cadence_roi` asks
whether a job PRODUCES anything per fire -- a yield question about work already done. This asks
whether the job can still be in time: whether the interval between observations is short relative
to how fast the opportunity decays. A job can be productive on every fire and still be losing most
of the edge, because it only ever sees what survived until it looked.

THE LOSS IS INVISIBLE BY CONSTRUCTION, which is why it needs a number rather than a habit. A
scheduler that runs hourly against a signal with a 20-minute half-life does not error, does not
log, and reports healthy: it simply never observes the opportunities that opened and closed
between fires. Every metric the desk keeps is computed over what was observed, so the missed
fraction never appears in any of them.

    surviving fraction of edge at observation = 2 ** (-interval / half_life)

    interval = 1/4 half-life  ->  ~84% of the edge still there
    interval = 1 half-life    ->  ~50%
    interval = 4 half-lives   ->  ~6%, and the job still reports success on what it caught

**CADENCE IS DERIVED, NOT CHOSEN.** A scheduler interval typed into a crontab is a number somebody
picked once, and it will outlive every assumption behind it. The strategy declares its information
horizon; the required cadence follows from it, and a configuration where the interval materially
exceeds the half-life is REFUSED rather than noted.

**FASTER IS NOT FREE AND THIS MODULE DOES NOT PRETEND IT IS.** Polling faster costs rate limit,
compute and contention with the recorders -- the one irreplaceable process on the box. So the
recommendation is the cheapest MECHANISM that meets the horizon, not the fastest one available:
periodic where periodic suffices, event-driven where it does not, streaming only where the horizon
is shorter than any poll could serve.

Measures and reports. Schedules nothing, changes no crontab.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MECHANISMS",
    "StrategyCadence",
    "alignment",
    "cadence_regret",
    "required_interval_minutes",
    "summarise",
]

#: Acquisition mechanisms, cheapest first. The recommendation is the cheapest one that MEETS the
#: horizon: faster polling is not free -- it costs rate limit, compute, and contention with the
#: recorders, which write the one asset that cannot be re-acquired at any price.
MECHANISMS: tuple[tuple[float, str], ...] = (
    (1440.0, "daily periodic"),
    (60.0, "hourly periodic"),
    (5.0, "high-frequency polling"),
    (1.0, "sub-minute polling"),
    (0.0, "websocket / event-driven stream"),
)

#: Fraction of edge that must survive to observation before a cadence is considered aligned. 0.75
#: rather than 0.95: demanding near-perfect capture would push every strategy to streaming and
#: spend the box's capacity on horizons that do not need it.
MIN_SURVIVING_FRACTION: float = 0.75


@dataclass(frozen=True)
class StrategyCadence:
    """One strategy's information horizon against the cadence it is actually run at."""

    strategy: str
    #: Minutes over which half the edge is gone. 0 = UNMEASURED, never "instant".
    half_life_minutes: float
    #: The interval it is scheduled at today.
    interval_minutes: float
    #: Expected edge per captured opportunity, for costing the regret. 0 = unmeasured.
    edge_bps: float = 0.0
    #: Opportunities per day the strategy would see with a perfect observer.
    opportunities_per_day: float = 0.0
    #: A horizon that genuinely cannot be shortened -- a daily bar, a funding settlement.
    hard_floor_reason: str = ""

    @property
    def measured(self) -> bool:
        return self.half_life_minutes > 0 and self.interval_minutes > 0

    @property
    def surviving_fraction(self) -> float | None:
        """Share of the edge still present when the scheduler next looks. None when unmeasured."""
        if not self.measured:
            return None
        return float(2.0 ** (-self.interval_minutes / self.half_life_minutes))


def required_interval_minutes(half_life_minutes: float,
                              *, surviving: float = MIN_SURVIVING_FRACTION) -> float | None:
    """Longest interval that still observes `surviving` of the edge. None when unmeasurable.

    Inverts the decay: interval = -half_life * log2(surviving). Returned rather than compared, so
    a caller can report the gap between what a strategy needs and what it is given instead of only
    a pass/fail.
    """
    if half_life_minutes <= 0 or not 0.0 < surviving < 1.0:
        return None
    return -half_life_minutes * math.log2(surviving)


def recommended_mechanism(interval_minutes: float) -> str:
    """The CHEAPEST acquisition mechanism that serves this interval."""
    for threshold, name in MECHANISMS:
        if interval_minutes >= threshold:
            return name
    return MECHANISMS[-1][1]


def alignment(c: StrategyCadence) -> tuple[str, str]:
    """(verdict, why). ALIGNED | TOO_SLOW | FLOORED | UNMEASURED.

    HARD FLOORS ARE CHECKED FIRST. A strategy watching a daily bar cannot be observed faster than
    the bar exists, so calling it TOO_SLOW would generate work nobody can do -- and a fence that
    emits impossible work gets muted, taking its real findings with it.
    """
    if c.hard_floor_reason:
        return "FLOORED", (
            f"the horizon is bounded by {c.hard_floor_reason}, so the interval cannot be "
            "shortened. If capture is still poor the lever is the MECHANISM or the strategy's "
            "own horizon, never the schedule")
    if not c.measured:
        return "UNMEASURED", (
            "no half-life recorded, so the cadence cannot be justified OR refused. A schedule "
            "nobody derived is a number somebody picked once, and it will outlive every "
            "assumption behind it -- measure the decay")
    surv = c.surviving_fraction
    need = required_interval_minutes(c.half_life_minutes)
    assert surv is not None and need is not None
    if surv >= MIN_SURVIVING_FRACTION:
        return "ALIGNED", (
            f"{surv:.0%} of the edge survives to observation at {c.interval_minutes:g}min against "
            f"a {c.half_life_minutes:g}min half-life")
    return "TOO_SLOW", (
        f"only {surv:.0%} of the edge survives to observation: {c.interval_minutes:g}min interval "
        f"against a {c.half_life_minutes:g}min half-life. Needs <= {need:.1f}min "
        f"({recommended_mechanism(need)}). The loss is INVISIBLE -- the job does not error, and "
        "every metric the desk keeps is computed over what it managed to observe")


def cadence_regret(c: StrategyCadence, *, days: float = 1.0) -> tuple[float, str]:
    """Bps of edge lost to the schedule alone over `days`. THE NUMBER NOBODY CHARGES.

    Deliberately conservative: it prices only the DECAY on opportunities the strategy still sees,
    not the ones that opened and closed entirely between fires. Those are invisible to any
    measurement taken at the fire, so counting them would require a model of what was never
    observed -- an estimate the desk cannot defend. The true regret is therefore at least this.
    """
    surv = c.surviving_fraction
    if surv is None or c.edge_bps <= 0 or c.opportunities_per_day <= 0:
        return 0.0, ("UNMEASURED -- needs a half-life, an edge and an opportunity rate. Zero here "
                     "means nothing was measured, never that nothing was lost")
    lost = c.edge_bps * (1.0 - surv) * c.opportunities_per_day * days
    return lost, (
        f"{lost:.1f} bp of edge lost to the SCHEDULE over {days:g} day(s) -- "
        f"{c.opportunities_per_day:g} opportunities/day x {c.edge_bps:g}bp x "
        f"{1 - surv:.0%} decayed before observation. A LOWER BOUND: opportunities that "
        "opened and closed entirely between fires are invisible to any measurement "
        "taken at the fire and are not counted here")


def summarise(records: list[StrategyCadence], *, days: float = 1.0) -> dict[str, object]:
    """Report shape. Leads with TOO_SLOW, ranked by the regret each one costs."""
    if not records:
        return {"strategies": 0, "headline": (
            "no cadence records -- every schedule on this desk is a number somebody picked, and "
            "whether any of them is fast enough for its edge is UNMEASURED")}
    rows = []
    for c in records:
        v, why = alignment(c)
        regret, rwhy = cadence_regret(c, days=days)
        need = required_interval_minutes(c.half_life_minutes)
        rows.append({"strategy": c.strategy, "verdict": v, "why": why,
                     "interval_minutes": c.interval_minutes,
                     "half_life_minutes": c.half_life_minutes,
                     "surviving_fraction": (None if c.surviving_fraction is None
                                            else round(c.surviving_fraction, 4)),
                     "required_interval_minutes": None if need is None else round(need, 2),
                     "recommended_mechanism": (None if need is None
                                               else recommended_mechanism(need)),
                     "cadence_regret_bps": round(regret, 2), "regret_note": rwhy})
    order = {"TOO_SLOW": 0, "UNMEASURED": 1, "FLOORED": 2, "ALIGNED": 3}
    rows.sort(key=lambda d: (order[str(d["verdict"])], -float(str(d["cadence_regret_bps"]))))
    slow = [r for r in rows if r["verdict"] == "TOO_SLOW"]
    total = sum(float(str(r["cadence_regret_bps"])) for r in rows)
    return {
        "strategies": len(records),
        "too_slow": len(slow),
        "total_cadence_regret_bps": round(total, 2),
        "headline": (
            f"{len(slow)} strategy(ies) scheduled slower than their edge decays, costing at least "
            f"{total:.1f} bp/day: {[r['strategy'] for r in slow[:3]]}" if slow else
            f"{sum(1 for r in rows if r['verdict'] == 'UNMEASURED')} of {len(rows)} cadences "
            "carry no half-life, so alignment is UNMEASURED -- a schedule nobody derived cannot "
            "be justified or refused"),
        "rows": rows,
        "note": ("This is NOT `cadence_roi`. That asks whether a job produces anything per fire; "
                 "this asks whether it can still be in time. A job can be productive on every "
                 "fire and lose most of the edge, because it only ever sees what survived until "
                 "it looked. Faster is not free: the recommendation is the CHEAPEST mechanism "
                 "that meets the horizon, since polling costs rate limit, compute and contention "
                 "with the recorders."),
    }


def render(records: list[StrategyCadence], *, days: float = 1.0) -> str:
    rep = summarise(records, days=days)
    lines = [str(rep["headline"])]
    rows = rep.get("rows")
    for r in rows if isinstance(rows, list) else []:
        lines.append(f"  [{r['verdict']}] {r['strategy']}: {r['why']}")
    return "\n".join(lines)
