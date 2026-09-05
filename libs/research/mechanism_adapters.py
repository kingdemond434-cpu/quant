"""Adapters: the ONE place that says how a mechanism class is measured on this desk.

WHY ADAPTERS, AND WHY THIS IS NOT ANOTHER TABLE OF FAMILIES. The desk can now GENERATE structure
at scale -- the data-first miner emits thousands of (symbol, condition, horizon) cells with honest
trial counts -- and it can REFUSE honestly, because the measurement resolver answers what is
measurable. What sits between them is the step that has always been done by guessing: given an
observed regularity, what CLASS of cause could produce it, and what would that class predict
NEXT that a coincidence would not?

That question is the whole difference between an anomaly and a candidate. `miner_candidate_compiler`
already refuses to cross it -- "exact recipe or structured causal data only, no prose-to-family
guessing" -- which is correct and is why prose converts at 0 from 341 rows. But refusing is only
half an answer: it leaves every generated anomaly stranded as a correlation nobody may trade.

WHAT AN ADAPTER IS. A named mechanism CLASS with three things attached: the observable it needs
(resolved through `measurement_resolver`, so an adapter can be UNMEASURABLE on this desk and say
so), the SIGNATURE it predicts -- a property the data must show if this cause is real -- and a
FALSIFIER, a property that would kill it. An anomaly is offered to every adapter; those whose
signature it matches become candidate EXPLANATIONS, ranked, each carrying its own falsifier.

NO FAMILY IS HARDCODED AND NONE IS INVENTED. An adapter does not name a trading family, choose
params or emit a rule -- doing that from a correlation is the guessing this desk forbids. It
proposes a CAUSE and the test that would refute it. Compiling a cause into an executable family
remains the compiler's job, under its existing rule, and every survivor still walks the ten gates.

THE ASYMMETRY IS DELIBERATE. An adapter that matches proves nothing: many causes produce the same
signature, which is why several may match and none is promoted. An adapter that FAILS its own
falsifier is informative -- that cause is out. Discovery here proceeds by elimination, because
that is the direction where evidence is cheap and honest.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from libs.research.measurement_resolver import Resolution, resolve


@dataclass(frozen=True)
class Adapter:
    """One mechanism class: what it needs, what it predicts, what would kill it."""

    name: str
    causal_story: str
    required_observable: str
    #: Does this anomaly LOOK like this cause? Cheap, structural, never a verdict.
    signature: Callable[[dict[str, Any]], bool]
    #: What must be FALSE for this cause to survive. Stated as an instruction to the desk.
    falsifier: str
    #: Who pays, in the economic sense. A mechanism with no payer is a coincidence with a story.
    payer: str
    tags: tuple[str, ...] = field(default_factory=tuple)

    def measurability(self) -> Resolution:
        return resolve(self.causal_story, self.required_observable)


def _cond(a: dict[str, Any]) -> str:
    return str(a.get("condition") or "")


def _hint(a: dict[str, Any]) -> str:
    return str(a.get("family_hint") or "")


#: THE ADAPTERS. Each is a CLASS OF CAUSE, not a strategy. The list is open: adding one widens what
#: the desk can explain, and none of them can promote anything by itself.
ADAPTERS: tuple[Adapter, ...] = (
    Adapter(
        name="carry_accrual",
        causal_story="a financing differential accrues while a position is held overnight",
        required_observable="swap",
        signature=lambda a: int(a.get("horizon") or 0) >= 6,
        falsifier=("charge the SYMBOL'S OWN swap at the correct side and sign; if the effect "
                   "disappears the anomaly was the financing, not an edge over it"),
        payer="the counterparty funding the position, via the broker's swap book",
        tags=("overnight", "financing"),
    ),
    Adapter(
        name="liquidity_premium",
        causal_story="compensation for providing liquidity when it is scarce",
        required_observable="spread",
        # Same discipline: match the PRIMITIVE, not a substring that could appear anywhere.
        signature=lambda a: _cond(a).split("_")[0] in ("vol", "range", "absret"),
        falsifier=("re-price at the spread OBSERVED IN THAT REGIME rather than the median; a "
                   "liquidity premium that does not survive its own regime's spread is the "
                   "spread"),
        payer="whoever needed immediacy while it was expensive",
        tags=("microstructure", "volatility"),
    ),
    Adapter(
        name="scheduled_flow",
        causal_story=("a recurring, calendar-driven order flow that must transact "
                      "regardless of price"),
        required_observable="calendar",
        signature=lambda a: _cond(a).split("_")[0] in ("hour", "dow"),
        falsifier=("hold the clock and shuffle the DATES; a real scheduled flow dies when the "
                   "calendar is broken, a clock artefact does not"),
        payer="the mandated participant transacting on a schedule",
        tags=("calendar", "session"),
    ),
    Adapter(
        name="positioning_unwind",
        causal_story="crowded positioning reverts when it can no longer be added to",
        required_observable="cot",
        # THE PRIMITIVE MUST BE POSITIONING-SHAPED, NOT MERELY EXTREME. This read
        # `any(k in cond for k in ("mom", "q0.9", "q0-0.1"))`, so it matched `hour_q0.9-1` -- a
        # top-decile HOUR -- and offered "crowded positioning reverts" as a cause for the time of
        # day. A band is not a mechanism: every primitive has a top decile, and matching on the
        # band alone attaches a causal story to all of them indiscriminately.
        signature=lambda a: (_cond(a).split("_")[0] in ("mom", "ret", "absret")
                             and any(b in _cond(a) for b in ("q0.9", "q0-0.1"))),
        falsifier=("condition on POSITIONING rather than on price extremity; if price extremity "
                   "alone reproduces it, positioning was never the cause"),
        payer="the crowded side, exiting",
        tags=("positioning", "reversal"),
    ),
    Adapter(
        name="cross_asset_transmission",
        causal_story="a shared factor reaches one instrument before the other",
        required_observable="return",
        signature=lambda a: _hint(a) in ("lead_lag", "cross_asset_residual"),
        falsifier=("re-run with the legs' clocks ALIGNED and the lead reversed; a transmission "
                   "that is symmetric under reversal is shared noise, not lead-lag"),
        payer="the slower venue's participants, at the faster venue's price",
        tags=("cross_asset", "lead_lag"),
    ),
    Adapter(
        name="inventory_rebalance",
        causal_story="a dealer flattens accumulated inventory at a predictable time",
        required_observable="orderflow",
        signature=lambda a: (_cond(a).split("_")[0] == "hour"
                             and int(a.get("horizon") or 0) <= 3),
        falsifier=("check the effect against the desk's own recorded tape for one-sided flow; "
                   "no flow signature means no inventory to rebalance"),
        payer="the dealer paying to be flat",
        tags=("microstructure", "session"),
    ),
    Adapter(
        name="gap_repricing",
        causal_story="information arriving while the market is shut is priced at the reopen",
        required_observable="gap",
        signature=lambda a: _cond(a).split("_")[0] == "gap",
        falsifier=("split by whether the gap CLOSES; a repricing continues, an overreaction "
                   "reverts, and one anomaly cannot be both"),
        payer="whoever had to trade across the closure",
        tags=("gap", "overnight"),
    ),
)


def explain(anomaly: dict[str, Any]) -> dict[str, Any]:
    """Which mechanism classes could produce this anomaly, with each one's falsifier.

    RETURNS EXPLANATIONS, NEVER A PROMOTION. Several adapters matching is the normal case and is
    not evidence: many causes share a signature. The output is a research instruction -- run these
    falsifiers -- not a candidate, and nothing here may enter the gauntlet without a mechanism a
    brain has NAMED and the compiler has admitted under its own rule.
    """
    matched: list[dict[str, Any]] = []
    unmeasurable: list[dict[str, Any]] = []
    for ad in ADAPTERS:
        try:
            if not ad.signature(anomaly):
                continue
        except Exception:
            continue
        res = ad.measurability()
        row = {
            "mechanism": ad.name,
            "causal_story": ad.causal_story,
            "payer": ad.payer,
            "falsifier": ad.falsifier,
            "measurement_class": res.measurement_class,
            "attribution_allowed": res.attribution_allowed,
            "why_measurable": res.why,
            "tags": list(ad.tags),
        }
        (matched if res.may_run else unmeasurable).append(row)

    return {
        "anomaly": {k: anomaly.get(k) for k in
                    ("symbol", "against", "condition", "horizon", "n", "t_stat")},
        "candidate_explanations": matched,
        "unmeasurable_explanations": unmeasurable,
        "status": ("EXPLAINED_CANDIDATES" if matched else
                   "UNEXPLAINED" if not unmeasurable else "UNMEASURABLE_ONLY"),
        "note": ("Explanations, not promotions. Several causes may share one signature, so a "
                 "match is not evidence -- the falsifiers are. A cause that survives its own "
                 "falsifier may then be compiled by the existing compiler, under its existing "
                 "rule, and still walks all ten gates."),
    }


def coverage() -> dict[str, Any]:
    """Which adapters this desk can actually run, for the health fences."""
    rows = []
    for ad in ADAPTERS:
        res = ad.measurability()
        rows.append({"mechanism": ad.name, "class": res.measurement_class,
                     "may_run": res.may_run, "needs": ad.required_observable})
    return {
        "n_adapters": len(ADAPTERS),
        "runnable": sum(1 for r in rows if r["may_run"]),
        "adapters": rows,
        "note": "An adapter whose observable this desk lacks is reported, never silently dropped.",
    }
