"""THE REJECTED-TRADE LEDGER — the desk's decisions are currently only legible where they said yes.

WHAT IS MISSING WITHOUT THIS. Every artifact on this desk records what was DONE: fills, positions,
P&L, survivors. Nothing records what was declined. That asymmetry has three consequences and all
three cost money.

    1. THE REJECTION POPULATION IS THE LARGEST DATASET THE DESK GENERATES AND IT IS DISCARDED.
       750 of 762 cells died at one gate in the last sweep. The 12 that lived have a report; the
       750 left no per-decision record at all, so "is that gate correct" was unanswerable until
       kill_audit forced the cells to be retained. The same hole exists one layer down, at every
       signal that fired and was not traded.

    2. A SYSTEMATIC REJECTION REASON IS INVISIBLE UNTIL IT IS CATASTROPHIC. If the cost model is
       15% too pessimistic, the desk does not observe a bias -- it observes fewer trades, which
       looks like a quiet market. The counterfactual outcomes attached here are what turn that
       into a measurement.

    3. THE FIRST QUESTION AFTER A BAD DAY IS ALWAYS "WHAT DID WE NOT DO", and the honest answer
       has always been that nobody knows.

**COUNTERFACTUALS ARE ATTACHED, NOT PROMOTED, AND THE DISTINCTION IS THE WHOLE SAFETY ARGUMENT.**
Knowing that a rejected signal would have made 40bp is information about the REJECTOR. It is not
evidence about the signal, because the signal was selected for the counterfactual by having been
rejected -- the population is conditioned on the very thing being tested. `promotion_is_forbidden`
exists as a named function so that any future caller reaching for "but it would have worked" hits
a wall with the reason written on it. The legitimate use is `systematic_bias`, which asks whether
a rejection REASON is wrong across its whole population, and the new-hypothesis path, which sends
the finding back through preregistration on untouched data.

Records and measures. Trades nothing, promotes nothing, and cannot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "MIN_POPULATION_FOR_BIAS",
    "OUTCOMES",
    "REJECTION_CLASSES",
    "Decision",
    "counterfactual_summary",
    "promotion_is_forbidden",
    "summarise",
    "systematic_bias",
]

#: Every terminal state a candidate opportunity can reach. EXECUTED is one of ten, which is roughly
#: the share of the decision surface it actually occupies -- nine ways to decline, one to act.
OUTCOMES: tuple[str, ...] = (
    "EXECUTED",
    "SIGNAL_REJECTED",
    "VALIDATION_REJECTED",
    "PORTFOLIO_REJECTED",
    "RISK_REJECTED",
    "COST_REJECTED",
    "CAPACITY_REJECTED",
    "EXECUTION_REJECTED",
    "VENUE_UNAVAILABLE",
    "MISSED_LATENCY",
)

REJECTION_CLASSES: frozenset[str] = frozenset(o for o in OUTCOMES if o != "EXECUTED")

#: Below this many decisions sharing a rejection reason, a bias estimate is noise. The whole point
#: of this ledger is to stop small samples being read as findings, and it would be absurd for the
#: ledger itself to produce one.
MIN_POPULATION_FOR_BIAS: int = 50


@dataclass(frozen=True)
class Decision:
    """One evaluated opportunity, executed or not, with the exact reason and the state it saw."""

    decision_id: str
    strategy_id: str
    symbol: str
    #: ISO timestamp of the DECISION, not of the record being written.
    decided_at: str
    outcome: str
    #: The specific reason string, e.g. "spread 14bp > modelled edge 9bp". Free text on purpose:
    #: the class is for counting, the reason is for reading.
    reason: str = ""
    #: Feature values the decision saw. Kept so a bias can be conditioned on state.
    features: dict[str, float] = field(default_factory=dict)
    regime: str = ""
    #: Signal strength in bps, as estimated at decision time.
    signal_bps: float = 0.0
    #: Modelled all-in cost in bps at decision time.
    modelled_cost_bps: float = 0.0
    #: Realised forward return of the instrument over the intended horizon, in bps, filled in
    #: LATER. None = not yet resolved, which is the honest state for a recent decision.
    counterfactual_bps: float | None = None
    #: Size that would have been taken, for weighting the counterfactual.
    intended_notional: float = 0.0

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"outcome must be one of {OUTCOMES}, got {self.outcome!r}")

    @property
    def rejected(self) -> bool:
        return self.outcome in REJECTION_CLASSES

    @property
    def resolved(self) -> bool:
        return self.counterfactual_bps is not None


def promotion_is_forbidden(d: Decision) -> str:
    """The reason a good counterfactual can never promote its own decision. Called for the message.

    Present as a function rather than a comment so that it appears in the report next to every
    attractive number, and so that a future caller looking for a promotion path finds this instead
    of writing one.
    """
    return (
        f"{d.decision_id} was REJECTED and its counterfactual is therefore conditioned on the "
        "rejection. The population of 'rejected things that would have worked' is selected by the "
        "outcome being tested, so its mean is biased upward by construction and no significance "
        "computed on it is valid. This number may be used to test whether the REASON "
        f"({d.outcome}) is systematically wrong across its whole population, and to seed a NEW "
        "preregistered hypothesis on untouched data. It may never reinstate this decision.")


def counterfactual_summary(decisions: list[Decision]) -> dict[str, dict[str, float | int | bool]]:
    """Resolved counterfactuals by rejection class. Descriptive; every number carries the caveat."""
    by_class: dict[str, list[float]] = {}
    for d in decisions:
        if d.rejected and d.resolved:
            by_class.setdefault(d.outcome, []).append(float(d.counterfactual_bps or 0.0))
    out: dict[str, dict[str, float | int | bool]] = {}
    for cls, vals in sorted(by_class.items()):
        n = len(vals)
        mean = sum(vals) / n
        sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / n) if n > 1 else 0.0
        out[cls] = {
            "n_resolved": n,
            "mean_counterfactual_bps": round(mean, 3),
            "sd_bps": round(sd, 3),
            "positive_share": round(sum(1 for v in vals if v > 0) / n, 3),
            "sufficient_for_a_bias_claim": n >= MIN_POPULATION_FOR_BIAS,
        }
    return out


def systematic_bias(decisions: list[Decision]) -> list[dict[str, object]]:
    """Rejection reasons whose whole population was wrong in one direction. THE LEGITIMATE USE.

    This is a claim about the REJECTOR, not about any candidate, so the selection problem above
    does not apply in the same way: the question is whether a rule that fired N times produced a
    population whose mean forward return is inconsistent with the rule being correct. That is
    answerable, and it is how a 15%-too-pessimistic cost model gets found.

    Still requires MIN_POPULATION_FOR_BIAS. A rule that rejected 9 things is not a rule with a
    measurable bias, however lopsided those nine look.
    """
    summary = counterfactual_summary(decisions)
    findings: list[dict[str, object]] = []
    for cls, row in summary.items():
        n = int(row["n_resolved"])
        if n < MIN_POPULATION_FOR_BIAS:
            continue
        mean = float(row["mean_counterfactual_bps"])
        sd = float(row["sd_bps"])
        if sd <= 0:
            continue
        t = mean / (sd / math.sqrt(n))
        if abs(t) < 3.0:
            continue
        findings.append({
            "rejection_class": cls,
            "n": n,
            "mean_counterfactual_bps": mean,
            "t": round(t, 2),
            "finding": (
                f"{cls} rejected {n} opportunities whose mean forward return was {mean:+.2f}bp "
                f"(t={t:.1f}). A correct rejection rule should produce a population centred near "
                "zero net of costs; this one does not. The finding is about the RULE -- it "
                "licenses a preregistered test of a recalibrated rule on untouched data, and it "
                "reinstates nothing"),
        })
    findings.sort(key=lambda f: -abs(float(str(f["t"]))))
    return findings


def summarise(decisions: list[Decision]) -> dict[str, object]:
    """Report shape for `data/decision_ledger.json`."""
    if not decisions:
        return {"decisions": 0, "headline": (
            "no decisions recorded. The desk's decision surface is currently legible only where "
            "it said yes, which is the smallest and least informative part of it")}
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d.outcome] = counts.get(d.outcome, 0) + 1
    executed = counts.get("EXECUTED", 0)
    rejected = len(decisions) - executed
    unresolved = sum(1 for d in decisions if d.rejected and not d.resolved)
    bias = systematic_bias(decisions)
    return {
        "decisions": len(decisions),
        "executed": executed,
        "rejected": rejected,
        "execution_share": round(executed / len(decisions), 4),
        "counts_by_outcome": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "counterfactuals": counterfactual_summary(decisions),
        "unresolved_rejections": unresolved,
        "systematic_bias": bias,
        "headline": (
            f"{len(bias)} rejection rule(s) show a systematic bias across their populations: "
            f"{[b['rejection_class'] for b in bias]}" if bias else
            f"{executed} executed of {len(decisions)} evaluated ({executed / len(decisions):.1%}); "
            f"{unresolved} rejection(s) have no counterfactual attached yet, so whether any "
            "rejection rule is systematically wrong is UNMEASURED for those"),
        "note": ("A favourable counterfactual NEVER reinstates the decision it belongs to -- the "
                 "population is conditioned on the rejection being tested. Counterfactuals are "
                 "admissible only as evidence about a rejection RULE across at least "
                 f"{MIN_POPULATION_FOR_BIAS} decisions, and any resulting change must be "
                 "preregistered and tested on untouched data."),
    }
