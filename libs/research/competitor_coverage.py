"""COMPETITOR COVERAGE — mechanically proving no known external return engine was omitted.

THE FAILURE THIS PREVENTS is not being outperformed. It is being outperformed by a mechanism the
desk never considered, and never noticing, because "have we covered everything they do" was
answered from memory. A prose answer to that question is correct on the day it is written and
quietly wrong every day after.

So coverage becomes a MATRIX with six independent dimensions, and the ordering matters more than
any single cell::

    IDENTIFIED             we know the engine exists
    SPECIFIED              we have written down what it would mean here
    IMPLEMENTED            code exists
    VERIFIED               tests and evidence exist
    LIVE                   it is running against real capital
    ECONOMICALLY_VALIDATED it has produced measured economic contribution

**ADOPTED REQUIRES ALL SIX, AND THE COMMONEST LIE IS STOPPING AT TWO.** A capability that is
IDENTIFIED and SPECIFIED feels handled -- there is a document, there is a plan, someone described
it in a meeting. It contributes exactly nothing. `adoption_status` therefore reports the FIRST
missing dimension rather than the count achieved, because the first gap is the one to close.

**"OURS IS BETTER" IS THREE DIFFERENT CLAIMS AND ONLY ONE OF THEM PAYS.** A broader specification
is not superiority; a working implementation is not economic superiority. The three are tracked
separately (DESIGN / IMPLEMENTATION / LIVE_ECONOMIC) and only the last can be claimed on evidence
this desk does not yet have.

**UNKNOWN IS A PERMANENT, LEGITIMATE VALUE.** Private competitor logic is not observable, and
inventing a plausible reconstruction would put fiction into the one artifact whose whole job is to
say what is genuinely missing.

Measures and reports. Adopts nothing; the completion ledger owns adoption for our own capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ADOPTION_DIMENSIONS",
    "SUPERIORITY_CLASSES",
    "EngineCoverage",
    "adoption_status",
    "coverage_score",
    "residual_frontier",
    "summarise",
    "superiority",
]

#: Ordered. Adoption is the FIRST missing dimension, never the count achieved.
ADOPTION_DIMENSIONS: tuple[str, ...] = (
    "IDENTIFIED", "SPECIFIED", "IMPLEMENTED", "VERIFIED", "LIVE", "ECONOMICALLY_VALIDATED",
)

#: Three separate claims. Only the third is settled by money.
SUPERIORITY_CLASSES: tuple[str, ...] = (
    "DESIGN_SUPERIORITY",          # our specification is broader. Cheapest and least meaningful.
    "IMPLEMENTATION_SUPERIORITY",  # ours runs and theirs is described
    "LIVE_ECONOMIC_SUPERIORITY",   # ours has produced more retained net log wealth. The only one
                                   # that decides anything, and the only one requiring real fills
)


@dataclass(frozen=True)
class EngineCoverage:
    """One externally-observed return engine, and exactly how far we have taken our version."""

    engine: str
    #: Does the competitor demonstrably use this? UNKNOWN is legitimate and permanent for private
    #: logic -- inventing a reconstruction puts fiction into the gap register.
    external_uses: str = "UNKNOWN"       # YES | NO | UNKNOWN
    external_evidence: str = ""
    #: Our module/capability id, when one exists.
    our_equivalent: str = ""
    #: Which adoption dimensions we have actually reached, by name.
    dimensions_met: tuple[str, ...] = field(default_factory=tuple)
    #: Measured economic contribution of OUR version. Empty = nothing measured, which is the
    #: honest state for everything on this desk today.
    measured_value: str = ""
    residual_gap: str = ""
    #: Expected ΔE[log W] from closing the residual, for ranking. 0 = unestimated.
    expected_close_value: float = 0.0
    estimated_cost_units: float = 0.0

    def __post_init__(self) -> None:
        if self.external_uses not in ("YES", "NO", "UNKNOWN"):
            raise ValueError("external_uses must be YES, NO or UNKNOWN")
        for d in self.dimensions_met:
            if d not in ADOPTION_DIMENSIONS:
                raise ValueError(f"unknown adoption dimension {d!r}: {ADOPTION_DIMENSIONS}")


def adoption_status(e: EngineCoverage) -> tuple[str, str]:
    """(ADOPTED | NOT_ADOPTED, why). Reports the FIRST missing dimension.

    Deliberately binary at the top level. A six-point scale invites a capability at 2/6 to be
    described as "40% adopted", which is how IDENTIFIED-and-SPECIFIED comes to feel like progress
    when it has produced nothing.
    """
    met = set(e.dimensions_met)
    missing = [d for d in ADOPTION_DIMENSIONS if d not in met]
    if not missing:
        return "ADOPTED", (
            f"{e.engine}: all six dimensions reached, including measured economic contribution "
            f"({e.measured_value or 'recorded'})")
    first = missing[0]
    reached = [d for d in ADOPTION_DIMENSIONS if d in met]
    return "NOT_ADOPTED", (
        f"{e.engine}: reached {reached or ['nothing']}, first missing dimension is {first}. "
        + ("A capability that is only IDENTIFIED and SPECIFIED contributes nothing -- there is a "
           "document and no economics" if first == "IMPLEMENTED" else
           "Code without evidence is a claim the desk cannot cash" if first == "VERIFIED" else
           "Verified and not live is edge sitting still while it decays" if first == "LIVE" else
           "Live with no measured contribution cannot be compared against anything else "
           "competing for the same capital" if first == "ECONOMICALLY_VALIDATED" else
           "Nothing has been written down about what this would mean here"))


def coverage_score(engines: list[EngineCoverage]) -> dict[str, object]:
    """Per-dimension counts. NOT a single percentage, on purpose.

    One number would average a capability that is live against one that has a paragraph, and the
    average would be reported as progress. The shape of the shortfall IS the finding.
    """
    counts = {d: sum(1 for e in engines if d in e.dimensions_met) for d in ADOPTION_DIMENSIONS}
    adopted = sum(1 for e in engines if adoption_status(e)[0] == "ADOPTED")
    known_external = [e for e in engines if e.external_uses == "YES"]
    unknown = [e for e in engines if e.external_uses == "UNKNOWN"]
    return {
        "engines": len(engines),
        "by_dimension": counts,
        "adopted": adopted,
        "externally_confirmed": len(known_external),
        "external_unknown": len(unknown),
        "note": ("Reported per dimension rather than as one percentage: averaging a live "
                 "capability with a paragraph produces a number that reads like progress. "
                 "UNKNOWN external usage is permanent and legitimate -- private logic is not "
                 "observable and must never be reconstructed by guess."),
    }


def superiority(engine: str, *, our_dimensions: tuple[str, ...],
                external_evidence_class: str,
                our_measured_value: str = "") -> tuple[str, str]:
    """Which of the three superiority claims the evidence actually supports. NEVER the top one
    unless real economics exist on our side."""
    met = set(our_dimensions)
    if our_measured_value and "ECONOMICALLY_VALIDATED" in met:
        return "LIVE_ECONOMIC_SUPERIORITY", (
            f"{engine}: our version has measured economic contribution ({our_measured_value}) "
            f"against external evidence of class {external_evidence_class}")
    if "VERIFIED" in met:
        return "IMPLEMENTATION_SUPERIORITY", (
            f"{engine}: ours is implemented and verified; that is an ENGINEERING claim and it "
            "settles nothing economically. No real capital has tested it")
    if "SPECIFIED" in met:
        return "DESIGN_SUPERIORITY", (
            f"{engine}: our specification is broader. This is the cheapest of the three claims "
            "and the one most likely to be mistaken for the others -- a broader design that "
            "nothing runs loses to a narrow one that does")
    return "NO_CLAIM", f"{engine}: nothing on our side supports any superiority claim"


def residual_frontier(engines: list[EngineCoverage]) -> list[dict[str, object]]:
    """Unadopted engines ranked by expected value of closing them per unit cost.

    Unestimated items sort LAST but are never dropped: an engine nobody costed is an engine nobody
    will schedule, and that is a defect in the estimate rather than a verdict on the engine.
    """
    rows: list[dict[str, object]] = []
    for e in engines:
        status, why = adoption_status(e)
        if status == "ADOPTED":
            continue
        ratio = (e.expected_close_value / e.estimated_cost_units
                 if e.estimated_cost_units > 0 and e.expected_close_value > 0 else None)
        rows.append({
            "engine": e.engine,
            "first_missing": next(d for d in ADOPTION_DIMENSIONS if d not in set(e.dimensions_met)),
            "external_uses": e.external_uses,
            "our_equivalent": e.our_equivalent or None,
            "residual_gap": e.residual_gap,
            "expected_close_value": e.expected_close_value or None,
            "value_per_cost": None if ratio is None else round(ratio, 4),
            "why": why,
        })
    rows.sort(key=lambda r: -(float(str(r["value_per_cost"]))
                              if r["value_per_cost"] is not None else -1.0))
    return rows


def summarise(engines: list[EngineCoverage]) -> dict[str, object]:
    """Report shape for `data/intelligence/competitor_coverage.json`."""
    if not engines:
        return {"engines": 0, "headline": (
            "no coverage matrix recorded -- whether a known external return engine has been "
            "omitted is UNMEASURED, and it would be omitted silently")}
    score = coverage_score(engines)
    frontier = residual_frontier(engines)
    stalled = [r for r in frontier if r["first_missing"] in ("IMPLEMENTED", "SPECIFIED")]
    return {
        "coverage_score": score,
        "residual_frontier": frontier,
        "rows": [{"engine": e.engine, "external_uses": e.external_uses,
                  "external_evidence": e.external_evidence,
                  "our_equivalent": e.our_equivalent or None,
                  "dimensions_met": list(e.dimensions_met),
                  "adoption": adoption_status(e)[0],
                  "measured_value": e.measured_value or None,
                  "residual_gap": e.residual_gap} for e in engines],
        "headline": (
            f"{score['adopted']} of {len(engines)} external return engine(s) ADOPTED (all six "
            f"dimensions incl. measured economics); {len(stalled)} are stalled at SPECIFIED or "
            f"IMPLEMENTED, which is the state that feels handled and pays nothing"),
        "note": ("Adoption is the FIRST missing dimension, never the count achieved. "
                 "'Ours is better' splits into DESIGN / IMPLEMENTATION / LIVE_ECONOMIC "
                 "superiority and only the last is settled by money -- which this desk does not "
                 "yet have on either side of the comparison."),
    }
