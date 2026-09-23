"""NET IS THE CURRENCY: one edge-after-every-cost function every stage of the desk calls.

The principal's order is an institution that trades all global public information for "maximum
edge possible of NET". Until this module the desk ranked, judged and allocated on GROSS
statistics and priced costs in separate organs -- `cost_surface` knew the spread, `impact_lab`
knew the impact, `financing` knew the swap, `fusion_cost` knew the commission and the gauntlet
knew the multiplicity charge -- and no single number carried all five at once. A candidate could
therefore be ranked first on a figure nobody had ever paid.

    net = gross
        - spread/slippage at the cell's OWN size and state
        - market impact at that size
        - financing and swap carry over the holding period
        - commission
        - the multiplicity charge already owed

THE ONE RULE THIS MODULE EXISTS TO ENFORCE: an UNMEASURED term is never a zero. A cost that
could not be measured makes the row's net a BOUND and not a figure, and the verdict says so.
Five of the six terms can only ever reduce the edge, so a bound that is already negative is a
finding; financing alone is signed (a swap can be a credit), so a negative bound with financing
unpriced is COST_DEAD_UNCONFIRMED and not COST_DEAD. That asymmetry is the whole honesty of the
thing: it lets the desk act on what it knows without pretending it knows the rest.

GROWTH GOVERNANCE (docs/GROWTH_GOVERNANCE.md, rules 1 and 2). Nothing here is a veto, a cap or
a shrink. `reweight_preserving_heat` moves heat TOWARD higher net and returns a book with
exactly the heat it was given -- the refusal of a COST_DEAD cell frees heat for the rest of the
book rather than retiring it -- and every COST_DEAD verdict carries a `missed_growth_line` so
the refusal is billed in forward log-wealth like every other rail on this desk.

Pure arithmetic: no I/O, no network, numpy-free. `desks/mt5/research/net_edge_spine.py` is the
organ that feeds it the desk's artifacts and publishes `reports/NET_EDGE.json`.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

MEASURED = "MEASURED"
MODELLED = "MODELLED"
UNMEASURED = "UNMEASURED"

#: every cost term, in the order the decomposition is published
TERMS: tuple[str, ...] = ("spread_slippage", "impact", "financing", "commission", "multiplicity")
#: terms whose SIGN is known before they are measured: they can only ever reduce the edge, so an
#: unpriced one makes the net bound CONSERVATIVE (the truth is at or below it).
NON_NEGATIVE_TERMS: frozenset[str] = frozenset(
    {"spread_slippage", "impact", "commission", "multiplicity"})
#: terms that may be a CREDIT. A swap on the right side of a carry pair is paid TO the desk, so
#: an unpriced financing term means the true net may be ABOVE the bound as well as below it.
SIGNED_TERMS: frozenset[str] = frozenset({"financing"})

R_PER_TRADE = "R_per_trade"
R_PER_DAY = "R_per_day"

# verdicts
NET_POSITIVE = "NET_POSITIVE"
NET_POSITIVE_UNCONFIRMED = "NET_POSITIVE_UNCONFIRMED"
COST_DEAD = "COST_DEAD"
COST_DEAD_UNCONFIRMED = "COST_DEAD_UNCONFIRMED"
GROSS_NEGATIVE = "GROSS_NEGATIVE"

#: the square-root impact law. Impact grows with the square root of participation, so the size
#: at which net decays to zero is the reference size scaled by ((gross - fixed)/impact_ref)^2.
#: Declared here once and carried into every published capacity row as `exponent`.
IMPACT_EXPONENT = 0.5


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


# --------------------------------------------------------------------------- the cost terms


@dataclass(frozen=True)
class CostTerm:
    """One cost, in the row's own unit, POSITIVE IS A COST. `value` is None when UNMEASURED."""

    name: str
    value: float | None
    status: str
    source: str = ""
    note: str = ""

    @property
    def priced(self) -> bool:
        return self.status != UNMEASURED and self.value is not None

    @property
    def charge(self) -> float:
        """What this term actually takes off the edge. Zero ONLY when the term is priced at
        zero -- an unpriced term contributes nothing here because it is carried in
        `unpriced_terms`, never silently folded in as a zero."""
        return float(self.value) if self.priced and self.value is not None else 0.0

    def scaled(self, factor: float) -> CostTerm:
        """The same term in another unit (per-trade -> per-day at a measured trade rate)."""
        if not self.priced or self.value is None:
            return self
        return CostTerm(self.name, float(self.value) * float(factor), self.status, self.source,
                        (self.note + f"; x{factor:g} to the row's unit").lstrip("; "))

    def as_dict(self) -> dict[str, Any]:
        return {"value": None if self.value is None else round(float(self.value), 8),
                "status": self.status, "source": self.source, "note": self.note,
                "sign_known": self.name in NON_NEGATIVE_TERMS}


