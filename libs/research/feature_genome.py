"""THE FEATURE GENOME: every feature's chain from data origin to portfolio behaviour, and the
HIERARCHICAL orthogonality that falls out of it (LAWS 5m; RESEARCH 11).

THE CHAIN. DATA ORIGIN -> PIT normalisation -> entity alignment -> representation ->
transform/interaction -> mechanism hypothesis -> model/rule/program -> regime conditional ->
execution policy -> portfolio behaviour. Each layer carries the tokens that name what the feature
IS at that layer (which dataset, which PIT rule, which instrument, which representation, which
transform chain, which mechanism, ...). A layer nobody has assigned yet is EMPTY and reads
UNMEASURED in every distance -- never "different", never "same".

WHY DISTANCE IS HIERARCHICAL. Two strategies with a 0.1 return correlation but the same dataset,
the same feature and the same mechanism are LESS independent than their PnL suggests: one
revision of the dataset, one regime the mechanism stops working in, one researcher's blind spot
hits both at once, and the 0.1 was measured in a sample where none of that happened. So the
effective independence of a pair is the MINIMUM of what the returns say and what the lineage
says, and the lineage distance is a weighted mean over the axes the law names (data-source,
representation, mechanism, researcher/search, signal, PnL/tail) with the weight concentrated on
the roots of the chain.

`lineage_concentration()` is EVIDENCE for the portfolio-capital allocator (GROWTH_GOVERNANCE
Rule 1): it reports how concentrated the book's capital is on shared lineage at every layer and
never emits a cap, a shrink or a veto. The allocator decides by dE[log W]; this tells it what it
would otherwise be unable to see. Pure: no I/O.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Final

UNMEASURED: Final = "UNMEASURED"

#: The ten layers of the chain, in order. The order IS the hierarchy: sharing at a lower index is
#: a deeper dependence than sharing at a higher one.
LAYERS: Final[tuple[str, ...]] = (
    "data_origin", "pit_normalisation", "entity_alignment", "representation", "transform",
    "mechanism", "model", "regime", "execution", "portfolio",
)

#: The six distance axes the law names, each reading one or more layers of the chain. `signal`
#: and `pnl_tail` are MEASURED axes (they need series); the other four are structural.
DISTANCE_AXES: Final[tuple[str, ...]] = ("data_source", "representation", "mechanism",
                                         "researcher", "signal", "pnl_tail")
AXIS_LAYERS: Final[dict[str, tuple[str, ...]]] = {
    "data_source": ("data_origin", "pit_normalisation", "entity_alignment"),
    "representation": ("representation", "transform"),
    "mechanism": ("mechanism", "model", "regime"),
    "researcher": ("researcher",),
    "signal": (),
    "pnl_tail": (),
}
#: Weight concentrated on the roots: a shared dataset is the dependence every other layer
#: inherits; a shared execution policy is the shallowest.
AXIS_WEIGHT: Final[dict[str, float]] = {
    "data_source": 0.30, "representation": 0.20, "mechanism": 0.25, "researcher": 0.10,
    "signal": 0.075, "pnl_tail": 0.075,
}
STRUCTURAL_AXES: Final[tuple[str, ...]] = ("data_source", "representation", "mechanism",
                                           "researcher")

RULE: Final = ("orthogonality is hierarchical: two strategies with the same dataset, feature and "
               "mechanism are less independent than their return correlation says, so effective "
               "independence is the minimum of the PnL reading and the lineage reading")
EVIDENCE_RULE: Final = ("lineage concentration is EVIDENCE the allocator conditions on by "
                        "dE[log W]; it is never a cap, a shrink or a veto (GROWTH_GOVERNANCE "
                        "Rule 1)")


def _tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip().lower(),) if value.strip() else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(sorted({str(v).strip().lower() for v in value if str(v).strip()}))
    return (str(value).strip().lower(),)


# -------------------------------------------------------------------------------- the genome
@dataclass(frozen=True)
class Genome:
    """One feature's (or strategy's) whole chain. Every layer is a tuple of tokens; empty means
    UNASSIGNED at that layer, which is a measurement of where the chain stops."""

    feature_id: str
    data_origin: tuple[str, ...] = ()
    pit_normalisation: tuple[str, ...] = ()
    entity_alignment: tuple[str, ...] = ()
    representation: tuple[str, ...] = ()
    transform: tuple[str, ...] = ()
    mechanism: tuple[str, ...] = ()
    model: tuple[str, ...] = ()
    regime: tuple[str, ...] = ()
    execution: tuple[str, ...] = ()
    portfolio: tuple[str, ...] = ()
    #: The search process that produced the feature: a miner, a seat, a forge, a person.
    researcher: tuple[str, ...] = ()
    #: The DatasetContract ids the data origin is held under.
    contract_ids: tuple[str, ...] = ()
    #: The lineage records the feature's data version is replayable from.
    lineage_ids: tuple[str, ...] = ()
    meta: Mapping[str, Any] = field(default_factory=dict)

    def layer(self, name: str) -> frozenset[str]:
        if name not in LAYERS and name != "researcher":
            raise KeyError(f"unknown genome layer {name!r}")
        value = getattr(self, name)
        return frozenset(_tokens(value))

    def chain(self) -> list[tuple[str, tuple[str, ...]]]:
        return [(name, tuple(sorted(self.layer(name)))) for name in LAYERS]

    def unassigned_layers(self) -> tuple[str, ...]:
        return tuple(name for name in LAYERS if not self.layer(name))

    @property
    def depth(self) -> int:
        """How far down the chain the feature has been carried: the last assigned layer + 1."""
        assigned = [i for i, name in enumerate(LAYERS) if self.layer(name)]
        return (max(assigned) + 1) if assigned else 0

    def genome_hash(self) -> str:
        body = {name: sorted(self.layer(name)) for name in LAYERS}
        body["researcher"] = sorted(self.layer("researcher"))
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:24]

    def to_json(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["meta"] = dict(self.meta)
        doc["genome_hash"] = self.genome_hash()
        doc["depth"] = self.depth
        doc["unassigned_layers"] = list(self.unassigned_layers())
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Genome:
        kw: dict[str, Any] = {name: _tokens(doc.get(name))
                              for name in (*LAYERS, "researcher", "contract_ids", "lineage_ids")}
        meta = doc.get("meta")
        return cls(feature_id=str(doc.get("feature_id") or ""),
                   meta=dict(meta) if isinstance(meta, Mapping) else {}, **kw)


def genome(feature_id: str, **layers: Any) -> Genome:
    """Build a genome from loosely-typed layer values (str, list, tuple, set)."""
    unknown = sorted(k for k in layers if k not in LAYERS
                     and k not in ("researcher", "contract_ids", "lineage_ids", "meta"))
    if unknown:
        raise KeyError(f"unknown genome layers {unknown}; layers are {list(LAYERS)}")
    kw: dict[str, Any] = {}
    for name, value in layers.items():
        kw[name] = dict(value) if name == "meta" else _tokens(value)
    return Genome(feature_id=feature_id, **kw)


# ------------------------------------------------------------------------------- distances
def jaccard_distance(a: frozenset[str], b: frozenset[str]) -> float | None:
    """1 - |a & b| / |a | b|; None when BOTH sides are empty (nothing was measured)."""
    if not a and not b:
        return None
    union = a | b
    return 1.0 - len(a & b) / len(union)


def layer_distance(left: Genome, right: Genome, layer: str) -> float | None:
    return jaccard_distance(left.layer(layer), right.layer(layer))


def axis_distance(left: Genome, right: Genome, axis: str, *,
                  signal_correlation: float | None = None,
                  tail_dependence: float | None = None) -> float | None:
    """One of the six named distances. Structural axes average their layers over the layers
    that are measured on at least one side; the two measured axes read the correlations."""
    if axis == "signal":
        return None if signal_correlation is None else 1.0 - min(1.0, abs(signal_correlation))
    if axis == "pnl_tail":
        return None if tail_dependence is None else 1.0 - min(1.0, max(0.0, tail_dependence))
    if axis not in AXIS_LAYERS:
        raise KeyError(f"unknown distance axis {axis!r}; axes are {list(DISTANCE_AXES)}")
    parts = [d for d in (layer_distance(left, right, name) for name in AXIS_LAYERS[axis])
             if d is not None]
    return sum(parts) / len(parts) if parts else None


@dataclass(frozen=True)
class Independence:
    """What a pair's lineage and returns say, separately and combined."""

    left: str
    right: str
    axes: dict[str, float | None]
    structural: float | None
    pnl_independence: float | None
    effective: float | None
    shared_layers: tuple[str, ...]
    unmeasured_axes: tuple[str, ...]
    basis: str
    rule: str = RULE

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def hierarchical_distance(left: Genome, right: Genome, *, return_correlation: float | None = None,
                          signal_correlation: float | None = None,
                          tail_dependence: float | None = None) -> Independence:
    """The pair's effective independence in [0, 1]: min(PnL reading, lineage reading).

    The lineage reading is the AXIS_WEIGHT-weighted mean of the measured axes; an axis nobody
    measured contributes nothing and is NAMED in `unmeasured_axes`. When neither returns nor any
    axis is measured the answer is None -- UNMEASURED is a value, 1.0 is a claim.
    """
    axes: dict[str, float | None] = {
        axis: axis_distance(left, right, axis, signal_correlation=signal_correlation,
                            tail_dependence=tail_dependence)
        for axis in DISTANCE_AXES}
    measured = {a: d for a, d in axes.items() if d is not None}
    weight = sum(AXIS_WEIGHT[a] for a in measured)
    structural = (sum(AXIS_WEIGHT[a] * d for a, d in measured.items()) / weight) if weight > 0 \
        else None
    pnl = None if return_correlation is None else 1.0 - min(1.0, abs(return_correlation))
    readings = [r for r in (structural, pnl) if r is not None]
    effective = min(readings) if readings else None
    shared = tuple(name for name in LAYERS if left.layer(name) & right.layer(name))
    if effective is None:
        basis = "UNMEASURED: no axis and no return correlation was measured"
    elif pnl is not None and structural is not None and structural < pnl:
        basis = (f"lineage binds: shared {', '.join(shared) or 'nothing'} makes the pair less "
                 f"independent ({structural:.3f}) than its return correlation says ({pnl:.3f})")
    elif pnl is not None and structural is not None:
        basis = f"returns bind: PnL independence {pnl:.3f} <= lineage independence {structural:.3f}"
    else:
        basis = "one reading only: " + ("lineage" if structural is not None else "returns")
    return Independence(left=left.feature_id, right=right.feature_id, axes=axes,
                        structural=None if structural is None else round(structural, 6),
                        pnl_independence=None if pnl is None else round(pnl, 6),
                        effective=None if effective is None else round(effective, 6),
                        shared_layers=shared,
                        unmeasured_axes=tuple(a for a in DISTANCE_AXES if a not in measured),
                        basis=basis)


