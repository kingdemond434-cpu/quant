"""MECHANISM SUPPLY CENSUS -- how many distinct ECONOMIC mechanisms has this desk actually tested?

THE DISTINCTION THIS MODULE EXISTS TO ENFORCE, and the only reason it is not a fourth family
counter. A FEATURE FAMILY is a way of writing a number down. An ECONOMIC MECHANISM is a claim
about WHO is on the other side of the trade and WHY THEY CANNOT STOP PAYING.

    "20-day breakout" and "50-day breakout" are ONE mechanism at two parameters. Both say: a
    trader under-reacted to information and must complete the same adjustment later at a worse
    price. Moving the window does not change the payer, so it does not change the mechanism --
    and a desk that counts it twice believes it has run two experiments when it has run one.

    "carry", "order-flow imbalance" and "capital-control barrier rent" are THREE mechanisms.
    The first is paid by a leveraged long who must post funding every eight hours; the second by
    an uninformed counterparty who fills an informed order and learns its information only after
    the price has moved; the third by a local saver who cannot move capital across a border and
    pays whoever holds the rail. No amount of evidence about one is evidence about another.

THE MEASUREMENT THAT MOTIVATED THIS. The desk ran its highest-power campaign to date -- 21
symbols x 5.6 years, pooled by mechanism so power at a true annualised Sharpe of 1.0 is ~70%
rather than ~5% -- and got 0 survivors from 44 pooled candidates (``reports/real_campaign.json``).
Power was not the binding constraint in that run. The HYPOTHESIS SET was: read this census's
own output and those 44 "mechanisms" resolve to a handful of economic classes, every one of them
derived from the same OHLCV tape. More price transformations cannot fix that, because a hundred
price transformations are one economic mechanism wearing a hundred hats. Nothing on the desk
measured this before, so the funnel looked BLOCKED AT THE GATE when it is STARVED AT THE TOP.

WHAT IT REPORTS. Per economic class: candidates tested, distinct constructions, distinct
parameterisations, best out-of-sample result, verdict distribution. Then the number that matters,
MECHANISM COVERAGE -- classes tested to adequate depth vs named-but-untested vs no candidate at
all -- and a DIVERSITY reading that stays LOW when volume rises inside classes the desk already
owns. Then the deliverable: the ranked list of highest-value untested classes and the specific
data each one needs.

HOW THE MERGE/SPLIT CALLS WERE MADE, since they set every number here. Two constructions are the
SAME class when they answer "who pays, and why can they not stop?" identically. That is why
`zscore_fade`, `vwap_reversion`, `shock_fade`, `wyckoff_spring`, `ict_sweep_reversal` and
`supply_demand_retest` are ONE class: every one of them says a trader was forced to transact NOW
-- by a stop, a margin call, an inventory limit -- and pays whoever warehouses the other side.
They differ only in where they claim the forced flow sits. Conversely `network_usage_demand` and
`holder_cost_basis_capitulation` are SPLIT despite sharing on-chain data, because adoption demand
and underwater-holder capitulation are different payers with different clocks. The taxonomy errs
toward SPLITTING wherever the payer is arguably different, which biases the diversity reading UP:
a low reading here is therefore conservative.

HONESTY RAILS, all three enforced mechanically and all three visible in the output.
  * A class with no evidence on disk is UNTESTED. It is never reported as failed, its verdict
    distribution is empty, and its best OOS is ``None`` rather than 0.0 -- because "we looked and
    found nothing" and "nobody has looked" are different states and only one of them is a result.
  * A runtime-only artifact that is absent from this checkout is NOT-READABLE-HERE. It is never
    counted as zero evidence, and the class it would have informed says so on its own row.
  * Nothing is classified that cannot be read. Every classification records the signature tokens
    that produced it, and any record matching no signature lands in ``unclassified`` where it is
    reported -- never silently dropped, never assigned to the nearest plausible class.

WHERE THIS SITS AMONG THE MACHINERY THAT ALREADY EXISTS, since none of it is duplicated here.
``libs/hypmax/invention.py`` refuses an interaction when both primitives share an INFORMATION
CLASS -- "same observation read twice" -- and that veto is the same idea one level down: this
module applies it to whole hypotheses instead of feature pairs, and asks about the PAYER rather
than the observation. ``libs/research/mechanism_fingerprint.py`` buckets an idea as
family/transform/horizon to catch trivial reparameterisation, and ``collapse_detector.py`` takes
entropy over those fingerprints per BATCH; both are correct and both are blind to the question
here, because a fingerprint's family axis is a FEATURE family -- ``trend`` and ``breakout``
fingerprint apart while being one economic mechanism. ``hypothesis_novelty`` answers "is this a
near-duplicate of a prior?", which is a different question from "which mechanism is it?", so it
is not imported: a candidate can be perfectly novel against every prior and still be the four
hundredth member of a class the desk has exhausted. The graveyard table parse is the same one
``scripts/screen_idle_axes.py`` uses for its novelty priors, hardened for the rows that grew in
after it.

ZERO AUTHORITY. This is a measurement instrument. It promotes nothing, blocks nothing, and
changes no gate, threshold or bar anywhere in the desk. Its own depth and scoring constants
(``DEPTH_MIN_*``, per-class plausibility/orthogonality, the availability ladder) are REPORTING
parameters of this census and confer no standing on any candidate whatsoever.

Pure stdlib -- no numpy, no pandas, no repo imports. The census must be readable on a box where
the research stack does not install.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "CLASS_BY_ID",
    "DEPTH_MIN_CONSTRUCTIONS",
    "SCHEMA_VERSION",
    "TAXONOMY",
    "CandidateEvidence",
    "CensusReport",
    "ClassCensus",
    "Coverage",
    "DataAvailability",
    "DataRequirement",
    "Diversity",
    "GapRow",
    "MechanismClass",
    "SourceStatus",
    "Verdict",
    "census",
    "classify",
    "collect_evidence",
    "measure_diversity",
    "rank_gaps",
]

ROOT = Path(__file__).resolve().parents[2]

SCHEMA_VERSION = "1.0.0"

#: Distinct CONSTRUCTIONS that must each carry a CONCLUSIVE verdict before a class reads as
#: tested to adequate depth.
#:
#: DENOMINATED IN CONSTRUCTIONS, NEVER IN CANDIDATES, and that is the whole design. A bar written
#: as "n candidates" is satisfied by reparameterising one construction four times, which is
#: precisely the accounting error this module exists to remove -- the bar would certify depth the
#: desk does not have, using the exact mechanism that produced the illusion. Four rather than two
#: because construction variance in this asset class is measured LARGER than sampling variance
#: (GAP_REGISTER #71), so two constructions cannot separate "the mechanism is absent" from "both
#: of these ways of writing it down were wrong".
DEPTH_MIN_CONSTRUCTIONS = 4


# ------------------------------------------------------------------------------- vocabulary ----
class Verdict(StrEnum):
    """What actually happened to a candidate. The first four are TESTS; the rest are not."""

    SURVIVED = "SURVIVED"            # cleared every gate it was put through
    REFUTED = "REFUTED"              # tested on desk data, the mechanism did not pay
    ARTIFACT = "ARTIFACT"            # tested, and the apparent edge was contamination/look-ahead
    UNDERPOWERED = "UNDERPOWERED"    # tested, and the sample could not resolve the question
    NOT_MEASURED = "NOT-MEASURED"    # the run was blocked: no data, no tape, no licence
    EV_REJECTED = "EV-REJECTED"      # refused before compute by the EV gate -- never tested
    NAMED_ONLY = "NAMED-ONLY"        # written down in a queue or pre-registration -- never tested
    EXTERNAL_PRIOR = "EXTERNAL-PRIOR"  # killed by somebody else's evidence, not re-run here
    UNKNOWN = "UNKNOWN"              # a readable record whose status this census cannot normalise


#: Verdicts that mean a test was actually run against data.
TESTED_VERDICTS = frozenset({Verdict.SURVIVED, Verdict.REFUTED, Verdict.ARTIFACT,
                             Verdict.UNDERPOWERED})
#: Verdicts that mean the question was answered rather than merely attempted.
CONCLUSIVE_VERDICTS = frozenset({Verdict.SURVIVED, Verdict.REFUTED, Verdict.ARTIFACT})
#: Strength order, used when several records describe the same construction.
_VERDICT_STRENGTH: dict[Verdict, int] = {
    Verdict.SURVIVED: 6, Verdict.REFUTED: 5, Verdict.ARTIFACT: 4, Verdict.UNDERPOWERED: 3,
    Verdict.EXTERNAL_PRIOR: 2, Verdict.NOT_MEASURED: 1, Verdict.EV_REJECTED: 1,
    Verdict.NAMED_ONLY: 0, Verdict.UNKNOWN: 0,
}


class Coverage(StrEnum):
    """How well a class has been covered. UNTESTED states are never failure states."""

    TESTED_DEEP = "TESTED-DEEP"
    TESTED_SHALLOW = "TESTED-SHALLOW"
    NAMED_UNTESTED = "NAMED-UNTESTED"
    NO_CANDIDATE = "NO-CANDIDATE"
    NOT_READABLE_HERE = "NOT-READABLE-HERE"


class DataAvailability(StrEnum):
    ON_DISK = "ON-DISK"
    FREE_ACQUIRABLE = "FREE-ACQUIRABLE"
    RECORD_FORWARD = "RECORD-FORWARD"      # obtainable at zero cost, but only going forward
    PAID = "PAID"
    LICENCE_BLOCKED = "LICENCE-BLOCKED"
    UNAVAILABLE = "UNAVAILABLE"


#: How much a class's data situation discounts its value as a next target. Declared, not fitted.
_FEASIBILITY: dict[DataAvailability, float] = {
    DataAvailability.ON_DISK: 1.00,
    DataAvailability.FREE_ACQUIRABLE: 0.80,
    DataAvailability.RECORD_FORWARD: 0.55,
    DataAvailability.PAID: 0.30,
    DataAvailability.LICENCE_BLOCKED: 0.05,
    DataAvailability.UNAVAILABLE: 0.00,
}

#: How much room a class still has. A class already tested to depth is not a gap.
_DEPTH_DEFICIT: dict[Coverage, float] = {
    Coverage.NO_CANDIDATE: 1.00,
    Coverage.NAMED_UNTESTED: 1.00,
    Coverage.TESTED_SHALLOW: 0.60,
    Coverage.TESTED_DEEP: 0.00,
    Coverage.NOT_READABLE_HERE: 0.00,      # ranked separately; see rank_gaps
}


@dataclass(frozen=True)
class DataRequirement:
    """What testing this class would actually take."""

    datasets: tuple[str, ...]
    availability: DataAvailability
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"datasets": list(self.datasets), "availability": str(self.availability),
                "feasibility": _FEASIBILITY[self.availability], "note": self.note}


@dataclass(frozen=True)
class MechanismClass:
    """One economic mechanism: a named payer and the reason they cannot stop paying."""

    id: str
    name: str
    payer: str                     # who pays, and why they are compelled
    economic_definition: str       # the claim, stated so it could be wrong
    signatures: tuple[str, ...]    # tokens that identify this class in a candidate's own text
    plausibility: float            # 0..1, strength of the payer story BEFORE any desk evidence
    orthogonality: float           # 0..1, independence of its driver from what the desk already has
    data: DataRequirement
    priority: int = 0              # tie-break order; specific classes before generic price ones

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "payer": self.payer,
                "economic_definition": self.economic_definition,
                "plausibility": self.plausibility, "orthogonality": self.orthogonality,
                "data": self.data.to_dict()}


# --------------------------------------------------------------------------------- taxonomy ----
# ORDER IS PRIORITY ORDER and it is load-bearing. Data-specific classes come first so that a
# generic price word never outbids a specific economic one: "funding_momentum" is a carry idea
# that happens to contain the word "momentum", not a momentum idea that happens to mention
# funding. The two price-only classes sit last precisely because their vocabulary is the most
# promiscuous on the desk.
TAXONOMY: tuple[MechanismClass, ...] = (
    MechanismClass(
        id="capital_control_barrier_rent",
        name="capital-control / barrier rent",
        payer="a local holder who cannot move capital across a barrier -- capital controls, a "
              "frozen withdrawal rail, KYC tiers, sanctions -- and pays whoever holds the rail",
        economic_definition="A cross-venue or cross-border price gap that PERSISTS is rent on "
                            "whatever barrier is currently binding, not an inefficiency. Its "
                            "magnitude tracks barrier height; it is information about local "
                            "flow, and it is only harvestable by whoever owns the specific rail.",
        signatures=("kimchi", "capital control", "capital flight", "venue premium",
                    "fiat premium", "regional premium", "coinbase premium", "kr premium",
                    "try premium", "crossvenue", "cross venue", "withdrawal", "banzhuan",
                    "bithumb", "upbit", "coinone", "bitbank", "mercado", "barrier", "rail",
                    "jurisdiction", "stablecoin rent"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("per-venue local-currency quotes (Upbit/Bithumb/Binance TRY/BRL/CNY OTC)",
                      "the matching official FX fixing on the same instant"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Already screened across KR/JP/BR/TR/US venues and five documented eras; the "
                 "class is well covered rather than data-starved."),
        priority=0),
    MechanismClass(
        id="venue_subsidy_rent",
        name="venue subsidy / rebate rent",
        payer="the venue itself, paying a maker rebate or listing incentive to buy liquidity it "
              "cannot otherwise attract",
        economic_definition="When a venue pays negative maker fees, passive provision earns the "
                            "subsidy independent of any forecast. The edge is the rebate, it is "
                            "sized on the rebate, and it dies the day the schedule changes.",
        signatures=("rebate", "maker fee", "negative maker", "subsidy", "incentive programme",
                    "market maker program", "fee schedule", "liquidity mining"),
        plausibility=0.50, orthogonality=0.85,
        data=DataRequirement(
            datasets=("per-venue fee schedules with maker-rebate tiers and effective dates",
                      "own-fill records proving the rebate tier is reachable at the desk's size"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Fee schedules are public; the load-bearing missing input is evidence the desk "
                 "can reach the rebate tier, which only its own fills can supply."),
        priority=1),
    MechanismClass(
        id="orderbook_microstructure_state",
        name="order-book microstructure state",
        payer="an impatient taker who pays a spread the book's state had already widened, and a "
              "resting order that is picked off because it did not withdraw in time",
        economic_definition="The shape, replenishment and withdrawal dynamics of resting depth "
                            "reveal the intent behind the next print before the print happens. "
                            "It cannot be reconstructed after the fact at any price, which is "
                            "why it is the desk's only genuinely non-replicable data asset.",
        signatures=("order book", "orderbook", "book slope", "book depth", "microprice",
                    "replenish", "withdrawal rate", "resting stability", "effective spread",
                    "quote", "level 2", "l2 tick", "moat"),
        plausibility=0.80, orthogonality=0.90,
        data=DataRequirement(
            datasets=("L2 book snapshots recorded forward under data/moat/ (the recorder exists; "
                      "reports/moat_campaign.json reports the tape EMPTY)",
                      "Tardis.dev historical book snapshots as the paid substitute"),
            availability=DataAvailability.RECORD_FORWARD,
            note="Zero acquisition cost and unbounded replication cost, but it only accrues in "
                 "calendar time -- every day not recording is a day permanently unrecoverable."),
        priority=2),
    MechanismClass(
        id="volatility_risk_premium",
        name="volatility risk premium",
        payer="the option buyer, who pays for insurance systematically above the realised cost "
              "of the risk because he cannot bear the tail himself",
        economic_definition="Implied variance exceeds subsequent realised variance on average "
                            "because someone is paying to transfer tail risk. The premium is "
                            "compensation for bearing that tail, not a forecast.",
        signatures=("vrp", "variance risk premium", "volatility risk premium", "implied vol",
                    "option", "options", "skew", "risk reversal", "straddle", "gamma",
                    "deribit"),
        plausibility=0.85, orthogonality=0.80,
        data=DataRequirement(
            datasets=("Deribit public options chains (keyless): implied surface by expiry",
                      "realised variance on the identical clock",
                      "MORE VOL MARKETS -- the binding constraint named by the existing kill"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The graveyard's `options VRP` row is the campaign's BEST measured IC (+0.06) "
                 "and it died on BREADTH (2 markets), not on sign. The missing input is more "
                 "vol markets, not a better estimator."),
        priority=3),
    MechanismClass(
        id="mechanical_supply_release",
        name="mechanical supply release",
        payer="a vesting insider or a miner with near-zero cost basis who receives coins on a "
              "contractually fixed, publicly known date and whose fund lifecycle forces sale",
        economic_definition="A seller who cannot sell before receipt and must distribute after "
                            "it faces a demand curve that is not waiting for him. Forced seller, "
                            "immutable schedule -- the same shape as funding/carry.",
        signatures=("unlock", "vesting", "insider release", "emission", "halving", "miner sell",
                    "miner distribution", "supply schedule", "float", "cliff"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("data/unlock_events.json (ON DISK, already screened at one construction)",
                      "the vesting SCHEDULE as a time series -- RESOLVED 2026-08-13 (R0385, "
                      "commit f08e041): the parser only consulted instant/timestamp, silently "
                      "dropping all 24,201 rows to the 'current snapshot' fallback that is "
                      "defect_1; adding the schedule's real ts (epoch-seconds) field recovers "
                      "the full series. libs/research/unlock_supply_series.py now reads it as a "
                      "genuine time series, ON DISK, not a snapshot",
                      "circulating-supply history to compute pct-of-float AT the event date"),
            availability=DataAvailability.ON_DISK,
            note="MEASURED 2026-08-13: the schedule-parsing and price-panel-wiring defects "
                 "(R0385) are both fixed and tested (27 tests); the first real run against the "
                 "recovered 24,201-row schedule is this screen's own next scheduled fire "
                 "(Monday 06:25 UTC) -- taking the input from 0 rows to a real count is itself a "
                 "re-run with a real result, so the verdict must be read then, not assumed. The "
                 "remaining genuine gap is pct-of-float normalization (dataset 3)."),
        priority=4),
    MechanismClass(
        id="primary_market_creation_flow",
        name="primary-market creation flow",
        payer="an ETF authorised participant or stablecoin issuer who must buy spot to satisfy a "
              "creation, into whatever float exists on the day",
        economic_definition="Primary-market issuance is REALISED demand that has to be sourced "
                            "in the secondary market. The buyer is contractually committed and "
                            "cannot wait for a better price.",
        signatures=("etf", "creation", "redemption", "authorised participant", "stablecoin",
                    "mint", "issuance", "primary market", "net creations", "flow pressure"),
        plausibility=0.70, orthogonality=0.65,
        data=DataRequirement(
            datasets=("daily spot-ETF creation/redemption flows per issuer",
                      "on-chain stablecoin mint/burn events with issuer attribution",
                      "float/free-supply estimates to scale the flow"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="EV-gated at 0.0191 and REOPENED on the 2026-07-31 gate recalibration, but no "
                 "screen artifact for it exists anywhere in this tree: it is named, not tested."),
        priority=5),
    MechanismClass(
        id="scheduled_event_diffusion",
        name="scheduled-event information diffusion",
        payer="a holder who learns of a listing, delisting or exchange announcement at a fixed "
              "public instant and cannot act before it",
        economic_definition="Information released at a known instant is absorbed over a window "
                            "rather than instantly, so the path after the instant is not a "
                            "martingale. The claim is about the ABSORPTION window, not the news.",
        signatures=("listing", "delisting", "announcement", "event study", "scheduled event",
                    "calendar event", "index inclusion"),
        plausibility=0.45, orthogonality=0.70,
        data=DataRequirement(
            datasets=("data/exchange_announcements.jsonl (ON DISK)",
                      "the announcement INSTANT, not the date -- a same-bar artifact otherwise",
                      "price at sub-daily resolution around the instant"),
            availability=DataAvailability.ON_DISK,
            note="Plausibility is held DOWN on purpose: this is the most latency-contested "
                 "event class in crypto and the desk is not a millisecond participant."),
        priority=6),
    MechanismClass(
        id="manager_skill_persistence",
        name="manager skill persistence",
        payer="nobody is compelled -- the claim is that some agents are persistently skilled and "
              "following them transfers their edge",
        economic_definition="Past risk-adjusted performance predicts future performance strongly "
                            "enough to pay for the copy latency. Selecting past winners must beat "
                            "selecting at random after the winner's-curse correction.",
        signatures=("copytrad", "copy trading", "leaderboard", "trader skill",
                    "skill persistence", "hyperliquid", "elite trader", "lead trader",
                    "top trader", "follow a lead"),
        plausibility=0.10, orthogonality=0.60,
        data=DataRequirement(
            datasets=("gapped formation/holding panels of verified on-chain trader records",),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Tested four independent ways including the strongest available evidence class "
                 "(multi-year cryptographically verifiable records). Plausibility is set at the "
                 "floor BY that evidence -- this is a covered class, not a gap."),
        priority=7),
    MechanismClass(
        id="holder_cost_basis_capitulation",
        name="holder cost-basis capitulation",
        payer="a holder sitting on an unrealised loss who capitulates into whatever bid exists, "
              "or moves coins to the only venue where they can be sold",
        economic_definition="Aggregate cost basis relative to price is a state variable for "
                            "forced-ish selling. Coins arriving at exchanges are revealed "
                            "selling intent and should lead weaker returns.",
        signatures=("mvrv", "realized cap", "realised cap", "realized price", "cost basis",
                    "sopr", "exchange netflow", "netflow", "exchange inflow", "exchange outflow",
                    "nvt", "mayer multiple", "capitulation"),
        plausibility=0.55, orthogonality=0.60,
        data=DataRequirement(
            datasets=("Coin Metrics community daily (netflow_ntv, CapMVRVCur) -- 16y depth",
                      "PER-EXCHANGE decomposition rather than the aggregate, and/or intraday "
                      "granularity: the exact two escalations the exchange-netflow kill names"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Two constructions tested, both dead at daily aggregate frequency, and both "
                 "kills name the same unexplored escalation. Licence for production use of the "
                 "CM community CSV (CC BY-NC) is an open ruling, not a settled permission."),
        priority=8),
    MechanismClass(
        id="positioning_crowding_unwind",
        name="positioning / crowding unwind",
        payer="a leveraged trader whose position is liquidated by the venue at whatever price "
              "the book offers, having lost the choice of when to trade",
        economic_definition="Crowded leverage is an inventory that must be unwound on somebody "
                            "else's schedule. Observable positioning should therefore predict "
                            "the direction of the forced flow that follows.",
        signatures=("open interest", "oi", "oi divergence", "long short ratio", "ls contrarian",
                    "liquidation", "positioning", "crowding", "cot", "commitments of traders",
                    "hedging pressure", "leverage stress", "funding stress", "account ratio",
                    "position ratio", "smart money", "dumb money"),
        plausibility=0.65, orthogonality=0.50,
        data=DataRequirement(
            datasets=("Binance derivative-metrics archive (OI, long/short ratios) -- ON DISK",
                      "liquidation prints at trade granularity"),
            availability=DataAvailability.ON_DISK,
            note="Broadly covered: six-plus constructions across crypto positioning and 26 years "
                 "of CFTC COT, whose lagged-form test was pre-committed as a class-level gate."),
        priority=9),
    MechanismClass(
        id="informed_order_flow",
        name="informed order flow",
        payer="the uninformed counterparty who fills an informed order and learns its "
              "information only after the price has already moved",
        economic_definition="Signed aggressive flow carries information beyond its own price "
                            "impact. The test that matters is whether flow LEADS the return or "
                            "is merely CONCURRENT with it -- buying moves price by construction.",
        signatures=("order flow", "orderflow", "taker", "taker buy", "ofi", "vpin",
                    "aggressive buying", "absorption", "signed flow", "trade imbalance",
                    "block trade", "large print", "directional order flow"),
        plausibility=0.70, orthogonality=0.55,
        data=DataRequirement(
            datasets=("trade-level signed flow (Binance aggTrades / Hyperliquid fills)",
                      "data/idle_axis_screen.json -- the one screen carrying the "
                      "return-residualised absorption construction -- is NOT READABLE in this "
                      "checkout, so its cells cannot be counted here"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Every kill so far dies on the same defect: flow is concurrent with price and "
                 "fails de-contamination. The untested form is flow that is residualised against "
                 "the same-period return BEFORE it is asked to predict anything."),
        priority=10),
    MechanismClass(
        id="network_usage_demand",
        name="network usage / adoption demand",
        payer="nobody is compelled -- the claim is that real settlement demand for a "
              "supply-inelastic asset is absorbed slowly enough to be tradeable",
        economic_definition="Blockspace, fee and application usage is economic activity that "
                            "cannot be manufactured with leverage. Adoption-driven demand should "
                            "therefore lead returns at the horizon at which adoption operates.",
        signatures=("on chain", "onchain", "blockspace", "throughput", "transaction volume",
                    "tvl", "defi", "dex", "gas", "mempool", "active address", "hashrate",
                    "difficulty", "commit velocity", "developer", "github", "adoption"),
        plausibility=0.35, orthogonality=0.55,
        data=DataRequirement(
            datasets=("blockchain.info / DefiLlama / Coin Metrics activity aggregates",
                      "a WEEKLY-or-slower target clock: every kill in this class was run daily"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Well covered at the daily horizon and dead there. The residual question is "
                 "horizon, not data."),
        priority=11),
    MechanismClass(
        id="derivative_carry_basis",
        name="derivative carry / basis",
        payer="the leveraged long, who pays funding or a basis premium every interval to hold "
              "exposure he cannot or will not fund with cash",
        economic_definition="Perpetual funding and dated-future basis are a recurring payment "
                            "from levered longs to whoever supplies the spot leg. The payment is "
                            "observable in advance and the convergence is contractual.",
        signatures=("funding", "carry", "basis", "cash and carry", "cashcarry", "perp premium",
                    "roll yield", "contango", "backwardation", "term structure", "cme basis"),
        plausibility=0.85, orthogonality=0.30,
        data=DataRequirement(
            datasets=("Binance/BitMEX funding history and perp-spot basis -- ON DISK",),
            availability=DataAvailability.ON_DISK,
            note="The desk's only repeat-surviving family and its live book. Depth is real; the "
                 "open questions here are execution and capacity, not mechanism supply."),
        priority=12),
    MechanismClass(
        id="macro_liquidity_transmission",
        name="macro / liquidity transmission",
        payer="nobody is compelled -- the claim is that global liquidity and risk appetite reach "
              "a risk asset with a lag long enough to trade",
        economic_definition="Dollar, policy-liquidity and cross-asset risk states propagate into "
                            "the traded instrument (FX, gold, indices, energy) with a delay. The "
                            "tradeable form must be a standalone directional claim, not a "
                            "conditioning overlay on an existing book.",
        signatures=("macro", "dxy", "dollar strength", "fed", "walcl", "net liquidity",
                    "treasury", "rates", "spx", "ndx", "equity", "gold", "digital gold",
                    "risk regime", "crossasset", "cross asset", "risk off", "rotation"),
        plausibility=0.40, orthogonality=0.40,
        data=DataRequirement(
            datasets=("FRED public-domain series (WALCL/TGA/RRP, DXY, rates)",
                      "equity and metal index closes on a declared session clock"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The OVERLAY form of this class is dead three separate ways. Only the "
                 "standalone directional form is live, and it has been EV-gated rather than run."),
        priority=13),
    MechanismClass(
        id="attention_sentiment_overreaction",
        name="attention / sentiment overreaction",
        payer="the late retail buyer whose attention arrives after the move and who marks local "
              "crowding by arriving",
        economic_definition="Attention proxies peak at crowding rather than leading it, so the "
                            "tradeable claim is a FADE of attention spikes -- and it must beat "
                            "the fact that attention co-moves with the return it would predict.",
        signatures=("attention", "wikipedia", "pageview", "google trends", "search trends",
                    "sentiment", "fear", "greed", "social", "nlp", "twitter", "reddit"),
        plausibility=0.25, orthogonality=0.50,
        data=DataRequirement(
            datasets=("Wikipedia pageviews API (free)", "Fear&Greed index history"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Killed across five languages at daily horizon, which the kill note generalises "
                 "to the whole search-trends category. Weekly conditioning is the only residual."),
        priority=14),
    MechanismClass(
        id="cross_sectional_risk_premium",
        name="cross-sectional risk premium",
        payer="the investor who declines to hold a priced characteristic -- smallness, "
              "illiquidity, high idiosyncratic risk -- and pays whoever will",
        economic_definition="A characteristic commands a return spread in the cross-section "
                            "because holding it carries a risk somebody wants to avoid. The "
                            "spread must survive value-weighting and a liquid universe.",
        signatures=("xsec", "cross sectional", "cross section", "size effect", "low vol",
                    "lowvol", "illiquidity", "value factor", "anomaly", "factor model",
                    "characteristic sort", "ratio mining", "trading frictions"),
        plausibility=0.30, orthogonality=0.25,
        data=DataRequirement(
            datasets=("the existing perp panel -- ON DISK, no new data required",),
            availability=DataAvailability.ON_DISK,
            note="Two independent published crypto teams and one 452-anomaly equity replication "
                 "put this class's survival rate near zero once micro-caps and equal-weighting "
                 "are removed. Low plausibility is EARNED, not assumed."),
        priority=15),
    MechanismClass(
        id="relative_value_convergence",
        name="relative-value convergence",
        payer="whoever demanded immediacy in one leg of a pair whose legs are tied by a common "
              "factor, and pays the trader willing to hold the residual until it closes",
        economic_definition="Two instruments linked by a shared factor diverge on flow rather "
                            "than information, and the residual re-converges. The claim is about "
                            "the RESIDUAL; the shared factor is differenced away, not traded.",
        signatures=("intermarket", "relative value", "pairs trad", "pair trade", "cointegrat",
                    "statarb", "statistical arbitrage", "kalman", "hedge ratio", "leadlag",
                    "lead lag", "inverse reference", "spread convergence", "residual"),
        plausibility=0.55, orthogonality=0.45,
        data=DataRequirement(
            datasets=("the existing panel plus each reference leg's RANGE, not only its close",
                      "borrow/short cost per leg -- the RU evidence says this class dies on "
                      "costs and capacity, never on the estimator"),
            availability=DataAvailability.ON_DISK,
            note="The graveyard kills the Kalman REFINEMENT and states explicitly that pairs "
                 "trading itself is UNTESTED here. Two thin constructions exist in the campaign."),
        priority=16),
    MechanismClass(
        id="market_risk_premium",
        name="market risk premium",
        payer="the investor who will not hold undiversifiable market risk and pays whoever does",
        economic_definition="Holding the asset earns compensation for its non-diversifiable "
                            "risk. This is the benchmark every other mechanism must beat, and "
                            "harvesting it is an allocation decision rather than an edge.",
        signatures=("persistent long", "buy and hold", "risk premia", "risk premium harvest",
                    "beta exposure", "long run premium"),
        plausibility=0.90, orthogonality=0.05,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="Real and already available to anyone. Orthogonality ~0 by definition: it is "
                 "the benchmark, so testing it more cannot widen the hypothesis set."),
        priority=29),
    MechanismClass(
        id="liquidity_provision_immediacy",
        name="liquidity provision / immediacy",
        payer="a trader forced to transact NOW -- a stop, a margin call, an index rebalance, an "
              "inventory limit -- who pays whoever will warehouse the other side",
        economic_definition="Price dislocates from value when immediacy demand exceeds the "
                            "inventory the market will hold, and reverts as inventory is laid "
                            "off. Every variant differs only in WHERE it claims the forced flow "
                            "sits: a z-score band, a VWAP stretch, a range extreme, a swept "
                            "swing high, or an unfilled institutional base.",
        signatures=("mean revers", "mean revert", "reversal", "fade", "zscore fade",
                    "vwap reversion", "shock fade", "wyckoff", "spring", "upthrust",
                    "liquidity sweep", "sweep reversal", "supply demand", "supply and demand",
                    "contrarian", "short term reversal", "olmar", "olps", "follow the loser",
                    "grid", "ladder", "liquidity provision", "market making", "inventory"),
        plausibility=0.55, orthogonality=0.10,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="Tested to exhaustion on price alone. The only untested escalation needs the "
                 "book, which is a different class (orderbook_microstructure_state)."),
        priority=30),
    MechanismClass(
        id="price_continuation",
        name="price continuation / underreaction",
        payer="a trader who under-reacted to information and must complete the same adjustment "
              "later, at a worse price",
        economic_definition="Information diffuses into price slowly, so the sign of a past move "
                            "predicts the sign of the next one. Every window, every smoother and "
                            "every breakout definition is one parameterisation of that sentence.",
        signatures=("trend", "momentum", "breakout", "donchian", "ma cross", "moving average",
                    "continuation", "tsmom", "time series mom", "vwap trend", "displacement",
                    "market structure shift", "mss", "fair value gap", "fvg", "squeeze",
                    "vol trend", "drift", "ichimoku", "macd", "adx", "ema", "kama",
                    "ta indicator", "channel"),
        plausibility=0.35, orthogonality=0.03,
        data=DataRequirement(
            datasets=("the price panel already on disk",),
            availability=DataAvailability.ON_DISK,
            note="The desk's most-tested class by an order of magnitude and the one an "
                 "independent 2013-14 pre-registered natural experiment killed as well. Adding "
                 "candidates here cannot widen the hypothesis set."),
        priority=31),
    # ================================================================================ 2026-08-05
    # SIX CLASSES THE TAXONOMY HAD NEVER NAMED. The census can only rank what it has named, so an
    # absent class is not low-ranked -- it is INVISIBLE, and every coverage number the desk quotes
    # is computed against a denominator that silently excludes it. With the binding constraint
    # measured as DISTINCT MECHANISM SUPPLY (44 candidates covering 2.787 effective classes,
    # cross-mechanism N_eff 4.08 against the ~100 a weak-edge portfolio needs), widening what can
    # be ranked is worth more than another candidate inside an existing class.
    #
    # ADMISSION TEST APPLIED TO EACH, and it is the same one the charter uses: name a participant
    # compelled by a BALANCE SHEET, A COURT OR A RULE -- never by an opinion -- and say why they
    # cannot stop. A class whose "payer" is someone being wrong is a pattern, not a mechanism, and
    # does not belong here however well it would backtest.
    #
    # Each was checked against all twenty existing classes for genuine distinctness rather than
    # vocabulary overlap; the distinction is recorded in each entry because "isn't that just
    # X?" is the first question any of these will face.
    MechanismClass(
        id="index_reconstitution_flow",
        name="index reconstitution / rebalance flow",
        payer="a tracking fund, ETP or structured product whose MANDATE forces it to hold the "
              "index as published -- it must trade the reconstitution on the effective date at "
              "whatever price clears, and a manager who declines is running tracking error they "
              "are contractually not permitted to run",
        economic_definition="An index change is a dated, pre-announced, price-insensitive order "
                            "of known direction and approximately known size. Whoever supplies "
                            "that liquidity is paid for immediacy by a buyer who cannot wait and "
                            "cannot negotiate. The edge lives between announcement and effective "
                            "date and dies with the flow -- it is compensation for absorbing a "
                            "mandate, not a forecast of value.",
        signatures=("index inclusion", "index exclusion", "reconstitution", "rebalance date",
                    "index add", "index delete", "effective date", "tracking fund", "etp basket",
                    "index methodology", "quarterly review", "free float adjustment"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("index methodology documents with announcement and effective dates",
                      "constituent lists before and after each review",
                      "daily bars around the two dates for members and non-members"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT primary_market_creation_flow: that class is creation/redemption of wrapper "
                 "SHARES (flow into the vehicle). This is the vehicle's INTERNAL rebalance, on a "
                 "different date, with a different observable and an opposite sign convention. "
                 "The canonical forced-participant mechanism in equities, with a direct crypto "
                 "analogue in index products and exchange index composition; never screened."),
        priority=17),
    MechanismClass(
        id="treasury_cost_base_liquidation",
        name="producer treasury / fixed-cost-base liquidation",
        payer="a miner or validator carrying a FIAT cost base -- power, hosting, leased hardware, "
              "debt service -- against a coin-denominated revenue. Fiat obligations do not "
              "reschedule for a drawdown, so coin must be sold on the operator's calendar rather "
              "than on the market's, and hardest exactly when price is weakest",
        economic_definition="A structurally price-INSENSITIVE seller whose supply rises as margin "
                            "compresses. The flow is forced by a balance sheet, is observable "
                            "on-chain before it reaches an exchange, and is uncorrelated with any "
                            "view about value -- the seller would prefer not to sell.",
        signatures=("miner outflow", "miner treasury", "hashprice", "hash price", "difficulty "
                    "adjustment", "validator treasury", "staking reward sale", "producer "
                    "selling", "mining pool payout", "coinbase output", "cost of production"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("on-chain mining-pool payout addresses and their exchange-bound transfers",
                      "network difficulty and block subsidy for a cost-of-production proxy",
                      "public hashprice series"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT mechanical_supply_release: that is a SCHEDULE (vesting, emissions) known in "
                 "advance. This is a BALANCE-SHEET constraint whose timing is driven by the "
                 "operator's fiat obligations and margin, not by a calendar. NOT "
                 "network_usage_demand, which is adoption. The desk's own VRP pre-registration "
                 "already named this payer type -- 'a miner with a fixed fiat cost base' -- while "
                 "the taxonomy had no class to file it under."),
        priority=18),
    MechanismClass(
        id="estate_liquidation_distribution",
        name="estate / court-ordered liquidation and distribution",
        payer="a bankruptcy estate, receiver or liquidator under a COURT ORDER, and the creditors "
              "who receive an in-kind distribution they did not choose the timing of. A trustee "
              "sells because a court told them to and on the court's schedule; a creditor "
              "receiving coin after years of illiquidity is a highly motivated seller",
        economic_definition="A legally compelled, publicly docketed supply event with a knowable "
                            "size and an approximately knowable date. The compulsion is judicial "
                            "rather than economic, which is why it does not respond to price and "
                            "why the schedule survives changes in market conditions.",
        signatures=("estate", "bankruptcy", "trustee", "receiver", "liquidator", "creditor "
                    "distribution", "in-kind distribution", "court order", "chapter 11",
                    "civil rehabilitation", "mt gox", "ftx estate", "claims process"),
        plausibility=0.70, orthogonality=0.80,
        data=DataRequirement(
            datasets=("court dockets and trustee announcements with distribution dates",
                      "on-chain estate wallet balances and their outbound transfers",
                      "daily bars around each announced and executed tranche"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="Distinct from mechanical_supply_release (protocol emissions) and from "
                 "holder_cost_basis_capitulation (a price-triggered decision). Here the trigger "
                 "is a filing. Rare events, so the honest expectation is a SMALL n -- which makes "
                 "it a class where the desk must state power before testing rather than after."),
        priority=19),
    MechanismClass(
        id="collateral_rule_deleveraging",
        name="collateral rule change / forced deleveraging",
        payer="a levered borrower whose position is closed by a RULE rather than by their own "
              "decision -- a raised haircut, a lowered LTV ceiling, a collateral-eligibility "
              "removal, an oracle re-mark or a liquidation-engine parameter change. The borrower "
              "cannot opt out: the venue closes the position for them",
        economic_definition="A supply or demand shock whose timing is set by a published "
                            "governance or risk-parameter change, not by price. Because the "
                            "parameter change is announced and the affected positions are visible "
                            "on-chain, the flow is forecastable in direction and approximate size "
                            "BEFORE it executes -- which is what distinguishes it from watching a "
                            "cascade after the fact.",
        signatures=("haircut", "loan to value", "ltv", "collateral factor", "liquidation "
                    "threshold", "collateral eligibility", "risk parameter", "oracle update",
                    "margin requirement change", "isolated mode", "debt ceiling"),
        plausibility=0.70, orthogonality=0.65,
        data=DataRequirement(
            datasets=("lending-protocol governance logs with parameter values and effective "
                      "blocks (Aave/Compound/Maker event logs via free RPC)",
                      "position-level collateral and debt snapshots around each change"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT positioning_crowding_unwind: that class is crowding measured from "
                 "positioning data and unwinding under its own weight. This one is RULE-DRIVEN "
                 "and typically PRE-ANNOUNCED, so it is forecastable ex ante rather than "
                 "diagnosable ex post -- the difference between a scheduled eviction and a fire."),
        priority=20),
    MechanismClass(
        id="settlement_expiry_mechanics",
        name="settlement / expiry hedging mechanics",
        payer="a dealer or market maker who is short optionality into a DATED settlement and must "
              "hedge to a fixing they do not control, plus every holder whose contract "
              "cash-settles against that same print. Neither chooses the timing: the contract "
              "specifies it",
        economic_definition="Delta and gamma hedging demand concentrates mechanically as a dated "
                            "expiry approaches, and its sign flips with strike placement. The "
                            "flow is a function of open interest and time, both public, rather "
                            "than of any view -- so it is predictable from the contract "
                            "specification alone.",
        signatures=("expiry", "expiration", "settlement fixing", "pin risk", "max pain",
                    "gamma exposure", "dealer gamma", "open interest at strike", "quarterly "
                    "settlement", "roll date", "final settlement price"),
        plausibility=0.60, orthogonality=0.60,
        data=DataRequirement(
            datasets=("option open interest by strike and expiry (Deribit public API)",
                      "settlement/fixing methodology and timestamps per venue",
                      "sub-daily bars spanning the settlement window"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT volatility_risk_premium: that class prices the PREMIUM paid for insurance. "
                 "This one is the mechanical HEDGING FLOW around a dated settlement, which exists "
                 "whether the premium is rich or cheap. The desk already collects the Deribit "
                 "chain for VRP, so the input largely exists and is unread for this purpose."),
        priority=21),
    MechanismClass(
        id="fiscal_calendar_flow",
        name="fiscal / tax calendar forced flow",
        payer="a holder compelled by a TAX OR ACCOUNTING deadline -- loss harvesting before a "
              "fiscal year end, a wash-sale window, a fund's reporting-date window dressing, a "
              "corporate treasury marking to a quarter end. The deadline is set by a statute or "
              "an accounting standard, so it does not move because the market did",
        economic_definition="A recurring, date-anchored flow whose direction is predictable from "
                            "the holder's prior-period P&L rather than from any forecast. It "
                            "reverses after the deadline passes, which is the falsifiable part: "
                            "no reversal means the flow was a preference, not a compulsion.",
        signatures=("tax loss harvesting", "wash sale", "fiscal year end", "financial year end",
                    "window dressing", "quarter end", "reporting date", "turn of the year",
                    "january effect", "capital gains deadline"),
        plausibility=0.55, orthogonality=0.70,
        data=DataRequirement(
            datasets=("jurisdiction fiscal-year-end and wash-sale rule dates",
                      "daily bars with prior-period return to sign the expected flow",
                      "a control cohort not subject to the same deadline"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="The weakest payer story of the six and priced accordingly -- crypto's holder "
                 "base is jurisdictionally mixed, so the compelled fraction is unknown and may be "
                 "small. Recorded anyway: L1.49 says a weak mechanism is not a dead one, and an "
                 "UNNAMED class cannot even be ranked as weak."),
        priority=22),
    # ================================================================================ 2026-08-18
    # SIX MT5-NATIVE CLASSES THE TAXONOMY HAD NEVER NAMED. The desk's universe is now the full
    # MT5/Fusion market (FX, gold, metals, indices, energy, share CFDs), and every forced-flow
    # mechanism below was INVISIBLE to a census whose vocabulary was crypto: FX carry is a sovereign
    # rate differential, not perp funding; COT producer hedging is a physical short, not a miner
    # dump; a benchmark fix is a mandated order, not an inferred sweep. Each is data-specific, so it
    # sorts before the generic price tail (priorities 29-31, bumped up to open this band). All are
    # testable on FREE data the desk already reaches or can pull keyless: FRED rate curves, the
    # CFTC COT weekly file, EIA inventories, and the desk's own MT5 session bars.
    MechanismClass(
        id="fx_carry_rate_differential",
        name="FX carry / interest-rate differential",
        payer="the holder short the higher-yielding currency, who is contractually debited the "
              "overnight interest-rate differential every day the position is held -- a swap / "
              "rollover charge the broker MUST apply and that the position cannot avoid without "
              "closing -- and pays it to whoever is long the carry and warehouses the crash risk",
        economic_definition="Two sovereign short rates differ, and a position spanning them earns "
                            "or pays that differential as a daily rollover independent of any "
                            "price forecast. The excess return is compensation for bearing the "
                            "crash risk that periodically unwinds the carry trade violently, so "
                            "the payoff is negatively skewed by construction rather than by luck.",
        signatures=("carry", "carry trade", "interest rate differential", "rate differential",
                    "rollover", "swap points", "swap long", "swap short", "forward points",
                    "covered interest parity", "cip", "funding currency", "yield differential"),
        plausibility=0.80, orthogonality=0.75,
        data=DataRequirement(
            datasets=("FRED sovereign policy / short rates per currency (keyless, free)",
                      "the desk's FX spot bars for the two legs on the same clock",
                      "broker swap_long/swap_short for the realised (not theoretical) daily cost"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT derivative_carry_basis: that class's payer is a crypto perpetual long paying "
                 "an 8-hour funding rate to a shorter; this payer is short a sovereign yield and "
                 "pays a rollover set by two central banks' policy rates -- a different balance "
                 "sheet, a different clock, and an unwind driven by rate-regime shifts."),
        priority=23),
    MechanismClass(
        id="central_bank_event_surprise",
        name="central-bank / macro event surprise",
        payer="every holder forced to reprice at a scheduled, known-instant policy decision or "
              "top-tier data print (FOMC, ECB, BoE, NFP, CPI): the surprise -- actual minus what "
              "the futures curve had priced -- lands on whoever was mandated to hold through the "
              "release and cannot pre-position past their risk limit; it moves in one clock tick",
        economic_definition="The market prices a consensus before a scheduled release; the gap "
                            "between outcome and that priced consensus drives an immediate jump "
                            "plus a documented multi-hour drift as slower participants complete "
                            "the adjustment. The tradeable object is the SURPRISE, constructed "
                            "point-in-time, not the announced level.",
        signatures=("nfp", "non-farm", "non farm payrolls", "cpi", "fomc", "ecb", "boe", "boj",
                    "rate decision", "central bank", "economic calendar", "surprise", "consensus",
                    "data release", "post-announcement drift", "eco surprise", "macro print"),
        plausibility=0.75, orthogonality=0.70,
        data=DataRequirement(
            datasets=("FRED releases plus a free economic-calendar consensus (keyless)",
                      "fed-funds / STIR futures-implied probabilities to build the surprise",
                      "the desk's FX / metal / index bars stamped around each release"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT macro_liquidity_transmission: that class is a slow, ambient drift of "
                 "dollar and rates liquidity into a risk asset with NO event; this one is an "
                 "instantaneous, scheduled, known-clock repricing whose signal is the surprise "
                 "around a single timestamp, not a lagged spillover."),
        priority=24),
    MechanismClass(
        id="session_fix_liquidity",
        name="session structure / benchmark-fix liquidity",
        payer="the passive fund and the corporate hedger mandated to execute at a published "
              "benchmark fixing they do not control -- the 4pm WMR London FX fix, the LBMA gold "
              "fix -- who MUST submit a price-insensitive, time-concentrated order at the window "
              "regardless of level, and pays the warehouser who takes the other side of that flow",
        economic_definition="A benchmark fix concentrates mandated, price-insensitive order flow "
                            "into a fixed daily window, so the flow imbalance predicts a "
                            "systematic pre-fix drift and post-fix reversal; and the session-open "
                            "and -close handoffs (Tokyo to London to New York) carry their own "
                            "liquidity-regime transitions that a 24-hour tape would smear out.",
        signatures=("session", "london fix", "wmr", "4pm fix", "lbma", "gold fix", "asian session",
                    "london open", "new york session", "tokyo session", "session open",
                    "fixing", "benchmark fix", "rollover time", "session close"),
        plausibility=0.65, orthogonality=0.75,
        data=DataRequirement(
            datasets=("the desk's own intraday FX / metal bars stamped to session and fix windows",
                      "published fix times and methodology (free)"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT liquidity_provision_immediacy: that class fades a generic forced flow "
                 "wherever a price band says it sits; this one is anchored to a CALENDARED, "
                 "published fixing whose participants and clock are known in advance, so the "
                 "forced flow is scheduled rather than inferred from price."),
        priority=25),
    MechanismClass(
        id="commodity_inventory_supply",
        name="commodity inventory / convenience yield",
        payer="the physically-short consumer or the long forced to finance storage when "
              "inventories swing -- a refiner, a utility, a merchant -- whose hedging book MUST "
              "rebalance to a published inventory print (EIA petroleum status, LME/COMEX "
              "warehouse stocks) and pays whoever holds the convenience-yield term structure",
        economic_definition="Physical inventory levels and their surprises drive the convenience "
                            "yield and the front-of-curve spread; a consumer short the physical "
                            "must pay up when stocks draw and the curve backwardates. The signal "
                            "is the inventory surprise, and it is orthogonal to every "
                            "financial-flow mechanism the desk already names.",
        signatures=("inventory", "eia", "petroleum status", "warehouse stocks", "convenience yield",
                    "contango", "backwardation", "storage", "wasde", "crop report", "lme stocks",
                    "comex warehouse", "physical supply", "stock draw", "stock build"),
        plausibility=0.65, orthogonality=0.85,
        data=DataRequirement(
            datasets=("EIA weekly petroleum status (free public file)",
                      "USDA/WASDE and LME/COMEX warehouse stocks (free)",
                      "the desk's energy / metal bars on the release clock"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT mechanical_supply_release: that class is a crypto insider or miner dumping "
                 "vested coins with a near-zero cost basis on a fixed unlock date; this is a "
                 "physical-commodity inventory surprise repricing a convenience yield -- a storage "
                 "economy, not a vesting schedule."),
        priority=26),
    MechanismClass(
        id="overnight_gap_risk_premium",
        name="overnight / weekend gap-risk premium",
        payer="the holder who cannot flatten across a market closure -- an FX book into the "
              "weekend, an index or share CFD overnight -- who either pays for gap insurance or is "
              "compensated for warehousing the jump risk a closed market cannot price "
              "continuously; the closure is a hard calendar fact the position cannot trade around",
        economic_definition="Instruments with defined session closes accumulate information while "
                            "shut and re-open at a gap, so the close-to-open jump carries a risk "
                            "premium distinct from intraday realised variance, fat-tailed around "
                            "weekends, holidays and scheduled closures.",
        signatures=("gap", "overnight", "weekend gap", "holiday gap", "close to open",
                    "opening gap", "session close", "gap risk", "jump risk", "overnight hold",
                    "carry across weekend", "monday gap", "gap fill"),
        plausibility=0.60, orthogonality=0.70,
        data=DataRequirement(
            datasets=("the desk's own bars split into close-to-open jumps versus intraday range",
                      "the session / holiday calendar per instrument (free)"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT volatility_risk_premium: that class sells implied-minus-realised variance "
                 "through options; this one prices the discrete close-to-open JUMP of an "
                 "instrument that literally stops trading -- a gap risk 24/7 crypto does not have "
                 "and that needs no options market to measure."),
        priority=27),
    MechanismClass(
        id="producer_hedging_flow",
        name="commodity producer hedging flow (COT commercial)",
        payer="the commodity producer contractually forward-selling output to lock a fiat margin "
              "-- a gold miner, an oil driller, a farmer -- whose hedge is a mandated, "
              "price-insensitive supply visible in the CFTC commercial category, and who MUST "
              "roll and add to it on the operator's calendar regardless of where price sits",
        economic_definition="Commercial hedgers carry a structural short driven by production "
                            "schedules, not by a forecast; the extremes and changes of their COT "
                            "position mark where price-insensitive supply is entering, which "
                            "predicts the speculative side's forced accommodation.",
        signatures=("producer hedging", "commercial hedger", "cot commercial", "cot",
                    "commitments of traders", "forward selling", "producer short",
                    "hedging pressure", "commercial net", "swap dealer", "merchant hedge",
                    "gold miner hedge", "disaggregated cot"),
        plausibility=0.65, orthogonality=0.80,
        data=DataRequirement(
            datasets=("CFTC COT commercial / hedger category (free weekly file, already parsed "
                      "for the desk's positioning work)",
                      "the desk's futures / CFD bars for gold, silver, energy and indices"),
            availability=DataAvailability.FREE_ACQUIRABLE,
            note="NOT treasury_cost_base_liquidation: that class is a crypto miner selling block "
                 "rewards to cover a fiat electricity bill, read on-chain; this is a TradFi "
                 "commodity producer forward-hedging output, read in the CFTC commercial COT "
                 "category -- a hedging programme, not an on-chain payout."),
        priority=28),
)

CLASS_BY_ID: dict[str, MechanismClass] = {c.id: c for c in TAXONOMY}


# ------------------------------------------------------------------- construction ground truth --
# READ FACTS, not guesses. Each key is a construction name that appears verbatim in
# reports/real_campaign.json; each value is the class its IMPLEMENTATION in
# libs/autodiscovery/generators.py places it in. This map exists because the campaign's declared
# FAMILY label is occasionally not the economic mechanism: `drift_proxy` is filed under the
# `carry` family and is implemented as `momentum_positions(lookback=200)` -- generators.py labels
# it "PROXY: no swap/rate data" in its own edge_source string. Classifying it as carry would
# credit the desk with a carry test it never ran, which is exactly the error this census exists
# to remove. Anything absent from this map falls through to signature classification.
CONSTRUCTION_CLASS: dict[str, str] = {
    "ma_cross": "price_continuation",
    "time_series_mom": "price_continuation",
    "donchian": "price_continuation",
    "squeeze_breakout": "price_continuation",
    "vol_trend": "price_continuation",
    "vol_onset_trend": "price_continuation",
    "vwap_trend": "price_continuation",
    "ict_mss_follow": "price_continuation",
    "ict_fvg_follow": "price_continuation",
    "session_open_mom": "price_continuation",
    "drift_proxy": "price_continuation",
    "zscore_fade": "liquidity_provision_immediacy",
    "vwap_reversion": "liquidity_provision_immediacy",
    "shock_fade": "liquidity_provision_immediacy",
    "wyckoff_spring": "liquidity_provision_immediacy",
    "ict_sweep_reversal": "liquidity_provision_immediacy",
    "supply_demand_retest": "liquidity_provision_immediacy",
    "intermarket_difference": "relative_value_convergence",
    "inverse_reference": "relative_value_convergence",
    "persistent_long": "market_risk_premium",
    "funding_stress_reversal": "positioning_crowding_unwind",
}


# --------------------------------------------------------------------------- classification ----
_WS = re.compile(r"\s+")


def _hay(text: str) -> str:
    """Normalise a candidate's text so `ma_cross`, `ma-cross` and `MA cross` all read alike."""
    low = (text or "").lower()
    low = re.sub(r"[^a-z0-9]+", " ", low)
    return _WS.sub(" ", low).strip()


