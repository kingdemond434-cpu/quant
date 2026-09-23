"""THE ALLOCATOR-V2 EVIDENCE VECTOR (LAWS 5m, "TWO ALLOCATORS, NEVER ONE OPTIMISER").

The portfolio-capital allocator answers where the next unit of risk, liquidity and balance
sheet goes:

    posterior edge x confidence x regime relevance x diversification x capacity x liquidity
    x execution quality x alpha half-life, less impact, financing stress, common hidden
    exposures, LINEAGE CONCENTRATION and tail risk.

This module is that formula as a NAMED BUNDLE: every term has a name, a measurement (or
UNMEASURED with a reason), a factor, and a declaration of WHERE the allocator already prices it.
Eight of the fourteen terms are priced INSIDE `pf_allocator`'s own arithmetic today (the
posterior, its shrinkage, the macro kernel, the sampled worlds, the capacity ceiling, the
execution under-charge, the decay posterior, the crisis worlds); for those the bundle reports the
measurement and consumes nothing, because charging a term twice is a shrink nobody ordered. The
terms the allocator did NOT price -- research ROI, lineage concentration and financing -- are the
ones it now reads from `data/allocator_evidence.json` and `data/roi_capital_evidence.json`.

HOW THE CONSUMED TERMS ENTER, AND WHY THIS IS NOT A REDUCTION (GROWTH_GOVERNANCE Rules 1 and 2):

  * research ROI and lineage concentration enter as a TILT of the sleeve's posterior mean,
    bounded to [TILT_LO, TILT_HI] around 1.0, two-sided by construction, shrunk toward 1.0 by
    the evidence behind it, and 1.0 exactly when UNMEASURED. Lineage concentration is
    HEAT-NEUTRAL: it is normalised so that the heat-weighted mean tilt across the book is 1.0,
    so a sleeve whose lineage the book already holds is tilted down and a sleeve with a unique
    lineage is tilted UP by the same book -- capital moves BETWEEN sleeves, the total is decided
    upstream by the heat law (20% floor, measured ceiling) and never touched here.
  * financing enters as a SIGNED LEVEL SHIFT of the return series in R per day: a carry credit
    RAISES the posterior mean and a carry debit lowers it, in the exact amount the venue's own
    swap table prices, and only where the replay did not already charge it. It is a cost in the
    objective `E[log(1 + h'R - C)]`, listed in the growth identity's own cost table beside spread
    and commission; an uncosted optimum sizes a quantity the desk cannot buy.

Neither path applies a multiplier outside the solve, neither touches the 20% heat floor, the
0.02-lot gold floor or the daily-loss parameters, and both can RAISE a sleeve.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
DECLARED = "DECLARED"

#: The bound on the consumed tilt of a sleeve's posterior mean -- the same band as the AI
#: capital modifier's categories (STRONG_VETO..STRONG_BOOST are 0.0x..2.0x; this never vetoes).
TILT_LO = 0.5
TILT_HI = 2.0
#: Shrinkage constants: how many judged cells make the ROI rank fully believed, and how much of
#: a same-lineage share is charged before normalisation.
K_ROI = 40.0
KAPPA_LINEAGE = 0.5
#: How stale the lab's evidence may be before the allocator reads it as neutral.
MAX_AGE_S = 26 * 3600


@dataclass(frozen=True)
class TermSpec:
    name: str
    #: "factor" multiplies; "deduction" is a share in [0, 1) folded in as (1 - share)
    role: str
    #: True when pf_allocator already prices this term from returns; the bundle then reports it
    #: and consumes nothing
    priced_inside_allocator: bool
    where: str
    consumed_as: str = ""


TERM_SPECS: tuple[TermSpec, ...] = (
    TermSpec("posterior_edge", "factor", True,
             "robust_elog._posterior_mu: the hierarchical posterior of the sleeve's mean R/day"),
    TermSpec("confidence", "factor", True,
             "robust_elog._posterior_mu: n/(n+k) shrinkage weighted 4x forward, 12x live days"),
    TermSpec("regime_relevance", "factor", True,
             "SleeveEvidence.macro_w: the macro kernel's regime-weighted contrast"),
    TermSpec("diversification", "factor", True,
             "robust_elog.sample_worlds: the sampled worlds carry the book's covariance"),
    TermSpec("capacity", "factor", True,
             "pf_allocator._capacity_ceiling <- reports/CAPACITY.json"),
    TermSpec("liquidity", "factor", True,
             "libs.portfolio.execution_cost: spread at the sleeve's own fill hour"),
    TermSpec("execution_quality", "factor", True,
             "SleeveEvidence.cost_bias_r: the measured execution under-charge"),
    TermSpec("alpha_half_life", "factor", True,
             "SleeveEvidence.decay_prob_i <- drift_monitor hazard"),
    TermSpec("research_roi", "factor", False,
             "data/roi_capital_evidence.json (research_roi, per mechanism)",
             consumed_as="tilt of the posterior mean, bounded, shrunk by judged count"),
    TermSpec("impact", "deduction", True,
             "reports/CAPACITY.json ceiling (UNMEASURED until matched fills exist)"),
    TermSpec("financing_stress", "deduction", False,
             "libs.portfolio.financing: the venue's swap table, nights from the sleeve's ledger",
             consumed_as="signed level shift of the return series in R/day where not charged"),
    TermSpec("common_hidden_exposures", "deduction", True,
             "SleeveEvidence.factor_load / heat_policy.effective_ceiling"),
    TermSpec("lineage_concentration", "deduction", False,
             "family/symbol-legs/timeframe lineage of the funded book "
             "(libs/research/feature_genome.py when it lands)",
             consumed_as="heat-neutral tilt of the posterior mean, bounded"),
    TermSpec("tail_risk", "deduction", True,
             "robust_elog crisis worlds / kelly_surface.envelope"),
    # THE THREE W11 TERMS (2026-09-22): published for months and read by nothing.
    TermSpec("forward_posterior_prior", "factor", False,
             "reports/POSTERIOR_ALPHA.json (hierarchical forward posterior, family-pooled)",
             consumed_as="heat-neutral rank tilt of the posterior mean, shrunk by forward n"),
    TermSpec("marginal_breadth", "factor", False,
             "reports/POSTERIOR_ALPHA.json rho_book (incremental P&L independence)",
             consumed_as="heat-neutral tilt by independence relative to the book's mean"),
    TermSpec("factor_tier", "deduction", False,
             "reports/EXPOSURE_DECOMPOSITION.json (cosine with the book's factor exposure)",
             consumed_as="heat-neutral tilt: a sleeve repeating the book's direction moves down"),
    # DOOR (c) OF THE NET-EDGE SPINE (2026-09-23). Every other term above prices the sleeve's
    # GROSS behaviour; this one prices what is left after the spread, the impact, the financing,
    # the commission and the multiplicity charge the desk already owes. It is a heat-neutral
    # TILT -- it moves the book toward the sleeves that survive their own costs and it cannot
    # change the total, which is what makes it legal under GROWTH GOVERNANCE rule 1.
    TermSpec("net_of_cost", "factor", False,
             "reports/NET_EDGE.json (net = gross - spread/slippage - impact - financing - "
             "commission - multiplicity), with the sleeve's capacity beside it",
             consumed_as="heat-neutral tilt by net-of-cost edge relative to the book's mean"),
)
SPEC_BY_NAME: dict[str, TermSpec] = {s.name: s for s in TERM_SPECS}
CONSUMED_TILT_TERMS: tuple[str, ...] = ("research_roi", "lineage_concentration",
                                        "forward_posterior_prior", "marginal_breadth",
                                        "factor_tier", "net_of_cost")


@dataclass(frozen=True)
class Term:
    name: str
    value: float | None
    status: str
    #: the multiplicative factor this term contributes; 1.0 when UNMEASURED, always
    factor: float = 1.0
    source: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        spec = SPEC_BY_NAME.get(self.name)
        return {"value": (None if self.value is None or not math.isfinite(self.value)
                          else round(self.value, 8)),
                "status": self.status, "factor": round(self.factor, 6),
                "role": spec.role if spec else "", "source": self.source, "note": self.note,
                "priced_inside_allocator": bool(spec.priced_inside_allocator) if spec else False,
                "consumed": bool(spec and not spec.priced_inside_allocator and self.status
                                 != UNMEASURED)}


def neutral(name: str, why: str) -> Term:
    """An UNMEASURED term: factor exactly 1.0, with the reason it could not be measured."""
    return Term(name, None, UNMEASURED, 1.0, "", why)


def descriptive(name: str, value: float, source: str, note: str = "") -> Term:
    """A term the allocator already prices inside its own arithmetic: reported, factor 1.0."""
    return Term(name, float(value), MEASURED, 1.0, source, note or "priced inside the allocator")


@dataclass(frozen=True)
class EvidenceVector:
    sleeve: str
    terms: dict[str, Term] = field(default_factory=dict)
    family: str = ""
    symbol: str = ""
    lineage: str = ""
    #: financing in R per day, POSITIVE IS A COST; None when UNMEASURED
    financing_cost_r_per_day: float | None = None
    #: whether the sleeve's return series already carries the swap: True / False / None
    financing_charged_in_replay: bool | None = None

    def term(self, name: str) -> Term:
        return self.terms.get(name) or neutral(name, "term not built")

    def composite(self) -> float:
        """Every term's factor multiplied: the law's product, 1.0 when nothing is measured."""
        out = 1.0
        for spec in TERM_SPECS:
            out *= self.term(spec.name).factor
        return float(out)

    def consumed_tilt(self) -> float:
        """The tilt the allocator reads: the consumed factor terms only, bounded."""
        out = 1.0
        for name in CONSUMED_TILT_TERMS:
            out *= self.term(name).factor
        return float(min(TILT_HI, max(TILT_LO, out)))

    def n_measured(self) -> int:
        return sum(1 for s in TERM_SPECS if self.term(s.name).status != UNMEASURED)

    def as_dict(self) -> dict[str, Any]:
        return {"sleeve": self.sleeve, "family": self.family, "symbol": self.symbol,
                "lineage": self.lineage,
                "terms": {s.name: self.term(s.name).as_dict() for s in TERM_SPECS},
                "composite": round(self.composite(), 6),
                "consumed_tilt": round(self.consumed_tilt(), 6),
                "lineage_factor": round(self.term("lineage_concentration").factor, 6),
                "roi_factor": round(self.term("research_roi").factor, 6),
                "financing_cost_r_per_day": self.financing_cost_r_per_day,
                "financing_charged_in_replay": self.financing_charged_in_replay,
                "n_measured": self.n_measured(), "n_terms": len(TERM_SPECS)}


# ---------------------------------------------------------------------------- term builders


def roi_factor(row: Mapping[str, Any] | None, measured_rois: Sequence[float]) -> Term:
    """Research-ROI prior for one mechanism: a rank among MEASURED mechanisms, shrunk by count.

    factor = 1 + lam x (2 x pct_rank - 1) x 0.5, lam = judged / (judged + K_ROI): the best
    mechanism of many judged cells reads up to 1.5x, the worst down to 0.5x, one with few judged
    cells barely moves, and one whose ROI is UNMEASURED (or with fewer than two measured peers to
    rank against) reads exactly 1.0. NEGATIVE_KNOWLEDGE ranks at the bottom by definition.
    """
    if not row:
        return neutral("research_roi", "mechanism absent from roi_capital_evidence.json")
    status = str(row.get("roi_status") or UNMEASURED)
    roi = row.get("roi")
    try:
        roi_f = float(roi) if roi is not None else None
    except (TypeError, ValueError):
        roi_f = None
    if status != MEASURED or roi_f is None or not math.isfinite(roi_f):
        return neutral("research_roi", f"roi_status {status}")
    peers = [x for x in measured_rois if math.isfinite(x)]
    if len(peers) < 2:
        return neutral("research_roi", "fewer than two measured mechanisms to rank against")
    below = sum(1 for x in peers if x < roi_f)
    equal = sum(1 for x in peers if x == roi_f)
    pct = (below + 0.5 * max(equal - 1, 0)) / max(len(peers) - 1, 1)
    if str(row.get("verdict")) == "NEGATIVE_KNOWLEDGE":
        pct = 0.0
    try:
        judged = float(row.get("judged") or 0.0)
    except (TypeError, ValueError):
        judged = 0.0
    lam = judged / (judged + K_ROI) if judged > 0 else 0.0
    factor = 1.0 + lam * (2.0 * pct - 1.0) * 0.5
    return Term("research_roi", roi_f, MEASURED, float(min(1.5, max(0.5, factor))),
                "data/roi_capital_evidence.json",
                f"rank {pct:.2f} among {len(peers)} measured mechanisms, judged {judged:.0f}, "
                f"lam {lam:.2f}")


def match_mechanism(sleeve: str, family: str, mechanisms: Sequence[str]) -> str | None:
    """The longest mechanism key the sleeve's family or name carries; None when none does."""
    fam = (family or "").lower()
    name = (sleeve or "").lower()
    best: str | None = None
    for m in mechanisms:
        k = str(m).lower()
        if not k or k in ("unknown", "generic"):
            continue
        hit = fam == k or fam.startswith(k + "_") or f"_{k}_" in f"_{name}_"
        if hit and (best is None or len(k) > len(best)):
            best = str(m)
    return best


