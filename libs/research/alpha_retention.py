"""OPERATIONAL ALPHA RETENTION — the edge that was real, was validated, and never arrived.

THE GAP BETWEEN TWO NUMBERS NOBODY HAS EVER PUT SIDE BY SIDE::

    what the strategy WOULD have earned running exactly as validated
    what it ACTUALLY earned

The ratio is ALPHA_RETENTION_RATIO, and everything between the two numbers was lost to operations
rather than to the market. A stale feed, a scheduler that skipped, a provider that timed out, an
order that did not fill, a process that stopped three weeks ago -- each is a silent tax on an edge
that was correct. **None of them produces a loss on any P&L statement.** They produce a smaller
gain, which is indistinguishable from the edge simply being weaker than believed, and the desk's
natural response to a weaker-looking edge is to doubt the research rather than the plumbing.

**THIS IS WHY INFRASTRUCTURE WORK CANNOT BE PRIORITISED BY FEEL.** Fixing a stalled recorder and
building a new alpha compete for the same day, and only one of them has ever had a number attached.
`recoverable_ratio` gives infrastructure its number: expected recovered edge per unit of cost,
directly comparable with everything else in the work queue. A defect that costs 40bp/day and takes
an hour outranks a research idea worth 5bp/day, and until this module existed there was no
arithmetic that could say so.

**THE COUNTERFACTUAL IS THE HARD PART AND IS TREATED AS SUCH.** "What it would have earned" is an
estimate, and an unfalsifiable one if built carelessly. So the only counterfactual admitted here is
the strategy's OWN validated expectation over the period in question -- the number the gauntlet
already produced and the desk already staked a promotion on. Nothing is inferred from what the
market did afterwards, because that would let every quiet week look like an outage.

Measures and ranks. Fixes nothing, schedules nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "LOSS_CAUSES",
    "MIN_DAYS_FOR_A_RATIO",
    "LossEvent",
    "RetentionRecord",
    "alpha_retention_ratio",
    "decompose",
    "recoverable_ratio",
    "summarise",
]

#: Every way validated edge is lost between the model and the money, from §45. Closed on purpose:
#: an unlisted cause is either a missing entry that must be added deliberately, or it is not an
#: operational loss at all -- it is the edge being wrong, which is a research finding and belongs
#: in the kill audit rather than here.
LOSS_CAUSES: tuple[str, ...] = (
    "STALE_DATA",
    "PROCESS_STALL",
    "SCHEDULER_MISS",
    "PROVIDER_OUTAGE",
    "MODEL_ERROR",
    "DELAYED_SIGNAL",
    "EXECUTION_FAILURE",
    "MISSED_FILL",
    "SLIPPAGE_EXCESS",
    "VENUE_OUTAGE",
    "ALLOCATION_FAILURE",
    "STRATEGY_MUTATION",
    "RISK_SYSTEM_ISSUE",
)

#: Below this many days a retention ratio describes an incident, not an operation.
MIN_DAYS_FOR_A_RATIO: float = 14.0


@dataclass(frozen=True)
class LossEvent:
    """One operational incident, with the edge it cost and what fixing it would take."""

    cause: str
    #: Basis points of validated edge lost to this incident. Positive.
    lost_bps: float
    #: Days the condition persisted. Used only for reporting; the bps is the cost.
    duration_days: float = 0.0
    #: Whether the same cause can recur. A one-off migration is not a standing tax.
    recurring: bool = True
    #: Estimated engineering hours to remove the cause. 0 = UNMEASURED, never "free".
    fix_cost_hours: float = 0.0
    detail: str = ""

    def __post_init__(self) -> None:
        if self.cause not in LOSS_CAUSES:
            raise ValueError(
                f"unknown loss cause {self.cause!r}. The list is closed: an unlisted cause is "
                "either a missing entry to be added deliberately, or it is the EDGE being wrong "
                f"rather than an operational loss. Valid: {LOSS_CAUSES}")


@dataclass(frozen=True)
class RetentionRecord:
    """One strategy's realised contribution against its own validated expectation."""

    strategy_id: str
    #: Days the strategy has been live. Below MIN_DAYS_FOR_A_RATIO nothing is reported.
    live_days: float
    #: What the gauntlet said it would earn over this period, in bps. 0 = UNMEASURED.
    expected_bps: float = 0.0
    #: What it actually earned, net of everything, in bps. May be negative.
    realised_bps: float = 0.0
    losses: tuple[LossEvent, ...] = field(default_factory=tuple)

    @property
    def measured(self) -> bool:
        return self.live_days >= MIN_DAYS_FOR_A_RATIO and self.expected_bps > 0


def alpha_retention_ratio(r: RetentionRecord) -> tuple[float | None, str]:
    """realised / validated-expected. None when unmeasured.

    Above 1.0 is possible and is NOT good news by itself: it means the strategy out-earned its own
    validated expectation, which is either luck or a validation that understated the edge, and both
    deserve a look rather than a celebration.
    """
    if not r.measured:
        return None, (
            f"{r.strategy_id}: {r.live_days:g} live day(s)"
            + ("" if r.expected_bps > 0 else " and no validated expectation recorded")
            + f". UNMEASURED against a floor of {MIN_DAYS_FOR_A_RATIO:g} days -- a retention "
              "ratio over a shorter window describes an incident, not an operation")
    ratio = r.realised_bps / r.expected_bps
    if ratio > 1.0:
        return ratio, (
            f"{r.strategy_id}: retained {ratio:.0%} of its validated expectation -- ABOVE 100%, "
            "which is not good news on its own. Either the period was lucky or the validation "
            "understated the edge, and both are worth a look rather than a celebration")
    return ratio, (
        f"{r.strategy_id}: retained {ratio:.0%} of its validated expectation "
        f"({r.realised_bps:.1f} of {r.expected_bps:.1f}bp over {r.live_days:g} days). The "
        f"missing {1 - ratio:.0%} appears on no P&L statement -- it presents as a weaker edge, "
        "which invites doubt about the research rather than about the plumbing")