_SIG_RE: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    c.id: tuple((s, re.compile(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])"))
                for s in c.signatures)
    for c in TAXONOMY
}


def classify(text: str, *, construction: str | None = None) -> tuple[str | None, tuple[str, ...]]:
    """Return ``(class_id, matched_signatures)``; ``(None, ())`` when nothing matches.

    A construction present in ``CONSTRUCTION_CLASS`` short-circuits: that map is read from the
    implementation, and an implementation beats a keyword every time. Otherwise the class with
    the MOST matched signatures wins, ties broken by taxonomy priority so that a specific
    economic vocabulary always outbids the promiscuous price-only one.

    Returning ``None`` is a first-class outcome. A record this function cannot place is reported
    as unclassified rather than pushed into the nearest plausible class -- a fabricated
    classification would show up as coverage the desk does not have.
    """
    if construction is not None:
        declared = CONSTRUCTION_CLASS.get(construction)
        if declared is not None:
            return declared, ("construction:" + construction,)
    hay = _hay(text)
    if not hay:
        return None, ()
    best: tuple[int, int, str] | None = None
    matched: dict[str, tuple[str, ...]] = {}
    for cls in TAXONOMY:
        hits = tuple(sig for sig, rx in _SIG_RE[cls.id] if rx.search(hay) is not None)
        if not hits:
            continue
        matched[cls.id] = hits
        key = (-len(hits), cls.priority, cls.id)
        if best is None or key < best:
            best = key
    if best is None:
        return None, ()
    return best[2], matched[best[2]]


