"""ASSESS -- one call from arriving bytes to a scored, ledgerable event record.

THE ORDER OF OPERATIONS IS THE ARGUMENT. Classify, then credit, then price, then express, then
score. Importance comes LAST and is a product, which is what makes the desk's refusals arithmetic
rather than remembered:

    importance = P(true) x unpriced_fraction x magnitude / uncertainty_multiplier

Every term can veto. A perfectly credible event that is fully priced scores zero because the
second term is zero. A large measured reaction that no admitted exposure can express scores zero
because there is no magnitude to carry. A contested report is divided by a multiplier above one.
Nobody has to remember to check any of that.

TWO SCORES, AND THEY ARE NOT INTERCHANGEABLE.

    importance     the capital-relevant score. Zero unless every input is MEASURED. This is the
                   only number `interrupt.py` may read.
    triage_score   a monitoring score that survives unmeasured inputs, so a novel, credible event
                   the desk cannot yet price is VISIBLE in the report instead of scoring zero and
                   vanishing. It carries no capital authority and is labelled so in the record.

The distinction matters because the two failure modes are opposite. Letting the capital score
survive missing inputs authorises trades on ignorance. Letting the monitoring score die on missing
inputs makes the desk blind to exactly the events it most needs a human to look at -- the novel
ones.

CAPITAL AUTHORITY IS A CONJUNCTION AND IT IS CHECKED HERE, ONCE. A record earns it only when the
category is known and has sample, the credibility is measured, the unpriced fraction is measured
and positive, there is at least one measured tradeable expression, and the category has survived
point-in-time replay. Any one missing gives `capital_authority=False` and a reason string that
names which. Nothing downstream re-derives this.

THE DESK CAN CONCLUDE "DO NOTHING", AND OFTEN WILL. That is the normal outcome, not the error
path. A headline that sounds bullish for gold while the metal has not moved, the exposure is
unmeasured, and the category has no sample yields importance zero, no capital authority, and one
ledger row -- which is the entire correct response.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .credibility import Claim, CredibilityModel
from .expression import Exposure, express, lexical_drivers
from .factors import FactorBasis, measure_response
from .ledger import EventLedger
from .priced import already_priced
from .priced import estimate as priced_estimate
from .prices import PriceReader, move_sigma
from .schema import EventRecord, PricedEstimate, Status, SurpriseEstimate, now_iso, parse_ts
from .sources import RawItem
from .surprise import Interpretation, interpret, summarise
from .taxonomy import Taxonomy, vectorise

#: The factor move, in sigma, that counts as a full-size event for the magnitude term. Not a
#: threshold for acting -- a normaliser, so magnitude lands in [0, 1] and importance stays
#: comparable across categories. Two sigma is the reference because that is roughly where a
#: measured event response stops looking like an ordinary hour.
MAGNITUDE_REF_SIGMA = 2.0

#: How far after arrival the reaction window is measured when scoring live. Short, because the
#: question at assessment time is "what is the market doing with this NOW"; `attribution.py`
#: measures the long horizon afterwards.
REACTION_WINDOW_S = 900.0

__all__ = ["Assessment", "assess"]


@dataclass(frozen=True)
class Assessment:
    record: EventRecord
    interpretation: Interpretation
    priced: PricedEstimate
    surprise: SurpriseEstimate
    blind_spots: list[dict[str, Any]]

    @property
    def importance(self) -> float:
        return self.record.importance

    @property
    def actionable(self) -> bool:
        return self.record.capital_authority and self.record.importance > 0.0


def assess(item: RawItem, *,
           taxonomy: Taxonomy,
           credibility: CredibilityModel,
           ledger: EventLedger,
           reader: PriceReader,
           basis: FactorBasis,
           exposures: Sequence[Exposure],
           universe: Mapping[str, Mapping[str, Any]],
           aliases: Mapping[str, Sequence[str]],
           source_tier: str = "UNKNOWN",
           source_licence: str = "UNDECLARED",
           source_terms: str = "",
           robots_ok: bool | None = None,
           retrieval: str = "unknown",
           corroborations: Sequence[Claim] = (),
           surprise: SurpriseEstimate | None = None,
           replayed_categories: Sequence[str] = (),
           decay_samples: Mapping[str, Sequence[float]] | None = None,
           recent_vectors: Sequence[dict[int, float]] = (),
           positioning_z: float | None = None,
           liquidity_stress: float | None = None,
           regime_confidence: float | None = None) -> Assessment:
    """Score one arriving item. Never raises on missing data; refuses with a reason instead."""
    text = f"{item.title}. {item.body}".strip()
    t_rec = parse_ts(item.received_at)
    t_pub = parse_ts(item.published_at)

    # 1 -- what kind of thing is this. An answer of UNCLASSIFIED is a real answer.
    assignment = taxonomy.classify(text, known_vectors=recent_vectors)
    stats = ledger.category_stats(assignment.category, decay_samples=decay_samples)

    # 2 -- who says so. The item's own source is always a claim; corroborations and
    # contradictions are handed in by the caller, which is what makes conflict explicit.
    claims = [Claim(item.source_id, True, item.received_at), *corroborations]
    credibility.tier_of.setdefault(item.source_id, source_tier)
    cred = credibility.combine(claims)

    # 3 -- what could carry it. Lexical driver resolution is a READING step: which instruments
    # the text is talking about. The causal work is all in the measured betas.
    drivers_named = lexical_drivers(text, aliases)
    candidates = sorted({*drivers_named, *basis.symbols})[:40]

    # 4 -- how much is already gone. This is the term that can zero everything.
    priced = priced_estimate(reader, symbols=candidates or list(basis.symbols),
                             published_at=item.published_at, received_at=item.received_at,
                             stats=stats)

    # 5 -- what the market is doing with it, measured. The SIGN of everything downstream comes
    # from here and from nowhere else.
    factor_response: dict[str, float] = {}
    driver_moves: dict[str, float] = {}
    if t_rec is not None and basis.status == Status.MEASURED:
        t0 = t_pub or t_rec
        t1 = t_rec + timedelta(seconds=REACTION_WINDOW_S)
        factor_response, _gaps = measure_response(reader, basis, t0=t0, t1=t1)
        for drv in drivers_named:
            val, _ = move_sigma(reader, drv, t0, t1)
            if val is not None:
                driver_moves[drv] = val

    sup = surprise or SurpriseEstimate(None, None, 0, Status.UNMEASURED,
                                       note="no scheduled-release figures attached")
    interp = interpret(
        sup, factor_response,
        unpriced_fraction=priced.unpriced_fraction,
        positioning_z=positioning_z, liquidity_stress=liquidity_stress,
        pre_event_move_sigma=priced.pre_move_sigma, regime_confidence=regime_confidence,
        credibility_uncertainty=cred.uncertainty_mult)

    # 6 -- where the desk can actually put it.
    economies = _economies(text)
    forecasts, blind = express(
        factor_deltas=interp.factor_deltas, basis=basis, drivers_named=drivers_named,
        driver_moves=driver_moves or None, exposures=exposures, universe=universe,
        economies=economies)

    # 7 -- the product, and the conjunction that gates capital.
    magnitude = min(1.0, interp.magnitude / MAGNITUDE_REF_SIGMA)
    measured_forecast = any(f.status == Status.MEASURED for f in forecasts)
    reasons: list[str] = []
    if assignment.category == "UNCLASSIFIED":
        reasons.append("category UNCLASSIFIED (recorded, high uncertainty)")
    if not stats.has_sample:
        reasons.append(f"category has {stats.n_measured} measured reactions "
                       f"(< floor); no conditional estimate is reportable")
    if cred.status != Status.MEASURED:
        reasons.append("source credibility UNMEASURED (on tier prior only)")
    if priced.status != Status.MEASURED:
        reasons.append(f"unpriced fraction {priced.status}: {priced.note}")
    elif (priced.unpriced_fraction or 0.0) <= 0.0:
        reasons.append("fully priced -- the information is behind the market")
    if not measured_forecast:
        reasons.append("no measured tradeable expression")
    if assignment.category not in set(replayed_categories):
        reasons.append("category has not survived point-in-time replay")

    # A MEASURED ZERO IS NOT AN UNKNOWN, and the schema forbids spelling them the same way.
    # "Everything was measured and the answer is do nothing" and "we could not tell" are
    # opposite instructions, and only the first is a finding. `fully_priced_only` is the case
    # where every gate passed except that the market had already absorbed the information --
    # importance is then a hard, reportable zero.
    priced_zero = (priced.status == Status.MEASURED
                   and (priced.unpriced_fraction or 0.0) <= 0.0)
    other_reasons = [r for r in reasons if not r.startswith("fully priced")]
    authorised = not reasons
    if authorised and not already_priced(priced):
        importance = round(
            cred.p_true * float(priced.unpriced_fraction or 0.0) * magnitude
            / max(1.0, cred.uncertainty_mult), 6)
        importance_status = Status.MEASURED
    elif priced_zero and not other_reasons:
        importance = 0.0
        importance_status = Status.MEASURED
    else:
        importance = 0.0
        importance_status = Status.UNMEASURED

    # The monitoring score: deliberately survives missing inputs, deliberately carries no
    # authority. Novelty is weighted because the events worth a human's attention are the ones
    # the desk has never seen.
    triage = round(cred.p_true * (0.5 + 0.5 * (assignment.novelty or 0.0))
                   * (0.25 + 0.75 * magnitude) / max(1.0, cred.uncertainty_mult), 6)

    rec = EventRecord(
        event_id=item.event_id,
        happened_at=item.happened_at, published_at=item.published_at,
        received_at=item.received_at, processed_at=now_iso(),
        source_id=item.source_id, source_tier=source_tier, source_url=item.url,
        licence=source_licence, retrieval=retrieval, robots_ok=robots_ok,
        terms_url=source_terms,
        title=item.title[:400], body_excerpt=item.body[:1200],
        content_hash=item.event_id, language="",
        category=assignment.category, category_status=assignment.status,
        category_similarity=assignment.similarity, novelty=assignment.novelty,
        credibility={"p_true": cred.p_true, "alpha": cred.alpha, "beta": cred.beta,
                     "uncertainty_mult": cred.uncertainty_mult, "contested": cred.contested,
                     "status": cred.status, "basis": cred.basis,
                     "n_verified": cred.n_verified, "n_falsified": cred.n_falsified,
                     "branches": list(cred.branches)},
        confirmed_by=tuple(c.source_id for c in corroborations if c.supports),
        contradicted_by=tuple(c.source_id for c in corroborations if not c.supports),
        economies=tuple(economies), factors=dict(interp.factor_deltas),
        instruments=tuple(f.symbol for f in forecasts),
        decay_half_life_s=stats.decay_half_life_s,
        surprise=summarise(interp, sup),
        priced={"unpriced_fraction": priced.unpriced_fraction,
                "pre_move_sigma": priced.pre_move_sigma, "lag_s": priced.lag_s,
                "method": priced.method, "n": priced.n, "status": priced.status,
                "per_symbol": priced.per_symbol, "note": priced.note},
        forecasts=[{"symbol": f.symbol, "expected_move_sigma": f.expected_move_sigma,
                    "confidence": f.confidence, "path": list(f.path), "n": f.n,
                    "status": f.status} for f in forecasts],
        importance=importance, importance_status=importance_status,
        capital_authority=authorised and not already_priced(priced),
        authority_reason=("; ".join(reasons) if reasons
                          else ("already priced -- abstain" if already_priced(priced)
                                else "all gates measured and passed")),
        extra={"triage_score": triage,
               "triage_note": ("monitoring only -- survives UNMEASURED inputs and carries NO "
                               "capital authority"),
               "drivers_named": drivers_named,
               "blind_spots": blind,
               "reaction_window_s": REACTION_WINDOW_S})
    return Assessment(rec, interp, priced, sup, blind)


#: Currency codes are read from the text only when they appear as standalone uppercase tokens.
#: This is deliberately conservative parsing, not entity resolution: a false economy tag would
#: send the expression step looking for exposures that were never implied.
_CCY_TOKENS = frozenset((
    "USD", "EUR", "JPY", "GBP", "AUD", "NZD", "CAD", "CHF", "CNY", "CNH", "HKD", "SGD",
    "SEK", "NOK", "DKK", "PLN", "HUF", "CZK", "TRY", "ZAR", "MXN", "BRL", "ARS", "CLP",
    "COP", "PEN", "INR", "IDR", "KRW", "TWD", "THB", "PHP", "MYR", "RUB", "ILS", "SAR",
    "AED", "QAR", "NGN", "EGP", "UAH", "RON", "BGN", "ISK",
))


def _economies(text: str) -> list[str]:
    toks = {t for t in text.replace(",", " ").replace(".", " ").split() if t.isupper()}
    return sorted(toks & _CCY_TOKENS)


def recent_vectors(ledger: EventLedger, limit: int = 400) -> list[dict[int, float]]:
    """Vectors of the most recent ledger titles -- the novelty comparison set.

    Bounded because novelty is a question about the RECENT past: an item that resembles nothing
    from the last few hundred events is novel in the sense that matters, even if something like
    it happened in 2019.
    """
    rows = ledger.records()[-limit:]
    return [vectorise(f"{r.title}. {r.body_excerpt}") for r in rows]
