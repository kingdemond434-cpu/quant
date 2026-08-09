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

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from libs.core.coerce import finite_float, integer

__all__ = [
    "CASCADE_STAGES",
    "DISPOSITIONS",
    "DIVERSITY_FIELDS",
    "MEANINGFUL_CHANGE_FIELDS",
    "STAGES",
    "Funnel",
    "FunnelDiagnosis",
    "diagnose",
    "meaningful_research_throughput",
    "throughput",
]

#: The pipeline, in order. Each stage's count is the number that REACHED it. A stage cannot exceed
#: its predecessor, and `Funnel.inconsistencies` reports it when one does rather than quietly
#: clipping -- a funnel that widens downstream is a counting bug, and counting bugs in this
#: direction manufacture throughput.
STAGES: tuple[str, ...] = (
    "mined",  # raw ore returned by the miners
    "hypotheses",  # ore translated into falsifiable statements
    "novel_families",  # after semantic de-duplication: distinct ideas, not formulas
    "tested",  # experiments actually COMPLETED against data
    "net_positive",  # cleared costs
    "deflated",  # cleared the multiple-testing hurdle
    "out_of_sample",  # held up on data not used to select them
    "independent",  # distinct MECHANISMS after correlation clustering
    "portfolio_positive",  # improved geometric growth after correlation, cost and capacity
)