def lineage_key(family: str, symbol: str, legs: Sequence[str] | None, timeframe: str) -> str:
    """family | sorted legs (or symbol) | timeframe: what two sleeves share when they are one."""
    leg_txt = "+".join(sorted(str(x).upper() for x in legs if x)) if legs else symbol.upper()
    return f"{(family or 'unspecified').lower()}|{leg_txt}|{(timeframe or '?').upper()}"


def lineage_shares(book: Mapping[str, float], lineage_of: Mapping[str, str]
                   ) -> dict[str, float]:
    """Per sleeve: the share of the book's heat held by its lineage (the sleeve included).

    A candidate outside the book (heat 0) reads the share its lineage already holds, so two
    sleeves that are one bet see the same concentration whichever of them is asked.
    """
    total = sum(max(float(h), 0.0) for h in book.values())
    out: dict[str, float] = {}
    for name, lin in lineage_of.items():
        if total <= 0:
            out[name] = 0.0
            continue
        same = sum(max(float(h), 0.0) for other, h in book.items()
                   if lineage_of.get(other) == lin)
        out[name] = same / total
    return out


def lineage_factors(book: Mapping[str, float], lineage_of: Mapping[str, str]
                    ) -> dict[str, Term]:
    """Heat-neutral lineage tilt per sleeve: raw 1 - kappa x share, normalised to mean 1.0.

    The normaliser is the HEAT-WEIGHTED mean of the raw factors over the funded book, so the
    tilt moves capital between lineages and leaves the total where the heat law put it. A book
    with one lineage everywhere normalises back to exactly 1.0 for every sleeve: concentration
    the whole book shares is not a reason to shrink the whole book.
    """
    shares = lineage_shares(book, lineage_of)
    raw = {n: 1.0 - KAPPA_LINEAGE * s for n, s in shares.items()}
    w = {n: max(float(book.get(n, 0.0)), 0.0) for n in raw}
    tw = sum(w.values())
    mean = (sum(raw[n] * w[n] for n in raw) / tw) if tw > 0 else 1.0
    out: dict[str, Term] = {}
    for n, r in raw.items():
        f = r / mean if mean > 0 else 1.0
        out[n] = Term("lineage_concentration", shares[n], MEASURED,
                      float(min(TILT_HI, max(TILT_LO, f))), "funded book lineage",
                      f"same-lineage share {shares[n]:.3f} of book heat; raw {r:.3f} / "
                      f"book mean {mean:.3f}")
    return out


