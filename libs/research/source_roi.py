"""RESEARCH-SOURCE ROI — which miner, model or prompt actually produces validated alpha.

THE QUESTION THIS ANSWERS. The desk runs seven regional miners, a BRAIN hunter, several external
model seats and a growing set of prompts. Every one of them consumes compute, credit and triage
attention, and NONE of them has ever been measured against what it produced downstream. The desk
knows how many documents a miner found. It does not know whether any of them became a survivor.

WHY DOCUMENT COUNT IS THE WRONG NUMBER, stated once because it is the intuitive one: a miner
returning 100,000 pages and zero independent survivors is WORSE than one returning 100 pages and
two, because the first also spends the desk's triage budget — the scarcest input in the chain. So
the metric is validated output per unit of research resource, and volume appears only as a cost.

THE FIVE FUNNEL COUNTS, and the gap between adjacent ones is where a source is actually failing:

    found -> novel -> hypotheses -> tested -> independent survivors -> portfolio contributing

A source with `found=5000, novel=12` has a REDUNDANCY problem. One with `novel=400, tested=3` is
not the source's fault at all — that is an executor bottleneck, and cutting the source's budget
would be attacking the wrong stage. The module names WHICH gap binds rather than emitting one
score, because a single number cannot distinguish those two and they have opposite fixes.

ZERO SURVIVORS IS NOT ZERO VALUE, and this is the correction that keeps the metric honest over
short horizons. Survivors are rare and lumpy; a source measured over four weeks with none is
UNMEASURED, not refuted (L1.28a). Judging it otherwise would defund every slow-burn source in
favour of whichever one got lucky this month — the exact selection error the desk polices in its
alpha research, applied to its own research process.

REDUCE, NEVER DELETE. A source that stops producing loses budget share and keeps a floor. L1.52
forbids reducing exploration to zero, and a source pruned to nothing can never produce the evidence
that would justify restoring it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = [
    "EXPLORATION_FLOOR",
    "MIN_TESTED_FOR_VERDICT",
    "SourceRecord",
    "allocate",
    "bottleneck",
    "render",
    "verdict",
]

#: Tested hypotheses below which a source's survivor count says nothing. Survivors are rare and
#: lumpy: with 8 tested and 0 survivors the expected count was well under one anyway, so "no
#: survivors" is the null result of a sample too small to have produced one.
MIN_TESTED_FOR_VERDICT: int = 30

#: No source is ever cut below this share of the research budget. L1.52 forbids reducing
#: exploration to zero, and a source pruned to nothing cannot generate the evidence that would
#: justify restoring it -- the defunding becomes self-confirming.
EXPLORATION_FLOOR: float = 0.05


@dataclass(frozen=True)
class SourceRecord:
    """One miner / model / prompt, and what it produced along the chain."""

    name: str
    kind: str                       # "miner" | "model" | "prompt" | "region" | "dataset"
    found: int = 0                  # raw items surfaced
    novel: int = 0                  # survived the novelty gate
    hypotheses: int = 0             # became a stated, testable hypothesis
    tested: int = 0                 # actually executed
    survivors: int = 0              # cleared the deflated bar
    independent: int = 0            # distinct MECHANISM, not the nth expression of one
    portfolio_positive: int = 0     # improved the existing book
    cost_units: float = 0.0         # compute + credit + triage, in whatever unit the caller uses
    window_days: int = 0

    @property
    def measured(self) -> bool:
        """Enough executed tests for the survivor count to carry information."""
        return self.tested >= MIN_TESTED_FOR_VERDICT

    @property
    def value(self) -> int:
        """The only output that counts: independent mechanisms that improved the book.

        Falls back to `independent` when portfolio testing has not run, because a desk with no
        portfolio stage would otherwise score every source zero and conclude all research is
        worthless -- a measurement artifact, not a finding.
        """
        return self.portfolio_positive or self.independent

    @property
    def roi(self) -> float | None:
        """Value per cost unit. None when unmeasured or costless -- never 0.0.

        0.0 reads as "measured and worthless" and None reads as "not measured yet", and over a
        short window the second is almost always the true statement.
        """
        if not self.measured or self.cost_units <= 0:
            return None
        return self.value / self.cost_units


def bottleneck(r: SourceRecord) -> tuple[str, str]:
    """(stage, why) — WHERE this source's chain is failing. Not a score.

    A single ROI number cannot distinguish a redundant source from a starved executor, and those
    have opposite fixes: one wants a different search, the other wants more compute. Cutting the
    source's budget is the right answer to exactly one of them.
    """
    if r.found and not r.novel:
        return "NOVELTY", (f"{r.found} found, 0 novel -- this source is re-finding known ground. "
                           "Redundant candidates burn multiplicity budget twice; change the "
                           "search, not the volume")
    if r.novel and not r.hypotheses:
        return "EXTRACTION", (f"{r.novel} novel item(s), 0 hypotheses -- the source produces "
                              "information nobody converts into a testable statement. That is an "
                              "EXTRACTION gap in the desk, not a fault in the source")
    if r.hypotheses and not r.tested:
        return "EXECUTION", (f"{r.hypotheses} hypothesis(es), 0 tested -- NOT this source's "
                             "failure. The executor binds, and cutting the source's budget would "
                             "attack the wrong stage (L1.52: queue backlogged -> EXECUTE)")
    if r.tested and not r.survivors:
        if not r.measured:
            return "UNMEASURED", (f"{r.tested} tested, 0 survivors -- below the "
                                  f"{MIN_TESTED_FOR_VERDICT}-test floor, so the expected survivor "
                                  "count was under one anyway. This is a sample too small to have "
                                  "produced a survivor, never evidence the source is barren")
        return "YIELD", (f"{r.tested} tested, 0 survivors over a real sample -- the source "
                         "produces testable material that does not survive. Reduce share, keep "
                         "the floor")
    if r.survivors and not r.independent:
        return "INDEPENDENCE", (f"{r.survivors} survivor(s), 0 independent -- this source keeps "
                                "re-finding mechanisms the book already has. Valuable once, and "
                                "the repeats are not discoveries")
    if r.independent and not r.portfolio_positive:
        return "PORTFOLIO", (f"{r.independent} independent mechanism(s), 0 improving the book -- "
                             "distinct is not the same as additive after correlation and capacity")
    if not r.found:
        return "SILENT", "this source produced nothing at all in the window -- check it still runs"
    return "NONE", "chain intact end to end"


def verdict(r: SourceRecord) -> str:
    """EARNING | UNMEASURED | REDUCE. Never DELETE."""
    if not r.measured:
        return "UNMEASURED"
    return "EARNING" if r.value > 0 else "REDUCE"


def allocate(records: list[SourceRecord], *, floor: float = EXPLORATION_FLOOR) -> dict[str, float]:
    """Budget shares from measured ROI, with a hard exploration floor under every source.

    UNMEASURED SOURCES GET THE FLOOR AND NOT ZERO. A source that has not yet had 30 tests run
    against it cannot be shown to be failing, and defunding it would guarantee it never reaches
    the sample that would settle the question -- a self-confirming judgement, and the same error
    as retiring an alpha on one bad period.
    """
    if not records:
        return {}
    n = len(records)
    if n * floor >= 1.0:
        # More sources than the floor can fund. Equal shares is the honest answer: any ranking
        # here would be a distinction the budget cannot actually express.
        return {r.name: round(1.0 / n, 4) for r in records}
    earners = {r.name: (r.roi or 0.0) for r in records if verdict(r) == "EARNING"}
    total = sum(earners.values())
    free = 1.0 - n * floor
    out = {r.name: floor for r in records}
    if total > 0:
        for name, roi in earners.items():
            out[name] += free * (roi / total)
    else:
        # Nothing measured as earning yet -- spread the free share evenly rather than freezing the
        # desk at the floor. Exploration is the correct default when nothing is proven.
        for r in records:
            out[r.name] += free / n
    return {k: round(v, 4) for k, v in out.items()}


def summarise(records: list[SourceRecord]) -> dict[str, object]:
    if not records:
        return {"sources": 0, "headline": "no source records -- UNMEASURED, not zero value"}
    shares = allocate(records)
    rows = []
    for r in sorted(records, key=lambda x: (-(x.roi or -1.0), x.name)):
        stage, why = bottleneck(r)
        rows.append({"name": r.name, "kind": r.kind, "verdict": verdict(r),
                     "value": r.value, "tested": r.tested, "found": r.found,
                     "roi": None if r.roi is None else round(r.roi, 5),
                     "bottleneck": stage, "why": why, "share": shares.get(r.name)})
    measured = [r for r in records if r.measured]
    return {
        "ts": datetime.now(tz=UTC).isoformat(),
        "sources": len(records), "measured": len(measured),
        "headline": (
            f"{len(measured)}/{len(records)} sources have enough executed tests to judge; "
            f"{sum(1 for r in records if verdict(r) == 'EARNING')} earning"),
        "rows": rows,
        "note": ("volume is a COST, never an output. A source returning 100,000 pages and zero "
                 "independent survivors is worse than one returning 100 pages and two, because it "
                 "also spends triage -- the scarcest input in the chain. No source is ever cut to "
                 f"zero: the exploration floor is {EXPLORATION_FLOOR:.0%} (L1.52)"),
    }


def render(records: list[SourceRecord]) -> str:
    rep = summarise(records)
    if not records:
        return str(rep["headline"])
    lines = [str(rep["headline"])]
    rows = rep["rows"]
    for row in rows if isinstance(rows, list) else []:
        lines.append(f"  [{row['verdict']}] {row['name']} ({row['kind']}) "
                     f"share {row['share']} | bottleneck {row['bottleneck']}")
        lines.append(f"      {row['why']}")
    return "\n".join(lines)