# ------------------------------------------------------------------------- verdict normalising --
#: Phrases that say the kill came from SOMEBODY ELSE'S evidence rather than a desk test: a
#: published paper, an era forum thread, a community attribution study. Checked before anything
#: else, because those write-ups are full of ordinary kill vocabulary and would otherwise read as
#: desk results -- inflating tested depth with experiments this desk never ran.
_EXTERNAL_BASIS_MARKERS: tuple[str, ...] = (
    "external literature", "pre emptive kill", "pre emptively killed", "pre emptive",
    "era evidence", "era instance", "era provenance", "killed at source", "refuted at source",
    "not by us", "not a desk backtest", "killed by the replies", "external prior",
)

#: Phrases that must beat the un-negated token they contain. "NOT REFUTED, NOT SUPPORTED --
#: UNMEASURED at the threshold that carries the mechanism" contains the substring "refuted" and
#: means the opposite of it; reading that row as a kill is the exact failure this census forbids.
_NEGATIONS: tuple[tuple[str, Verdict], ...] = (
    ("not refuted", Verdict.UNDERPOWERED),
    ("not supported", Verdict.UNDERPOWERED),
    ("licence forbids", Verdict.NOT_MEASURED),
    ("not a technical failure", Verdict.NOT_MEASURED),
)

