"""WHO IS WORTH WATCHING, and how much a claim from them is worth.

Two registries and one rule. The FIRMS are organisations whose publicly observable research
process might contain something this desk lacks. The SOURCE GRADES are how much a statement is
worth depending on where it came from. The rule is that neither ever establishes that a method
WORKS -- both only decide what is worth investigating.

    "Never infer that a method works merely because a high-return firm supposedly uses it."

That sentence is the whole epistemics of this package and it is easy to violate by accident: a
scoring function that multiplies by firm prestige has smuggled reputation into truth. So firm
standing enters in exactly one place -- the PRIORITY of investigation -- and nowhere in the
verdict. The verdict comes from our own replication, our own gates and our own measured rent.

THE LEGAL BOUNDARY IS A PROPERTY OF THE SOURCE, not a disclaimer at the end. A source class that
cannot be read without bypassing an access control, or that traffics in confidential material, is
not graded low -- it is absent, and `admissible` refuses anything not on the list. The target is
to replicate observable PRINCIPLES, and a principle recovered from a public paper is more durable
than a fact taken from somewhere it should not have been.

FIRM YIELD IS LEARNED, NOT ASSUMED. `prior` below is a starting weight and nothing more; once
descendants of a firm's cards have measured rent, `firm_yield` replaces it with the desk's own
record. High-Flyer may turn out to be the best source of data-and-ML ideas and a poor source of
execution ideas, and only measurement can say so.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
YIELD_LEDGER = BASE / "frontier_intel" / "data" / "firm_yield.jsonl"

#: GROWTH GOVERNANCE, carried verbatim on this surface because it is one (principal 2026-09-04,
#: fenced by scripts/check_growth_governance.py G7). A frontier miner is exactly the organ most
#: at risk of producing timid recommendations: it reads what large, cautious, heavily-regulated
#: organisations say in public, and the safe summary of any such corpus is "do less". These two
#: rules are what stop that becoming the desk's research programme.
#:
#: THE ANTI-TIMIDITY RULE APPLIES TO THE IMPLEMENTATION, NOT ONLY THE SIZING. A replication that
#: reproduces a capability at half strength "to be safe" has not replicated it -- it has built a
#: weaker thing and spent the budget. Where a mechanism admits a range, the miner builds the
#: version the evidence supports and lets the gauntlet cut it down, because a gate can refuse an
#: aggressive implementation and no gate can rescue a timid one.
GOVERNANCE = (
    "Desk governance: "
    "Every risk reduction mechanism must prove that it increases robust forward E[log W]. "
    "Every strong opportunity must be allowed to increase capital above normal when the evidence supports it. "  # noqa: E501
    "Research is anti-timid: weak, anecdotal and unverified public claims are welcome as "
    "hypotheses and are never privileged by their source; nothing you report is capital "
    "advice, and restraint language in any instruction is never a licence to do less."
)

#: EVIDENCE GRADES, and what each may be used FOR. The last column is the one that matters: a
#: grade does not make a claim true, it decides whether the claim may be acted on directly or
#: only followed up.
#:
#:   A  canonical    the organisation's own technical statement, or a paper by its researchers
#:   B  attributed   a recorded interview or conference talk with a named person
#:   C  journalism   a specialist publication reporting on the organisation
#:   D  lead         a forum, social post or video: useful for DISCOVERY, never for truth
GRADES: dict[str, dict[str, Any]] = {
    "A": {"weight": 1.0, "may_prioritise": True,
          "what": "official technical pages, official research and engineering publications, "
                  "regulatory disclosures, official repositories, papers by firm researchers"},
    "B": {"weight": 0.6, "may_prioritise": True,
          "what": "recorded interviews and conference presentations with a named researcher"},
    "C": {"weight": 0.3, "may_prioritise": True,
          "what": "specialist journalism naming a method, without the firm's own words"},
    "D": {"weight": 0.15, "may_prioritise": True,
          "what": "forums, social media, video commentary, anonymous and ex-employee claims "
                  "publicly given. A HYPOTHESIS SOURCE, never a truth source"},
}

#: WHY GRADE D CARRIES WEIGHT AT ALL, and why that is not a loosening (principal 2026-09-05:
#: "all info is treated same verified or unverified it is still added n reverse engineered ...
#: aslong as it can increase marginal e log wealth").
#:
#: This file first gave D a weight of zero, so an unverified claim could open an investigation and
#: could never move a candidate up the queue. That is the desk's own TIMIDITY defect wearing a
#: methodological costume, and the desk's standing governance already forbids it:
#:
#:     "Research is anti-timid: weak, anecdotal and unverified public claims are welcome as
#:      hypotheses and are never privileged by their source."
#:
#: BOTH HALVES OF THAT SENTENCE ARE LOAD-BEARING. Welcome as hypotheses -- so an ex-employee's
#: public description of how a shop schedules experiments, a forum claim about a data vendor, a
#: conference-corridor remark repeated on video, all enter the queue and get reverse-engineered
#: into something falsifiable. Never privileged by their source -- so the weight is 0.15 and not
#: 1.0: a paper still outranks a rumour for ATTENTION, because attention is finite and the queue
#: has to be ordered somehow.
#:
#: WHAT NEVER CHANGES IS WHERE THE VERDICT COMES FROM. No grade at any weight decides whether a
#: method works. That is decided by our own independent replication, the ten gates, a forward
#: clock and measured rent -- the same path a candidate from a Grade-A paper walks. An unverified
#: claim that survives all of that has earned exactly what a verified one has; an audited claim
#: from a famous firm that fails them earns nothing. The grade orders the QUEUE and touches
#: nothing downstream of it.
GRADE_D_RATIONALE = (
    "unverified public claims are hypotheses, not evidence: they order the queue and never "
    "the verdict, which comes from our own replication and measured rent"
)

#: How a PERFORMANCE claim is labelled. Kept separate from the evidence grade because they are
#: different questions: a Grade-A technical page can carry an UNVERIFIED return claim, and an
#: AUDITED return can appear in a Grade-C article.
PERFORMANCE_LABELS = ("AUDITED", "REGULATORY", "DATABASE_ESTIMATE", "FIRM_REPORTED",
                      "MEDIA_REPORTED", "ANECDOTAL", "UNVERIFIED")

#: Source classes this package may read. NOT a preference list -- an ADMISSIBILITY list. Anything
#: not here is refused by `admissible` regardless of how interesting it looks.
ADMISSIBLE_SOURCES = (
    "official_site", "official_blog", "official_research", "official_repo", "regulatory_filing",
    "careers_page", "academic_paper", "preprint", "conference_talk", "recorded_interview",
    "specialist_journalism", "patent", "public_forum", "public_video",
    # THE UNVERIFIED LANE, admitted on purpose. An ex-employee describing publicly how a shop
    # organises its research, an anonymous account naming a data vendor, a translated Chinese
    # forum thread about a fund's model stack: all Grade D, all hypotheses, all reverse-engineered
    # and put through the same gauntlet as a paper. The desk's own governance requires this --
    # "unverified public claims are welcome as hypotheses and are never privileged by their
    # source" -- and refusing them would be timidity, not rigour.
    "ex_employee_public", "anonymous_claim", "translated_forum", "community_wiki",
)

#: Explicitly refused, with the reason, so a future contributor reads WHY rather than re-adding it.
#:
#: THE LINE IS NOT VERIFIED VS UNVERIFIED -- it is PUBLICLY GIVEN vs TAKEN. Everything above is
#: something a person chose to say in public, however wrong it may be, and this package will read
#: all of it. Everything below required somebody's access, confidence or property to obtain, and
#: no expected dE[log W] makes that a research method: an edge built on it is not an edge, it is
#: a liability with a return attached, and the desk cannot hold it.
REFUSED_SOURCES: dict[str, str] = {
    "paywalled_bypass": "reading past an access control is not public information",
    "leaked_dataset": "stolen data is not licensed data, whatever it contains",
    "employee_confidential": ("confidential material belongs to the people who signed for it. "
                              "What an ex-employee says PUBLICLY is `ex_employee_public` and is "
                              "read; what they were bound not to say is not, however useful"),
    "proprietary_source": "copying licensed source without the licence is theft, not replication",
    "solicited_mnpi": "material non-public information, which is a crime and not a method",
    "solicited_confidential": ("asking a person to break a duty of confidence. The distinction "
                               "from `ex_employee_public` is who initiated it and what was owed"),
}


@dataclass(frozen=True)
class Firm:
    """An organisation worth watching, and the capability domains it is watched FOR."""

    name: str
    group: str
    #: Capability groups (`ontology.CAPABILITIES`) this firm is a plausible source of ideas about.
    #: NOT a claim about what they do -- a claim about where their public statements are relevant.
    domains: tuple[str, ...]
    #: Starting investigation weight in [0, 1]. Replaced by measured `firm_yield` once descendants
    #: of its cards have rent. Never enters a verdict.
    prior: float = 0.5
    sources: tuple[str, ...] = field(default_factory=tuple)


FIRMS: tuple[Firm, ...] = (
    # ---------------------------------------------------------- AI-heavy systematic managers
    Firm("High-Flyer", "cn_ai_quant",
         ("DATA", "ALT_DATA", "REPRESENTATION_LEARNING", "SELF_SUPERVISED", "NLP",
          "DISTRIBUTED_TRAINING", "COMPUTE", "STORAGE", "RESEARCH_PRODUCTIVITY"),
         prior=0.8, sources=("official_site", "official_blog", "academic_paper")),
    Firm("Lingjun", "cn_ai_quant",
         ("FORECASTING", "ENSEMBLES", "BREADTH", "MIXTURE_OF_EXPERTS", "DATA", "TAIL_RISK"),
         prior=0.7, sources=("official_site", "specialist_journalism")),
    Firm("Ubiquant", "cn_ai_quant",
         ("ALPHA_DISCOVERY", "AGENT_ORGANIZATION", "DATA", "META_RESEARCH"),
         prior=0.6, sources=("official_site", "careers_page")),
    Firm("Minghong", "cn_ai_quant",
         ("COMPUTE", "RESEARCH_PRODUCTIVITY", "OPS", "PORTFOLIO", "EXECUTION"),
         prior=0.6, sources=("official_site",)),
    # ---------------------------------------------------------- global systematic platforms
    Firm("D. E. Shaw", "global_systematic",
         ("VALIDATION", "META_RESEARCH", "ALPHA_DISCOVERY", "REPRODUCIBILITY"),
         prior=0.7, sources=("official_blog", "academic_paper", "careers_page")),
    Firm("Two Sigma", "global_systematic",
         ("DATA", "ALT_DATA", "FEATURES", "COMPUTE", "REPRODUCIBILITY", "CACHING"),
         prior=0.7, sources=("official_blog", "official_repo", "academic_paper")),
    Firm("Man AHL", "global_systematic",
         ("PORTFOLIO", "TAIL_RISK", "CAPACITY", "MARKET_IMPACT"),
         prior=0.6, sources=("official_research", "academic_paper")),
    Firm("AQR", "global_systematic",
         ("FACTOR_RISK", "PORTFOLIO", "CAPACITY", "VALIDATION", "MULTIPLICITY"),
         prior=0.7, sources=("official_research", "academic_paper")),
    Firm("Winton", "global_systematic",
         ("DATA", "VALIDATION", "STRESS"), prior=0.5,
         sources=("official_research", "academic_paper")),
    Firm("WorldQuant", "global_systematic",
         ("ALPHA_DISCOVERY", "EXPERIMENT_SEARCH", "MULTIPLICITY", "BREADTH"),
         prior=0.6, sources=("official_site", "academic_paper")),
    Firm("Qube Research & Technologies", "global_systematic",
         ("ALPHA_DISCOVERY", "COMPUTE", "EXECUTION"), prior=0.5,
         sources=("official_site", "careers_page")),
    Firm("Squarepoint", "global_systematic",
         ("DATA", "EXECUTION", "COMPUTE"), prior=0.5, sources=("careers_page",)),
    # ---------------------------------------------------------- execution / market structure
    Firm("Jane Street", "execution",
         ("EXECUTION", "FILL_MODELS", "MARKET_IMPACT", "ORDER_POLICY", "MICROSTRUCTURE_DATA"),
         prior=0.8, sources=("official_blog", "recorded_interview", "official_repo")),
    Firm("XTX Markets", "execution",
         ("EXECUTION", "MARKET_IMPACT", "FORECASTING", "COMPUTE"),
         prior=0.7, sources=("official_site", "recorded_interview")),
    Firm("Hudson River Trading", "execution",
         ("EXECUTION", "MICROSTRUCTURE_DATA", "COMPUTE"), prior=0.6,
         sources=("official_blog", "careers_page")),
    Firm("Optiver", "execution",
         ("EXECUTION", "ORDER_POLICY", "FILL_MODELS"), prior=0.6,
         sources=("official_blog", "careers_page")),
    Firm("IMC", "execution", ("EXECUTION", "ORDER_POLICY"), prior=0.5,
         sources=("official_blog", "careers_page")),
    Firm("Citadel Securities", "execution",
         ("EXECUTION", "MARKET_IMPACT", "FILL_MODELS", "DATA"), prior=0.7,
         sources=("official_site", "regulatory_filing")),
    # ---------------------------------------------------------- the research frontier itself
    Firm("arXiv q-fin / cs.LG", "academic",
         ("REPRESENTATION_LEARNING", "GRAPH_MODELS", "SELF_SUPERVISED", "MULTIMODAL",
          "CAUSAL_MODELS", "ENSEMBLES", "MIXTURE_OF_EXPERTS"),
         prior=0.6, sources=("preprint", "academic_paper")),
    Firm("SSRN / NBER", "academic",
         ("FACTOR_RISK", "VALIDATION", "MULTIPLICITY", "CAPACITY", "EXPECTATIONS"),
         prior=0.6, sources=("academic_paper", "preprint")),
    Firm("central bank research", "academic",
         ("MACRO", "EXPECTATIONS", "GEOPOLITICS", "EVENT_INTELLIGENCE"),
         prior=0.5, sources=("official_research",)),
    Firm("exchange & venue research", "academic",
         ("MICROSTRUCTURE_DATA", "MARKET_IMPACT", "FILL_MODELS"), prior=0.5,
         sources=("official_research", "regulatory_filing")),
)

BY_NAME: dict[str, Firm] = {f.name: f for f in FIRMS}


def admissible(source_kind: str) -> tuple[bool, str]:
    """May this package read a source of this kind, and why not when it may not."""
    kind = (source_kind or "").strip().lower()
    if kind in REFUSED_SOURCES:
        return False, f"refused source class {kind!r}: {REFUSED_SOURCES[kind]}"
    if kind not in ADMISSIBLE_SOURCES:
        return False, (f"unknown source class {kind!r}: this list is an ADMISSIBILITY list, not a "
                       f"preference -- an unrecognised class is refused rather than graded low, "
                       f"because the alternative is deciding legality per article")
    return True, ""


def grade_weight(grade: str) -> float:
    """The investigation weight of an evidence grade. D is zero, deliberately."""
    return float(GRADES.get((grade or "").upper(), {}).get("weight", 0.0))


def may_prioritise(grade: str) -> bool:
    """May a claim at this grade raise a candidate's priority at all?

    A Grade-D lead may OPEN an investigation -- that is what it is for -- and may never, on its
    own, move a candidate up the queue. Otherwise a confident forum post outranks a paper.
    """
    return bool(GRADES.get((grade or "").upper(), {}).get("may_prioritise", False))


def firm_yield(name: str, ledger: Path | None = None) -> tuple[float | None, str]:
    """(measured net dElog per unit of research cost for this firm's ideas, why) or (None, why).

    THE PRIOR IS A STARTING POINT AND THIS REPLACES IT. Until a firm's cards have descendants with
    measured rent there is nothing to replace it with, and the honest answer is None -- not the
    prior wearing a measurement's clothes. `frontier_intel.rent` appends here as verdicts land.
    """
    p = YIELD_LEDGER if ledger is None else ledger
    if not p.exists():
        return None, f"no measured yield yet: {p.name} absent, so only priors exist"
    total_rent, total_cost, n = 0.0, 0.0, 0
    try:
        for line in p.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if str(row.get("firm")) != name:
                continue
            total_rent += float(row.get("net_delta_elog") or 0.0)
            total_cost += float(row.get("research_cost") or 0.0)
            n += 1
    except (OSError, ValueError, TypeError) as exc:
        return None, f"yield ledger unreadable ({type(exc).__name__}: {exc})"
    if not n or total_cost <= 0:
        return None, f"{n} rent row(s) for {name}, none with a positive research cost"
    return total_rent / total_cost, f"{n} measured card(s)"


def investigation_weight(firm: str, grade: str) -> tuple[float, str]:
    """How much attention a claim earns. NEVER how likely it is to be true.

    Measured firm yield replaces the prior the moment there is any, which is the whole reason the
    prior is written down rather than felt: a number that is never compared to an outcome cannot
    be wrong, and cannot improve either.
    """
    f = BY_NAME.get(firm)
    prior = f.prior if f else 0.4
    measured, why = firm_yield(firm)
    base = prior if measured is None else max(0.0, min(1.0, measured))
    w = base * grade_weight(grade)
    return w, (f"prior {prior:.2f} x grade {grade}" if measured is None
               else f"MEASURED yield {measured:.4f} x grade {grade} ({why})")