def measured(name: str, value: float, source: str, note: str = "") -> CostTerm:
    return CostTerm(name, float(value), MEASURED, source, note)


def modelled(name: str, value: float, source: str, note: str = "") -> CostTerm:
    return CostTerm(name, float(value), MODELLED, source, note)


def unpriced(name: str, why: str) -> CostTerm:
    """An UNMEASURED term. It carries None, never 0.0: see the module docstring."""
    return CostTerm(name, None, UNMEASURED, "", why)


# --------------------------------------------------------------------------- the net edge


@dataclass(frozen=True)
class NetEdge:
    """One cell's edge after every cost the desk actually pays, with the decomposition."""

    key: str
    gross: float | None
    terms: dict[str, CostTerm] = field(default_factory=dict)
    unit: str = R_PER_TRADE
    symbol: str = ""
    family: str = ""
    lane: str = ""
    size_lots: float | None = None
    gross_source: str = ""
    #: how many observations the gross edge was measured on. None is UNMEASURED and routes the
    #: cell's descendant as `no_data` rather than `cost_dead`, which is the correct answer: a
    #: cell nobody counted cannot be said to have died of its costs.
    n: float | None = None

    def term(self, name: str) -> CostTerm:
        return self.terms.get(name) or unpriced(name, "term not built on this pass")

    @property
    def cost_priced(self) -> float:
        """The sum of the terms that HAVE a number. Never a stand-in for the ones that do not."""
        return float(sum(self.term(n).charge for n in TERMS))

    @property
    def unpriced_terms(self) -> tuple[str, ...]:
        return tuple(n for n in TERMS if not self.term(n).priced)

    @property
    def conservative(self) -> bool:
        """True when every unpriced term can only make the net WORSE, so `net` is an upper
        bound and a negative reading is a finding rather than a guess."""
        return all(n in NON_NEGATIVE_TERMS for n in self.unpriced_terms)

    @property
    def net(self) -> float | None:
        if self.gross is None:
            return None
        return float(self.gross) - self.cost_priced

    @property
    def status(self) -> str:
        if self.gross is None:
            return UNMEASURED
        if not self.unpriced_terms:
            return MEASURED
        if len(self.unpriced_terms) == len(TERMS):
            return UNMEASURED
        return "PARTIAL"

    @property
    def verdict(self) -> str:
        net, gross = self.net, self.gross
        if net is None or gross is None:
            return UNMEASURED
        if gross <= 0:
            return GROSS_NEGATIVE
        if net <= 0:
            return COST_DEAD if self.conservative else COST_DEAD_UNCONFIRMED
        return NET_POSITIVE if not self.unpriced_terms else NET_POSITIVE_UNCONFIRMED

    @property
    def cost_share(self) -> float | None:
        """The priced cost as a share of the gross edge. None when there is no gross to share."""
        if self.gross is None or self.gross == 0:
            return None
        return float(self.cost_priced / abs(float(self.gross)))

    def with_term(self, term: CostTerm) -> NetEdge:
        terms = dict(self.terms)
        terms[term.name] = term
        return NetEdge(self.key, self.gross, terms, self.unit, self.symbol, self.family,
                       self.lane, self.size_lots, self.gross_source, self.n)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "symbol": self.symbol, "family": self.family, "lane": self.lane,
            "unit": self.unit, "size_lots": self.size_lots, "n": self.n,
            "gross": None if self.gross is None else round(float(self.gross), 8),
            "gross_source": self.gross_source,
            "net": None if self.net is None else round(float(self.net), 8),
            "net_is_bound": bool(self.unpriced_terms),
            "cost_priced": round(self.cost_priced, 8),
            "cost_share_of_gross": (None if self.cost_share is None
                                    else round(self.cost_share, 6)),
            "terms": {n: self.term(n).as_dict() for n in TERMS},
            "unpriced_terms": list(self.unpriced_terms),
            "conservative_bound": self.conservative,
            "status": self.status, "verdict": self.verdict,
        }