#: Longest-token-first so `no_edge_daily` is not swallowed by `no_edge`.
#:
#: `survived` IS DELIBERATELY ABSENT. SURVIVED is only ever set structurally -- every gate on the
#: record cleared -- and never inferred from prose, so no write-up can talk a dead candidate into
#: the survivor column by containing the word. (It nearly did: a kill note reporting that "4 of
#: 15,256 arbitrage signals survived manual review" read as a surviving hypothesis.)
_VERDICT_TOKENS: tuple[tuple[str, Verdict], ...] = (
    ("screen underpowered", Verdict.UNDERPOWERED),
    ("underpowered", Verdict.UNDERPOWERED),
    ("untestable", Verdict.UNDERPOWERED),
    ("could not tell", Verdict.UNDERPOWERED),
    ("insignificant", Verdict.REFUTED),
    ("lookahead artifact", Verdict.ARTIFACT),
    ("look ahead", Verdict.ARTIFACT),
    ("timing artifact", Verdict.ARTIFACT),
    ("position overlap artifact", Verdict.ARTIFACT),
    ("unstable artifact", Verdict.ARTIFACT),
    ("regime artifact", Verdict.ARTIFACT),
    ("contaminated", Verdict.ARTIFACT),
    ("screen weak", Verdict.REFUTED),
    ("no edge daily", Verdict.REFUTED),
    ("no edge", Verdict.REFUTED),
    ("no economics", Verdict.REFUTED),
    ("no predictive power", Verdict.REFUTED),
    ("mechanism refuted", Verdict.REFUTED),
    ("wrong sign", Verdict.REFUTED),
    ("wrong orthogonality", Verdict.REFUTED),
    ("costs killed edge", Verdict.REFUTED),
    ("no breadth", Verdict.REFUTED),
    ("narrow breadth", Verdict.REFUTED),
    ("overfit", Verdict.REFUTED),
    ("crowded", Verdict.REFUTED),
    ("redundant", Verdict.REFUTED),
    ("null", Verdict.REFUTED),
    ("refuted", Verdict.REFUTED),
    ("no data", Verdict.NOT_MEASURED),
    ("unmeasured", Verdict.NOT_MEASURED),
    ("blocked", Verdict.NOT_MEASURED),
    ("forward clock", Verdict.NOT_MEASURED),
    ("screen interesting", Verdict.UNDERPOWERED),
)


