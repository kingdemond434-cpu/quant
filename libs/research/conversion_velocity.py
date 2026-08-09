"""ECONOMIC CONVERSION VELOCITY — the desk's measured advantage is science; its measured deficit
is the clock between knowing something and owning a position in it.

THE ARGUMENT, WHICH IS UNCOMFORTABLE AND CORRECT. The operator this desk is benchmarked against
does not have better statistics, better multiplicity control or better cost modelling. He acts.
The gap between "we have evidence" and "we have exposure" is where this desk gives back its entire
methodological edge, and the gap has never been measured, which is why nobody has ever had to
defend its size.

So it becomes four numbers, each a LATENCY, each measured in days:

    research  -> survivor            how long discovery takes
    survivor  -> first live fill     how long conviction takes to become a position
    first fill-> meaningful capital   how long a working strategy stays a rounding error
    capital   -> realised return     how long the position takes to pay

**LATENCY IS NOT FREE AND THIS MODULE CHARGES IT.** `waiting_cost` in `evidence_clock` prices the
alpha decay of a candidate sitting in a gate. This prices the whole chain, including the two
stages that module cannot see: a survivor with no canary, and a canary that has been running at a
size too small to matter for longer than its own half-life. Both look healthy on every dashboard
the desk owns -- something IS happening to them -- and both are stranding under §66.

**BUT SPEED IS NOT THE OBJECTIVE AND THIS MODULE MUST NOT BECOME A REASON TO SKIP EVIDENCE.** The
specification is explicit: maximise conversion velocity SUBJECT TO evidence integrity. A latency
that exists because a candidate genuinely lacks independent observations is correct and is
reported as EVIDENCE_BOUND, distinct from PROCESS_BOUND -- the latency nobody chose, which is the
one worth attacking. Conflating the two would turn a throughput metric into an argument for
lowering a bar, which is the failure this desk has a law against.

Measures and ranks. Deploys nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

__all__ = [
    "STAGES",
    "STALE_STAGE_DAYS",
    "ConversionRecord",
    "bound_by",
    "economic_waiting_cost",
    "stage_latencies",
    "summarise",
    "velocity",
]

#: The chain, in order. A stage that never happened has a `None` timestamp, and the FIRST such
#: stage is where the candidate is stranded -- not the last one that succeeded.
STAGES: tuple[str, ...] = (
    "discovered", "survivor", "portfolio_admitted", "canary_requested",
    "first_fill", "meaningful_capital", "realised_return",
)

#: Days a candidate may sit at one stage before the delay is itself the finding. Not a promotion
#: rule and not a deadline -- it is the point past which "in progress" stops being informative.
STALE_STAGE_DAYS: float = 7.0


@dataclass(frozen=True)
class ConversionRecord:
    """One candidate's journey, in days since discovery. None = the stage has not happened.

    Days rather than timestamps on purpose: the arithmetic is all differences, and storing
    absolute times invites a timezone bug into a latency metric, where it would be invisible.
    """

    candidate_id: str
    #: Days since discovery at which each stage occurred. Keys from STAGES.
    stage_days: dict[str, float | None]
    #: Measured or estimated alpha half-life in days. 0 = UNMEASURED, never "long".
    half_life_days: float = 0.0
    #: Expected net bps per day this candidate would earn at meaningful size.
    expected_bps_per_day: float = 0.0
    #: Effective independent observations accumulated so far (from evidence_clock).
    effective_n: float = 0.0
    #: Effective observations this candidate OWES before it may be sized.
    required_effective_n: float = 0.0
    #: Age of the record in days, for the stall check.
    age_days: float = 0.0

    @property
    def current_stage(self) -> str:
        """The last stage reached. 'discovered' when nothing else has."""
        reached = [s for s in STAGES if self.stage_days.get(s) is not None]
        return reached[-1] if reached else "discovered"

    @property
    def next_stage(self) -> str | None:
        idx = STAGES.index(self.current_stage)
        return STAGES[idx + 1] if idx + 1 < len(STAGES) else None

    @property
    def days_at_current_stage(self) -> float | None:
        d = self.stage_days.get(self.current_stage)
        if d is None or self.age_days <= 0:
            return None
        return max(0.0, self.age_days - d)


def stage_latencies(r: ConversionRecord) -> dict[str, float | None]:
    """Days spent traversing each adjacent pair of stages. None when either end is missing."""
    out: dict[str, float | None] = {}
    for a, b in pairwise(STAGES):
        da, db = r.stage_days.get(a), r.stage_days.get(b)
        out[f"{a}->{b}"] = None if da is None or db is None else max(0.0, db - da)
    return out


def bound_by(r: ConversionRecord) -> tuple[str, str]:
    """(EVIDENCE_BOUND | PROCESS_BOUND | COMPLETE | UNMEASURED, why).

    THE DISTINCTION THIS FUNCTION EXISTS FOR. A candidate waiting because it has 12 effective
    observations against a requirement of 60 is waiting correctly, and shortening that wait would
    be lowering a bar with a stopwatch as the excuse. A candidate with 400 effective observations
    that has been sitting at `survivor` for eleven days is waiting because nobody moved it, and
    that delay is pure economic loss with no offsetting evidence gained.
    """
    if r.current_stage == STAGES[-1]:
        return "COMPLETE", "the chain closed: this candidate produced a realised return"
    if r.required_effective_n <= 0 or r.effective_n <= 0:
        return "UNMEASURED", (
            f"{r.candidate_id}: no effective-observation counts recorded, so it cannot be said "
            "whether this candidate is waiting for evidence or waiting for attention. Those are "
            "opposite findings and defaulting to either one is the WS-005 shape")
    if r.effective_n < r.required_effective_n:
        return "EVIDENCE_BOUND", (
            f"{r.candidate_id}: {r.effective_n:.0f} of {r.required_effective_n:.0f} effective "
            f"observations. Stalled at {r.current_stage!r} CORRECTLY -- this latency buys "
            "something and shortening it would be a lowered bar wearing a stopwatch")
    days = r.days_at_current_stage
    return "PROCESS_BOUND", (
        f"{r.candidate_id}: {r.effective_n:.0f} effective observations against a requirement of "
        f"{r.required_effective_n:.0f} -- the evidence is IN. It has been at {r.current_stage!r} "
        f"for {'unmeasured' if days is None else f'{days:.1f}'} day(s) waiting for "
        f"{r.next_stage!r}. This delay buys nothing and costs alpha decay every day it continues")


def economic_waiting_cost(r: ConversionRecord) -> tuple[float, str]:
    """Bps of expected return already lost to the delay at the CURRENT stage.

    Prices two of the three components the specification names -- decay of the edge, and the P&L
    not earned during the wait. The third, information lost by not being live, is real and is
    deliberately NOT estimated: it would require modelling what the live tape would have taught,
    and a number invented for it would dominate the two that are measurable. The total is
    therefore a LOWER bound and says so.
    """
    days = r.days_at_current_stage
    if days is None or r.half_life_days <= 0 or r.expected_bps_per_day <= 0:
        return 0.0, ("UNMEASURED -- needs a half-life, an expected daily edge and a stage age. "
                     "Zero here means nothing was priced, never that nothing was lost")
    decayed = 1.0 - 0.5 ** (days / r.half_life_days)
    forgone = r.expected_bps_per_day * days
    lost_edge = r.expected_bps_per_day * decayed * max(0.0, r.half_life_days)
    total = forgone + lost_edge
    return total, (
        f"{total:.1f}bp lower bound: {forgone:.1f}bp of P&L not earned over {days:.1f} day(s) "
        f"plus {lost_edge:.1f}bp of edge decayed ({decayed:.0%} of a "
        f"{r.half_life_days:g}-day half-life). Excludes the live information not acquired, which "
        "is real and is not estimated here because an invented figure for it would dominate the "
        "two that are measured")


def velocity(records: list[ConversionRecord]) -> dict[str, float | None]:
    """Median days for each headline transition. Medians, not means: one 200-day straggler would
    otherwise define the desk's throughput."""
    pairs = {
        "research_to_survivor": ("discovered", "survivor"),
        "survivor_to_first_fill": ("survivor", "first_fill"),
        "first_fill_to_meaningful_capital": ("first_fill", "meaningful_capital"),
        "capital_to_realised_return": ("meaningful_capital", "realised_return"),
    }
    out: dict[str, float | None] = {}
    for label, (a, b) in pairs.items():
        vals = []
        for r in records:
            da, db = r.stage_days.get(a), r.stage_days.get(b)
            if da is not None and db is not None:
                vals.append(max(0.0, db - da))
        if not vals:
            out[label] = None
            continue
        vals.sort()
        mid = len(vals) // 2
        out[label] = vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0
    return out