def net_edge(key: str, gross: float | None, *, spread_slippage: CostTerm | None = None,
             impact: CostTerm | None = None, financing: CostTerm | None = None,
             commission: CostTerm | None = None, multiplicity: CostTerm | None = None,
             unit: str = R_PER_TRADE, symbol: str = "", family: str = "", lane: str = "",
             size_lots: float | None = None, gross_source: str = "",
             n: float | None = None) -> NetEdge:
    """THE function. Every stage of the desk prices a cell through exactly this call.

    A term left out is UNMEASURED and says so; it is never a zero. `gross` None means the cell
    carries no edge estimate at all, which is its own verdict and not a net of zero.
    """
    given: dict[str, CostTerm | None] = {
        "spread_slippage": spread_slippage, "impact": impact, "financing": financing,
        "commission": commission, "multiplicity": multiplicity}
    terms: dict[str, CostTerm] = {}
    for name in TERMS:
        supplied = given[name]
        terms[name] = (supplied if isinstance(supplied, CostTerm)
                       else unpriced(name, "no input for this term on this pass"))
    return NetEdge(key=key, gross=_finite(gross), terms=terms, unit=unit, symbol=symbol,
                   family=family, lane=lane, size_lots=_finite(size_lots),
                   gross_source=gross_source, n=_finite(n))


def rescale_to_unit(row: NetEdge, *, unit: str, per_trade_to_unit: float | None) -> NetEdge:
    """Carry a per-trade cost decomposition into a per-day row at a MEASURED trade rate.

    With no measured rate every cost term becomes UNMEASURED with the reason, because a cost
    quoted per trade and an edge quoted per day are not comparable and the desk has paid for
    pretending otherwise.
    """
    if per_trade_to_unit is None or not math.isfinite(per_trade_to_unit) \
            or per_trade_to_unit <= 0:
        why = (f"the edge is quoted in {unit} and every cost is priced per trade; no measured "
               "trade rate joins them on this pass")
        terms = {n: unpriced(n, why) for n in TERMS}
    else:
        terms = {n: row.term(n).scaled(float(per_trade_to_unit)) for n in TERMS}
    return NetEdge(row.key, row.gross, terms, unit, row.symbol, row.family, row.lane,
                   row.size_lots, row.gross_source, row.n)


# --------------------------------------------------------------------------- term builders


def multiplicity_charge(sr0: float | None, sigma_r: float | None, *,
                        source: str = "", n_trials: int | None = None) -> CostTerm:
    """The deflated-Sharpe hurdle the gauntlet ALREADY charged, restated in R per trade.

    `sr0` is E[max Sharpe] over the trials the search spent, in per-trade Sharpe units; times
    the cell's own per-trade sigma it is the mean R a no-skill cell of that search width would
    have shown. That is the edge the desk owes back to its own multiple testing, and it belongs
    in the cost stack beside the spread because the desk pays it in exactly the same way.
    """
    s0, sd = _finite(sr0), _finite(sigma_r)
    if s0 is None or sd is None or sd <= 0:
        return unpriced("multiplicity", "no deflated-Sharpe hurdle or no per-trade sigma for "
                                        "this cell: the trial charge is unmeasured, not zero")
    note = f"sr0 {s0:.4f} x sigma_R {sd:.4f}"
    if n_trials:
        note += f" over {int(n_trials)} trials"
    return measured("multiplicity", max(0.0, s0 * sd),
                    source or "UNIVERSAL_SURVIVORS gates.deflated_sharpe.sr0", note)


def multiplicity_from_trials(n_trials: int | None, variance_of_sharpes: float | None,
                             sigma_r: float | None) -> CostTerm:
    """The same charge for a cell the gauntlet has not judged yet, from the trial count.

    `libs.validation.dsr.expected_max_sharpe` is the SAME function the sealed gauntlet raises
    its benchmark to, imported behind a guard: a host without scipy records UNMEASURED and the
    pass continues, which is the law's answer and not a crash.
    """
    n = int(n_trials or 0)
    var, sd = _finite(variance_of_sharpes), _finite(sigma_r)
    if n < 2 or var is None or var <= 0 or sd is None or sd <= 0:
        return unpriced("multiplicity",
                        f"trial charge needs n>=2 trials, a variance of Sharpes and a sigma; "
                        f"have n={n}, var={var}, sigma={sd}")
    try:
        from libs.validation.dsr import expected_max_sharpe
        hurdle = float(expected_max_sharpe(n, float(var)))
    except Exception as exc:  # pragma: no cover - host without scipy
        return unpriced("multiplicity",
                        f"expected_max_sharpe unavailable ({type(exc).__name__}): the trial "
                        "charge is unmeasured on this host")
    return modelled("multiplicity", max(0.0, hurdle * sd), "libs.validation.dsr",
                    f"E[max Sharpe | {n} trials, var={var:.6f}] x sigma_R {sd:.4f}")


