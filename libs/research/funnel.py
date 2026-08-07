"""SURVIVOR THROUGHPUT, AND WHERE THE FUNNEL IS ACTUALLY BLOCKED.

THE OPTIMISATION TARGET (principal 2026-08-07): *maximise the expected number of independent,
executable, out-of-sample survivors discovered per month, subject to FIXED statistical and
execution gates.* The subordinate clause is the whole thing. A survivor count is trivially
maximised by weakening the gates, so the target is only meaningful while the gates are constants --
which is why nothing in this module can read, set or reference a threshold.

THE DIAGNOSIS THIS EXISTS FOR. When the desk produces zero survivors, there are eight candidate
explanations and they imply OPPOSITE actions::

    too few hypotheses     -> generate            |  poor hypotheses    -> mine better sources
    insufficient data      -> acquire             |  poor testing       -> fix the harness
    overfitting            -> tighten             |  weak validation    -> tighten
    wrong market           -> look elsewhere      |  excessive costs    -> different horizon

Picking the wrong one is not a small error. "Generate more" is the default failure -- it is the
cheapest action, it always feels productive, and it is exactly wrong when the blockage is
downstream. This desk has the archetypal case in its own register: ~900k enumerated candidates,
20,052 pre-registered trials, ZERO executed. The correct diagnosis there is EXECUTION, and a
diagnostic that reported "poor hypotheses" would send the desk to build a bigger generator.

**SO THE FIRST RULE IS THAT A STAGE WITH NO THROUGHPUT DIAGNOSES ITSELF, NOT ITS SUCCESSORS.** If
zero hypotheses were ever TESTED, the desk knows nothing whatever about hypothesis quality,
overfitting, validation or costs -- those stages have no observations. Reporting on them would be
inventing a verdict for a stage that never ran (L1.49), and the flattering direction is always to
blame the stage you can most cheaply act on.

**AND THE SECOND: A RATE OVER A PERIOD WITH NO COMPLETED EXPERIMENTS IS NOT ZERO, IT IS
UNDEFINED.** 0 survivors / 0 experiments is not a 0% survivor rate; it is no measurement. Rendering
it as 0% would make an idle month look like a failing method, and the two call for opposite
responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "STAGES",
    "Funnel",
    "FunnelDiagnosis",
    "diagnose",
    "throughput",
]

#: The pipeline, in order. Each stage's count is the number that REACHED it. A stage cannot exceed
#: its predecessor, and `Funnel.inconsistencies` reports it when one does rather than quietly
#: clipping -- a funnel that widens downstream is a counting bug, and counting bugs in this
#: direction manufacture throughput.
STAGES: tuple[str, ...] = (
    "mined",              # raw ore returned by the miners
    "hypotheses",         # ore translated into falsifiable statements
    "novel_families",     # after semantic de-duplication: distinct ideas, not formulas
    "tested",             # experiments actually COMPLETED against data
    "net_positive",       # cleared costs
    "deflated",           # cleared the multiple-testing hurdle
    "out_of_sample",      # held up on data not used to select them
    "independent",        # distinct MECHANISMS after correlation clustering
    "portfolio_positive", # improved geometric growth after correlation, cost and capacity
)

#: Which stage each diagnosis blames, and what to do. Ordered EARLIEST-FIRST: the earliest empty
#: stage is the binding one, because every later stage is starved by construction and says nothing
#: about itself.
_BLOCKAGE: dict[str, tuple[str, str]] = {
    "mined": ("INFORMATION", "no ore is arriving -- the miners are the constraint, not the tests"),
    "hypotheses": ("TRANSLATION", "ore is arriving and nothing is being turned into a falsifiable "
                                  "statement. This is a refinery problem, not a mining one"),
    "novel_families": ("NOVELTY", "hypotheses exist but collapse to almost no distinct ideas -- "
                                  "the generator is re-searching one neighbourhood"),
    "tested": ("EXECUTION", "hypotheses are queued and nothing is being RUN. Generating more is "
                            "the cheapest action and the wrong one: it grows the queue that is "
                            "already the bottleneck (L1.52(a): queue backlogged -> EXECUTE)"),
    "net_positive": ("COSTS", "candidates test but nothing clears costs. Look at horizon and "
                              "turnover before signal quality -- and check the liquidity "
                              "distribution, since an edge that survives only in the tightest "
                              "names is a liquidity finding (WS-006)"),
    "deflated": ("SEARCH WIDTH or SIGNAL", "things clear costs but not the multiple-testing bar. "
                                           "Either the search is too wide for the evidence, or the "
                                           "effects are real but small -- those need different "
                                           "responses, and more trials worsens both"),
    "out_of_sample": ("OVERFITTING", "candidates clear in-sample and die out-of-sample. The "
                                     "harness is selecting on noise; widening the search makes it "
                                     "worse, not better"),
    "independent": ("REDUNDANCY", "survivors exist but collapse to one mechanism. The count is "
                                  "inventory, not discovery -- hunt orthogonal mechanisms"),
    "portfolio_positive": ("PORTFOLIO", "independent mechanisms exist but none improves geometric "
                                        "growth after correlation, cost and capacity"),
}


@dataclass(frozen=True)
class Funnel:
    """Counts reaching each stage over one period. Absent stages are UNMEASURED, not zero."""

    counts: dict[str, int | None] = field(default_factory=dict)
    period_days: float = 30.0

    def get(self, stage: str) -> int | None:
        return self.counts.get(stage)

    @property
    def inconsistencies(self) -> list[str]:
        """Stages that exceed their predecessor -- a counting bug that inflates throughput."""
        out, prev_name, prev = [], "", None
        for s in STAGES:
            v = self.counts.get(s)
            if v is not None and prev is not None and v > prev:
                out.append(f"{s}={v} exceeds {prev_name}={prev}: a funnel cannot widen downstream")
            if v is not None:
                prev_name, prev = s, v
        return out


@dataclass(frozen=True)
class FunnelDiagnosis:
    """Where the pipeline is blocked, and what the blockage licenses."""

    blocked_at: str | None
    blockage: str
    action: str
    survivor_rate: float | None
    survivors_per_month: float | None
    unmeasured_downstream: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def headline(self) -> str:
        if self.blocked_at is None:
            return "no blockage detected -- every stage has throughput"
        return f"BLOCKED AT {self.blocked_at.upper()} ({self.blockage})"


def throughput(f: Funnel) -> tuple[float | None, float | None]:
    """(survivor rate, survivors per 30 days). None where the denominator does not exist.

    0 survivors / 0 experiments IS NOT A 0% SURVIVOR RATE. It is no measurement, and rendering it
    as 0% makes an idle month look like a failing method -- opposite problems with opposite fixes.
    """
    tested, indep = f.get("tested"), f.get("independent")
    rate = (indep / tested) if (tested and indep is not None) else None
    per_month = ((indep / f.period_days) * 30.0
                 if (indep is not None and f.period_days > 0) else None)
    return rate, per_month


def diagnose(f: Funnel) -> FunnelDiagnosis:
    """Find the EARLIEST stage with no throughput and blame that one.

    EARLIEST, because every later stage is starved by construction. A funnel with 20,000 queued
    hypotheses and zero executed tests says NOTHING about overfitting, costs or validation -- those
    stages have no observations, and reporting a verdict for them would be inventing one for a gate
    that never ran (L1.49). The stages downstream of the blockage are returned as explicitly
    UNMEASURED so the reader cannot mistake silence for health.
    """
    rate, per_month = throughput(f)
    warnings = list(f.inconsistencies)

    blocked_at = None
    for stage in STAGES:
        v = f.get(stage)
        if v is None:
            warnings.append(f"{stage} was never counted -- UNMEASURED, which is not zero and not "
                            "fine; a stage nobody instrumented cannot be diagnosed")
            continue
        if v <= 0:
            blocked_at = stage
            break

    if blocked_at is None:
        return FunnelDiagnosis(
            None, "none", "every stage has throughput; optimise the narrowest ratio", rate,
            per_month, (), tuple(warnings))

    idx = STAGES.index(blocked_at)
    downstream = STAGES[idx + 1:]
    blockage, action = _BLOCKAGE[blocked_at]
    return FunnelDiagnosis(
        blocked_at, blockage, action, rate, per_month, downstream,
        (*warnings,
         f"the {len(downstream)} stage(s) after {blocked_at} are starved by construction and say "
         "NOTHING about themselves -- do not read their zeros as findings"))


def render(f: Funnel) -> str:
    """The block a human or an organ reads. Rates print as UNMEASURED where undefined."""
    d = diagnose(f)
    rate = "UNMEASURED (no completed experiments)" if d.survivor_rate is None \
        else f"{d.survivor_rate:.2%}"
    per_month = "UNMEASURED" if d.survivors_per_month is None else f"{d.survivors_per_month:.2f}"
    lines = [
        d.headline,
        f"  survivor rate {rate} | independent survivors / 30d {per_month}",
        "  " + " -> ".join(f"{s}:{f.get(s) if f.get(s) is not None else '?'}" for s in STAGES),
        f"  ACTION: {d.action}",
    ]
    lines += [f"  ! {w}" for w in d.warnings]
    lines.append("  THE TARGET IS SURVIVOR THROUGHPUT AT FIXED GATES. A survivor count is "
                 "trivially maximised by weakening a threshold, so a rise that coincides with a "
                 "gate change is not a rise.")
    return "\n".join(lines)
