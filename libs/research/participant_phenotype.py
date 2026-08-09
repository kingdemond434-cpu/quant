"""PARTICIPANT PHENOTYPE — "retail" is not a cohort, and treating it as one destroys the signal.

THE DEFECT IN THE SINGLE-BUCKET VIEW. Aggregate flow from a broker or an exchange is a sum over
populations that behave in opposite ways. Momentum chasers buy strength; persistent accumulators
buy weakness. Panic sellers and profit takers both sell into a decline for unrelated reasons and
with unrelated forward implications. Add them together and the informative components cancel,
leaving a series that looks like noise -- which is exactly what most published "retail flow"
studies find, and it may be a fact about the aggregation rather than about the participants.

**FOLLOW-RETAIL AND FADE-RETAIL ARE BOTH WRONG, AND FOR THE SAME REASON.** Each asserts a fixed
relationship where the relationship is conditional. The same cohort can lead in one state,
coincide in another and be contrarian in a third, so the object to estimate is a SURFACE
(phenotype x state -> lead/lag/contrarian), not a sign.

**THE MEASUREMENT THAT MUST COME FIRST, AND ALMOST NEVER DOES.** An aggregate can move because the
same people changed behaviour, or because different people arrived. Those have opposite
implications -- the first is information about positioning, the second is information about who is
in the sample -- and they are indistinguishable in the aggregate. `composition_shift` separates
them, and `directionality` refuses to return a verdict when composition moved materially, because
a behavioural reading of a population change is a statement about the wrong thing.

**BEHAVIOUR, NEVER IDENTITY.** Phenotypes are defined by what an account does -- turnover,
response to prior returns, holding persistence. Nothing here uses or infers protected personal
attributes, and the cohort definitions are deliberately expressed as trading statistics.

Estimates and reports. Trades nothing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MAX_COMPOSITION_DRIFT",
    "MIN_COHORT_OBSERVATIONS",
    "PHENOTYPES",
    "RELATIONS",
    "CohortObservation",
    "composition_shift",
    "directionality",
    "summarise",
]

#: Behavioural cohorts, defined by conduct rather than by who anyone is.
PHENOTYPES: tuple[str, ...] = (
    "MOMENTUM_CHASER",          # buys strength, sells weakness
    "PERSISTENT_ACCUMULATOR",   # buys weakness, low turnover
    "PANIC_SELLER",             # sells sharply into declines, re-enters late or not at all
    "PROFIT_TAKER",             # sells into strength
    "LEVERAGE_SEEKER",          # high notional against equity, funding-sensitive
    "HIGH_FREQUENCY_SPECULATOR",  # very high turnover, short holding
    "LOW_TURNOVER_HOLDER",      # rarely transacts
    "CROSS_ASSET_ALLOCATOR",    # rotates between asset classes
)

#: What a cohort's flow can be relative to price. NEUTRAL is a real and common answer.
RELATIONS: tuple[str, ...] = ("LEADING", "COINCIDENT", "LAGGING", "CONTRARIAN", "NEUTRAL")

#: Below this many observations in a (phenotype, state) cell, a relation is a coincidence.
MIN_COHORT_OBSERVATIONS: int = 100

#: Fraction of the cohort mix that may change before an aggregate reading is about the population
#: rather than about behaviour.
MAX_COMPOSITION_DRIFT: float = 0.15


@dataclass(frozen=True)
class CohortObservation:
    """One phenotype's flow in one market state, with the lead/lag evidence attached."""

    phenotype: str
    state: str = ""
    observations: int = 0
    #: Correlation between cohort net flow at t and price return at t+1. Positive = the flow
    #: precedes the move.
    flow_leads_price: float = 0.0
    #: Correlation between cohort net flow at t and price return at t-1. Positive = the flow
    #: FOLLOWS the move, which is reaction and not information.
    flow_follows_price: float = 0.0
    #: Share of the total population this cohort represents, now and at baseline.
    population_share: float = 0.0
    baseline_population_share: float = 0.0
    #: Fraction of accounts in this cohort present in the baseline window too. Low values mean the
    #: cohort is made of different people, not the same people behaving differently.
    account_persistence: float = 1.0

    def __post_init__(self) -> None:
        if self.phenotype not in PHENOTYPES:
            raise ValueError(f"phenotype must be one of {PHENOTYPES}; got {self.phenotype!r}")

    @property
    def measured(self) -> bool:
        return self.observations >= MIN_COHORT_OBSERVATIONS


def composition_shift(obs: list[CohortObservation]) -> tuple[float, bool, str]:
    """(drift, aggregate_is_interpretable, why). RUN THIS BEFORE READING ANY AGGREGATE.

    Total absolute change in cohort mix. Above MAX_COMPOSITION_DRIFT, a change in aggregate flow is
    at least as likely to be a change in WHO is in the sample as a change in what anyone is doing,
    and the two carry opposite implications.
    """
    if not obs:
        return 0.0, False, "no cohort observations -- composition is UNMEASURED"
    drift = sum(abs(o.population_share - o.baseline_population_share) for o in obs) / 2.0
    weak = [o.phenotype for o in obs if o.account_persistence < 0.5]
    ok = drift <= MAX_COMPOSITION_DRIFT and not weak
    return drift, ok, (
        f"cohort mix moved {drift:.1%} against a tolerance of {MAX_COMPOSITION_DRIFT:.0%}"
        + (f"; {weak} are made of largely DIFFERENT accounts than at baseline" if weak else "")
        + (". The aggregate is interpretable as behaviour" if ok else
           ". The aggregate is NOT interpretable as behaviour: a shift this size is at least as "
           "likely to be different people arriving as the same people changing their minds, and "
           "reading it as positioning would be a statement about the wrong thing"))