# --------------------------------------------------------------------- Tier-1 W11 tilts
#: THE THREE TERMS W11 NAMED AND NOTHING READ (measured 2026-09-16: "posterior_alpha and
#: exposure_decomposition are published but not yet read by the world sampler; the marginal-
#: breadth admission is a research credit, not an allocator tier"). Each is a HEAT-NEUTRAL tilt
#: of the sleeve's posterior mean: the raw factors are divided by their own mean across the
#: sleeves that carry them, so the tilt moves capital BETWEEN sleeves and the total the heat law
#: resolved (20% floor, measured ceiling) is untouched -- nothing here can shrink the book.
#: Each is TWO-SIDED by construction: a sleeve with the stronger forward posterior, the more
#: orthogonal factor exposure or the more independent return stream is tilted UP by exactly the
#: amount its peers are tilted down (GROWTH_GOVERNANCE Rule 2).
KAPPA_POSTERIOR = 0.5
KAPPA_FACTOR_TIER = 0.5
KAPPA_BREADTH = 0.5
#: Forward observations at which the posterior tilt is fully believed; below it the tilt is
#: shrunk toward 1.0 by n/(n+K), so one lucky week never reallocates the book.
K_POSTERIOR_N = 20.0


def _heat_neutral(raw: Mapping[str, float]) -> dict[str, float]:
    """`raw` divided by its own mean and clipped to the tilt band: mean 1.0 by construction.

    A book where every sleeve carries the same raw value normalises back to exactly 1.0 for
    every sleeve -- a property the whole book shares is not a reason to move the whole book.
    """
    vals = [float(v) for v in raw.values() if math.isfinite(float(v))]
    mean = (sum(vals) / len(vals)) if vals else 1.0
    if not math.isfinite(mean) or mean <= 0:
        return dict.fromkeys(raw, 1.0)
    return {n: float(min(TILT_HI, max(TILT_LO, float(v) / mean))) for n, v in raw.items()}