def impact_charge(size_lots: float | None, *, ref_lots: float | None,
                  ref_impact_r: float | None, exponent: float = IMPACT_EXPONENT,
                  source: str = "") -> CostTerm:
    """Market impact at THIS size under the square-root law, from a measured reference fill.

    impact(q) = impact(q_ref) x (q / q_ref) ** exponent. Without a measured reference the term
    is UNMEASURED: an impact of zero is the assumption that the desk is invisible, which is the
    one assumption a capacity number must never be built on.
    """
    q, qr, ir = _finite(size_lots), _finite(ref_lots), _finite(ref_impact_r)
    if q is None or qr is None or ir is None or qr <= 0 or q < 0:
        return unpriced("impact", "market impact needs a measured reference fill (size and its "
                                  "realised impact in R); matched fills are absent")
    if ir < 0:
        return unpriced("impact", f"reference impact {ir:.6f} is negative: not a cost curve")
    return modelled("impact", float(ir) * (q / qr) ** float(exponent),
                    source or "libs/research/impact_lab.py reference fill",
                    f"sqrt-law: {ir:.6f}R at {qr:g} lots -> {q:g} lots, exponent {exponent:g}")


# --------------------------------------------------------------------------- capacity


def net_at_size(row: NetEdge, size_lots: float, *, ref_lots: float | None,
                ref_impact_r: float | None, exponent: float = IMPACT_EXPONENT) -> float | None:
    """The row's net edge if it were traded at `size_lots`. Falls as size rises, by the law."""
    charged = row.with_term(impact_charge(size_lots, ref_lots=ref_lots,
                                          ref_impact_r=ref_impact_r, exponent=exponent))
    return charged.net


def capacity_size(row: NetEdge, *, ref_lots: float | None, ref_impact_r: float | None,
                  exponent: float = IMPACT_EXPONENT) -> dict[str, Any]:
    """The size at which this row's net edge decays to ZERO -- the book's real carry limit.

    Solving gross - fixed - impact_ref (q/q_ref)^a = 0 gives q* = q_ref ((gross-fixed)/impact_ref)
    ** (1/a). Without a measured impact reference the answer is UNMEASURED and NOT "unlimited":
    the desk does not get to size a book on the absence of a measurement (L1.28a).
    """
    qr, ir = _finite(ref_lots), _finite(ref_impact_r)
    base = row.with_term(unpriced("impact", "excluded from the fixed cost for the capacity solve"))
    headroom = None if base.net is None else float(base.net)
    if qr is None or ir is None or qr <= 0 or ir <= 0:
        return {"lots": None, "status": UNMEASURED, "exponent": exponent,
                "net_at_ref": None,
                "why": ("capacity is the size at which net decays to zero and needs a measured "
                        "market-impact reference; matched fills are 0 on this host, so the "
                        "ceiling is UNMEASURED -- which is not the same as unlimited")}
    if headroom is None:
        return {"lots": None, "status": UNMEASURED, "exponent": exponent, "net_at_ref": None,
                "why": "no gross edge for this row: there is no net to decay to zero"}
    if headroom <= 0:
        return {"lots": 0.0, "status": MEASURED, "exponent": exponent,
                "net_at_ref": round(headroom - ir, 8),
                "why": ("net is already at or below zero before any impact is charged: the "
                        "size this row can carry at a positive net edge is zero")}
    lots = float(qr) * (headroom / float(ir)) ** (1.0 / float(exponent))
    return {"lots": round(lots, 6), "status": MODELLED, "exponent": exponent,
            "ref_lots": qr, "ref_impact_r": ir,
            "net_at_ref": round(headroom - ir, 8),
            "why": (f"net {headroom:.6f}R before impact; {ir:.6f}R of impact at {qr:g} lots "
                    f"under the sqrt law decays it to zero at {lots:.4f} lots")}


# --------------------------------------------------------------------------- ranking / routing