def summarise(records: list[ConversionRecord]) -> dict[str, object]:
    """Report shape for `data/conversion_velocity.json`.

    Leads with PROCESS_BOUND, ranked by the cost each delay is running up.
    """
    if not records:
        return {"candidates": 0, "headline": (
            "no conversion records -- ECONOMIC_CONVERSION_VELOCITY is UNMEASURED. The desk "
            "cannot currently say how long anything takes to become a position, which means the "
            "one gap the benchmark spec names as decisive is the one gap nobody is watching")}
    rows = []
    for r in records:
        b, why = bound_by(r)
        cost, cwhy = economic_waiting_cost(r)
        rows.append({
            "candidate_id": r.candidate_id,
            "current_stage": r.current_stage,
            "next_stage": r.next_stage,
            "days_at_current_stage": (None if r.days_at_current_stage is None
                                      else round(r.days_at_current_stage, 2)),
            "bound_by": b, "why": why,
            "ECONOMIC_WAITING_COST_bps": round(cost, 2), "cost_note": cwhy,
            "stage_latencies": stage_latencies(r),
            "stale": (r.days_at_current_stage or 0.0) > STALE_STAGE_DAYS and b == "PROCESS_BOUND",
        })
    order = {"PROCESS_BOUND": 0, "UNMEASURED": 1, "EVIDENCE_BOUND": 2, "COMPLETE": 3}
    rows.sort(key=lambda d: (order[str(d["bound_by"])],
                             -float(str(d["ECONOMIC_WAITING_COST_bps"]))))
    process = [r for r in rows if r["bound_by"] == "PROCESS_BOUND"]
    total_cost = sum(float(str(r["ECONOMIC_WAITING_COST_bps"])) for r in process)
    return {
        "candidates": len(records),
        "ECONOMIC_CONVERSION_VELOCITY_days": velocity(records),
        "process_bound": len(process),
        "evidence_bound": sum(1 for r in rows if r["bound_by"] == "EVIDENCE_BOUND"),
        "total_process_waiting_cost_bps": round(total_cost, 2),
        "rows": rows,
        "headline": (
            f"{len(process)} candidate(s) are PROCESS-bound -- the evidence is in and nothing is "
            f"moving them -- costing at least {total_cost:.0f}bp: "
            f"{[r['candidate_id'] for r in process[:3]]}" if process else
            f"0 candidates process-bound; {sum(1 for r in rows if r['bound_by'] == 'UNMEASURED')} "
            "carry no effective-observation counts, so whether they are waiting for evidence or "
            "for attention is UNMEASURED"),
        "note": ("EVIDENCE_BOUND latency is correct and is not a target for reduction. Only "
                 "PROCESS_BOUND latency is waste. Conflating them would turn this metric into an "
                 "argument for lowering a validation bar, which is the one use it must never "
                 "have. The waiting cost excludes information not acquired by being live and is "
                 "therefore a lower bound."),
    }