def decompose(records: list[RetentionRecord]) -> dict[str, dict[str, float]]:
    """Lost bps by cause across every record. THE TABLE THAT DECIDES INFRASTRUCTURE PRIORITY."""
    out: dict[str, dict[str, float]] = {}
    for r in records:
        for ev in r.losses:
            row = out.setdefault(ev.cause, {"lost_bps": 0.0, "events": 0.0,
                                            "recurring_bps": 0.0, "fix_cost_hours": 0.0})
            row["lost_bps"] += ev.lost_bps
            row["events"] += 1
            if ev.recurring:
                row["recurring_bps"] += ev.lost_bps
            row["fix_cost_hours"] += ev.fix_cost_hours
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["lost_bps"]))


def recoverable_ratio(cause: str, table: dict[str, dict[str, float]]) -> tuple[float | None, str]:
    """Recoverable bps per engineering hour. THE NUMBER THAT LETS INFRASTRUCTURE COMPETE.

    Only RECURRING loss counts as recoverable. A one-off incident is already spent, and crediting
    a fix with edge it can never earn back is how a plausible-looking infrastructure backlog
    outranks the research it was supposed to protect.
    """
    row = table.get(cause)
    if not row:
        return None, f"{cause}: no recorded events"
    hours = row["fix_cost_hours"]
    if hours <= 0:
        return None, (
            f"{cause}: {row['recurring_bps']:.1f}bp of RECURRING loss and no fix-cost estimate. "
            "UNMEASURED -- and an unestimated fix cannot be ranked against research, which in "
            "practice means it never gets scheduled")
    return row["recurring_bps"] / hours, (
        f"{cause}: {row['recurring_bps']:.1f}bp recurring / {hours:.1f}h = "
        f"{row['recurring_bps'] / hours:.2f} bp per engineering hour. Directly comparable with "
        "any research item carrying the same units, which is the only way infrastructure work "
        "ever wins a day it deserves")


def summarise(records: list[RetentionRecord]) -> dict[str, object]:
    """Report shape for the wealth report's operational section."""
    if not records:
        return {"strategies": 0, "headline": (
            "no retention records -- ALPHA_RETENTION_RATIO is UNMEASURED, so every shortfall "
            "against a validated expectation currently reads as the research having been wrong")}
    rows = []
    for r in records:
        ratio, why = alpha_retention_ratio(r)
        rows.append({
            "strategy_id": r.strategy_id,
            "ALPHA_RETENTION_RATIO": None if ratio is None else round(ratio, 4),
            "why": why,
            "live_days": r.live_days,
            "expected_bps": r.expected_bps,
            "realised_bps": r.realised_bps,
            "loss_events": len(r.losses),
        })
    rows.sort(key=lambda d: (d["ALPHA_RETENTION_RATIO"] is None,
                             float(str(d["ALPHA_RETENTION_RATIO"] or 0.0))))
    table = decompose(records)
    ranked = []
    for cause in table:
        rr, rwhy = recoverable_ratio(cause, table)
        ranked.append({"cause": cause, "lost_bps": round(table[cause]["lost_bps"], 2),
                       "recurring_bps": round(table[cause]["recurring_bps"], 2),
                       "events": int(table[cause]["events"]),
                       "RECOVERABLE_BPS_PER_HOUR": None if rr is None else round(rr, 3),
                       "why": rwhy})
    ranked.sort(key=lambda d: -(float(str(d["RECOVERABLE_BPS_PER_HOUR"]))
                                if d["RECOVERABLE_BPS_PER_HOUR"] is not None else -1.0))
    measured = [r for r in rows if r["ALPHA_RETENTION_RATIO"] is not None]
    total_lost = sum(float(str(c["lost_bps"])) for c in ranked)
    return {
        "strategies": len(records),
        "rows": rows,
        "loss_by_cause": ranked,
        "total_lost_bps": round(total_lost, 2),
        "worst_retention": measured[0]["strategy_id"] if measured else None,
        "headline": (
            f"{len(measured)} strategy(ies) measurable; worst retains "
            f"{float(str(measured[0]['ALPHA_RETENTION_RATIO'])):.0%} of its validated "
            f"expectation. {total_lost:.0f}bp lost to operations across "
            f"{len(ranked)} cause(s), led by {ranked[0]['cause'] if ranked else 'nothing'}"
            if measured else
            f"0 of {len(records)} strategies have both a validated expectation and "
            f"{MIN_DAYS_FOR_A_RATIO:g}+ live days, so operational alpha loss is UNMEASURED"),
        "note": ("The counterfactual is the strategy's OWN validated expectation, never what the "
                 "market did afterwards -- inferring the counterfactual from subsequent returns "
                 "would let every quiet week look like an outage. Only RECURRING loss is "
                 "recoverable: a one-off incident is already spent, and crediting a fix with edge "
                 "it can never earn back is how an infrastructure backlog outranks the research "
                 "it exists to protect."),
    }