def _sleeve_rows(doc: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = (doc or {}).get("sleeves") if isinstance(doc, Mapping) else None
    if not isinstance(rows, list):
        return []
    out: list[Mapping[str, Any]] = []
    for r in rows:
        if isinstance(r, Mapping) and r.get("name"):
            out.append(r)
    return out


def posterior_prior_factors(doc: Mapping[str, Any] | None
                            ) -> tuple[dict[str, Term], str]:
    """The forward posterior `posterior_alpha` publishes, as a heat-neutral tilt per sleeve.

    NOT A SECOND CHARGE OF THE ALLOCATOR'S OWN POSTERIOR. `robust_elog._posterior_mu` shrinks
    the sleeve's OWN daily series toward a no-edge prior and knows nothing else;
    `posterior_alpha` publishes a HIERARCHICAL posterior -- pooled across the sleeve's family,
    across the shadow/forward/live lanes, with the hazard's decay probability -- which is a
    different estimator over different evidence. It enters as a rank tilt around the book's own
    mean, shrunk by the sleeve's forward count, so it reallocates and never levers.
    """
    rows = _sleeve_rows(doc)
    if not rows:
        return {}, "POSTERIOR_ALPHA.json absent or carries no sleeve: every tilt neutral"
    mus: dict[str, float] = {}
    ns: dict[str, float] = {}
    for r in rows:
        mu = r.get("mu_shrunk_family", r.get("mu_mean"))
        try:
            val = float(mu)
        except (TypeError, ValueError):
            continue
        if math.isfinite(val):
            mus[str(r["name"])] = val
            try:
                ns[str(r["name"])] = float(r.get("n") or 0.0)
            except (TypeError, ValueError):
                ns[str(r["name"])] = 0.0
    if len(mus) < 2:
        return {}, (f"POSTERIOR_ALPHA.json prices {len(mus)} sleeve(s): a rank tilt needs two, "
                    "every tilt neutral")
    vals = list(mus.values())
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1)
    sd = math.sqrt(var)
    out: dict[str, Term] = {}
    raw: dict[str, float] = {}
    for name, mu in mus.items():
        z = (mu - mean) / sd if sd > 0 else 0.0
        shrink = ns[name] / (ns[name] + K_POSTERIOR_N) if ns[name] >= 0 else 0.0
        raw[name] = 1.0 + KAPPA_POSTERIOR * shrink * math.tanh(z)
    tilts = _heat_neutral(raw)
    for name, mu in mus.items():
        out[name] = Term("forward_posterior_prior", mu, MEASURED, tilts[name],
                         "reports/POSTERIOR_ALPHA.json",
                         f"family-shrunk posterior {mu:+.6f} R/day against a book mean of "
                         f"{mean:+.6f} on n={ns[name]:.0f} forward observation(s)")
    return out, (f"POSTERIOR_ALPHA.json read: {len(out)} sleeve(s), book mean {mean:+.6f} "
                 f"R/day, sd {sd:.6f}")


