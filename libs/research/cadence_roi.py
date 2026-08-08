"""CADENCE vs ROI — is each schedule running at the frequency its yield justifies?

THE GAP THIS CLOSES. The desk runs ~20 cron lines and 10 systemd timers, and every cadence on it
was CHOSEN rather than measured. "Daily" and "every 4 hours" are numbers somebody picked, and the
manifest records what they picked without recording why. L1.28c says every schedule hunts its own
ceiling; nothing has ever checked whether one is at it.

TWO FAILURES, OPPOSITE SIGNS, AND ONLY ONE OF THEM IS EVER NOTICED:

    UNDER-RUN   the job yields something almost every fire -> the interval is leaving value
                on the table, and the loss is invisible because nothing errors
    OVER-RUN    the job yields almost nothing per fire but keeps costing -> compute and triage
                spent producing nothing new, which crowds out work that would produce something

The desk is structurally blind to the first and mildly allergic to the second, because a job that
runs too often at least LOOKS busy. Idle cadence headroom is the same class of loss as idle capital
(L1.28a): it appears in no P&L and raises no error.

THE MEASUREMENT IS YIELD PER FIRE, not yield per day. A job fired 24 times producing 2 findings and
one fired twice producing the same 2 findings have identical daily output and opposite verdicts: the
first is running 12x too often, the second is possibly under-run. Per-fire is the only ratio that
separates them.

**FASTER IS THE DEFAULT ONLY WHERE YIELD SUPPORTS IT, AND SLOWER IS NEVER RECOMMENDED FOR COMFORT.**
A recommendation to slow a job must cite a measured per-fire yield below the floor. Absent that
measurement, the verdict is UNMEASURED and the cadence stands: this module may not become the route
by which the desk talks itself into doing less (L1.28).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = [
    "MIN_FIRES_FOR_VERDICT",
    "OVER_RUN_YIELD",
    "UNDER_RUN_YIELD",
    "CadenceRecord",
    "assess",
    "render",
    "summarise",
]

#: Fires below which a per-fire yield is noise. Eight because a daily job needs a week before its
#: hit rate means anything, and a verdict on three fires would re-time the desk on a coin flip.
MIN_FIRES_FOR_VERDICT: int = 8

#: Per-fire yield at or above which a job is producing something nearly every time it runs -- so
#: the interval is probably the binding constraint and should TIGHTEN.
UNDER_RUN_YIELD: float = 0.75

#: Per-fire yield below which a job is mostly producing nothing. The only condition under which
#: slowing a cadence may be recommended, and it must be measured, never assumed.
OVER_RUN_YIELD: float = 0.10


@dataclass(frozen=True)
class CadenceRecord:
    """One scheduled job over an observation window."""

    job: str
    interval_minutes: float
    fires: int = 0
    #: Fires that produced something the desk acted on or recorded as a finding.
    productive_fires: int = 0
    findings: int = 0
    #: Cost per fire in whatever unit the caller uses (cpu-minutes, credit, triage items).
    cost_per_fire: float = 0.0
    #: A cadence that CANNOT tighten -- an external rate limit, a settlement clock, a daily bar.
    hard_floor_reason: str = ""

    @property
    def measured(self) -> bool:
        return self.fires >= MIN_FIRES_FOR_VERDICT

    @property
    def yield_per_fire(self) -> float | None:
        """None rather than 0.0 when unmeasured -- 0.0 reads as 'measured and barren'."""
        if not self.measured:
            return None
        return self.productive_fires / self.fires

    @property
    def findings_per_fire(self) -> float | None:
        if not self.measured:
            return None
        return self.findings / self.fires


def assess(r: CadenceRecord) -> tuple[str, str]:
    """(verdict, why). TIGHTEN | HOLD | LOOSEN | UNMEASURED | FLOORED.

    ORDER OF CHECKS MATTERS. The hard floor is tested FIRST, because a job that cannot run more
    often is not under-run however high its yield -- recommending a tighter interval there produces
    a queue of impossible work, which is how a real fence gets ignored.
    """
    if r.hard_floor_reason:
        y = r.yield_per_fire
        return "FLOORED", (
            f"cadence is bounded by {r.hard_floor_reason} -- it cannot tighten, so a high yield "
            f"({'unmeasured' if y is None else f'{y:.0%}'}) is not a finding about the schedule. "
            "If the yield is high, the lever is PARALLELISM or scope per fire, not frequency")
    y = r.yield_per_fire
    if y is None:
        return "UNMEASURED", (
            f"{r.fires} fire(s) is below the {MIN_FIRES_FOR_VERDICT}-fire floor, so the hit rate "
            "is noise. THE CADENCE STANDS: an unmeasured schedule is never slowed, because that "
            "would let absence of evidence buy a reduction (L1.28)")
    if y >= UNDER_RUN_YIELD:
        return "TIGHTEN", (
            f"productive on {y:.0%} of fires -- the job finds something nearly every time it runs, "
            "so the INTERVAL is the binding constraint and the value left on the table is "
            "invisible because nothing errors. Halve the interval and re-measure")
    if y <= OVER_RUN_YIELD:
        return "LOOSEN", (
            f"productive on only {y:.0%} of fires at {r.cost_per_fire:g} per fire -- compute and "
            "triage are being spent to produce nothing new, which crowds out work that would. "
            "This is the ONLY condition under which a slower cadence is legitimate, and it is "
            "measured rather than assumed")
    return "HOLD", (
        f"productive on {y:.0%} of fires -- between the {OVER_RUN_YIELD:.0%} and "
        f"{UNDER_RUN_YIELD:.0%} bands, which is what a well-tuned cadence looks like")


def summarise(records: list[CadenceRecord]) -> dict[str, object]:
    """Report shape. THE HEADLINE LEADS WITH UNDER-RUN JOBS, because those are the invisible loss.

    An over-run job is at least visible in a cost report. An under-run one produces no signal at
    all: it simply finds less than it could have, forever, and nothing anywhere records the
    difference.
    """
    if not records:
        return {"jobs": 0, "headline": (
            "no cadence records -- every schedule on this desk was CHOSEN rather than measured, "
            "and that is the finding")}
    rows = []
    for r in records:
        v, why = assess(r)
        rows.append({"job": r.job, "interval_minutes": r.interval_minutes, "verdict": v,
                     "fires": r.fires,
                     "yield_per_fire": None if r.yield_per_fire is None
                     else round(r.yield_per_fire, 4),
                     "findings_per_fire": None if r.findings_per_fire is None
                     else round(r.findings_per_fire, 4),
                     "why": why})
    order = {"TIGHTEN": 0, "UNMEASURED": 1, "LOOSEN": 2, "FLOORED": 3, "HOLD": 4}
    rows.sort(key=lambda d: (order[str(d["verdict"])], str(d["job"])))
    tighten = [r["job"] for r in rows if r["verdict"] == "TIGHTEN"]
    loosen = [r["job"] for r in rows if r["verdict"] == "LOOSEN"]
    unmeasured = [r["job"] for r in rows if r["verdict"] == "UNMEASURED"]
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "jobs": len(records), "tally": {
            "TIGHTEN": len(tighten), "LOOSEN": len(loosen), "UNMEASURED": len(unmeasured),
            "HOLD": sum(1 for r in rows if r["verdict"] == "HOLD"),
            "FLOORED": sum(1 for r in rows if r["verdict"] == "FLOORED")},
        "headline": (
            f"{len(tighten)} job(s) UNDER-RUN and leaving value on the table: {tighten[:5]}"
            if tighten else
            f"{len(unmeasured)} of {len(records)} cadences unmeasured -- no schedule may be slowed "
            "on an unmeasured yield" if unmeasured else
            f"{len(loosen)} job(s) over-run; the rest are in band"),
        "rows": rows,
        "note": ("yield per FIRE, never per day: a job fired 24 times for 2 findings and one fired "
                 "twice for the same 2 have identical daily output and opposite verdicts. Slowing "
                 "a cadence requires a measured per-fire yield below the floor -- this module may "
                 "not become the route by which the desk does less (L1.28c)"),
    }


def render(records: list[CadenceRecord]) -> str:
    rep = summarise(records)
    lines = [str(rep["headline"])]
    rows = rep.get("rows")
    for row in rows if isinstance(rows, list) else []:
        lines.append(f"  [{row['verdict']}] {row['job']} every {row['interval_minutes']:g}min")
        lines.append(f"      {row['why']}")
    return "\n".join(lines)
