"""THE PRACTITIONER CORPUS — GPT Hunter's third mission, and the one with a memory.

WHAT THIS IS NOT. `libs/research/video_intelligence.py` tracks CHANNELS and their videos. This
tracks PEOPLE and everything they have ever put in public: interviews, podcasts, papers, books,
conference talks, repositories, regulatory filings, competition records. A practitioner appears
across a dozen channels and none of them is their corpus. Keeping the two separate is deliberate:
a channel can be exhausted while the person behind it has an untouched decade of material.

**EXTERNAL SUCCESS IS A PRIOR AND NEVER PRODUCTION EVIDENCE.** Every number in this module ranks
INVESTIGATION PRIORITY. None of it ranks belief. A practitioner with a verified 200% year moves to
the top of the read queue and moves nothing on any hypothesis, because the desk's own validation is
the only thing that can promote anything -- which is why `investigation_priority` is the only score
here and there is deliberately no `credibility` function for a downstream caller to misuse.

**THE THING WORTH MINING IS USUALLY THE PROCESS, NOT THE RULE.** A published entry rule is the
cheapest thing a practitioner owns and the first thing they give away. How they generate candidates,
how many they reject, what makes them retire a live strategy, how fast they field a replacement --
that is the part that compounds and the part almost nobody transcribes. `EXTRACTION_AXES` splits
the two so an extraction cannot claim completeness having read only the rules.

**THREE PEOPLE REPEATING ONE IDEA ARE ONE SOURCE.** `effective_independent_sources` deflates
convergence by whether the later discoverers could have read the earlier ones. Independent
conceptual convergence raises research priority; a citation chain wearing three names does not, and
telling them apart is the entire value of tracking who-knew-what-when.

**DISAGREEMENT IS ORE.** Where two credible practitioners contradict each other -- volatility
scaling versus preserving the right tail, simple rules versus complex models -- neither is evidence
and the disagreement itself is a testable question about which regime each is right in.
`disagreement_hypotheses` turns those into rows rather than letting reputation settle them.

**NO CORPUS IS EVER `EXHAUSTED`.** It is CURRENTLY_EXHAUSTED_AS_OF a timestamp, and any new upload
reopens it. That is L1.51 applied to people: "we mined that practitioner" is a claim with an expiry
date, and one without a date is not a claim the desk can cash.

Records what was read and what remains. Extracts nothing by itself; the GPT seat fetches.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from libs.research.return_claims import evidence_prior

__all__ = [
    "EXTRACTION_AXES",
    "MATERIAL_KINDS",
    "SYSTEMATIC_STATUS",
    "Disagreement",
    "PractitionerRecord",
    "currently_exhausted",
    "disagreement_hypotheses",
    "effective_independent_sources",
    "investigation_priority",
    "source_roi",
    "summarise",
]

#: How confident the desk is that this person's results come from a REPEATABLE PROCESS. A
#: discretionary trader's returns may be entirely real and still contain nothing transferable.
SYSTEMATIC_STATUS: tuple[str, ...] = (
    "CONFIRMED_SYSTEMATIC",   # they describe rules, code, or a research pipeline in public
    "PROBABLE_SYSTEMATIC",    # strong indirect evidence: turnover, breadth, consistency
    "MIXED",                  # systematic core with discretionary overrides
    "DISCRETIONARY",          # judgement-driven; the method does not port
    "UNKNOWN",                # not yet assessed -- the honest default, and a queue entry
)

#: Where public material lives. Tracked so that "we read their stuff" cannot mean one video.
MATERIAL_KINDS: tuple[str, ...] = (
    "video", "podcast", "article", "paper", "book", "conference_talk",
    "repository", "regulatory_filing", "competition_record", "public_dashboard",
)

#: THE AXES AN EXTRACTION MUST COVER BEFORE IT MAY CALL ITSELF COMPLETE. Split rules from process
#: on purpose: an extraction that read the entry signal and stopped has taken the cheapest thing
#: the practitioner owns and left the part that compounds.
EXTRACTION_AXES: tuple[str, ...] = (
    "mechanism",            # WHY the money is there, and who is paying it
    "universe",             # what they trade, and how many of them
    "signal",               # entry/exit rules -- the cheap part
    "state",                # the regime conditioning, which is usually implicit
    "sizing",               # position size and leverage policy
    "portfolio",            # construction, diversification, correlation handling
    "execution",            # costs, slippage, venue, order type
    "research_process",     # HOW candidates are generated -- the expensive part
    "validation_process",   # how they reject; OOS, incubation, robustness
    "retirement_process",   # when a live strategy is switched off
    "replacement_process",  # what fills the gap, and how fast
    "failure_modes",        # what went wrong, and what they abandoned
)


@dataclass(frozen=True)
class PractitionerRecord:
    """One person's public corpus, and what this desk has actually read of it."""

    practitioner_id: str
    name: str = ""
    systematic_status: str = "UNKNOWN"
    #: Strongest evidence class attached to any performance claim of theirs. Vocabulary is shared
    #: with `libs.research.return_claims` on purpose -- two ladders would drift.
    evidence_class: str = "MARKETING_CLAIM"
    #: Public items KNOWN to exist. 0 = the corpus has never been enumerated, which is a different
    #: state from a corpus enumerated and found empty.
    items_discovered: int = 0
    items_processed: int = 0
    full_transcripts: int = 0
    partial_transcripts: int = 0
    unavailable_items: int = 0
    #: Which of EXTRACTION_AXES have actually been extracted from this corpus.
    axes_extracted: tuple[str, ...] = field(default_factory=tuple)
    genuinely_new_count: int = 0
    duplicate_count: int = 0
    experiments_spawned: int = 0
    validated_descendants: int = 0
    live_descendants: int = 0
    #: Realised economic value in units of portfolio equity. THE ONLY OUTPUT THAT PAYS.
    realized_economic_descendants: float = 0.0
    #: Cost of acquiring and reading this corpus, same units.
    acquisition_cost: float = 0.0
    #: Reported CAGR or similar headline, as a fraction. Used ONLY to rank investigation priority.
    claimed_annual_return: float = 0.0
    last_sweep: str = ""
    last_new_material: str = ""
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.systematic_status not in SYSTEMATIC_STATUS:
            raise ValueError(f"unknown systematic_status {self.systematic_status!r}; "
                             f"expected one of {SYSTEMATIC_STATUS}")
        for a in self.axes_extracted:
            if a not in EXTRACTION_AXES:
                raise ValueError(f"unknown extraction axis {a!r}; the vocabulary is "
                                 f"{EXTRACTION_AXES}")

    @property
    def enumerated(self) -> bool:
        return self.items_discovered > 0

    @property
    def process_axes_covered(self) -> int:
        """How many of the four PROCESS axes are done. The expensive half of the extraction."""
        process = {"research_process", "validation_process", "retirement_process",
                   "replacement_process"}
        return len(process & set(self.axes_extracted))