def marginal_breadth_factors(doc: Mapping[str, Any] | None) -> tuple[dict[str, Term], str]:
    """Marginal effective breadth, from the correlation to the book `posterior_alpha` measures.

    The admission question the item asks is incremental P&L INDEPENDENCE, not profit: a sleeve
    whose returns the book already owns adds one more copy of a bet it holds, and a sleeve the
    book is uncorrelated with adds a bet. `rho_book` is the desk's only DATE-ALIGNED correlation
    of a sleeve to its book (the organ that computes it holds the dates), so independence is
    1 - rho and the tilt is that independence relative to the book's own mean independence.
    """
    rows = _sleeve_rows(doc)
    indep: dict[str, float] = {}
    for r in rows:
        rho = r.get("rho_book")
        try:
            val = float(rho)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if math.isfinite(val):
            indep[str(r["name"])] = float(min(2.0, max(0.0, 1.0 - val)))
    if len(indep) < 2:
        return {}, (f"POSTERIOR_ALPHA.json carries rho_book for {len(indep)} sleeve(s): a "
                    "marginal-breadth tilt needs two, every tilt neutral")
    mean = sum(indep.values()) / len(indep)
    raw = {n: 1.0 + KAPPA_BREADTH * ((v / mean) - 1.0) if mean > 0 else 1.0
           for n, v in indep.items()}
    tilts = _heat_neutral(raw)
    return ({n: Term("marginal_breadth", indep[n], MEASURED, tilts[n],
                     "reports/POSTERIOR_ALPHA.json rho_book",
                     f"independence {indep[n]:.3f} against a book mean of {mean:.3f}")
             for n in indep},
            f"marginal breadth read for {len(indep)} sleeve(s); mean independence {mean:.3f}")