def rank_by_net(rows: Iterable[NetEdge]) -> list[NetEdge]:
    """Rank on NET, never on gross. Rows with no net at all sort last, in key order, so an
    unpriced cell is visibly at the back rather than silently at the front on a zero cost."""
    return sorted(rows, key=lambda r: (r.net is None, -(r.net or 0.0), r.key))


def cost_dead(rows: Iterable[NetEdge], *, include_unconfirmed: bool = False) -> list[NetEdge]:
    """Every cell whose SIGN flips after costs: gross positive, net at or below zero."""
    wanted = {COST_DEAD} | ({COST_DEAD_UNCONFIRMED} if include_unconfirmed else set())
    return [r for r in rows if r.verdict in wanted]


def sign_flips(rows: Iterable[NetEdge]) -> int:
    return sum(1 for r in rows
               if r.verdict in (COST_DEAD, COST_DEAD_UNCONFIRMED))


def descendant_request(row: NetEdge) -> dict[str, Any]:
    """The COST-DEAD cell's CHILD, in the shape `libs.research.coevolution_lab` already routes.

    A COST_DEAD cell is never dropped. `classify_failure` in the coevolution lab reads
    `gross_gain` positive and `net_gain` non-positive as `cost_dead` and emits a
    `lower_turnover_descendant` -- the same idea at a longer horizon, a wider band or fewer
    rebalances. This builds the result row that classifier reads, so the routing is the desk's
    existing one and not a second opinion beside it.
    """
    return {"family": row.family, "model": row.key, "symbol": row.symbol,
            "n": row.n, "gross_gain": row.gross, "gain": row.gross, "net_gain": row.net,
            "verdict": row.verdict, "features": sorted(row.terms),
            "net_decomposition": {n: row.term(n).as_dict() for n in TERMS},
            "why": (f"gross {row.gross} {row.unit} survives and net {row.net} does not: "
                    f"{', '.join(n for n in TERMS if row.term(n).charge > 0) or 'costs'} eat it")}


def missed_growth_line(row: NetEdge, *, heat_share: float | None = None,
                       trades_per_day: float | None = None) -> dict[str, Any]:
    """The GROWTH-GOVERNANCE bill for refusing a COST_DEAD cell, in log-wealth per day.

    Rule 1 says every risk reduction must prove it raises robust forward E[log W]. COST_DEAD is
    a refusal, so it is billed like one: the growth the desk gives up is the cell's own GROSS
    edge at the heat it would have taken (which is what a gross-ranked desk believed it was
    buying), and the growth it keeps is the loss it would actually have paid, which is the net.
    A refusal whose net is negative EARNS its place; the line proves it rather than asserting it.
    """
    gross, net = row.gross, row.net
    rate = _finite(trades_per_day) or (1.0 if row.unit == R_PER_DAY else None)
    heat = _finite(heat_share)
    if gross is None or net is None:
        return {"rail": "net_edge_cost_dead", "cell": row.key, "verdict": UNMEASURED,
                "why": "no gross or no net for this cell: the refusal cannot be priced"}
    if rate is None:
        return {"rail": "net_edge_cost_dead", "cell": row.key, "symbol": row.symbol,
                "family": row.family, "unit": row.unit, "verdict": UNMEASURED,
                "gross": round(float(gross), 8), "net": round(float(net), 8),
                "cost_charged": round(row.cost_priced, 8), "two_sided": True,
                "why": ("no measured trade rate for this cell: the refusal's log-wealth per day "
                        "cannot be priced, which is a verdict and not a zero")}
    return {
        "rail": "net_edge_cost_dead", "cell": row.key, "symbol": row.symbol,
        "family": row.family, "unit": row.unit,
        "gross": round(float(gross), 8), "net": round(float(net), 8),
        "cost_charged": round(row.cost_priced, 8),
        "trades_per_day": rate, "heat_share": heat,
        "forgone_gross_per_day": round(float(gross) * rate, 8),
        "avoided_loss_per_day": round(-float(net) * rate, 8),
        "delta_elogw_per_day": (None if heat is None
                                else round(-float(net) * rate * heat, 10)),
        "verdict": ("EARNS_ITS_PLACE" if net < 0 else "NOT_BINDING"),
        "two_sided": True,
        "why": ("the cell is refused on NET, not on gross; the heat it would have taken is "
                "reallocated to the rest of the book by reweight_preserving_heat, never "
                "retired, so the refusal reallocates and does not shrink"),
    }


# --------------------------------------------------------------------------- heat, two-sided