@dataclass(frozen=True)
class Disagreement:
    """Two credible practitioners contradicting each other. A question, never a verdict."""

    topic: str
    position_a: str
    practitioner_a: str
    position_b: str
    practitioner_b: str
    #: Has this desk actually tested it under ITS capital, costs and objective?
    tested_here: bool = False
    resolution: str = ""


def currently_exhausted(r: PractitionerRecord) -> tuple[bool, str]:
    """(exhausted_now, why). NEVER a permanent verdict -- always as-of the last sweep.

    Per L1.51 this needs per-axis evidence: a corpus is not exhausted because the items ran out,
    it is exhausted when every extraction axis has been covered AND no item remains unread. The
    axis half is the one that is usually skipped, and it is the half that hides the process
    knowledge.
    """
    if not r.enumerated:
        return False, (f"{r.practitioner_id}: corpus never ENUMERATED. Zero items discovered is "
                       "not zero items existing, and 'we mined them' is unsupportable until "
                       "somebody has counted what there is to mine")
    unread = r.items_discovered - r.items_processed - r.unavailable_items
    missing = [a for a in EXTRACTION_AXES if a not in r.axes_extracted]
    if unread > 0:
        return False, (f"{r.practitioner_id}: {unread} of {r.items_discovered} item(s) still "
                       f"unread ({r.unavailable_items} unavailable). NOT exhausted")
    if missing:
        return False, (
            f"{r.practitioner_id}: every available item is read, but {len(missing)} extraction "
            f"axis/axes were never covered: {missing}. That is the usual shape of a false "
            "exhaustion claim -- the signal rules were taken and the research process was not")
    stamp = r.last_sweep or "UNDATED"
    return True, (
        f"{r.practitioner_id}: CURRENTLY_EXHAUSTED_AS_OF {stamp} -- {r.items_processed} item(s) "
        f"read across all {len(EXTRACTION_AXES)} axes. Reopens on any new upload"
        + (". The sweep carries NO DATE, so this claim has no expiry and cannot be trusted to "
           "still hold" if not r.last_sweep else ""))