def factor_tier_factors(doc: Mapping[str, Any] | None) -> tuple[dict[str, Term], str]:
    """`exposure_decomposition`'s factor tier: how much of the BOOK's exposure a sleeve repeats.

    The cosine between the sleeve's twelve-factor exposure vector and the book's own is the
    share of the book's direction the sleeve is another copy of. A sleeve pointing where the
    book already points is tilted down and one pointing somewhere else is tilted UP by the same
    book; a sleeve whose exposures are unmeasured is exactly neutral.
    """
    rows = [r for r in _sleeve_rows(doc) if isinstance(r.get("exposures"), Mapping)]
    book = (doc or {}).get("book") if isinstance(doc, Mapping) else None
    if not rows or not isinstance(book, Mapping) or not book:
        return {}, "EXPOSURE_DECOMPOSITION.json absent or carries no book: every tilt neutral"
    names = sorted({str(k) for k in book})
    bvec = [float(book.get(k) or 0.0) for k in names]
    bnorm = math.sqrt(sum(v * v for v in bvec))
    if bnorm <= 0:
        return {}, "EXPOSURE_DECOMPOSITION.json book exposure is all zero: every tilt neutral"
    cos: dict[str, float] = {}
    for r in rows:
        exp = r["exposures"]
        svec = [float(exp.get(k) or 0.0) for k in names]
        snorm = math.sqrt(sum(v * v for v in svec))
        if snorm <= 0:
            continue
        dot = sum(a * b for a, b in zip(svec, bvec, strict=True))
        cos[str(r["name"])] = float(min(1.0, max(-1.0, dot / (snorm * bnorm))))
    if len(cos) < 2:
        return {}, (f"EXPOSURE_DECOMPOSITION.json prices {len(cos)} sleeve exposure vector(s): "
                    "a factor tier needs two, every tilt neutral")
    raw = {n: 1.0 - KAPPA_FACTOR_TIER * max(0.0, c) for n, c in cos.items()}
    tilts = _heat_neutral(raw)
    return ({n: Term("factor_tier", cos[n], MEASURED, tilts[n],
                     "reports/EXPOSURE_DECOMPOSITION.json",
                     f"cosine {cos[n]:+.3f} with the book's factor exposure over "
                     f"{len(names)} factor(s)")
             for n in cos},
            f"EXPOSURE_DECOMPOSITION.json read: {len(cos)} sleeve(s) over {len(names)} factors")


def net_of_cost_factors(doc: Mapping[str, Any] | None
                        ) -> tuple[dict[str, Term], str]:
    """DOOR (c): the sleeve's edge AFTER every cost it pays, as a heat-neutral tilt.

    `desks/mt5/research/net_edge_spine.py` publishes `capacity_by_sleeve` in NET_EDGE.json: net,
    gross, the verdict, and the CAPACITY (the size at which net decays to zero). The tilt is
    each sleeve's net relative to the book's mean net, made heat-neutral by `_heat_neutral` so
    the product over the funded book is exactly 1.0 -- this reorders the book and can never
    shrink it (GROWTH GOVERNANCE rule 1; the missed-growth line for every COST_DEAD refusal is
    in the spine's own report).

    A sleeve the spine could not price is NEUTRAL WITH THE REASON, never a factor of 1.0 that
    silently claims it trades for free.
    """
    rows = (doc.get("capacity_by_sleeve") if isinstance(doc, Mapping) else None) or {}
    nets: dict[str, float] = {}
    why_by: dict[str, str] = {}
    for name, row in rows.items() if isinstance(rows, Mapping) else []:
        if not isinstance(row, Mapping):
            continue
        value = row.get("net")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            nets[str(name)] = float(value)
        else:
            why_by[str(name)] = str(row.get("verdict") or UNMEASURED)
    if len(nets) < 2:
        return {}, (f"NET_EDGE.json prices {len(nets)} sleeve net-of-cost edge(s): a tilt needs "
                    "two, so every sleeve reads neutral and nothing is re-weighted")
    mean = sum(nets.values()) / len(nets)
    if mean > 0:
        raw = {n: min(TILT_HI, max(TILT_LO, v / mean)) for n, v in nets.items()}
        basis = "ratio to the book's mean net"
    else:
        # A BOOK WHOSE MEAN NET IS AT OR BELOW ZERO CANNOT BE TILTED BY A RATIO -- the sign of
        # the denominator would invert the order and hand the WORST sleeve the largest factor.
        # The percentile rank of the net answers the same question without a denominator, is
        # two-sided by construction, and still moves capital toward the sleeves that survive
        # their own costs. It is never a neutral 1.0 for everyone: a book paying more than it
        # earns is exactly the book this term exists to reorder.
        order = sorted(nets, key=lambda k: nets[k])
        last = max(len(order) - 1, 1)
        raw = {name: TILT_LO + (TILT_HI - TILT_LO) * (i / last)
               for i, name in enumerate(order)}
        basis = "percentile rank of the net (the book's mean net is at or below zero)"
    tilts = _heat_neutral(raw)
    out: dict[str, Term] = {}
    for name, value in nets.items():
        cap = (rows.get(name) or {}).get("capacity") or {}
        lots, cap_status = cap.get("lots"), cap.get("status", UNMEASURED)
        out[name] = Term("net_of_cost", value, MEASURED, tilts[name], "reports/NET_EDGE.json",
                         f"net {value:+.6f} vs book mean {mean:+.6f}; capacity "
                         + (f"{lots} lots ({cap_status})" if lots is not None
                            else f"{cap_status}: {str(cap.get('why') or '')[:120]}"))
    for name, verdict in why_by.items():
        out[name] = neutral("net_of_cost",
                            f"NET_EDGE.json carries no net for this sleeve ({verdict})")
    return out, (f"NET_EDGE.json read: {len(nets)} sleeve(s) priced net of cost, book mean net "
                 f"{mean:+.6f}; tilt basis {basis}; heat-neutral, so it reallocates only")