def _external_basis(text: str) -> bool:
    """True when the write-up says the kill came from outside this desk."""
    hay = _hay(text)
    return any(marker in hay for marker in _EXTERNAL_BASIS_MARKERS)


def _verdict_from_text(text: str, *, default: Verdict = Verdict.UNKNOWN) -> Verdict:
    hay = _hay(text)
    if not hay:
        return default
    if _external_basis(hay):
        return Verdict.EXTERNAL_PRIOR
    for phrase, verdict in _NEGATIONS:
        if phrase in hay:
            return verdict
    for token, tok_verdict in _VERDICT_TOKENS:
        if token in hay:
            return tok_verdict
    return default


def _strongest(a: Verdict, b: Verdict) -> Verdict:
    return a if _VERDICT_STRENGTH[a] >= _VERDICT_STRENGTH[b] else b


# -------------------------------------------------------------------------------- evidence -----
@dataclass(frozen=True)
class CandidateEvidence:
    """One readable record of one hypothesis. ``construction`` is the idea; ``params`` the knob."""

    candidate_id: str
    class_id: str | None
    construction: str
    params: str
    verdict: Verdict
    source: str
    matched_on: tuple[str, ...] = ()
    oos_sharpe: float | None = None
    note: str = ""
    #: Parameter settings this ONE record covers. A campaign row is one setting; a screen
    #: artifact that swept 27 cells is 27 -- and 27 settings of one construction is still one
    #: construction, which is why the depth bar never reads this field.
    n_parameterisations: int = 1

    @property
    def tested(self) -> bool:
        return self.verdict in TESTED_VERDICTS

    def to_dict(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "class_id": self.class_id,
                "construction": self.construction, "params": self.params,
                "verdict": str(self.verdict), "source": self.source,
                "matched_on": list(self.matched_on), "oos_sharpe": self.oos_sharpe,
                "n_parameterisations": self.n_parameterisations, "note": self.note}


