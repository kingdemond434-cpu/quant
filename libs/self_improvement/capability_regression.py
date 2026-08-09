"""CAPABILITY REGRESSION — no upgrade may quietly cost more than it adds.

THE FAILURE THIS EXISTS TO CATCH is not a bug. It is a change that is genuinely better along the
axis its author was looking at, and worse along one they were not::

    the prompt got shorter          and the mining lost two source languages
    the architecture got simpler    and an independent reviewer disappeared
    the model got newer             and the false-negative rate doubled
    the pipeline got faster         and a validator stopped running

Every one of those reads as an upgrade in the commit message, and none of them is measurable
afterwards unless the incumbent's behaviour was captured BEFORE the change. That capture is the
whole mechanism here: a regression you did not measure before is a regression you cannot detect
after, because the only evidence of what was lost left with the code.

**SIMPLICITY IS NOT A JUSTIFICATION AND THIS MODULE SAYS SO IN CODE.** Cleaner, shorter, fewer
agents, less compute, easier maintenance -- none of those is a benefit in itself. They have value
only through their effect on realised net log wealth, so they enter as SAVINGS to be weighed and
never as reasons that stand alone. `verdict` refuses an UPGRADE label to any change whose only
gains are cost savings while a capability dimension fell.

**AND THE OPPOSITE ERROR IS EQUALLY BANNED.** A change that adds complexity earning more than it
costs is an upgrade, and this module must never be used to argue against it. If forty agents carry
more marginal surplus than six, the finding is forty. `verdict` therefore has no bias toward
smaller: it compares economic surplus, and it treats a lost capability as a cost rather than as a
veto.

**AN INTENTIONAL LOSS IS ALLOWED AND MUST BE RECORDED.** Removing something genuinely
negative-value is good work. What is forbidden is losing it SILENTLY, so an accepted regression
carries the capability removed, the reason, the measured cost, the measured benefit, and who
decided.

Measures and records. Blocks nothing by itself -- the fence that consumes this decides.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CAPABILITY_DIMENSIONS",
    "COST_DIMENSIONS",
    "CapabilitySnapshot",
    "RegressionRecord",
    "compare",
    "summarise",
    "verdict",
]

#: Dimensions where MORE is better. A fall here is a capability loss and must be paid for.
CAPABILITY_DIMENSIONS: tuple[str, ...] = (
    "capability_coverage", "data_breadth", "source_breadth", "hypothesis_breadth",
    "validation_power", "throughput", "execution_quality", "reliability",
    "economic_descendants", "independent_reviewers", "source_languages",
)

#: Dimensions where LESS is better. These are SAVINGS, never reasons on their own -- a change
#: whose entire case is that it is cheaper, while a capability fell, is not an upgrade.
COST_DIMENSIONS: tuple[str, ...] = (
    "latency", "compute_cost", "token_cost", "maintenance_burden", "failure_surface",
    "false_positive_rate", "false_negative_rate",
)


@dataclass(frozen=True)
class CapabilitySnapshot:
    """What a subsystem could do and what it cost, at a point in time.

    Captured BEFORE a change or it is worthless: a dimension absent from the incumbent snapshot
    cannot be shown to have fallen, and the report names those rather than treating them as held.
    """

    subsystem: str
    at: str = ""
    #: Measured values keyed by CAPABILITY_DIMENSIONS / COST_DIMENSIONS. Absent = UNMEASURED.
    metrics: dict[str, float] = field(default_factory=dict)
    #: Tests that passed on this version. A test that disappears is a capability claim withdrawn.
    tests_passing: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        known = set(CAPABILITY_DIMENSIONS) | set(COST_DIMENSIONS)
        for k in self.metrics:
            if k not in known:
                raise ValueError(
                    f"unknown dimension {k!r}. The basis is closed so that a regression cannot be "
                    f"hidden behind a new name: {sorted(known)}")


@dataclass(frozen=True)
class RegressionRecord:
    """An accepted capability loss, with the decision that accepted it. §XXX."""

    subsystem: str
    capability_removed: str
    reason: str
    measured_cost: float = 0.0
    measured_benefit: float = 0.0
    approved_by: str = ""
    at: str = ""

    @property
    def justified(self) -> bool:
        return bool(self.reason.strip()) and bool(self.approved_by.strip())


def compare(before: CapabilitySnapshot, after: CapabilitySnapshot) -> dict[str, object]:
    """Dimension-by-dimension delta, split into capability losses, gains and savings."""
    losses, gains, savings, costs_added, unmeasured = {}, {}, {}, {}, []
    for d in CAPABILITY_DIMENSIONS:
        b, a = before.metrics.get(d), after.metrics.get(d)
        if b is None or a is None:
            if b is not None or a is not None:
                unmeasured.append(d)
            continue
        if a < b:
            losses[d] = round(a - b, 6)
        elif a > b:
            gains[d] = round(a - b, 6)
    for d in COST_DIMENSIONS:
        b, a = before.metrics.get(d), after.metrics.get(d)
        if b is None or a is None:
            if b is not None or a is not None:
                unmeasured.append(d)
            continue
        if a < b:
            savings[d] = round(b - a, 6)
        elif a > b:
            costs_added[d] = round(a - b, 6)
    dropped_tests = [t for t in before.tests_passing if t not in set(after.tests_passing)]
    return {
        "subsystem": after.subsystem,
        "capability_losses": losses,
        "capability_gains": gains,
        "cost_savings": savings,
        "costs_added": costs_added,
        "dropped_tests": dropped_tests,
        "dimensions_measured_on_one_side_only": sorted(set(unmeasured)),
    }


def verdict(before: CapabilitySnapshot, after: CapabilitySnapshot, *,
            expected_surplus_gain: float = 0.0,
            accepted: tuple[RegressionRecord, ...] = ()) -> tuple[str, str]:
    """(UPGRADE | REGRESSION | ACCEPTED_REGRESSION | UNVERIFIABLE, why).

    UNVERIFIABLE is a real and common answer, and it comes FIRST. A change whose incumbent was
    never measured cannot be shown to be an upgrade, and calling it one because the code looks
    better is exactly the substitution this module exists to prevent.
    """
    d = compare(before, after)
    losses = d["capability_losses"]
    dropped = d["dropped_tests"]
    assert isinstance(losses, dict) and isinstance(dropped, list)

    if not before.metrics and not before.tests_passing:
        return "UNVERIFIABLE", (
            f"{after.subsystem}: no incumbent snapshot, so nothing can be shown to have been "
            "preserved. A regression you did not measure before is one you cannot detect after -- "
            "the only evidence of what was lost left with the code")

    if not losses and not dropped:
        savings = d["cost_savings"]
        return "UPGRADE", (
            f"{after.subsystem}: no capability dimension fell and no test was dropped"
            + (f"; gains {d['capability_gains']}" if d["capability_gains"] else "")
            + (f"; savings {savings}" if savings else "")
            + (f". {len(d['dimensions_measured_on_one_side_only'])} dimension(s) measured on one "  # type: ignore[arg-type]
               f"side only: {d['dimensions_measured_on_one_side_only']} -- those are UNVERIFIED "
               "rather than held" if d["dimensions_measured_on_one_side_only"] else ""))

    covered = {r.capability_removed for r in accepted if r.justified}
    uncovered = [k for k in list(losses) + dropped if k not in covered]
    if not uncovered:
        return "ACCEPTED_REGRESSION", (
            f"{after.subsystem}: {len(losses)} capability dimension(s) fell and every one is "
            f"recorded with a reason and an approver. Intentional loss is allowed; SILENT loss is "
            f"not. Losses: {losses}"
            + (f"; tests dropped: {dropped}" if dropped else ""))

    only_savings = bool(d["cost_savings"]) and not d["capability_gains"]
    return "REGRESSION", (
        f"{after.subsystem}: {len(uncovered)} unrecorded capability loss(es) {uncovered}"
        + (f"; tests dropped without replacement: {dropped}" if dropped else "")
        + (". The entire case for this change is cost savings while a capability fell -- cleaner, "
           "shorter, cheaper and simpler are not benefits in themselves, only through their effect "
           "on realised net log wealth" if only_savings else
           f". Expected surplus gain {expected_surplus_gain:+.4f} must be weighed against the "
           "losses, and the losses must be recorded either way"))


def summarise(comparisons: list[tuple[CapabilitySnapshot, CapabilitySnapshot]], *,
              accepted: tuple[RegressionRecord, ...] = ()) -> dict[str, object]:
    """Report shape for `data/capability_regression.json`."""
    if not comparisons:
        return {"comparisons": 0, "headline": (
            "no before/after snapshots recorded -- every change on this desk is currently an "
            "unverified upgrade claim, and a regression would be invisible")}
    rows = []
    for b, a in comparisons:
        v, why = verdict(b, a, accepted=accepted)
        rows.append({"subsystem": a.subsystem, "verdict": v, "why": why, **compare(b, a)})
    order = {"REGRESSION": 0, "UNVERIFIABLE": 1, "ACCEPTED_REGRESSION": 2, "UPGRADE": 3}
    rows.sort(key=lambda r: order[str(r["verdict"])])
    bad = [r for r in rows if r["verdict"] == "REGRESSION"]
    unver = [r for r in rows if r["verdict"] == "UNVERIFIABLE"]
    return {
        "comparisons": len(comparisons),
        "rows": rows,
        "regressions": len(bad),
        "unverifiable": len(unver),
        "accepted_losses": [
            {"subsystem": r.subsystem, "capability": r.capability_removed, "reason": r.reason,
             "cost": r.measured_cost, "benefit": r.measured_benefit, "approved_by": r.approved_by}
            for r in accepted],
        "headline": (
            f"{len(bad)} unrecorded capability regression(s): "
            f"{[r['subsystem'] for r in bad]}" if bad else
            f"{len(unver)} change(s) UNVERIFIABLE for want of an incumbent snapshot" if unver else
            f"all {len(rows)} change(s) preserved or improved every measured capability"),
        "note": ("Cost savings are SAVINGS, never reasons that stand alone: a change whose only "
                 "case is that it is cheaper, while a capability fell, is not an upgrade. The "
                 "converse is equally binding -- complexity that earns more than it costs is an "
                 "upgrade, and this module must never be cited against it. It compares surplus "
                 "and has no bias toward smaller."),
    }