def net_capacity_rows(doc: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Per-sleeve CAPACITY -- the size at which net edge decays to zero -- for the bundle.

    The allocator sizes on what the book can actually CARRY, not on what the edge would be at
    an unreachable size. An UNMEASURED capacity is published with its reason and is never read
    as unlimited: that reading is the one a book gets margin-called for.
    """
    rows = (doc.get("capacity_by_sleeve") if isinstance(doc, Mapping) else None) or {}
    out: dict[str, dict[str, Any]] = {}
    for name, row in rows.items() if isinstance(rows, Mapping) else []:
        if not isinstance(row, Mapping):
            continue
        cap = row.get("capacity") or {}
        out[str(name)] = {"lots": cap.get("lots") if isinstance(cap, Mapping) else None,
                          "status": (cap.get("status") if isinstance(cap, Mapping)
                                     else UNMEASURED),
                          "why": cap.get("why") if isinstance(cap, Mapping) else "",
                          "net": row.get("net"), "gross": row.get("gross"),
                          "verdict": row.get("verdict")}
    return out


def financing_term(cost_r_per_trade: float | None, trades_per_day: float | None,
                   edge_r_per_trade: float | None, *, why: str = "") -> Term:
    """Financing stress: the sleeve's swap as a share of its edge, and the R/day it costs.

    `value` is the cost in R PER DAY (positive is a cost). The factor is DESCRIPTIVE (1.0): the
    consumption is the level shift, and folding the share in here as well would charge it twice.
    """
    if cost_r_per_trade is None or trades_per_day is None:
        return neutral("financing_stress", why or "no measured swap charge for this sleeve")
    per_day = float(cost_r_per_trade) * float(trades_per_day)
    share = (abs(per_day) / (abs(edge_r_per_trade * trades_per_day))
             if edge_r_per_trade else None)
    note = (f"swap {cost_r_per_trade:+.5f} R/trade x {trades_per_day:.3f} trades/day"
            + (f"; {share:.1%} of the edge" if share is not None else ""))
    return Term("financing_stress", per_day, MEASURED, 1.0,
                "libs.portfolio.financing <- SWAP_REJUDGE / contract terms", note)


# ---------------------------------------------------------------------------- the bundles


def build_vector(sleeve: str, *, family: str, symbol: str, lineage: str,
                 lineage_term: Term | None, roi_term: Term | None,
                 financing: Term | None, financing_charged_in_replay: bool | None,
                 descriptive_terms: Mapping[str, Term] | None = None) -> EvidenceVector:
    terms: dict[str, Term] = {}
    for spec in TERM_SPECS:
        terms[spec.name] = neutral(spec.name, "not measured on this pass")
    for name, t in (descriptive_terms or {}).items():
        if name in SPEC_BY_NAME:
            terms[name] = t
    if lineage_term is not None:
        terms["lineage_concentration"] = lineage_term
    if roi_term is not None:
        terms["research_roi"] = roi_term
    if financing is not None:
        terms["financing_stress"] = financing
    fin = terms["financing_stress"]
    return EvidenceVector(sleeve=sleeve, terms=terms, family=family, symbol=symbol,
                          lineage=lineage,
                          financing_cost_r_per_day=(fin.value if fin.status == MEASURED
                                                    else None),
                          financing_charged_in_replay=financing_charged_in_replay)


def book_vector(vectors: Sequence[EvidenceVector], book: Mapping[str, float]) -> dict[str, Any]:
    """The book's own bundle: heat-weighted composite and tilt, lineage HHI, term coverage."""
    tw = 0.0
    comp = 0.0
    tilt = 0.0
    for v in vectors:
        h = max(float(book.get(v.sleeve, 0.0)), 0.0)
        tw += h
        comp += h * v.composite()
        tilt += h * v.consumed_tilt()
    lin_heat: dict[str, float] = {}
    for v in vectors:
        h = max(float(book.get(v.sleeve, 0.0)), 0.0)
        if h > 0:
            lin_heat[v.lineage] = lin_heat.get(v.lineage, 0.0) + h
    hhi = (sum((h / tw) ** 2 for h in lin_heat.values()) if tw > 0 else None)
    coverage: dict[str, int] = {}
    for spec in TERM_SPECS:
        coverage[spec.name] = sum(1 for v in vectors if v.term(spec.name).status != UNMEASURED)
    return {"n_sleeves": len(vectors), "funded_heat": round(tw, 6),
            "heat_weighted_composite": (round(comp / tw, 6) if tw > 0 else None),
            "heat_weighted_consumed_tilt": (round(tilt / tw, 6) if tw > 0 else None),
            "lineage_hhi": (None if hhi is None else round(hhi, 6)),
            "n_lineages_funded": len(lin_heat), "terms_measured_by_name": coverage}


# ---------------------------------------------------------------------- the consumer's read


def _age_s(doc: Mapping[str, Any], now: datetime | None) -> float | None:
    at = doc.get("at") or doc.get("generated_utc")
    if not at:
        return None
    try:
        t = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - t).total_seconds()