@dataclass(frozen=True)
class SourceStatus:
    """Whether an evidence source could be read HERE, and how much it carried."""

    path: str
    readable: bool
    n_records: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path,
                "status": "READABLE" if self.readable else "NOT-READABLE-HERE",
                "n_records": self.n_records, "detail": self.detail}


def _slug(text: str) -> str:
    head = re.split(r"\s*[(—\-]{1,2}\s", text.strip(), maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]+", "_", head.lower()).strip("_")[:70] or "unnamed"


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


# -- reader 1: the pooled campaign -----------------------------------------------------------
CAMPAIGN_PATH = "reports/real_campaign.json"


def read_campaign(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """Read the pooled-by-mechanism rows: the desk's maximum-power evidence, one row per idea.

    The POOLED view is used rather than the per-symbol one on purpose. Forty symbols running one
    mechanism is one hypothesis with forty symbols of evidence, not forty hypotheses -- counting
    it the other way is the same error at the symbol axis that this module removes at the
    parameter axis.
    """
    path = root / CAMPAIGN_PATH
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return [], SourceStatus(CAMPAIGN_PATH, False, 0,
                                "absent or unparseable in this checkout")
    pooled = doc.get("pooled_by_mechanism")
    rows = pooled.get("rows") if isinstance(pooled, dict) else None
    if not isinstance(rows, list):
        return [], SourceStatus(CAMPAIGN_PATH, True, 0,
                                "readable, but carries no pooled_by_mechanism.rows")
    out: list[CandidateEvidence] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", ""))
        parts = name.split(":")
        construction = parts[1] if len(parts) > 2 else _slug(name)
        params = parts[2] if len(parts) > 2 else ""
        family = str(row.get("family", ""))
        cid, matched = classify(f"{construction} {family}", construction=construction)
        failed = row.get("failed_gates")
        n_failed = len(failed) if isinstance(failed, list) else 0
        oos = row.get("oos_sharpe")
        out.append(CandidateEvidence(
            candidate_id=name or construction,
            class_id=cid, construction=construction, params=params,
            verdict=Verdict.REFUTED if n_failed else Verdict.SURVIVED,
            source=CAMPAIGN_PATH, matched_on=matched,
            oos_sharpe=float(oos) if isinstance(oos, int | float) else None,
            note=f"declared family '{family}'; failed {n_failed} gate(s)"))
    return out, SourceStatus(CAMPAIGN_PATH, True, len(out),
                             f"{len(out)} pooled mechanisms at maximum campaign power")


# -- reader 2: the graveyard -------------------------------------------------------------------
GRAVEYARD_PATH = "docs/graveyard.md"
#: A graveyard verdict cell that is nothing but an expected-value number.
_EV_CELL = re.compile(r"ev \d")
#: Prose sections that are NOT hypothesis kills and must not be counted as candidates.
_GRAVEYARD_NON_KILL = ("cross-era synthesis", "code / capability retirements",
                       "external-literature priors")


def _graveyard_verdict(verdict_text: str, tag: str) -> Verdict:
    """Read a graveyard row's disposition, TAG FIRST.

    Three rules, in this order, and the order is the whole point:

      1. AN EXTERNAL BASIS ANYWHERE IN THE ROW WINS. The desk's own graveyard declares two
         non-desk kill bases -- `external-literature` and era-provenance -- and rows carrying
         them describe somebody else's experiment in ordinary kill vocabulary.
      2. A VERDICT CELL THAT IS AN EV NUMBER ("EV 0.0005") is an EV-GATE disposition taken before
         a single research hour was spent. Those rows still carry ordinary kill tags, and reading
         them as tests would credit the desk with experiments it explicitly declined to run.
      3. THE TAG BEATS THE PROSE. The tag is the desk's own one-word classification of the death;
         the verdict cell is a narrative that routinely mentions several failure modes. Reading
         the prose first mislabelled `unstable_artifact` as merely underpowered, because its
         write-up happens to say "underpowered" about one cohort of the experiment.
    """
    if _external_basis(f"{tag} {verdict_text}"):
        return Verdict.EXTERNAL_PRIOR
    if _EV_CELL.match(_hay(verdict_text)) is not None:
        return Verdict.EV_REJECTED
    by_tag = _verdict_from_text(tag, default=Verdict.UNKNOWN)
    if by_tag is not Verdict.UNKNOWN:
        return by_tag
    return _verdict_from_text(verdict_text, default=Verdict.REFUTED)


def read_graveyard(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """Every killed row, plus the prose sections that carry a mechanism-of-death.

    Table rows are taken only from tables whose header names Hypothesis, plus rows appended after
    prose with no header of their own (the file grows that way). The cross-era synthesis table is
    excluded by that rule -- it is a summary of one existing kill, not five new candidates.
    """
    path = root / GRAVEYARD_PATH
    if not path.exists():
        return [], SourceStatus(GRAVEYARD_PATH, False, 0, "absent in this checkout")
    lines = path.read_text("utf-8").splitlines()
    out: list[CandidateEvidence] = []
    header: list[str] | None = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line.startswith("|"):
            if not line:
                header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if nxt.startswith("|--") or nxt.startswith("|:-"):
            header = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) is not None for c in cells):
            continue      # a `|---|---|` rule that is not the row after a header
        if header is not None and not header[0].lower().startswith("hypothesis"):
            continue
        if len(cells) < 3:
            continue
        name, verdict_text, tag = cells[0], cells[1], cells[2]
        lesson = cells[3] if len(cells) > 3 else ""
        blob = f"{name} {verdict_text} {tag} {lesson}"
        cid, matched = classify(blob)
        verdict = _graveyard_verdict(verdict_text, tag)
        out.append(CandidateEvidence(
            candidate_id=_slug(name), class_id=cid, construction=_slug(name), params="",
            verdict=verdict, source=GRAVEYARD_PATH, matched_on=matched, note=tag[:120]))

    # prose kills: a heading whose own section states a kill, excluding the summary sections
    body: list[str] = []
    head = ""
    sections: list[tuple[str, str]] = []
    for raw in lines:
        if re.match(r"^#{2,4} ", raw):
            if head:
                sections.append((head, "\n".join(body)))
            head, body = raw.lstrip("# ").strip(), []
        else:
            body.append(raw)
    if head:
        sections.append((head, "\n".join(body)))
    for title, text in sections:
        low = title.lower()
        if any(marker in low for marker in _GRAVEYARD_NON_KILL):
            continue
        if "KILLED" not in title and "KILLED" not in text[:900]:
            continue
        cid, matched = classify(f"{title} {text[:2500]}")
        out.append(CandidateEvidence(
            candidate_id=_slug(title), class_id=cid, construction=_slug(title), params="",
            verdict=_verdict_from_text(f"{title} {text[:900]}", default=Verdict.REFUTED),
            source=GRAVEYARD_PATH, matched_on=matched, note="prose kill section"))
    return out, SourceStatus(GRAVEYARD_PATH, True, len(out),
                             f"{len(out)} killed rows and prose kill sections parsed")


