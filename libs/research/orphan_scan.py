"""ORPHANS BEYOND MODULES — every producer whose output nothing consumes.

`dormancy` answers this for CODE: which module does nothing import, which script does nothing
schedule. That is one producer class out of many, and it is not the expensive one. The expensive
orphans are further down the chain, where the desk has already paid for the discovery:

    a dataset collected and turned into no feature
    a feature computed and used in no hypothesis
    a hypothesis written and never tested
    a recommendation accepted and never implemented
    a survivor validated and never portfolio-tested
    a failure recorded and never mined
    a near-survivor banked and never revisited

Each of those is value that reached the desk and stopped. NONE of them is visible to an importer
count, a scheduler check, or a test suite -- the code all works, the artifacts all exist, and the
chain is broken at a join nobody is watching. This is L1.54(a)'s CONVERSION_FAILURE state applied
to research objects rather than to Python modules.

WHY THIS IS A SCAN AND NOT A LEDGER. A ledger would require every producer to register its output,
which is a change to every producer and would be half-adopted forever. The scan reads the artifacts
the desk ALREADY writes and asks whether each stage's population appears downstream. It is
therefore approximate, and it is honest about that: a stage whose artifact is absent reports
UNMEASURED, never zero, because "nobody looked" and "nothing was stranded" are opposite facts and
only one of them is good news.

IT PUBLISHES RATHER THAN PRINTS. Rows go to the `gap_contract` channel, so the max-push queue ranks
them beside every other gap without anyone editing the ranker. Detection that cannot reach a
priority is half a control -- the exact defect that produced this module's sibling this morning.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libs.research.gap_contract import Gap

__all__ = ["STAGES", "Stage", "StageCount", "scan", "to_gaps"]

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Stage:
    """One join in the conversion chain, and how to count both sides of it."""

    name: str
    produced_artifact: str
    consumed_artifact: str
    #: Why a stranded object here is expensive, in the desk's own terms.
    why: str
    #: What to do about it -- required, because a row nobody can act on is a complaint.
    action: str
    source: str = "conversion_debt"


#: The joins, ordered along the chain. Each names the artifact that holds the PRODUCED population
#: and the artifact that would show it was CONSUMED. Where the desk writes no such artifact yet,
#: the stage still appears and reports UNMEASURED -- an unwatched join is the finding.
STAGES: tuple[Stage, ...] = (
    Stage("data_to_feature", "data/data_universe_map.json", "data/feature_registry.json",
          "a dataset collected and turned into no feature is storage cost with no research "
          "output, and it is the stage where the desk's own measurement showed the largest "
          "leak (catalog breadth ~8.5/10 against ingested-and-tested ~4.5/10)",
          "run the Stage-A screen on the unconverted axes -- SCREEN-ON-DISCOVERY makes this the "
          "same run as the discovery, not a later one"),
    Stage("feature_to_hypothesis", "data/feature_registry.json", "data/hypothesis_ledger.json",
          "a feature computed and used in no hypothesis is compute already spent that bought no "
          "test; the combination engine can enumerate over it for free",
          "enumerate the unused features into the candidate space -- generation is not a trial "
          "(L1.52), so this costs no multiplicity budget"),
    Stage("hypothesis_to_test", "data/hypothesis_ledger.json", "data/full_sweep.json",
          "a hypothesis written and never executed is the queue-backlog state L1.52 names "
          "explicitly: with ideas queued and none tested, the next priority is THROUGHPUT",
          "execute the untested backlog; if experiment capacity binds, that is the engineering "
          "target -- never a reason to generate fewer (L1.54)"),
    Stage("recommendation_to_change", "data/recommendation_ledger.json",
          "data/conversion_status.json",
          "an accepted recommendation that never became a change is advice the desk paid for and "
          "declined to collect; §41 already requires every row to reach implemented or rejected",
          "close each open row to implemented (with commit) or rejected (with a substantive "
          "reason) -- 'still open' past 14 days is a defect to name, not a backlog"),
    Stage("survivor_to_portfolio", "data/full_sweep.json", "data/portfolio_candidates.json",
          "a validated survivor never tested for INCREMENTAL portfolio value may be the "
          "fiftieth expression of an alpha already deployed; standalone Sharpe cannot tell",
          "run marginal-contribution and independence clustering on each survivor before it is "
          "counted as a discovery"),
    Stage("failure_to_mining", "docs/graveyard.md", "data/failure_mining.json",
          "a failure recorded and never mined discards the most specific information the desk "
          "owns about where an effect is NOT -- which is also information about where it is",
          "extract failure mode, regime, horizon and cost for each killed hypothesis, then "
          "generate the mutations those fields license"),
    Stage("near_survivor_to_experiment", "data/research_review.json",
          "data/near_survivor_runs.json",
          "a banked near-survivor never revisited is the cheapest experiment the desk has, "
          "already located and already costed",
          "run the next_experiments the bank licenses, at the ancestry-deflated hurdle -- a "
          "descendant inherits the whole search that produced it"),
)


@dataclass(frozen=True)
class StageCount:
    """Both sides of one join. `produced`/`consumed` are None when the artifact is absent."""

    stage: Stage
    produced: int | None
    consumed: int | None

    @property
    def measured(self) -> bool:
        return self.produced is not None and self.consumed is not None

    @property
    def stranded(self) -> int | None:
        if self.produced is None or self.consumed is None:
            return None
        return max(0, self.produced - self.consumed)

    @property
    def conversion(self) -> float | None:
        """Consumed / produced, capped at 1.0. None when either side is unmeasured.

        Capped because a downstream population can legitimately EXCEED the upstream one -- one
        feature spawns many hypotheses -- and a ratio above 1.0 would read as over-conversion
        rather than as the ordinary fan-out it is.
        """
        if self.produced is None or self.consumed is None:
            return None
        if self.produced <= 0:
            # Nothing produced is not a conversion failure. It is an upstream problem, and the
            # stage above this one is where it will show up as a real gap.
            return 1.0
        return min(1.0, self.consumed / self.produced)


def _count(path: Path) -> int | None:
    """Population size of an artifact, or None when it is absent or unreadable.

    Handles the three shapes the desk actually writes -- a JSON list, a dict of records, or a dict
    with a list under a well-known key -- and a markdown file, counted by numbered entries. An
    unrecognised shape returns None rather than 0, because guessing a population is how a full
    stage comes to read as empty.
    """
    if not path.exists():
        return None
    if path.suffix == ".md":
        try:
            text = path.read_text("utf-8", errors="ignore")
        except OSError:
            return None
        return sum(1 for ln in text.splitlines() if ln.strip().startswith("|")) or None
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, dict):
        for key in ("entries", "rows", "items", "records", "survivors", "candidates",
                    "hypotheses", "features", "sources", "gaps", "runs"):
            v = doc.get(key)
            if isinstance(v, list):
                return len(v)
        # A dict-of-records keyed by id is the other shape the desk writes.
        if doc and all(isinstance(v, dict) for v in doc.values()):
            return len(doc)
    return None


def scan(*, root: Path | None = None, counter: Callable[[Path], int | None] | None = None,
         ) -> list[StageCount]:
    """Count both sides of every join. Pure over `counter`, so it is testable without artifacts."""
    r = root or _ROOT
    c = counter or _count
    return [StageCount(s, c(r / s.produced_artifact), c(r / s.consumed_artifact))
            for s in STAGES]


def to_gaps(counts: list[StageCount]) -> list[Gap]:
    """Published rows. AN UNWATCHED JOIN IS THE FINDING, not an omission from the report.

    A stage whose artifact is missing publishes `current=None`, which the queue ranks ABOVE a
    partially-converted stage. That ordering is deliberate and it is the whole reason this scan is
    worth running: the desk knows roughly how bad its measured conversion is, and does not know
    which joins nobody is watching at all.
    """
    out: list[Gap] = []
    for sc in counts:
        s = sc.stage
        if sc.measured:
            detail = (f"{sc.consumed} of {sc.produced} converted; {sc.stranded} stranded at "
                      f"{s.name}")
            action = s.action
        else:
            missing = [a for a, n in ((s.produced_artifact, sc.produced),
                                      (s.consumed_artifact, sc.consumed)) if n is None]
            detail = (f"UNMEASURED -- {', '.join(missing)} absent or unrecognised, so this join "
                      "is unwatched. Nobody-looked and nothing-stranded are opposite facts")
            action = (f"emit the missing artifact so the join can be counted, THEN {s.action}. "
                      "An unwatched join outranks a measured one because an unknown quantity is "
                      "being ignored rather than worked (L1.28a)")
        out.append(Gap(
            aspect=f"conversion::{s.name}", source=s.source,
            current=sc.conversion, ceiling=1.0, detail=detail, action=action,
            artifact=s.consumed_artifact, evidence=s.why,
            dependency=s.produced_artifact, tags=("conversion-chain",)))
    return out


def summarise(counts: list[StageCount]) -> dict[str, Any]:
    """Report shape: the WORST-CONVERTING measured join first, and the unwatched ones named.

    The bottleneck stage is the work (L1.53). A report ordered by stage name would bury it.
    """
    measured = [c for c in counts if c.measured]
    unwatched = [c.stage.name for c in counts if not c.measured]
    ranked = sorted(measured, key=lambda c: (c.conversion or 0.0))
    return {
        "joins": len(counts), "measured": len(measured), "unwatched": unwatched,
        "bottleneck": ranked[0].stage.name if ranked else None,
        "chain": [{"stage": c.stage.name, "produced": c.produced, "consumed": c.consumed,
                   "stranded": c.stranded,
                   "conversion": None if c.conversion is None else round(c.conversion, 4)}
                  for c in counts],
        "note": ("UNMEASURED joins outrank measured ones. The desk knows roughly how bad its "
                 "measured conversion is; it does not know which joins nobody watches at all."),
    }