def reweight_preserving_heat(book: Mapping[str, float], scores: Mapping[str, float],
                             *, floor: float = 0.0) -> dict[str, float]:
    """Move heat TOWARD higher net and return a book with EXACTLY the heat it was given.

    GROWTH GOVERNANCE, both rules at once. Rule 2: a sleeve whose net edge is better than the
    book's gets more than it had. Rule 1: nothing here reduces the total -- the returned
    fractions sum to the input's sum to floating-point, so a COST_DEAD refusal frees heat for
    the survivors instead of taking it off the table. An empty or unscorable book is returned
    unchanged, because a reweighting that cannot be computed must never become a reduction.
    """
    total = float(sum(max(float(v), 0.0) for v in book.values()))
    if total <= 0:
        return {k: float(v) for k, v in book.items()}
    weights: dict[str, float] = {}
    for name, heat in book.items():
        h = max(float(heat), 0.0)
        s = _finite(scores.get(name))
        weights[name] = h * max(float(s), floor) if s is not None else h
    mass = float(sum(weights.values()))
    if mass <= 0:
        return {k: float(v) for k, v in book.items()}
    return {k: (v / mass) * total for k, v in weights.items()}


def net_tilt(rows: Sequence[NetEdge], *, lo: float = 0.5, hi: float = 2.0) -> dict[str, float]:
    """Each row's net edge relative to the book's mean net, bounded -- the allocator's tilt.

    Heat-neutral by construction when it is fed through `reweight_preserving_heat`: this returns
    a RELATIVE score and never an absolute size, so it can reorder the book and cannot shrink it.
    """
    nets = [float(r.net) for r in rows if r.net is not None]
    if not nets:
        return {}
    mean = sum(nets) / len(nets)
    if mean <= 0:
        return {r.key: 1.0 for r in rows}
    return {r.key: min(hi, max(lo, float(r.net) / mean)) if r.net is not None else 1.0
            for r in rows}


# --------------------------------------------------------------------------- backward check


def prediction_error(predicted: NetEdge, realised_net: float | None, *,
                     realised_cost: float | None = None) -> dict[str, Any]:
    """The cost model judged by the tape: predicted net minus realised net, per closed trade.

    The model that prices the book must itself be priced. An absent realised figure is
    UNMEASURED; a model that is never scored against what was actually paid is a claim the desk
    cannot cash (L1.49).
    """
    r_net, r_cost = _finite(realised_net), _finite(realised_cost)
    p_net = predicted.net
    if p_net is None or r_net is None:
        return {"cell": predicted.key, "status": UNMEASURED,
                "why": ("no predicted net" if p_net is None else
                        "no realised net for this closed trade")}
    err = float(p_net) - float(r_net)
    out: dict[str, Any] = {
        "cell": predicted.key, "symbol": predicted.symbol, "status": MEASURED,
        "predicted_net": round(float(p_net), 8), "realised_net": round(float(r_net), 8),
        "error": round(err, 8),
        "direction": ("OVER_PREDICTED" if err > 0 else
                      "UNDER_PREDICTED" if err < 0 else "EXACT"),
    }
    if r_cost is not None:
        out["predicted_cost"] = round(predicted.cost_priced, 8)
        out["realised_cost"] = round(float(r_cost), 8)
        out["cost_error"] = round(predicted.cost_priced - float(r_cost), 8)
    return out


def calibration(errors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The cost model's own scorecard: bias, mean absolute error, and how many it could score."""
    vals = [float(e["error"]) for e in errors
            if e.get("status") == MEASURED and _finite(e.get("error")) is not None]
    if not vals:
        return {"n": 0, "status": UNMEASURED,
                "why": "no closed trade on this host carries both a predicted and a realised "
                       "net: the cost model is unjudged, which is a verdict and not a pass"}
    n = len(vals)
    bias = sum(vals) / n
    mae = sum(abs(v) for v in vals) / n
    var = sum((v - bias) ** 2 for v in vals) / (n - 1) if n > 1 else 0.0
    return {"n": n, "status": MEASURED, "bias": round(bias, 8), "mae": round(mae, 8),
            "sd": round(math.sqrt(var), 8),
            "t": (round(bias / math.sqrt(var / n), 4) if var > 0 and n > 1 else UNMEASURED),
            "verdict": ("CALIBRATED" if abs(bias) <= mae * 0.25 else
                        "OVER_CHARGING" if bias > 0 else "UNDER_CHARGING"),
            "why": "predicted net minus realised net over every closed trade both could price"}
