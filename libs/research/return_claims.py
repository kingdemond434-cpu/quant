"""EXTREME-RETURN INTELLIGENCE — a spectacular number raises URGENCY, never the evidence bar.

THE ASYMMETRY THAT MAKES THIS WORTH BUILDING. A verified +300% is either a mechanism this desk does
not have, or an artefact of leverage, concentration, beta or luck. Both answers are valuable and
they are cheap to separate, so an extreme claim earns fast INVESTIGATION. What it must never earn
is belief: the same number that makes a claim worth chasing is the number most likely to have been
produced by a process nobody would want to run twice.

    HIGH RETURN  ->  raises investigation priority
    HIGH RETURN  ->  does NOT raise evidentiary standing
    HIGH RETURN  ->  does NOT lower any validator bar

**THE DECOMPOSITION IS THE PRODUCT, NOT THE HEADLINE NUMBER.** A return is worth copying only to
the extent it came from a transferable mechanism. So every claim splits into alpha, beta, leverage,
concentration, carry, convexity, luck/path and unverifiable residual, and ONLY the transferable
part reaches the hypothesis factory. `LEVERAGE = ALPHA` is the specific lesson this desk must never
learn, and `transferable_share` is where that is enforced rather than remembered.

**AN UNVERIFIABLE RESIDUAL IS A FINDING.** When most of a claim cannot be attributed, the honest
report is that the desk does not know what produced it -- not a small residual line at the bottom
of a table that reads like rounding.

**A LOWER, BETTER-EVIDENCED RETURN CAN OUTRANK A LARGER ONE**, and `priority` is built so it does:
a verified market-neutral +50% with a described mechanism scores above a self-reported +1000%
directional bet, because P(real) x P(transferable) does most of the work and the raw magnitude is
only one factor among seven.

Records, decomposes and ranks. Verifies nothing itself -- the deterministic pipeline does that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "EVIDENCE_CLASSES",
    "RETURN_SOURCES",
    "TRANSFERABLE_SOURCES",
    "ReturnClaim",
    "decompose",
    "evidence_weight",
    "priority",
    "summarise",
    "transferable_share",
]

#: Ordered weakest to strongest. A MARKETING_CLAIM and an AUDITED record are not the same kind of
#: object and must never share a column without this label attached.
EVIDENCE_CLASSES: tuple[str, ...] = (
    "MARKETING_CLAIM",
    "SELF_REPORTED",
    "BACKTEST",
    "PUBLIC_DASHBOARD",
    "COMPETITION_RECORD",
    "PARTIALLY_VERIFIABLE",
    "VERIFIED",
    "AUDITED",
)

#: P(the reported economics are approximately real), by evidence class. Declared rather than
#: computed: the desk has no calibration data for these yet, and an invented posterior would be
#: less honest than a stated prior that can be argued with and later measured.
_EVIDENCE_PRIOR: dict[str, float] = {
    "MARKETING_CLAIM": 0.05,
    "SELF_REPORTED": 0.15,
    "BACKTEST": 0.10,          # BELOW self-reported on purpose: a backtest is a claim about the
                               # past made by the person who chose the parameters
    "PUBLIC_DASHBOARD": 0.45,
    "COMPETITION_RECORD": 0.70,
    "PARTIALLY_VERIFIABLE": 0.60,
    "VERIFIED": 0.90,
    "AUDITED": 0.97,
}

#: Every way an extraordinary return can arise. Closed on purpose.
RETURN_SOURCES: tuple[str, ...] = (
    "ALPHA", "BETA", "LEVERAGE", "CONCENTRATION", "CARRY", "CONVEXITY",
    "LUCK_PATH", "UNVERIFIABLE",
)

#: The subset the desk can actually take with it. Beta and leverage are available to anyone with
#: an account; concentration and luck are not mechanisms at all.
TRANSFERABLE_SOURCES: frozenset[str] = frozenset({"ALPHA", "CARRY", "CONVEXITY"})


@dataclass(frozen=True)
class ReturnClaim:
    """One public claim of extraordinary performance, with everything needed to discount it."""

    subject: str
    source: str
    observed_at: str
    evidence_class: str
    #: Reported total return over the horizon, as a fraction (2.0 = +200%).
    reported_return: float = 0.0
    horizon_days: float = 0.0
    starting_capital: float = 0.0
    ending_capital: float = 0.0
    net_of_costs: bool = False
    realised: bool = False
    flows_disclosed: bool = False
    max_leverage: float | None = None
    max_concentration: float | None = None
    estimated_beta: float | None = None
    reported_drawdown: float | None = None
    strategy_family: str = ""
    #: The described mechanism, if any. NO mechanism means nothing transferable, whatever the
    #: number was -- a return with no explanation cannot be reproduced even if it was real.
    mechanism: str = ""
    #: Fraction of the return attributed to each RETURN_SOURCES key. Need not sum to 1: whatever
    #: is unattributed lands in UNVERIFIABLE, which is a finding rather than a rounding line.
    attribution: dict[str, float] = field(default_factory=dict)
    contradictions: str = ""

    def __post_init__(self) -> None:
        if self.evidence_class not in EVIDENCE_CLASSES:
            raise ValueError(f"evidence_class must be one of {EVIDENCE_CLASSES}")
        for k in self.attribution:
            if k not in RETURN_SOURCES:
                raise ValueError(
                    f"unknown return source {k!r}; the basis is closed: {RETURN_SOURCES}")

    @property
    def annualised_log(self) -> float | None:
        """Log growth annualised. None when the horizon is unrecorded.

        Annualising a two-week result is arithmetic vandalism, so the caller gets the horizon back
        alongside the number and `priority` penalises short ones explicitly.
        """
        if self.horizon_days <= 0 or self.reported_return <= -1.0:
            return None
        return math.log1p(self.reported_return) * (365.0 / self.horizon_days)


def evidence_weight(c: ReturnClaim) -> float:
    """P(approximately real), adjusted downward for the disclosure gaps that always matter."""
    p = _EVIDENCE_PRIOR[c.evidence_class]
    if not c.net_of_costs:
        p *= 0.7          # gross figures compared against net ones have decided many comparisons
    if not c.realised:
        p *= 0.7          # an unrealised mark is a price, not a result
    if not c.flows_disclosed:
        p *= 0.6          # undisclosed flows can manufacture any curve
    if c.contradictions:
        p *= 0.5
    return max(0.0, min(1.0, p))


def decompose(c: ReturnClaim) -> dict[str, float]:
    """Attribution with the unattributed remainder made explicit as UNVERIFIABLE."""
    out = {k: max(0.0, float(v)) for k, v in c.attribution.items()}
    named = sum(out.values())
    out["UNVERIFIABLE"] = out.get("UNVERIFIABLE", 0.0) + max(0.0, 1.0 - named)
    total = sum(out.values()) or 1.0
    return {k: round(v / total, 4) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def transferable_share(c: ReturnClaim) -> tuple[float, str]:
    """Fraction of the return the desk could actually take with it. THE OPERATIVE NUMBER.

    Beta and leverage are available to anyone with an account and are not achievements to copy.
    Concentration is a sizing decision, not a mechanism. Luck is luck. What is left -- alpha,
    carry, convexity -- is the only part worth a hypothesis.
    """
    d = decompose(c)
    share = sum(v for k, v in d.items() if k in TRANSFERABLE_SOURCES)
    if not c.mechanism.strip():
        return 0.0, (
            f"{c.subject}: no mechanism described, so NOTHING is transferable regardless of the "
            f"attribution ({share:.0%} nominally). A return that cannot be explained cannot be "
            "reproduced even if it was entirely real")
    unver = d.get("UNVERIFIABLE", 0.0)
    return share, (
        f"{c.subject}: {share:.0%} of the reported return is attributed to transferable "
        f"mechanisms ({sorted(TRANSFERABLE_SOURCES)}); {unver:.0%} is UNVERIFIABLE"
        + (". The majority of this result has no attribution at all, which is the finding -- the "
           "desk does not know what produced it" if unver > 0.5 else ""))


def priority(c: ReturnClaim, *, novelty: float = 0.5, capacity_fit: float = 0.5) -> tuple[
        float, str]:
    """Investigation priority. HIGH RETURN RAISES THIS AND NOTHING ELSE.

        P(real) x P(transferable) x log-magnitude x novelty x capacity fit x horizon credibility

    Magnitude enters through a LOG so a claimed 1000% does not outrank a verified 50% by twenty
    times -- the spec's own example, and the reason this is not simply a sort on return.
    """
    p_real = evidence_weight(c)
    share, _ = transferable_share(c)
    g = c.annualised_log
    if g is None or g <= 0:
        return 0.0, (f"{c.subject}: no positive annualised growth computable "
                     f"({c.horizon_days:g}d horizon) -- nothing to prioritise")
    magnitude = math.log1p(max(0.0, g))
    horizon_credibility = min(1.0, c.horizon_days / 365.0)
    score = (p_real * share * magnitude * max(0.0, novelty) * max(0.0, capacity_fit)
             * horizon_credibility)
    return score, (
        f"{c.subject}: P(real) {p_real:.2f} x transferable {share:.2f} x log-magnitude "
        f"{magnitude:.2f} x novelty {novelty:.2f} x capacity {capacity_fit:.2f} x horizon "
        f"credibility {horizon_credibility:.2f} = {score:.4f}. Magnitude enters through a log so "
        "a claimed 1000% cannot outrank a verified 50% by twenty times")


def summarise(claims: list[ReturnClaim]) -> dict[str, object]:
    """Report shape for `data/intelligence/extreme_return_claims.json`."""
    if not claims:
        return {"claims": 0, "headline": (
            "no extreme-return claims recorded. The desk is not currently looking at anyone "
            "who has publicly outperformed it, which makes 'are we competitive' unanswerable")}
    rows = []
    for c in claims:
        score, why = priority(c)
        share, swhy = transferable_share(c)
        rows.append({
            "subject": c.subject, "source": c.source, "observed_at": c.observed_at,
            "evidence_class": c.evidence_class,
            "P_real": round(evidence_weight(c), 3),
            "reported_return": c.reported_return,
            "horizon_days": c.horizon_days,
            "annualised_log": (None if c.annualised_log is None
                               else round(c.annualised_log, 4)),
            "attribution": decompose(c),
            "transferable_share": round(share, 3), "transferable_note": swhy,
            "priority": round(score, 5), "priority_note": why,
            "strategy_family": c.strategy_family,
            "mechanism_recorded": bool(c.mechanism.strip()),
        })
    rows.sort(key=lambda r: -float(str(r["priority"])))
    no_mech = [r for r in rows if not r["mechanism_recorded"]]
    unver = [c for c in claims if decompose(c).get("UNVERIFIABLE", 0.0) > 0.5]
    top = rows[0]
    return {
        "claims": len(claims),
        "rows": rows,
        "top_priority": top["subject"],
        "no_mechanism_recorded": len(no_mech),
        "majority_unverifiable": len(unver),
        "headline": (
            f"top investigation target is {top['subject']} at priority {top['priority']} "
            f"({top['evidence_class']}, {top['transferable_share']:.0%} transferable); "
            f"{len(no_mech)} claim(s) describe no mechanism and are therefore worth nothing to "
            f"copy however large, {len(unver)} are majority UNVERIFIABLE"),
        "note": ("A large return raises investigation URGENCY and never the evidence bar, never "
                 "a validator threshold, and never a leverage allowance. Only the transferable "
                 "share -- alpha, carry, convexity -- reaches the hypothesis factory; beta and "
                 "leverage are available to anyone with an account and are not achievements to "
                 "copy. A claim with no described mechanism has a transferable share of zero by "
                 "construction."),
    }