def consumed_inputs(doc: Mapping[str, Any] | None, *, now: datetime | None = None,
                    max_age_s: float = MAX_AGE_S) -> tuple[dict[str, dict[str, Any]], str]:
    """What pf_allocator reads from `allocator_evidence.json`: per sleeve, the lineage factor,
    the financing R/day (cost positive) and whether the replay charged it. Absent, malformed or
    stale documents read as NOTHING with the reason, which the allocator treats as neutral."""
    if not doc or not isinstance(doc, Mapping):
        return {}, "allocator_evidence.json absent or unreadable: every term neutral"
    if doc.get("kind") != "evidence":
        return {}, f"allocator_evidence.json kind={doc.get('kind')!r} is not 'evidence'"
    age = _age_s(doc, now)
    if age is None:
        return {}, "allocator_evidence.json carries no readable timestamp"
    if age > max_age_s:
        return {}, f"allocator_evidence.json is {age / 3600:.1f}h old (> {max_age_s / 3600:.0f}h)"
    sleeves = doc.get("sleeves")
    if not isinstance(sleeves, Mapping):
        return {}, "allocator_evidence.json has no sleeves block"
    out: dict[str, dict[str, Any]] = {}
    for name, row in sleeves.items():
        if not isinstance(row, Mapping):
            continue
        try:
            lf = float(row.get("lineage_factor", 1.0))
        except (TypeError, ValueError):
            lf = 1.0
        if not math.isfinite(lf):
            lf = 1.0
        fin = row.get("financing_cost_r_per_day")
        try:
            fin_f: float | None = float(fin) if fin is not None else None
        except (TypeError, ValueError):
            fin_f = None
        if fin_f is not None and not math.isfinite(fin_f):
            fin_f = None
        charged = row.get("financing_charged_in_replay")
        out[str(name)] = {"lineage_factor": float(min(TILT_HI, max(TILT_LO, lf))),
                          "financing_cost_r_per_day": fin_f,
                          "financing_charged_in_replay": (None if charged is None
                                                          else bool(charged))}
    return out, f"allocator_evidence.json read: {len(out)} sleeve(s), {age / 60:.0f} min old"


def roi_factors_by_mechanism(roi_doc: Mapping[str, Any] | None) -> tuple[dict[str, Term], str]:
    """Per mechanism: the ROI prior term. Absent or malformed reads as nothing, with the why."""
    if not roi_doc or not isinstance(roi_doc, Mapping):
        return {}, "roi_capital_evidence.json absent or unreadable: ROI prior neutral"
    if roi_doc.get("kind") != "evidence":
        return {}, f"roi_capital_evidence.json kind={roi_doc.get('kind')!r} is not 'evidence'"
    by_mech = roi_doc.get("by_mechanism")
    if not isinstance(by_mech, Mapping):
        return {}, "roi_capital_evidence.json has no by_mechanism block"
    measured_rois: list[float] = []
    for row in by_mech.values():
        if isinstance(row, Mapping) and row.get("roi_status") == MEASURED:
            try:
                x = float(row.get("roi"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            if math.isfinite(x):
                measured_rois.append(x)
    out = {str(m): roi_factor(row if isinstance(row, Mapping) else None, measured_rois)
           for m, row in by_mech.items()}
    return out, (f"roi_capital_evidence.json read: {len(out)} mechanism(s), "
                 f"{len(measured_rois)} measured")