# ------------------------------------------------------------------- lineage concentration
@dataclass(frozen=True)
class LayerConcentration:
    layer: str
    hhi: float | None
    effective_number: float | None
    top_token: str
    top_share: float | None
    n_tokens: int
    unassigned_capital_share: float

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Concentration:
    """Capital-weighted lineage concentration, per layer and overall. EVIDENCE, never a cap."""

    n_positions: int
    capital: float
    by_layer: dict[str, LayerConcentration]
    lineage_hhi: float | None
    effective_lineages: float | None
    mean_pairwise_independence: float | None
    most_shared: tuple[tuple[str, str, float], ...]
    unmeasured: tuple[str, ...]
    kind: str = "evidence"
    is_cap: bool = False
    rule: str = EVIDENCE_RULE

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "is_cap": self.is_cap, "rule": self.rule,
            "n_positions": self.n_positions, "capital": self.capital,
            "by_layer": {k: v.to_json() for k, v in self.by_layer.items()},
            "lineage_hhi": self.lineage_hhi, "effective_lineages": self.effective_lineages,
            "mean_pairwise_independence": self.mean_pairwise_independence,
            "most_shared": [list(row) for row in self.most_shared],
            "unmeasured": list(self.unmeasured),
        }


def _layer_concentration(layer: str, book: Sequence[tuple[Genome, float]], capital: float
                         ) -> LayerConcentration:
    share: dict[str, float] = {}
    unassigned = 0.0
    for gen, weight in book:
        tokens = gen.layer(layer)
        w = abs(weight) / capital
        if not tokens:
            unassigned += w
            continue
        for token in tokens:
            share[token] = share.get(token, 0.0) + w / len(tokens)
    assigned = sum(share.values())
    if assigned <= 0.0:
        return LayerConcentration(layer=layer, hhi=None, effective_number=None, top_token="",
                                  top_share=None, n_tokens=0,
                                  unassigned_capital_share=round(unassigned, 6))
    normalised = {t: s / assigned for t, s in share.items()}
    hhi = sum(s * s for s in normalised.values())
    top = max(normalised.items(), key=lambda kv: (kv[1], kv[0]))
    return LayerConcentration(layer=layer, hhi=round(hhi, 6),
                              effective_number=round(1.0 / hhi, 6), top_token=top[0],
                              top_share=round(top[1], 6), n_tokens=len(normalised),
                              unassigned_capital_share=round(unassigned, 6))