#: Which stage each diagnosis blames, and what to do. Ordered EARLIEST-FIRST: the earliest empty
#: stage is the binding one, because every later stage is starved by construction and says nothing
#: about itself.
_BLOCKAGE: dict[str, tuple[str, str]] = {
    "mined": ("INFORMATION", "no ore is arriving -- the miners are the constraint, not the tests"),
    "hypotheses": (
        "TRANSLATION",
        "ore is arriving and nothing is being turned into a falsifiable "
        "statement. This is a refinery problem, not a mining one",
    ),
    "novel_families": (
        "NOVELTY",
        "hypotheses exist but collapse to almost no distinct ideas -- "
        "the generator is re-searching one neighbourhood",
    ),
    "tested": (
        "EXECUTION",
        "hypotheses are queued and nothing is being RUN. Generating more is "
        "the cheapest action and the wrong one: it grows the queue that is "
        "already the bottleneck (L1.52(a): queue backlogged -> EXECUTE)",
    ),
    "net_positive": (
        "COSTS",
        "candidates test but nothing clears costs. Look at horizon and "
        "turnover before signal quality -- and check the liquidity "
        "distribution, since an edge that survives only in the tightest "
        "names is a liquidity finding (WS-006)",
    ),
    "deflated": (
        "SEARCH WIDTH or SIGNAL",
        "things clear costs but not the multiple-testing bar. "
        "Either the search is too wide for the evidence, or the "
        "effects are real but small -- those need different "
        "responses, and more trials worsens both",
    ),
    "out_of_sample": (
        "OVERFITTING",
        "candidates clear in-sample and die out-of-sample. The "
        "harness is selecting on noise; widening the search makes it "
        "worse, not better",
    ),
    "independent": (
        "REDUNDANCY",
        "survivors exist but collapse to one mechanism. The count is "
        "inventory, not discovery -- hunt orthogonal mechanisms",
    ),
    "portfolio_positive": (
        "PORTFOLIO",
        "independent mechanisms exist but none improves geometric "
        "growth after correlation, cost and capacity",
    ),
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
    per_month = (
        (indep / f.period_days) * 30.0 if (indep is not None and f.period_days > 0) else None
    )
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
            warnings.append(
                f"{stage} was never counted -- UNMEASURED, which is not zero and not "
                "fine; a stage nobody instrumented cannot be diagnosed"
            )
            continue
        if v <= 0:
            blocked_at = stage
            break

    if blocked_at is None:
        return FunnelDiagnosis(
            None,
            "none",
            "every stage has throughput; optimise the narrowest ratio",
            rate,
            per_month,
            (),
            tuple(warnings),
        )

    idx = STAGES.index(blocked_at)
    downstream = STAGES[idx + 1 :]
    blockage, action = _BLOCKAGE[blocked_at]
    return FunnelDiagnosis(
        blocked_at,
        blockage,
        action,
        rate,
        per_month,
        downstream,
        (
            *warnings,
            f"the {len(downstream)} stage(s) after {blocked_at} are starved by "
            "construction and say "
            "NOTHING about themselves -- do not read their zeros as findings",
        ),
    )


def render(f: Funnel) -> str:
    """The block a human or an organ reads. Rates print as UNMEASURED where undefined."""
    d = diagnose(f)
    rate = (
        "UNMEASURED (no completed experiments)"
        if d.survivor_rate is None
        else f"{d.survivor_rate:.2%}"
    )
    per_month = "UNMEASURED" if d.survivors_per_month is None else f"{d.survivors_per_month:.2f}"
    lines = [
        d.headline,
        f"  survivor rate {rate} | independent survivors / 30d {per_month}",
        "  " + " -> ".join(f"{s}:{f.get(s) if f.get(s) is not None else '?'}" for s in STAGES),
        f"  ACTION: {d.action}",
    ]
    lines += [f"  ! {w}" for w in d.warnings]
    lines.append(
        "  THE TARGET IS SURVIVOR THROUGHPUT AT FIXED GATES. A survivor count is "
        "trivially maximised by weakening a threshold, so a rise that coincides with a "
        "gate change is not a rise."
    )
    return "\n".join(lines)


CASCADE_STAGES = (
    "semantic_mechanism_deduplication",
    "data_timestamp_feasibility",
    "cheapest_informative_falsification",
    "basic_empirical_test",
    "robustness_and_cost_realism",
    "true_oos_walk_forward",
    "portfolio_independence",
    "shadow_live",
)

DISPOSITIONS = ("TEST_NOW", "TEST_LATER_WITH_BLOCKER", "REJECT_BEFORE_TEST")

MEANINGFUL_CHANGE_FIELDS = (
    "economic_mechanism",
    "information_source",
    "participant_behavior",
    "market_state",
    "causal_structure",
    "data_modality",
    "cross_market_relationship",
    "execution_mechanism",
    "regime_dependency",
    "new_information_transformation",
    "distinct_source_interaction",
)

DIVERSITY_FIELDS = (
    "mechanism",
    "asset",
    "venue",
    "horizon",
    "regime",
    "participant",
    "data_source",
    "data_modality",
    "research_methodology",
)


def meaningful_research_throughput(
    candidates: Sequence[Mapping[str, object]],
    *,
    now: str | datetime | None = None,
    window_hours: float = 24.0,
) -> dict[str, object]:
    """Daily ledger for meaningful generation, cascade testing and explicit disposition."""
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")
    current = (
        now
        if isinstance(now, datetime)
        else datetime.fromisoformat(now)
        if now
        else datetime.now(tz=UTC)
    )
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    def parse(value: object) -> datetime | None:
        if not value:
            return None
        try:
            stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)

    recent = []
    for candidate in candidates:
        generated = parse(candidate.get("generated_at"))
        if generated is None or (current - generated).total_seconds() <= window_hours * 3600:
            recent.append(candidate)
    meaningful = []
    parameter_variants = []
    for candidate in recent:
        declared = candidate.get("substantive_changes", [])
        changes = {str(value) for value in declared} if isinstance(declared, list) else set()
        changes.update(name for name in MEANINGFUL_CHANGE_FIELDS if candidate.get(name))
        if changes and not bool(candidate.get("pure_parameter_variant")):
            meaningful.append(candidate)
        else:
            parameter_variants.append(candidate)

    stage_counts = dict.fromkeys(CASCADE_STAGES, 0)
    disposition_counts = dict.fromkeys(DISPOSITIONS, 0)
    un_dispositioned = []
    tests_started = completed = valid = oos = near = survivors = independent = recycled = 0
    blocked_missing_data = infrastructure_failures = automatically_testable = 0
    compute_seconds = data_loading_seconds = information_gain = 0.0
    valuable_waiting = []
    mechanism_ids = set()
    diversity: dict[str, Counter[str]] = {name: Counter() for name in DIVERSITY_FIELDS}
    for candidate in meaningful:
        mechanism = candidate.get("mechanism_id", candidate.get("mechanism"))
        if mechanism:
            mechanism_ids.add(str(mechanism))
        disposition = str(candidate.get("disposition", ""))
        if disposition in disposition_counts:
            disposition_counts[disposition] += 1
        else:
            un_dispositioned.append(candidate.get("id", mechanism))
        blocker = str(candidate.get("blocker", ""))
        if disposition == "TEST_LATER_WITH_BLOCKER" and "data" in blocker.casefold():
            blocked_missing_data += 1
        if bool(candidate.get("infrastructure_failure")):
            infrastructure_failures += 1
        if bool(candidate.get("automatically_testable")):
            automatically_testable += 1
        stages = candidate.get("stages", {})
        stages = stages if isinstance(stages, Mapping) else {}
        for stage in CASCADE_STAGES:
            stage_counts[stage] += int(bool(stages.get(stage)))
        started = bool(candidate.get("test_started_at")) or bool(stages.get(CASCADE_STAGES[3]))
        done = bool(candidate.get("test_completed_at"))
        is_valid = done and bool(candidate.get("valid_empirical_test"))
        tests_started += int(started)
        completed += int(done)
        valid += int(is_valid)
        oos += int(bool(stages.get(CASCADE_STAGES[5])) or bool(candidate.get("oos_tested")))
        near += int(bool(candidate.get("near_survivor")))
        survivors += int(bool(candidate.get("survivor")))
        independent += int(bool(candidate.get("independent_survivor")))
        recycled += integer(candidate.get("failure_descendants"))
        compute_seconds += finite_float(candidate.get("compute_seconds"))
        data_loading_seconds += finite_float(candidate.get("data_loading_seconds"))
        information_gain += finite_float(candidate.get("information_gain"))
        if disposition == "TEST_NOW" and not started:
            generated = parse(candidate.get("generated_at"))
            valuable_waiting.append((generated, candidate.get("id", mechanism)))
        for dimension in DIVERSITY_FIELDS:
            if candidate.get(dimension) is not None:
                diversity[dimension][str(candidate[dimension])] += 1

    diversity_rows = {}
    for dimension, counts in diversity.items():
        total = sum(counts.values())
        hhi = sum((count / total) ** 2 for count in counts.values()) if total else None
        diversity_rows[dimension] = {
            "represented": len(counts),
            "hhi": hhi,
            "effective_categories": 1 / hhi if hhi else None,
            "counts": dict(counts),
        }
    oldest = min((stamp for stamp, _ in valuable_waiting if stamp is not None), default=None)
    oldest_id = next(
        (identifier for stamp, identifier in valuable_waiting if stamp == oldest), None
    )
    waiting = len(valuable_waiting)
    if waiting:
        bottleneck = "TEST_EXECUTION"
    elif un_dispositioned:
        bottleneck = "DISPOSITION"
    elif blocked_missing_data:
        bottleneck = "MISSING_DATA"
    elif infrastructure_failures:
        bottleneck = "INFRASTRUCTURE"
    elif meaningful and not valid:
        bottleneck = "VALID_TEST_COMPLETION"
    elif not meaningful:
        bottleneck = "MEANINGFUL_GENERATION_UNMEASURED"
    else:
        bottleneck = "NO_BINDING_BOTTLENECK_OBSERVED"
    hours = window_hours
    return {
        "status": "MEASURED" if candidates else "UNMEASURED",
        "window_hours": hours,
        "raw_generated_specifications": len(recent),
        "deduplicated_meaningful_candidates": len(meaningful),
        "parameter_variants": len(parameter_variants),
        "unique_mechanisms": len(mechanism_ids),
        "candidates_submitted_to_testing": tests_started,
        "tests_executed": tests_started,
        "tests_completed": completed,
        "valid_empirical_tests": valid,
        "oos_tested_candidates": oos,
        "near_survivors": near,
        "survivors": survivors,
        "independent_survivors": independent,
        "failed_candidates_converted_to_hypotheses": recycled,
        "dispositions": disposition_counts,
        "undispositioned_candidates": un_dispositioned,
        "cascade_stage_counts": stage_counts,
        "candidates_generated_per_hour": len(meaningful) / hours,
        "tests_per_hour": tests_started / hours,
        "cpu_seconds_per_completed_test": compute_seconds / completed if completed else None,
        "data_loading_seconds": data_loading_seconds,
        "percentage_automatically_testable": (
            automatically_testable / len(meaningful) if meaningful else None
        ),
        "percentage_blocked_by_missing_data": (
            blocked_missing_data / len(meaningful) if meaningful else None
        ),
        "percentage_infrastructure_failure": (
            infrastructure_failures / len(meaningful) if meaningful else None
        ),
        "survivor_yield_per_1000_meaningful_tests": (independent * 1000 / valid if valid else None),
        "information_gain": information_gain,
        "information_gain_per_compute_hour": (
            information_gain / (compute_seconds / 3600) if compute_seconds > 0 else None
        ),
        "oldest_valuable_untested_candidate": oldest_id,
        "oldest_valuable_untested_age_hours": (
            (current - oldest).total_seconds() / 3600 if oldest else None
        ),
        "dominant_bottleneck": bottleneck,
        "diversity": diversity_rows,
        "generated_is_not_tested": True,
        "authority": "THROUGHPUT DIAGNOSTIC ONLY -- fixed statistical and survival gates",
    }
