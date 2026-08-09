"""MECHANISM ONTOLOGY AND ALPHA GRAMMAR — millions of real questions, not millions of formulas.

THE DIFFERENCE BETWEEN A HYPOTHESIS FACTORY AND A RANDOM FORMULA GENERATOR is not size. Both can
emit a million candidates. The generator emits a million things that could be true of any series;
the factory emits a million things that could be true of THIS market for a stated reason, and only
the second population is worth the compute or survivable under multiplicity correction.

    a 90-day holding period on order-flow imbalance is not a hypothesis.
    OFI measures who is currently pressing the book. It has no mechanism that could
    still be acting in three months, and a search that generates it is spending
    the multiplicity budget on a question nobody would ask out loud.

So every mechanism carries a CONTRACT: which observables measure it, which transformations mean
anything applied to it, which horizons its economics could plausibly survive, and what would
falsify it. `compatible` refuses combinations the contract forbids, and the refusal happens BEFORE
the candidate costs anything to test.

**THE PRUNING IS THE PRODUCT.** Enumerating a mechanism against every transformation, horizon,
state and venue produces a combinatorial explosion. Pruning against the contract removes the large
majority of it -- and the removed part is not a random sample, it is specifically the part with no
economic story, which is exactly the part that produces false positives at the highest rate.

**THE ONTOLOGY IS OPEN AND MUST STAY OPEN.** A closed list would freeze the desk's imagination at
whatever was known the day it was written, and the external-intelligence seats exist precisely to
find mechanisms nobody here has thought of. `register` adds one at runtime; what it will not do is
accept a mechanism with no falsifier, because an unfalsifiable mechanism generates candidates that
can never be killed and will accumulate forever.

**THIS IS NOT `libs/research/mechanism_fingerprint.py`.** That answers "are these two ideas the
same idea" for dedupe, using tokens and Jaccard overlap. This answers "may this idea be
constructed at all", using economic contracts. Dedupe operates on candidates that already exist;
this decides which ever get built.

Enumerates and prunes. Tests nothing, ranks nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CORE_MECHANISMS",
    "HORIZONS",
    "TRANSFORMS",
    "Candidate",
    "Mechanism",
    "compatible",
    "enumerate_candidates",
    "register",
    "selection_path",
    "summarise",
]

#: Horizon buckets, shortest first. A mechanism declares the SPAN it could plausibly act over, and
#: anything outside that span is refused rather than tested.
HORIZONS: tuple[str, ...] = (
    "SECONDS", "MINUTES", "HOURLY", "FUNDING_INTERVAL", "DAILY", "MULTI_DAY", "WEEKLY",
)

#: The transformation vocabulary. Which of these MEAN anything is a property of the observable,
#: not of the library -- a z-score of a funding rate is informative and a z-score of a boolean
#: event flag is not.
TRANSFORMS: tuple[str, ...] = (
    "LEVEL", "DIFFERENCE", "ACCELERATION", "ZSCORE", "PERCENTILE", "CROSS_SECTIONAL_RANK",
    "SURPRISE", "PERSISTENCE", "DIVERGENCE", "RATIO", "RESIDUAL", "DISPERSION", "BREADTH",
    "CONCENTRATION", "ENTROPY", "SLOPE", "INTERACTION",
)


@dataclass(frozen=True)
class Mechanism:
    """One economic reason a price could be predictable, and the boundaries of that reason."""

    mechanism_id: str
    #: WHY this could pay, in economic terms. Not a description of the signal -- a description of
    #: the constraint some participant is operating under.
    economic_rationale: str
    #: Who is forced or incentivised to act, which is what makes the effect recur rather than be
    #: a one-off.
    expected_actors: str = ""
    #: Observables that actually MEASURE this mechanism.
    observables: tuple[str, ...] = field(default_factory=tuple)
    #: Transformations that mean something applied to those observables.
    valid_transforms: tuple[str, ...] = field(default_factory=tuple)
    #: Horizons over which the economics could still be acting. THE STRONGEST PRUNING CONSTRAINT.
    valid_horizons: tuple[str, ...] = field(default_factory=tuple)
    #: States in which the mechanism could plausibly be conditional.
    valid_states: tuple[str, ...] = field(default_factory=tuple)
    #: What would show this mechanism is NOT operating. Required -- see `register`.
    falsifiers: tuple[str, ...] = field(default_factory=tuple)
    expected_decay: str = ""
    expected_capacity: str = ""

    def __post_init__(self) -> None:
        for h in self.valid_horizons:
            if h not in HORIZONS:
                raise ValueError(f"unknown horizon {h!r}; the bucket list is {HORIZONS}")
        for t in self.valid_transforms:
            if t not in TRANSFORMS:
                raise ValueError(f"unknown transform {t!r}; the vocabulary is {TRANSFORMS}")


@dataclass(frozen=True)
class Candidate:
    """One economically coherent question, with the path that produced it kept attached."""

    mechanism_id: str
    observable: str
    transform: str
    horizon: str
    state: str = ""
    #: The size of the search this candidate was drawn FROM. Carried on the candidate itself
    #: because a winner detached from its search path is indistinguishable from a preregistered
    #: hypothesis, and correcting for multiplicity afterwards requires knowing this number.
    siblings_enumerated: int = 0

    @property
    def candidate_id(self) -> str:
        base = f"{self.mechanism_id}::{self.observable}::{self.transform}::{self.horizon}"
        return base + (f"::{self.state}" if self.state else "")


#: A starting ontology. DELIBERATELY SMALL: these are mechanisms this desk can already measure from
#: data it already has. Adding one it cannot observe would create candidates it cannot test, which
#: is inventory rather than capability.
CORE_MECHANISMS: dict[str, Mechanism] = {
    "PERP_FUNDING_CARRY": Mechanism(
        mechanism_id="PERP_FUNDING_CARRY",
        economic_rationale=(
            "perpetual longs pay shorts to hold the position when the contract trades above spot. "
            "That payment is a transfer from participants who want leveraged exposure to those "
            "willing to warehouse the other side, and it recurs because leverage demand recurs"),
        expected_actors="leveraged directional traders paying to maintain exposure",
        observables=("funding_rate", "basis", "open_interest", "perp_spot_spread"),
        valid_transforms=("LEVEL", "DIFFERENCE", "ZSCORE", "PERCENTILE", "PERSISTENCE",
                          "CROSS_SECTIONAL_RANK", "DIVERGENCE"),
        # Bounded by the settlement clock at the short end and by how long crowding persists at
        # the long end. Nothing about this mechanism could still be acting in a month.
        valid_horizons=("FUNDING_INTERVAL", "HOURLY", "DAILY", "MULTI_DAY"),
        valid_states=("high_volatility", "crowded_long", "crowded_short", "low_liquidity"),
        falsifiers=("funding is unrelated to forward returns after costs",
                    "the carry is entirely consumed by the spread it must be captured through"),
        expected_decay="fast; this is the most publicly watched crypto carry there is",
        expected_capacity="bounded by open interest and by the depth of the hedging leg"),
    "FORCED_LIQUIDATION": Mechanism(
        mechanism_id="FORCED_LIQUIDATION",
        economic_rationale=(
            "liquidation engines sell without regard to price because they are closing an account, "
            "not expressing a view. The flow is mechanical, it exhausts when the positions are "
            "gone, and it overshoots what any informed seller would have accepted"),
        expected_actors="exchange liquidation engines closing margin accounts",
        observables=("liquidation_notional", "open_interest_change", "taker_flow_imbalance",
                     "depth", "spread"),
        valid_transforms=("LEVEL", "DIFFERENCE", "ACCELERATION", "ZSCORE", "PERCENTILE",
                          "CONCENTRATION", "SURPRISE"),
        # The overshoot is repaired in minutes to hours. A daily-or-longer horizon on this
        # mechanism is a different claim that this contract does not license.
        valid_horizons=("SECONDS", "MINUTES", "HOURLY"),
        valid_states=("high_volatility", "cascade", "low_liquidity"),
        falsifiers=("the overshoot does not revert beyond the cost of capturing it",
                    "liquidation intensity does not separate reverting from continuing declines"),
        expected_decay="slow; the mechanism is structural to margined trading",
        expected_capacity="thin, and worst exactly when the opportunity is largest"),
    "ORDER_FLOW_IMBALANCE": Mechanism(
        mechanism_id="ORDER_FLOW_IMBALANCE",
        economic_rationale=(
            "aggressive buying consumes resting liquidity, and the book takes time to be replaced. "
            "Until it is, the imbalance between what was consumed and what remains carries "
            "short-lived information about the next price"),
        expected_actors="market makers repricing after inventory shocks",
        observables=("order_flow_imbalance", "queue_imbalance", "microprice", "trade_pressure",
                     "depth_slope"),
        valid_transforms=("LEVEL", "DIFFERENCE", "ZSCORE", "PERSISTENCE", "DIVERGENCE"),
        # Book replacement is a seconds-to-minutes process. This is the contract that refuses the
        # 90-day OFI strategy named in the module docstring.
        valid_horizons=("SECONDS", "MINUTES"),
        valid_states=("high_volatility", "low_liquidity", "normal"),
        falsifiers=("the imbalance does not predict the next move beyond the spread",
                    "predictability vanishes once adverse selection on fills is charged"),
        expected_decay="very fast; this is the most competed signal in the market",
        expected_capacity="very small; impact consumes the edge almost immediately"),
    "CROSS_VENUE_PRICE_DISCOVERY": Mechanism(
        mechanism_id="CROSS_VENUE_PRICE_DISCOVERY",
        economic_rationale=(
            "the same asset trades on venues with different participants and different latency, so "
            "price is discovered on one and repriced on another. The lag is a transport delay, not "
            "a disagreement about value"),
        expected_actors="arbitrageurs, and venues whose flow is slower to arrive",
        observables=("cross_venue_spread", "venue_volume_share", "microprice", "basis"),
        valid_transforms=("LEVEL", "DIFFERENCE", "ZSCORE", "DIVERGENCE", "RATIO", "RESIDUAL"),
        valid_horizons=("SECONDS", "MINUTES", "HOURLY"),
        valid_states=("high_volatility", "cascade", "venue_outage"),
        falsifiers=("the lagging venue does not converge within the cost of trading it",
                    "leadership is unstable, so which venue leads cannot be known in advance"),
        expected_decay="fast where latency is the only barrier, slower where capital is trapped",
        expected_capacity="bounded by the thinner venue and by transfer time between them"),
    "CROSS_SECTIONAL_MOMENTUM": Mechanism(
        mechanism_id="CROSS_SECTIONAL_MOMENTUM",
        economic_rationale=(
            "capital rotates toward what has recently worked, and the rotation takes longer than "
            "the information that started it. The persistence is a flow effect rather than an "
            "information effect, which is why it is a cross-sectional rather than absolute claim"),
        expected_actors="allocators rebalancing toward recent strength",
        observables=("return", "volume", "open_interest", "breadth", "dispersion"),
        valid_transforms=("CROSS_SECTIONAL_RANK", "ZSCORE", "RESIDUAL", "DISPERSION", "BREADTH",
                          "PERSISTENCE", "ACCELERATION"),
        # Flow-driven rotation is a multi-day-to-weekly process. Seconds and minutes are refused:
        # nothing about capital rotation could act on that clock.
        valid_horizons=("DAILY", "MULTI_DAY", "WEEKLY"),
        valid_states=("trending", "high_dispersion", "low_dispersion", "risk_on"),
        falsifiers=("the ranking has no forward spread after costs",
                    "the effect is entirely explained by market beta"),
        expected_decay="moderate; widely known and still widely present",
        expected_capacity="large relative to the others here"),
}


def register(ontology: dict[str, Mechanism], m: Mechanism) -> dict[str, Mechanism]:
    """Add a mechanism. THE ONTOLOGY IS OPEN -- but a mechanism with no falsifier is refused.

    An unfalsifiable mechanism generates candidates that can never be killed. They accumulate,
    they consume the multiplicity budget forever, and every one of them survives every review
    because there is no evidence that could count against it.
    """
    if not m.falsifiers:
        raise ValueError(
            f"{m.mechanism_id}: no falsifier declared. An unfalsifiable mechanism produces "
            "candidates that can never be killed -- they accumulate, consume the multiplicity "
            "budget forever, and survive every review because no evidence could count against them")
    if not m.economic_rationale.strip():
        raise ValueError(f"{m.mechanism_id}: no economic rationale. Without one this is a formula "
                         "family rather than a mechanism, and it belongs in a different search")
    return {**ontology, m.mechanism_id: m}


def compatible(m: Mechanism, *, observable: str, transform: str, horizon: str,
               state: str = "") -> tuple[bool, str]:
    """May this combination be constructed at all? THE PRUNE, and it runs before any cost."""
    if observable not in m.observables:
        return False, (f"{observable!r} does not MEASURE {m.mechanism_id} -- it may correlate with "
                       "it, and a correlation without a measurement relationship is how a "
                       "mechanism-shaped search produces mechanism-free candidates")
    if transform not in m.valid_transforms:
        return False, (f"{transform!r} means nothing applied to {observable!r} under "
                       f"{m.mechanism_id}")
    if horizon not in m.valid_horizons:
        return False, (
            f"{horizon} is outside the span over which {m.mechanism_id} could still be acting "
            f"({list(m.valid_horizons)}). {m.expected_decay or 'The economics do not survive it'}")
    if state and m.valid_states and state not in m.valid_states:
        return False, f"{state!r} is not a state in which {m.mechanism_id} is expected to differ"
    return True, f"{m.mechanism_id} x {observable} x {transform} x {horizon} is coherent"


def enumerate_candidates(ontology: dict[str, Mechanism], *,
                         states: tuple[str, ...] = ()) -> tuple[list[Candidate], dict[str, int]]:
    """(candidates, counts). Every coherent question, and how many were pruned to get there.

    THE PRUNED COUNT IS AS IMPORTANT AS THE KEPT ONE. It is the size of the search that did NOT
    happen, and reporting it is what stops "we tested 4,000 things" from sounding like restraint
    when the unconstrained space was two million.
    """
    kept: list[Candidate] = []
    considered = pruned = 0
    for m in ontology.values():
        state_list = states or m.valid_states or ("",)
        for obs in m.observables:
            for tr in TRANSFORMS:
                for hz in HORIZONS:
                    for st in state_list:
                        considered += 1
                        ok, _ = compatible(m, observable=obs, transform=tr, horizon=hz, state=st)
                        if ok:
                            kept.append(Candidate(m.mechanism_id, obs, tr, hz, st))
                        else:
                            pruned += 1
    kept = [Candidate(c.mechanism_id, c.observable, c.transform, c.horizon, c.state,
                      siblings_enumerated=len(kept)) for c in kept]
    return kept, {"considered": considered, "kept": len(kept), "pruned": pruned}


def selection_path(candidates: list[Candidate]) -> dict[str, object]:
    """The multiplicity record. WITHOUT THIS, EVERY WINNER LOOKS PREREGISTERED.

    A candidate detached from the size of the search that produced it is indistinguishable from a
    hypothesis someone wrote down in advance, and the deflated significance hurdle depends entirely
    on that number.
    """
    if not candidates:
        return {"candidates": 0, "note": "no candidates enumerated; no selection path to record"}
    by_mech: dict[str, int] = {}
    for c in candidates:
        by_mech[c.mechanism_id] = by_mech.get(c.mechanism_id, 0) + 1
    return {
        "candidates": len(candidates),
        "by_mechanism": dict(sorted(by_mech.items(), key=lambda kv: -kv[1])),
        "transforms_searched": sorted({c.transform for c in candidates}),
        "horizons_searched": sorted({c.horizon for c in candidates}),
        "states_searched": sorted({c.state for c in candidates if c.state}),
        "note": ("Every candidate carries the size of the search it came from. A winner detached "
                 "from its selection path is indistinguishable from a preregistered hypothesis, "
                 "and the deflated hurdle depends entirely on this count."),
    }


def summarise(ontology: dict[str, Mechanism] | None = None, *,
              states: tuple[str, ...] = ()) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    ont = ontology if ontology is not None else CORE_MECHANISMS
    if not ont:
        return {"mechanisms": 0, "headline": (
            "empty ontology -- every candidate this desk generates is a formula rather than a "
            "question, and the multiplicity budget is being spent on things nobody would ask")}
    cands, counts = enumerate_candidates(ont, states=states)
    path = selection_path(cands)
    prune_rate = counts["pruned"] / counts["considered"] if counts["considered"] else 0.0
    no_falsifier = [m.mechanism_id for m in ont.values() if not m.falsifiers]
    return {
        "mechanisms": len(ont),
        "counts": counts,
        "prune_rate": round(prune_rate, 4),
        "selection_path": path,
        "mechanisms_without_falsifiers": no_falsifier,
        "headline": (
            f"{len(ont)} mechanism(s) generate {counts['kept']} economically coherent candidate(s) "
            f"from {counts['considered']} combinations -- {prune_rate:.0%} pruned before costing "
            "anything. The pruned part is not a random sample: it is specifically the part with no "
            "economic story, which is where false positives come from fastest"),
        "note": ("The ontology is OPEN and must stay open -- register() adds mechanisms at "
                 "runtime, and the external-intelligence seats exist to find ones nobody here has "
                 "thought of. What it refuses is a mechanism with no falsifier, because those "
                 "produce candidates that can never be killed. This is NOT mechanism_fingerprint: "
                 "that answers whether two ideas are the same for dedupe; this decides which ideas "
                 "may be constructed at all."),
    }