def directionality(o: CohortObservation, *, composition_ok: bool = True) -> tuple[str, str]:
    """(relation, why). LEADING | COINCIDENT | LAGGING | CONTRARIAN | NEUTRAL, or UNMEASURED.

    NEITHER FOLLOW NOR FADE IS ASSUMED. The relation is read from which correlation dominates, and
    NEUTRAL is returned when neither does -- which is the honest answer for most cohorts in most
    states and the one a directional prior would never produce.
    """
    if not o.measured:
        return "UNMEASURED", (
            f"{o.phenotype} in {o.state or 'unspecified state'}: {o.observations} observation(s) "
            f"against a floor of {MIN_COHORT_OBSERVATIONS}. A lead/lag relation on fewer is a "
            "coincidence with a sign")
    if not composition_ok:
        return "UNMEASURED", (
            f"{o.phenotype}: composition moved materially, so this cohort's flow cannot be read as "
            "behaviour. Whatever changed may be who is in the sample")
    lead, follow = o.flow_leads_price, o.flow_follows_price
    if abs(lead) < 0.05 and abs(follow) < 0.05:
        return "NEUTRAL", (
            f"{o.phenotype} in {o.state or 'unspecified state'}: neither lead ({lead:+.2f}) nor "
            f"lag ({follow:+.2f}) correlation is material. NEUTRAL -- the common answer, and one a "
            "follow-retail or fade-retail prior would never produce")
    if abs(follow) > abs(lead) * 1.5:
        return "LAGGING", (
            f"{o.phenotype} in {o.state or 'unspecified state'}: flow follows price "
            f"({follow:+.2f}) more strongly than it leads it ({lead:+.2f}). This cohort is "
            "REACTING, and reactive behaviour is not alpha however well it correlates")
    if lead <= -0.05:
        return "CONTRARIAN", (
            f"{o.phenotype} in {o.state or 'unspecified state'}: net buying precedes negative "
            f"returns ({lead:+.2f}). Fading this cohort is a candidate hypothesis IN THIS STATE "
            "and carries no implication for any other")
    if lead >= 0.05:
        return "LEADING", (
            f"{o.phenotype} in {o.state or 'unspecified state'}: net flow precedes same-signed "
            f"returns ({lead:+.2f}) more than it follows them ({follow:+.2f}). Candidate "
            "information IN THIS STATE only")
    return "COINCIDENT", (
        f"{o.phenotype}: lead {lead:+.2f} and lag {follow:+.2f} are comparable -- the flow moves "
        "with price and separating cause from effect is not possible from this evidence")


def summarise(obs: list[CohortObservation]) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not obs:
        return {"cohorts": 0, "headline": (
            "no participant observations -- flow on this desk is either unmeasured or aggregated "
            "into a single 'retail' bucket, in which cohorts that behave in opposite ways cancel")}
    drift, ok, dwhy = composition_shift(obs)
    rows = []
    for o in obs:
        rel, why = directionality(o, composition_ok=ok)
        rows.append({"phenotype": o.phenotype, "state": o.state, "relation": rel, "why": why,
                     "observations": o.observations,
                     "flow_leads_price": o.flow_leads_price,
                     "flow_follows_price": o.flow_follows_price,
                     "population_share": o.population_share})
    order = {r: i for i, r in enumerate(("LEADING", "CONTRARIAN", "COINCIDENT", "LAGGING",
                                         "NEUTRAL", "UNMEASURED"))}
    rows.sort(key=lambda r: order[str(r["relation"])])
    informative = [r for r in rows if r["relation"] in ("LEADING", "CONTRARIAN")]
    # THE CANCELLATION CHECK: opposite-signed leading cohorts are exactly what an aggregate hides.
    signs = {math.copysign(1.0, float(str(r["flow_leads_price"]))) for r in informative}
    cancelling = len(signs) > 1
    return {
        "cohorts": len(obs),
        "composition_drift": round(drift, 4),
        "aggregate_interpretable": ok,
        "composition_note": dwhy,
        "rows": rows,
        "informative": len(informative),
        "headline": (
            "composition moved too far to read any cohort as behaviour -- " + dwhy if not ok else
            f"{len(informative)} of {len(rows)} cohort(s) carry candidate information"
            + ("; they lead in OPPOSITE directions, which is precisely what a single aggregated "
               "'retail flow' series would have cancelled to noise" if cancelling else "")
            if informative else
            f"0 of {len(rows)} cohorts are informative; "
            f"{sum(1 for r in rows if r['relation'] == 'UNMEASURED')} are UNMEASURED"),
        "note": ("Follow-retail and fade-retail are both refused: the relation is estimated per "
                 "phenotype PER STATE and NEUTRAL is a common answer. Composition shift is "
                 "measured FIRST -- an aggregate can move because the same people changed "
                 "behaviour or because different people arrived, and those carry opposite "
                 "implications. Cohorts are defined by conduct; no personal attribute is used."),
    }