# -- reader 3: axis pre-registrations (EV-gated, NEVER tested) ---------------------------------
PREREG_PATH = "docs/research/AXIS_PREREGISTRATIONS.md"


def read_preregistrations(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """EV-gate dispositions. These are REFUSALS TO TEST and are never counted as tests."""
    path = root / PREREG_PATH
    if not path.exists():
        return [], SourceStatus(PREREG_PATH, False, 0, "absent in this checkout")
    out: list[CandidateEvidence] = []
    for raw in path.read_text("utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("|") or line.startswith("|--"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() == "axis":
            continue
        axis, hypothesis, verdict_text = cells[0], cells[1], cells[4]
        cid, matched = classify(f"{hypothesis} {axis}")
        out.append(CandidateEvidence(
            candidate_id=_slug(hypothesis), class_id=cid, construction=_slug(hypothesis),
            params="", verdict=Verdict.EV_REJECTED if "reject" in verdict_text.lower()
            else Verdict.NAMED_ONLY,
            source=PREREG_PATH, matched_on=matched, note=f"axis={axis}; {verdict_text}"[:120]))
    return out, SourceStatus(PREREG_PATH, True, len(out),
                             f"{len(out)} pre-registered axes, EV-gated before any compute")


# -- reader 4: the research agenda (named, queued, untested) -----------------------------------
AGENDA_PATH = "research_agenda.json"


def read_agenda(root: Path) -> tuple[list[CandidateEvidence], SourceStatus]:
    """The queue. A queued idea is NAMED-ONLY: it is supply the desk has written down, not run."""
    path = root / AGENDA_PATH
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return [], SourceStatus(AGENDA_PATH, False, 0, "absent or unparseable in this checkout")
    queue = doc.get("queue_ranked_by_expected_research_roi")
    if not isinstance(queue, list):
        return [], SourceStatus(AGENDA_PATH, True, 0, "readable, but carries no ranked queue")
    out: list[CandidateEvidence] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id", ""))
        if not ident:
            continue
        blob = f"{ident} {item.get('mechanism', '')} {item.get('pre_registration', '')}"
        cid, matched = classify(blob)
        status = str(item.get("status") or "")
        out.append(CandidateEvidence(
            candidate_id=_slug(ident), class_id=cid, construction=_slug(ident), params="",
            verdict=Verdict.REFUTED if "KILLED" in status else Verdict.NAMED_ONLY,
            source=AGENDA_PATH, matched_on=matched, note=status[:120]))
    return out, SourceStatus(AGENDA_PATH, True, len(out), f"{len(out)} queued research ideas")


# -- reader 5: declared screen artifacts -------------------------------------------------------
@dataclass(frozen=True)
class ScreenSource:
    """A named Stage-A screen artifact and the class its own ``mechanism`` text places it in."""

    path: str
    candidate_id: str
    class_id: str
    basis: str


#: Each entry's class is taken from the artifact's OWN declared mechanism string, quoted in
#: `basis`. The census still opens the file: an entry here asserts nothing about a file that is
#: not on disk, and a missing file is reported NOT-READABLE-HERE rather than counted as zero.
SCREEN_SOURCES: tuple[ScreenSource, ...] = (
    ScreenSource("reports/screen_exchange_netflow.json", "exchange_netflow",
                 "holder_cost_basis_capitulation",
                 "coins moving ONTO exchanges are supply arriving at the only venue where it "
                 "can be sold -- revealed selling intent"),
    ScreenSource("reports/carry_basis_path.json", "carry_entry_shorts_widening_basis",
                 "derivative_carry_basis",
                 "does ranking perps by funding select into a WIDENING basis?"),
    ScreenSource("data/unlock_event_screen.json", "token_unlock_forced_supply",
                 "mechanical_supply_release",
                 "vesting releases tokens to a holder with ~zero cost basis on a contractually "
                 "fixed PUBLIC date; fund lifecycle forces distribution"),
    ScreenSource("data/cot_screen_summary.json", "cot_lagged_positioning",
                 "positioning_crowding_unwind",
                 "hedging-pressure / speculator positioning, lagged form only. The artifact "
                 "carries per-asset t-statistics and NO verdict string, so this census records "
                 "UNKNOWN rather than synthesising a conclusion the file does not state"),
    ScreenSource("data/funding_spread_screen.json", "cross_exchange_funding_spread",
                 "derivative_carry_basis",
                 "segmented participants per venue -> leverage imbalances do not equalise -> a "
                 "funding spread persists beyond its trading cost"),
    ScreenSource("data/copytrading_screen.json", "copytrading_leader_follow",
                 "manager_skill_persistence",
                 "does following a lead trader transfer their edge?"),
    ScreenSource("data/idle_axis_screen.json", "taker_flow_absorption", "informed_order_flow",
                 "aggressive taker buying absorbed WITHOUT the price response that flow should "
                 "have produced marks a large passive distributor"),
    ScreenSource("reports/moat_campaign.json", "moat_book_reconstruction",
                 "orderbook_microstructure_state",
                 "the desk's own recorded books -- the only dataset it owns that the crowd "
                 "does not"),
)

_CELL_KEYS = ("cells", "rows", "trials")
_STATUS_KEYS = ("verdict", "result", "overall", "status", "blocker")


def _screen_cells(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in _CELL_KEYS:
        value = doc.get(key)
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            return [v for v in value if isinstance(v, dict)]
    for value in doc.values():
        if isinstance(value, dict):
            inner = value.get("rows")
            if isinstance(inner, list) and inner and all(isinstance(v, dict) for v in inner):
                return [v for v in inner if isinstance(v, dict)]
    return []


def read_screens(root: Path) -> tuple[list[CandidateEvidence], list[SourceStatus]]:
    """Read each declared screen artifact, or record it NOT-READABLE-HERE."""
    out: list[CandidateEvidence] = []
    statuses: list[SourceStatus] = []
    for src in SCREEN_SOURCES:
        doc = _load_json(root / src.path)
        if not isinstance(doc, dict):
            statuses.append(SourceStatus(
                src.path, False, 0,
                f"runtime-only artifact absent from this checkout; the "
                f"'{src.candidate_id}' evidence for class '{src.class_id}' cannot be counted "
                f"here and is NOT zero"))
            continue
        cells = _screen_cells(doc)
        verdicts = [_verdict_from_text(str(c.get("verdict", "")), default=Verdict.UNKNOWN)
                    for c in cells if c.get("verdict") is not None]
        top = ""
        for key in _STATUS_KEYS:
            value = doc.get(key)
            if isinstance(value, str) and value:
                top = value
                break
        verdict = _verdict_from_text(top, default=Verdict.UNKNOWN)
        for v in verdicts:
            verdict = _strongest(verdict, v)
        out.append(CandidateEvidence(
            candidate_id=src.candidate_id, class_id=src.class_id,
            construction=src.candidate_id, params=f"{len(cells)} cells" if cells else "",
            verdict=verdict, source=src.path, matched_on=("declared:" + src.class_id,),
            note=src.basis[:160], n_parameterisations=max(1, len(cells))))
        statuses.append(SourceStatus(src.path, True, len(cells) or 1,
                                     f"{len(cells)} screened cells" if cells
                                     else "single-record screen artifact"))
    return out, statuses


# ------------------------------------------------------------------------------ aggregation ----
def collect_evidence(root: Path = ROOT) -> tuple[list[CandidateEvidence], list[SourceStatus]]:
    """Every readable record in the tree, de-duplicated by (class, construction, params).

    De-duplication matters because the same idea is frequently recorded twice -- once as a screen
    artifact and once as a graveyard row. Counting both would inflate exactly the number this
    census exists to deflate. The surviving record keeps the STRONGEST verdict and the best OOS.
    """
    evidence: list[CandidateEvidence] = []
    sources: list[SourceStatus] = []
    for reader in (read_campaign, read_graveyard, read_preregistrations, read_agenda):
        rows, status = reader(root)
        evidence.extend(rows)
        sources.append(status)
    screen_rows, screen_status = read_screens(root)
    evidence.extend(screen_rows)
    sources.extend(screen_status)

    def _fuse(a: CandidateEvidence, b: CandidateEvidence) -> CandidateEvidence:
        oos_values = [v for v in (a.oos_sharpe, b.oos_sharpe) if v is not None]
        return CandidateEvidence(
            candidate_id=a.candidate_id, class_id=a.class_id, construction=a.construction,
            params=a.params, verdict=_strongest(a.verdict, b.verdict),
            source=a.source if b.source in a.source else f"{a.source}+{b.source}",
            matched_on=a.matched_on or b.matched_on,
            oos_sharpe=max(oos_values) if oos_values else None, note=a.note,
            n_parameterisations=max(a.n_parameterisations, b.n_parameterisations))

    merged: dict[tuple[str, str, str], CandidateEvidence] = {}
    order: list[tuple[str, str, str]] = []
    for row in evidence:
        key = (row.class_id or "?", row.construction, row.params)
        prior = merged.get(key)
        if prior is None:
            merged[key] = row
            order.append(key)
        else:
            merged[key] = _fuse(prior, row)

    # SECOND PASS -- fold the prose record into the parameterised one. The same idea is routinely
    # recorded twice: once as a screen artifact carrying its cells, once as a graveyard row
    # carrying its mechanism-of-death and no parameters. They are one candidate, and counting
    # both would inflate exactly the number this census exists to deflate.
    parameterised: dict[tuple[str, str], tuple[str, str, str]] = {}
    for key in order:
        if key[2]:
            parameterised.setdefault((key[0], key[1]), key)
    kept: list[tuple[str, str, str]] = []
    for key in order:
        target = parameterised.get((key[0], key[1]))
        if not key[2] and target is not None:
            merged[target] = _fuse(merged[target], merged[key])
            continue
        kept.append(key)
    return [merged[k] for k in kept], sources


@dataclass(frozen=True)
class ClassCensus:
    """What the tree can evidence about one economic class."""

    class_id: str
    name: str
    coverage: Coverage
    n_candidates: int
    n_tested: int
    n_constructions: int
    n_parameterisations: int
    n_external_priors: int
    best_oos_sharpe: float | None
    verdicts: dict[str, int]
    constructions: tuple[str, ...]
    unreadable_sources: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, Any]:
        cls = CLASS_BY_ID[self.class_id]
        return {"class_id": self.class_id, "name": self.name, "payer": cls.payer,
                "coverage": str(self.coverage), "n_candidates": self.n_candidates,
                "n_tested": self.n_tested, "n_constructions": self.n_constructions,
                "n_parameterisations": self.n_parameterisations,
                "n_external_priors": self.n_external_priors,
                "best_oos_sharpe": self.best_oos_sharpe, "verdicts": dict(self.verdicts),
                "constructions": list(self.constructions),
                "unreadable_sources": list(self.unreadable_sources), "note": self.note}


def _class_census(cls: MechanismClass, rows: list[CandidateEvidence],
                  unreadable: tuple[str, ...]) -> ClassCensus:
    tested = [r for r in rows if r.tested]
    constructions = tuple(sorted({r.construction for r in rows}))
    n_params = sum(r.n_parameterisations for r in rows)
    oos = [r.oos_sharpe for r in tested if r.oos_sharpe is not None]
    externals = sum(1 for r in rows if r.verdict is Verdict.EXTERNAL_PRIOR)
    conclusive_constructions = len({r.construction for r in rows
                                    if r.verdict in CONCLUSIVE_VERDICTS})

    if not tested and unreadable:
        coverage = Coverage.NOT_READABLE_HERE
        note = ("no readable test evidence, and this class's screen artifact is absent from this "
                "checkout -- UNKNOWN here, never zero")
    elif not rows:
        coverage = Coverage.NO_CANDIDATE
        note = "no candidate anywhere in this tree -- untested, not failed"
    elif not tested:
        coverage = Coverage.NAMED_UNTESTED
        note = ("written down but never tested on desk data"
                + (f"; {externals} external-literature/era prior(s) only" if externals else ""))
    elif conclusive_constructions >= DEPTH_MIN_CONSTRUCTIONS:
        coverage = Coverage.TESTED_DEEP
        note = (f"{conclusive_constructions} distinct constructions each carrying a conclusive "
                f"verdict, across {n_params} parameterisations")
    else:
        coverage = Coverage.TESTED_SHALLOW
        note = (f"only {conclusive_constructions} construction(s) reached a conclusive verdict "
                f"-- below the census depth bar of {DEPTH_MIN_CONSTRUCTIONS}; "
                f"{n_params} parameterisations do not substitute for constructions")
    return ClassCensus(
        class_id=cls.id, name=cls.name, coverage=coverage, n_candidates=len(rows),
        n_tested=len(tested), n_constructions=len(constructions),
        n_parameterisations=n_params, n_external_priors=externals,
        best_oos_sharpe=max(oos) if oos else None,
        verdicts=dict(sorted(Counter(str(r.verdict) for r in rows).items())),
        constructions=constructions, unreadable_sources=unreadable, note=note)


# ------------------------------------------------------------------------------- diversity -----
@dataclass(frozen=True)
class Diversity:
    """How wide the tested supply actually is, independent of how much of it there is."""

    n_candidates: int
    n_classes_occupied: int
    n_classes_in_taxonomy: int
    shannon_entropy: float
    effective_classes: float     # exp(H): the Hill number -- classes' worth of real spread
    diversity: float             # effective_classes / taxonomy size, in (0, 1]
    hhi: float
    top_class: str
    top_class_share: float

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def measure_diversity(rows: list[CandidateEvidence],
                      *, n_classes: int = len(TAXONOMY)) -> Diversity:
    """Effective number of economic classes in a candidate set, as a fraction of the taxonomy.

    WHY exp(H) OVER THE TAXONOMY, and not entropy over the item count. The question this census
    answers is "what fraction of the KNOWN mechanism space is the desk actually exploring", so
    the denominator has to be the opportunity set, not the batch size. The Hill number exp(H) is
    the number of equally-weighted classes that would produce the observed spread, which makes
    the reading directly legible: 400 candidates evenly split across 3 of 20 classes score 3/20 =
    0.15 no matter whether there are 400 of them or 40. That volume-invariance is the property
    that matters here -- it is exactly why generating another hundred price transformations does
    not move this number, and why a count of candidates could never have shown that.
    """
    counts = Counter(r.class_id for r in rows if r.class_id is not None)
    total = sum(counts.values())
    if total == 0 or n_classes <= 0:
        return Diversity(0, 0, n_classes, 0.0, 0.0, 0.0, 0.0, "", 0.0)
    shares = [c / total for c in counts.values()]
    entropy = -sum(p * math.log(p) for p in shares if p > 0)
    effective = math.exp(entropy)
    top, top_n = counts.most_common(1)[0]
    return Diversity(
        n_candidates=total, n_classes_occupied=len(counts), n_classes_in_taxonomy=n_classes,
        shannon_entropy=round(entropy, 4), effective_classes=round(effective, 3),
        diversity=round(min(1.0, effective / n_classes), 4),
        hhi=round(sum(p * p for p in shares), 4), top_class=top,
        top_class_share=round(top_n / total, 4))


# ------------------------------------------------------------------------------ the gap list ---
@dataclass(frozen=True)
class GapRow:
    """One untested or under-tested class, scored as a next target."""

    rank: int
    class_id: str
    name: str
    coverage: Coverage
    gap_score: float
    plausibility: float
    orthogonality: float
    feasibility: float
    depth_deficit: float
    payer: str
    data_required: DataRequirement
    prior_kills: tuple[str, ...]
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "class_id": self.class_id, "name": self.name,
                "coverage": str(self.coverage), "gap_score": self.gap_score,
                "plausibility": self.plausibility, "orthogonality": self.orthogonality,
                "feasibility": self.feasibility, "depth_deficit": self.depth_deficit,
                "payer": self.payer, "data_required": self.data_required.to_dict(),
                "prior_kills": list(self.prior_kills), "why": self.why}


def rank_gaps(classes: list[ClassCensus],
              evidence: list[CandidateEvidence]) -> tuple[list[GapRow], list[GapRow]]:
    """Rank the classes worth testing next, and separately those that cannot be ranked here.

    ``gap_score = plausibility x orthogonality x data_feasibility x depth_deficit``. Multiplicative
    on purpose: a class with an unimpeachable payer story and no obtainable data is not a target,
    and neither is one with perfect data and no reason anybody should pay. Every factor is a
    DECLARED constant of this census, never fitted to an outcome, and the score confers no
    standing on anything -- it orders a reading list.

    A class whose evidence is NOT-READABLE-HERE is returned in the second list, unscored. Ranking
    it would mean pricing a gap whose size this checkout cannot see.
    """
    kills: dict[str, list[str]] = {}
    for row in evidence:
        if row.class_id is not None and row.verdict in CONCLUSIVE_VERDICTS:
            kills.setdefault(row.class_id, []).append(row.construction)

    scored: list[tuple[float, ClassCensus]] = []
    blind: list[ClassCensus] = []
    for cen in classes:
        if cen.coverage is Coverage.NOT_READABLE_HERE:
            blind.append(cen)
            continue
        cls = CLASS_BY_ID[cen.class_id]
        score = (cls.plausibility * cls.orthogonality
                 * _FEASIBILITY[cls.data.availability] * _DEPTH_DEFICIT[cen.coverage])
        if score > 0.0:
            scored.append((score, cen))
    scored.sort(key=lambda kv: (-kv[0], kv[1].class_id))

    def _row(rank: int, score: float, cen: ClassCensus) -> GapRow:
        cls = CLASS_BY_ID[cen.class_id]
        prior = tuple(sorted(set(kills.get(cen.class_id, ()))))[:6]
        why = (f"{cen.coverage}: {cen.n_tested} tested candidate(s) across "
               f"{cen.n_constructions} construction(s); payer story {cls.plausibility:.2f}, "
               f"orthogonality {cls.orthogonality:.2f}, data "
               f"{cls.data.availability}")
        if prior:
            why += (f". NOT virgin ground -- {len(prior)} conclusive prior verdict(s) already "
                    f"sit in this class")
        if cen.unreadable_sources:
            why += (". Partly blind here: " + ", ".join(cen.unreadable_sources)
                    + " is absent from this checkout, so the tested count is a LOWER bound")
        return GapRow(rank=rank, class_id=cen.class_id, name=cen.name, coverage=cen.coverage,
                      gap_score=round(score, 4), plausibility=cls.plausibility,
                      orthogonality=cls.orthogonality,
                      feasibility=_FEASIBILITY[cls.data.availability],
                      depth_deficit=_DEPTH_DEFICIT[cen.coverage], payer=cls.payer,
                      data_required=cls.data, prior_kills=prior, why=why)

    ranked = [_row(i + 1, score, cen) for i, (score, cen) in enumerate(scored)]
    unrankable = [
        GapRow(rank=0, class_id=c.class_id, name=c.name, coverage=c.coverage, gap_score=0.0,
               plausibility=CLASS_BY_ID[c.class_id].plausibility,
               orthogonality=CLASS_BY_ID[c.class_id].orthogonality,
               feasibility=_FEASIBILITY[CLASS_BY_ID[c.class_id].data.availability],
               depth_deficit=0.0, payer=CLASS_BY_ID[c.class_id].payer,
               data_required=CLASS_BY_ID[c.class_id].data, prior_kills=(),
               why="cannot be ranked from this checkout: "
                   + "; ".join(c.unreadable_sources))
        for c in blind]
    return ranked, unrankable


# ---------------------------------------------------------------------------------- report -----
@dataclass(frozen=True)
class CensusReport:
    generated_utc: str
    classes: list[ClassCensus]
    diversity: Diversity
    campaign_diversity: Diversity
    gaps: list[GapRow]
    unrankable: list[GapRow]
    sources: list[SourceStatus]
    unclassified: list[CandidateEvidence]
    evidence: list[CandidateEvidence] = field(default_factory=list)

    def coverage_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(str(c.coverage) for c in self.classes).items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": self.generated_utc,
            "authority": ("MEASUREMENT ONLY. This census promotes nothing, blocks nothing, and "
                          "changes no gate, threshold or bar. Its depth and scoring constants "
                          "are reporting parameters and confer no standing."),
            "taxonomy_size": len(TAXONOMY),
            "depth_bar": {"min_conclusive_constructions": DEPTH_MIN_CONSTRUCTIONS,
                          "note": "a reporting bar for this census only, denominated in "
                                  "constructions -- never in candidates, which reparameterising "
                                  "one construction would satisfy"},
            "totals": {
                "n_records": len(self.evidence),
                "n_tested": sum(1 for r in self.evidence if r.tested),
                "n_classified": sum(1 for r in self.evidence if r.class_id is not None),
                "n_unclassified": len(self.unclassified),
            },
            "coverage_counts": self.coverage_counts(),
            "diversity": self.diversity.to_dict(),
            "campaign_diversity": self.campaign_diversity.to_dict(),
            "classes": [c.to_dict() for c in self.classes],
            "gaps": [g.to_dict() for g in self.gaps],
            "unrankable_gaps": [g.to_dict() for g in self.unrankable],
            "sources": [s.to_dict() for s in self.sources],
            "unclassified": [r.to_dict() for r in self.unclassified],
            "taxonomy": [c.to_dict() for c in TAXONOMY],
            "honesty_rails": [
                "a class with no evidence on disk is UNTESTED, never failed: its verdict "
                "distribution is empty and its best OOS is null, not 0.0",
                "a runtime-only artifact absent from this checkout is NOT-READABLE-HERE and is "
                "never counted as zero evidence",
                "EV-REJECTED and NAMED-ONLY are refusals to test, not test results, and are "
                "excluded from every tested count and from the depth bar",
                "EXTERNAL-PRIOR records are somebody else's evidence, not re-run here, and do "
                "not count toward depth",
                "records matching no signature are reported in `unclassified`, never assigned "
                "to the nearest plausible class",
            ],
        }