def investigation_priority(r: PractitionerRecord) -> tuple[float, str]:
    """How urgently to READ them. Never how much to believe them.

    Large claimed returns raise this and nothing else. That separation is the whole point: an
    unverified 400% year is the strongest possible reason to go and look, and no reason at all to
    act. Log-magnitude on the return so a 4000% claim does not swamp the ranking -- an implausible
    number is more likely to be a measurement of the claimant than of the market.
    """
    p_sys = {"CONFIRMED_SYSTEMATIC": 1.0, "PROBABLE_SYSTEMATIC": 0.7, "MIXED": 0.4,
             "UNKNOWN": 0.3, "DISCRETIONARY": 0.05}[r.systematic_status]
    ev = evidence_prior(r.evidence_class)
    magnitude = math.log1p(max(0.0, r.claimed_annual_return))
    unread = max(0, r.items_discovered - r.items_processed - r.unavailable_items)
    novelty = 1.0 if r.items_processed == 0 else max(
        0.05, r.genuinely_new_count / max(1, r.items_processed))
    cost = max(0.01, r.acquisition_cost) if r.acquisition_cost > 0 else 1.0
    score = (p_sys * ev * (1.0 + magnitude) * (1.0 + min(unread, 50) / 10.0) * novelty) / cost
    return score, (
        f"{r.practitioner_id}: P(systematic) {p_sys:.2f} x evidence {ev:.2f} x magnitude "
        f"{1 + magnitude:.2f} x {unread} unread x novelty {novelty:.2f} / cost {cost:.2f} "
        f"=> priority {score:.3f}. This ranks READING ORDER. It does not rank belief, and no "
        "number here may be cited in support of a hypothesis")


def source_roi(r: PractitionerRecord) -> tuple[float | None, str]:
    """Realised economic descendants per unit acquisition cost. None when nothing has been read.

    A large corpus with zero economic descendants should LOSE exploitation priority, not gain it
    for being large. Content volume is the classic Goodhart target here, and it is the one metric
    this function refuses to reward.
    """
    if r.items_processed == 0:
        return None, (f"{r.practitioner_id}: nothing processed yet, so ROI is UNMEASURED. An "
                      "unread corpus has no yield and no evidence of one")
    if r.acquisition_cost <= 0:
        return None, (f"{r.practitioner_id}: {r.items_processed} item(s) read with no recorded "
                      "acquisition cost -- ROI is unpriceable. Reading is not free, and a "
                      "source whose cost nobody recorded cannot be ranked against one that did")
    roi = r.realized_economic_descendants / r.acquisition_cost
    return roi, (
        f"{r.practitioner_id}: {r.realized_economic_descendants:+.4f} realised from "
        f"{r.items_processed} item(s) at cost {r.acquisition_cost:.4f} => ROI {roi:+.2f}. "
        f"{r.experiments_spawned} experiment(s), {r.validated_descendants} validated, "
        f"{r.live_descendants} live"
        + (". No economic descendant yet: this source has produced reading, not money, and volume "
           "is not a reason to keep it high in the queue"
           if r.realized_economic_descendants <= 0 else ""))


def effective_independent_sources(records: list[PractitionerRecord], *,
                                  could_have_read_each_other: bool = True) -> tuple[float, str]:
    """How many INDEPENDENT discoveries a convergence really represents.

    When several practitioners land on the same idea it feels like corroboration. It is only
    corroboration if they could not have copied one another. Pass
    `could_have_read_each_other=False` only when the timeline genuinely rules it out.
    """
    n = len(records)
    if n == 0:
        return 0.0, "no practitioners named -- convergence is UNMEASURED"
    if n == 1:
        return 1.0, "a single source; independence is not yet a question"
    if not could_have_read_each_other:
        return float(n), (
            f"{n} practitioners reached this independently -- the timeline rules out copying. "
            "That raises RESEARCH PRIORITY and still does not substitute for this desk's own test")
    # Diffusion is cheap and public: treat convergence as roughly one original plus a weak
    # contribution from each later restatement.
    eff = 1.0 + (n - 1) * 0.25
    return eff, (
        f"{n} practitioners describe this, but each could have read the others: worth about "
        f"{eff:.2f} INDEPENDENT source(s). A citation chain wearing {n} names is one discovery, "
        "and counting it as several is how a popular idea acquires the appearance of evidence")