def lineage_concentration(portfolio: Iterable[tuple[Genome, float]]) -> Concentration:
    """How much of the book's capital sits on shared lineage, layer by layer.

    Reads: per layer the Herfindahl of capital across lineage tokens (1.0 = every position on
    one dataset / feature / mechanism), its effective number, and the top token with its share;
    overall the mean HHI across the structural layers that are assigned, the mean pairwise
    structural independence, and the most-shared (layer, token, share) rows. Every number is a
    reading for the allocator to condition on; none is a bound.
    """
    book = [(g, float(w)) for g, w in portfolio if float(w) != 0.0]
    capital = sum(abs(w) for _, w in book)
    if not book or capital <= 0.0:
        return Concentration(n_positions=0, capital=0.0, by_layer={}, lineage_hhi=None,
                             effective_lineages=None, mean_pairwise_independence=None,
                             most_shared=(), unmeasured=("portfolio: no capital allocated",))
    by_layer = {name: _layer_concentration(name, book, capital) for name in LAYERS}
    structural_layers = [layer for axis in STRUCTURAL_AXES for layer in AXIS_LAYERS[axis]
                         if layer in by_layer]
    measured = [h for h in (by_layer[name].hhi for name in structural_layers) if h is not None]
    lineage_hhi = (sum(measured) / len(measured)) if measured else None
    pairs: list[float] = []
    for i in range(len(book)):
        for j in range(i + 1, len(book)):
            reading = hierarchical_distance(book[i][0], book[j][0]).structural
            if reading is not None:
                pairs.append(reading)
    shared = sorted(((c.layer, c.top_token, c.top_share or 0.0) for c in by_layer.values()
                     if c.top_share is not None and c.n_tokens > 0),
                    key=lambda row: (-row[2], LAYERS.index(row[0])))
    unmeasured = tuple(f"{name}: unassigned on every position"
                       for name in LAYERS if by_layer[name].hhi is None)
    return Concentration(
        n_positions=len(book), capital=round(capital, 6), by_layer=by_layer,
        lineage_hhi=None if lineage_hhi is None else round(lineage_hhi, 6),
        effective_lineages=None if not lineage_hhi else round(1.0 / lineage_hhi, 6),
        mean_pairwise_independence=(round(sum(pairs) / len(pairs), 6) if pairs else None),
        most_shared=tuple(shared[:8]), unmeasured=unmeasured)


__all__ = [
    "AXIS_LAYERS", "AXIS_WEIGHT", "DISTANCE_AXES", "EVIDENCE_RULE", "LAYERS", "RULE",
    "STRUCTURAL_AXES", "UNMEASURED", "Concentration", "Genome", "Independence",
    "LayerConcentration", "axis_distance", "genome", "hierarchical_distance", "jaccard_distance",
    "layer_distance", "lineage_concentration",
]