def census(root: Path = ROOT) -> CensusReport:
    """Read the tree and report the mechanism supply. Never writes anything."""
    evidence, sources = collect_evidence(root)
    unreadable_by_class: dict[str, list[str]] = {}
    readable_paths = {s.path for s in sources if s.readable}
    for src in SCREEN_SOURCES:
        if src.path not in readable_paths:
            unreadable_by_class.setdefault(src.class_id, []).append(src.path)

    by_class: dict[str, list[CandidateEvidence]] = {c.id: [] for c in TAXONOMY}
    unclassified: list[CandidateEvidence] = []
    for row in evidence:
        if row.class_id is None:
            unclassified.append(row)
        else:
            by_class[row.class_id].append(row)

    classes = [_class_census(c, by_class[c.id],
                             tuple(sorted(unreadable_by_class.get(c.id, ()))))
               for c in TAXONOMY]
    gaps, unrankable = rank_gaps(classes, evidence)
    campaign_rows = [r for r in evidence if CAMPAIGN_PATH in r.source]
    return CensusReport(
        generated_utc=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        classes=classes,
        diversity=measure_diversity([r for r in evidence if r.tested]),
        campaign_diversity=measure_diversity(campaign_rows),
        gaps=gaps, unrankable=unrankable, sources=sources, unclassified=unclassified,
        evidence=evidence)