def disagreement_hypotheses(rows: list[Disagreement]) -> list[dict[str, object]]:
    """Untested contradictions between credible practitioners, as research rows.

    A disagreement between two people who both made money is the most informative object in this
    whole corpus: it means the answer is CONDITIONAL, and the condition is the thing worth finding.
    """
    out = []
    for d in rows:
        out.append({
            "topic": d.topic,
            "a": f"{d.practitioner_a}: {d.position_a}",
            "b": f"{d.practitioner_b}: {d.position_b}",
            "tested_here": d.tested_here,
            "resolution": d.resolution or "",
            "why": (f"{d.practitioner_a} and {d.practitioner_b} both made money and disagree on "
                    f"{d.topic}. Neither position is evidence. The useful hypothesis is that both "
                    "are right in different regimes, and the research question is WHICH -- under "
                    "this desk's capital, costs and objective"
                    if not d.tested_here else
                    f"{d.topic}: tested here. {d.resolution or 'resolution not recorded'}"),
        })
    return out


def summarise(records: list[PractitionerRecord], *,
              disagreements: list[Disagreement] | None = None) -> dict[str, object]:
    """Report shape for the intelligence cycle."""
    if not records:
        return {"measured": False, "practitioners": 0, "headline": (
            "no practitioners tracked -- who the important systematic traders are, what they "
            "actually do and what has already failed for them is UNMEASURED. That is a permanent "
            "blind spot rather than a gap: nothing in this clone can fetch it, so the GPT seat is "
            "the only route and an empty ledger means the seat has not run")}
    rows = []
    for r in records:
        done, ewhy = currently_exhausted(r)
        pri, pwhy = investigation_priority(r)
        roi, rwhy = source_roi(r)
        rows.append({
            "practitioner_id": r.practitioner_id, "name": r.name,
            "systematic_status": r.systematic_status, "evidence_class": r.evidence_class,
            "items": {"discovered": r.items_discovered, "processed": r.items_processed,
                      "unavailable": r.unavailable_items},
            "axes_extracted": len(r.axes_extracted), "axes_total": len(EXTRACTION_AXES),
            "process_axes_covered": r.process_axes_covered,
            "currently_exhausted": done, "exhaustion_why": ewhy,
            "investigation_priority": round(pri, 4), "priority_why": pwhy,
            "source_roi": None if roi is None else round(roi, 4), "roi_why": rwhy,
            "live_descendants": r.live_descendants,
            "realized": r.realized_economic_descendants,
        })
    rows.sort(key=lambda r: float(str(r["investigation_priority"])), reverse=True)
    unenumerated = [r.practitioner_id for r in records if not r.enumerated]
    no_process = [r.practitioner_id for r in records
                  if r.items_processed > 0 and r.process_axes_covered == 0]
    descendants = sum(r.live_descendants for r in records)
    realized = sum(r.realized_economic_descendants for r in records)
    dis = disagreement_hypotheses(disagreements or [])
    untested = [d for d in dis if d["tested_here"] is False]
    return {
        "measured": True,
        "practitioners": len(records),
        "rows": rows,
        "never_enumerated": unenumerated,
        "read_but_no_process_extracted": no_process,
        "live_descendants": descendants,
        "realized_economic_descendants": round(realized, 6),
        "disagreements": dis,
        "untested_disagreements": len(untested),
        "next_read": rows[0]["practitioner_id"] if rows else None,
        "headline": (
            f"{len(records)} practitioner(s) tracked; {len(unenumerated)} never enumerated; "
            f"{descendants} live descendant(s) and {realized:+.4f} realised. Next read: "
            f"{rows[0]['practitioner_id']}"
            + (f". {len(no_process)} corpus/corpora were read WITHOUT extracting any process axis "
               f"({no_process}) -- the signal rules were taken and the part that compounds was "
               "left behind" if no_process else "")),
        "note": ("Ranks READING ORDER only. External success is a prior and never production "
                 "evidence: nothing here may be cited in support of a hypothesis, and no "
                 "practitioner's claim substitutes for this desk's own validation. Corpora are "
                 "CURRENTLY_EXHAUSTED_AS_OF a timestamp and reopen on any new upload. Convergence "
                 "between practitioners who could have read each other is one discovery, not "
                 "several."),
    }
