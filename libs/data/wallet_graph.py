"""WALLET ENTITY RESOLUTION -- who is behind an address, as of a point in time.

THE ASYMMETRY THIS IS, EXACTLY. Chain data is public, free and identical for everyone. The
CLUSTERING is not. Mapping thousands of addresses onto exchanges, market makers, treasuries and
retail takes heuristics, labelled seeds and sustained maintenance, and vendors charge for it
precisely because assembling it is the expensive part. That makes it a PROCESSING asymmetry rather
than an access one -- bought with engineering instead of money, which is the only kind a small desk
can actually win. `scripts/asymmetry_ledger.py` grades it RECONSTRUCTIBLE at depth 1, the largest
gap on that axis.

AS-OF RESOLUTION IS THE WHOLE DESIGN, AND WITHOUT IT THIS MODULE IS A LEAK GENERATOR. The obvious
implementation clusters the full history once and labels every address, then backtests a signal
using those labels. That signal knows, in 2024, that an address WOULD LATER be revealed as an
exchange hot wallet -- knowledge nobody had at the time, and knowledge that correlates with
exactly the flows being predicted. It is the most damaging lookahead available in on-chain work
because the resulting backtest looks plausible rather than absurd. Every function here takes an
`asof` and reads only transactions at or before it.

FALSE MERGES ARE THE EXPENSIVE ERROR, NOT FALSE SPLITS. Wrongly splitting one entity into two
costs statistical power. Wrongly MERGING an exchange with a whale produces an entity whose
"behaviour" is an artefact, and every feature built on it is confidently wrong. So the merge rules
are conservative, confidence is carried, and low-confidence classifications return UNKNOWN rather
than a guess -- a labelled entity is used as ground truth downstream, and a guess laundered into a
label is worse than an absent one.

THE COMMON-INPUT HEURISTIC IS A UTXO IDEA AND MOSTLY DOES NOT APPLY TO EVM CHAINS. On Bitcoin,
co-spent inputs are near-proof of shared control. On Ethereum a transaction has ONE sender, so the
heuristic yields nothing and the work must come from funding trees and behaviour instead. Stating
that here because applying the Bitcoin heuristic to EVM data silently produces singleton clusters
that look like a working clustering.

Pure stdlib + numpy. No I/O, no network.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

__all__ = [
    "ENTITY_TYPES",
    "MIN_TX_FOR_CLASSIFICATION",
    "EntityLabel",
    "Tx",
    "behavioural_profile",
    "classify",
    "cluster_asof",
    "entity_flow",
]

#: What the desk actually needs to tell apart. Deliberately coarse: finer classes are not
#: identifiable from behaviour alone, and inventing them produces confident noise.
ENTITY_TYPES = ("EXCHANGE", "MARKET_MAKER", "TREASURY", "WHALE", "RETAIL", "BOT", "UNKNOWN")

#: Below this many transactions a behavioural profile is describing coincidence. An address with
#: three transfers has no measurable timing regularity, and reporting one is fabrication.
MIN_TX_FOR_CLASSIFICATION = 30

#: Confidence below which the answer is UNKNOWN. A label is consumed downstream as ground truth.
MIN_CONFIDENCE = 0.55


@dataclass(frozen=True)
class Tx:
    """One transfer. `inputs` carries co-spent addresses on UTXO chains, empty on EVM."""

    ts: float
    sender: str
    receiver: str
    value: float
    inputs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("transfer value cannot be negative")


@dataclass(frozen=True)
class EntityLabel:
    """A classification, its confidence, and the evidence that produced it."""

    entity: str
    etype: str
    confidence: float
    n_tx: int
    reasons: tuple[str, ...] = field(default=())

    @property
    def usable(self) -> bool:
        return self.etype != "UNKNOWN" and self.confidence >= MIN_CONFIDENCE


class _Union:
    """Union-find with path compression. Small, and the alternative is a graph library."""

    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, a: str) -> str:
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_asof(txs: Sequence[Tx], asof: float) -> dict[str, str]:
    """address -> cluster id, using ONLY transactions at or before `asof`.

    The single rule applied is COMMON INPUT OWNERSHIP: addresses co-spent in one transaction are
    controlled by whoever signed it. It is the one heuristic strong enough to merge on, and it is
    a UTXO idea -- on EVM, where `inputs` is empty, every address stays its own cluster and the
    work has to come from behaviour instead.

    Deliberately NOT applied: change-address guessing, and merging on shared counterparties. Both
    merge aggressively and both produce FALSE MERGES, which are the expensive error -- an exchange
    fused with a whale yields an entity whose behaviour is an artefact and features that are
    confidently wrong.
    """
    u = _Union()
    for t in txs:
        if t.ts > asof:
            continue
        u.find(t.sender)
        u.find(t.receiver)
        if len(t.inputs) > 1:
            first = t.inputs[0]
            for other in t.inputs[1:]:
                u.union(first, other)
    return {a: u.find(a) for a in u.parent}


def behavioural_profile(entity: str, txs: Sequence[Tx], clusters: dict[str, str],
                        asof: float) -> dict[str, float]:
    """Behavioural statistics for one cluster, from transactions at or before `asof`.

    These are the features that separate a hot wallet from a person: how many distinct
    counterparties it touches, how regular its timing is, how round its amounts are, and how
    balanced its inflow is against its outflow.
    """
    rows = [t for t in txs
            if t.ts <= asof and (clusters.get(t.sender) == entity
                                 or clusters.get(t.receiver) == entity)]
    if not rows:
        return {"n_tx": 0.0}
    ts = np.array([t.ts for t in rows], dtype="float64")
    vals = np.array([t.value for t in rows], dtype="float64")
    counterparties = {clusters.get(t.receiver, t.receiver) if clusters.get(t.sender) == entity
                      else clusters.get(t.sender, t.sender) for t in rows}
    inflow = sum(t.value for t in rows if clusters.get(t.receiver) == entity)
    outflow = sum(t.value for t in rows if clusters.get(t.sender) == entity)

    gaps = np.diff(np.sort(ts))
    # Coefficient of variation of inter-arrival gaps. A machine is regular (low CV); a person is
    # bursty (high CV). Poisson arrivals sit near 1.0, so this separates scheduled from organic.
    regularity = float(gaps.std() / gaps.mean()) if gaps.size > 1 and gaps.mean() > 0 else 1.0
    # Fraction of values that are suspiciously round -- a human typing "0.5 ETH".
    roundness = float(np.mean([abs(v - round(v, 1)) < 1e-9 for v in vals])) if vals.size else 0.0
    total = inflow + outflow
    # COUNT IMBALANCE IS THE ROBUST ONE AND CLASSIFICATION USES IT. Value-weighted imbalance is
    # dominated by outliers: one 999-unit whale deposit into a hot wallet that had processed 400
    # balanced transfers moved its value imbalance from 0.00 to 0.60 and reclassified an exchange
    # as unrecognised. A single transfer must not change who an entity IS. What characterises a
    # hot wallet is that it processes many transfers in BOTH directions, which is a count fact.
    n_in = sum(1 for t in rows if clusters.get(t.receiver) == entity)
    n_out = sum(1 for t in rows if clusters.get(t.sender) == entity)
    n_both = n_in + n_out
    return {
        "n_tx": float(len(rows)),
        "n_counterparties": float(len(counterparties)),
        "counterparty_ratio": float(len(counterparties)) / len(rows),
        "timing_cv": regularity,
        "roundness": roundness,
        "count_imbalance": float((n_in - n_out) / n_both) if n_both else 0.0,
        "flow_imbalance": float((inflow - outflow) / total) if total > 0 else 0.0,
        "median_value": float(np.median(vals)),
        "span_days": float((ts.max() - ts.min()) / 86400.0),
    }


def classify(entity: str, profile: dict[str, float]) -> EntityLabel:
    """Behaviour -> entity type, with confidence, refusing to guess on thin evidence.

    THE REFUSAL IS THE FEATURE. Downstream code consumes a label as ground truth, so a guess
    laundered into a label is worse than no label: it produces a flow series that looks like
    "exchange inflow" and is actually noise with a name. Anything under MIN_TX_FOR_CLASSIFICATION
    transactions, or under MIN_CONFIDENCE, comes back UNKNOWN.
    """
    n = int(profile.get("n_tx", 0))
    if n < MIN_TX_FOR_CLASSIFICATION:
        return EntityLabel(entity, "UNKNOWN", 0.0, n,
                           (f"{n} tx (<{MIN_TX_FOR_CLASSIFICATION}) -- a behavioural profile on "
                            "this many transfers is describing coincidence",))

    cp = profile.get("n_counterparties", 0.0)
    cp_ratio = profile.get("counterparty_ratio", 0.0)
    cv = profile.get("timing_cv", 1.0)
    roundness = profile.get("roundness", 0.0)
    # Robust (count) for identity, value-weighted only where magnitude is the point.
    imbalance = profile.get("count_imbalance", profile.get("flow_imbalance", 0.0))
    value_imbalance = profile.get("flow_imbalance", 0.0)

    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = defaultdict(list)

    # EXCHANGE: enormous distinct counterparty count, near-balanced flow (deposits out to cold,
    # withdrawals in from cold), and it never stops.
    if cp >= 100 and abs(imbalance) < 0.35:
        scores["EXCHANGE"] = min(0.55 + cp / 1000.0, 0.95)
        reasons["EXCHANGE"].append(
            f"{cp:.0f} distinct counterparties with COUNT imbalance {imbalance:+.2f} "
            f"(value {value_imbalance:+.2f}) -- a hot wallet touches everyone and processes "
            "transfers both ways; the count is used because one whale deposit must not change "
            "who an entity is")

    # MARKET MAKER: high frequency, machine-regular timing, balanced flow, few counterparties
    # (venues), and unround sizes.
    if cv < 0.6 and cp_ratio < 0.2 and roundness < 0.2:
        scores["MARKET_MAKER"] = 0.55 + (0.6 - cv) * 0.5
        reasons["MARKET_MAKER"].append(
            f"timing CV {cv:.2f} (machine-regular), {cp_ratio:.2f} counterparties per tx, "
            f"{roundness:.0%} round amounts -- scheduled flow between few venues")

    # BOT: regular timing but WITHOUT the balanced two-sided flow of a maker.
    if cv < 0.45 and "MARKET_MAKER" not in scores:
        scores["BOT"] = 0.55 + (0.45 - cv)
        reasons["BOT"].append(f"timing CV {cv:.2f} -- scheduled, one-directional")

    # TREASURY: very few counterparties, strongly one-directional, large median size.
    if cp <= 10 and abs(imbalance) > 0.6:
        scores["TREASURY"] = 0.6
        reasons["TREASURY"].append(
            f"{cp:.0f} counterparties, count imbalance {imbalance:+.2f} -- accumulation or "
            "distribution against a handful of known addresses")

    # RETAIL: bursty timing, round numbers, few counterparties, small size.
    if cv > 1.2 and roundness > 0.3:
        scores["RETAIL"] = 0.55 + min(roundness, 0.4)
        reasons["RETAIL"].append(
            f"bursty timing (CV {cv:.2f}) with {roundness:.0%} round amounts -- a person typing "
            "numbers, not a machine emitting them")

    if not scores:
        return EntityLabel(entity, "UNKNOWN", 0.0, n,
                           ("no behavioural pattern matched -- reported as UNKNOWN rather than "
                            "assigned to the nearest class, because a label is consumed as "
                            "ground truth downstream",))

    best = max(scores, key=lambda k: scores[k])
    conf = min(scores[best], 0.95)
    if conf < MIN_CONFIDENCE:
        return EntityLabel(entity, "UNKNOWN", conf, n,
                           (f"best candidate {best} at {conf:.2f} confidence, below the "
                            f"{MIN_CONFIDENCE} bar",))
    # A second class scoring nearly as high means the evidence does not separate them.
    rival = sorted(scores.values(), reverse=True)
    if len(rival) > 1 and rival[0] - rival[1] < 0.1:
        return EntityLabel(entity, "UNKNOWN", conf, n,
                           (f"{best} and the runner-up are within 0.1 confidence -- the behaviour "
                            "does not separate them, and picking the larger would be arbitrary",))
    return EntityLabel(entity, best, conf, n, tuple(reasons[best]))


def entity_flow(txs: Sequence[Tx], clusters: dict[str, str],
                labels: dict[str, EntityLabel], asof: float,
                etype: str = "EXCHANGE") -> dict[str, float]:
    """Net flow INTO addresses of `etype`, from data at or before `asof`.

    This is the trading-relevant object the whole module exists to produce: "how much did
    identified entities of this kind take in", which is the on-chain analogue of exchange
    inflow -- and unlike a vendor's number, the desk can see exactly which addresses produced it
    and why they were classified that way.

    Only USABLE labels contribute. An UNKNOWN entity is excluded rather than bucketed as retail,
    because a residual bucket quietly becomes the biggest one and then gets a signal built on it.
    """
    inflow = outflow = 0.0
    counted = 0
    for t in txs:
        if t.ts > asof:
            continue
        recv, send = clusters.get(t.receiver), clusters.get(t.sender)
        lr, ls = labels.get(recv or ""), labels.get(send or "")
        if lr is not None and lr.usable and lr.etype == etype:
            inflow += t.value
            counted += 1
        if ls is not None and ls.usable and ls.etype == etype:
            outflow += t.value
            counted += 1
    return {"inflow": inflow, "outflow": outflow, "net": inflow - outflow,
            "transfers_counted": float(counted)}


def labels_asof(txs: Sequence[Tx], asof: float,
                entities: Iterable[str] | None = None) -> dict[str, EntityLabel]:
    """Cluster and classify in one pass, strictly from data at or before `asof`."""
    clusters = cluster_asof(txs, asof)
    targets = set(entities) if entities is not None else set(clusters.values())
    return {e: classify(e, behavioural_profile(e, txs, clusters, asof)) for e in targets}
