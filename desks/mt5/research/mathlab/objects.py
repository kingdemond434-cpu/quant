"""The mathematical object, and the panel the fourteen scientists all read.

ONE OBJECT TYPE FOR FIVE KINDS OF DISCOVERY. The principal's spec asks the traditions to search
for five separate things, and the kind field is which:

    relationship     a new data relationship: E[eps_{t+h}] responds to f(x1, x2, ...)
    representation   a new state variable / coordinate the desk did not have
    mechanism        a named economic process the relationship is the footprint of
    law              an invariant: something that holds ACROSS eras, regimes or markets
    search_method    a new transform, objective or search operator (meta-mathematics)

They share one shape because they share one fate: a canonical expression, variables bound to a
dataset id with a point-in-time stamp, an MDL complexity, an evidence block filled by `burden`,
an interpretation block that may be UNINTERPRETED, and a provenance chain back to the residual
target that motivated it. A representation with no evidence is not a representation, it is a
suggestion.

THE PANEL IS THE UNIT OF WORK and is deliberately free of desk imports: a target symbol, the
residual epsilon to explain, aligned columns from every eligible dataset and representation, the
regime/session labels, and the eras that stability is measured across. It can be built from a
world-model residual store on the box or from three numpy arrays in a test, and the scientists
cannot tell the difference -- which is the only way this package is testable in seconds.

PIT IS CARRIED, NEVER ASSUMED. Every column names the time its values became knowable. A column
that cannot say is stamped UNKNOWN and the objects that use it say so in their provenance; it is
not silently treated as knowable at the bar it is aligned to.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import grammar as G

#: The five things the traditions search for.
KINDS: tuple[str, ...] = ("relationship", "representation", "mechanism", "law", "search_method")

#: kind -> the canonical registry's discovery kind.
REGISTRY_KIND: dict[str, str] = {
    "relationship": "math_relationship",
    "representation": "math_representation",
    "mechanism": "math_mechanism",
    "law": "math_law",
    "search_method": "math_search_method",
}

UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class Variable:
    """One column, bound to where it came from and when it became knowable."""

    name: str
    dataset: str
    source: str = "bars"              # bars | axis | representation | derived | residual
    available_time: str = UNMEASURED  # PIT stamp of the newest usable vintage
    units: str = ""

    def to_row(self) -> dict[str, Any]:
        return {"name": self.name, "dataset": self.dataset, "source": self.source,
                "available_time": self.available_time, "units": self.units}


@dataclass
class Evidence:
    """What the object earned, filled by `burden.judge`. Every field is a measurement or None."""

    n_train: int = 0
    n_test: int = 0
    ic_in_sample: float | None = None
    ic_held_out: float | None = None
    t_held_out: float | None = None
    permutation_p: float | None = None
    era_stability: float | None = None
    transfer_ic: float | None = None
    transfer_symbol: str | None = None
    perturbation_min_t: float | None = None
    cost_stress: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    unmeasured: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {"n_train": self.n_train, "n_test": self.n_test,
                "ic_in_sample": self.ic_in_sample, "ic_held_out": self.ic_held_out,
                "t_held_out": self.t_held_out, "permutation_p": self.permutation_p,
                "era_stability": self.era_stability,
                "transfer_ic": self.transfer_ic, "transfer_symbol": self.transfer_symbol,
                "perturbation_min_t": self.perturbation_min_t,
                "cost_stress": self.cost_stress, "diagnostics": self.diagnostics,
                "unmeasured": self.unmeasured}


@dataclass
class Interpretation:
    """Which actor, doing what, for what reason -- or UNINTERPRETED, kept at a lower prior.

    AN OBJECT WITH NO INTERPRETATION IS NEVER DISCARDED. The desk's own standing lesson is that a
    mechanism nobody has thought of is exactly what an unknown-unknown search is FOR; refusing it
    would make the search a confirmation of the ontology it started with. It is kept, marked, and
    given a lower prior so it competes at a disadvantage rather than not competing.
    """

    mechanism_id: str = ""
    actor: str = ""
    rationale: str = ""
    falsifier: str = ""
    matched_on: list[str] = field(default_factory=list)
    status: str = "uninterpreted"      # interpreted | uninterpreted
    prior: float = 0.35

    def to_row(self) -> dict[str, Any]:
        return {"mechanism_id": self.mechanism_id, "actor": self.actor,
                "rationale": self.rationale, "falsifier": self.falsifier,
                "matched_on": self.matched_on, "status": self.status, "prior": self.prior}


@dataclass
class Provenance:
    """What motivated the object and what it was allowed to read."""

    residual_target: str = ""
    residual_discovery_id: str = ""
    datasets: list[str] = field(default_factory=list)
    representations: list[str] = field(default_factory=list)
    panel_source: str = ""
    seed: int = 0
    parents: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return {"residual_target": self.residual_target,
                "residual_discovery_id": self.residual_discovery_id,
                "datasets": self.datasets, "representations": self.representations,
                "panel_source": self.panel_source, "seed": self.seed, "parents": self.parents}


@dataclass
class MathObject:
    """One invented mathematical object: the thing the whole civilization produces."""

    kind: str
    tradition: str
    expression: Any
    target: str
    horizon: str = "H1"
    variables: list[Variable] = field(default_factory=list)
    evidence: Evidence = field(default_factory=Evidence)
    interpretation: Interpretation = field(default_factory=Interpretation)
    provenance: Provenance = field(default_factory=Provenance)
    #: Tradition-specific numbers that are not a fit: a Lyapunov proxy, a Hawkes branching ratio,
    #: a persistence entropy. They justify the object; they never substitute for held-out
    #: evidence, and `burden` does not read them.
    diagnostics: dict[str, Any] = field(default_factory=dict)
    statement: str = ""
    side_mode: str = "follow"
    value: float | None = None
    passed: bool = False
    burden: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind {self.kind!r} is not one of {KINDS}")
        self.expression, self._canonical = G.canonical(self.expression)

    @property
    def canonical(self) -> str:
        return self._canonical

    @property
    def complexity(self) -> dict[str, float]:
        """MDL: node count, free parameter count, and the description length in bits."""
        return {"nodes": G.nodes(self.expression), "parameters": G.parameters(self.expression),
                "mdl_bits": round(G.mdl_bits(self.expression), 4),
                "depth": G.depth(self.expression)}

    @property
    def object_id(self) -> str:
        """Identity is the CANONICAL form plus the kind and the target -- not the search path.

        Two traditions that reach the same law from different directions produce the same id and
        charge one trial between them, which is the only way the burden arithmetic is honest.
        """
        body = f"{self.kind}|{self.target}|{self.horizon}|{self._canonical}"
        return "math_" + hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]

    def to_row(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id, "kind": self.kind, "tradition": self.tradition,
            "registry_kind": REGISTRY_KIND[self.kind],
            "expression": self.expression, "canonical": self._canonical,
            "statement": self.statement, "target": self.target, "horizon": self.horizon,
            "side_mode": self.side_mode,
            "variables": [v.to_row() for v in self.variables],
            "complexity": self.complexity,
            "evidence": self.evidence.to_row(),
            "interpretation": self.interpretation.to_row(),
            "provenance": self.provenance.to_row(),
            "diagnostics": self.diagnostics,
            "value": self.value, "passed": self.passed, "burden": self.burden,
            "notes": self.notes,
        }


# ------------------------------------------------------------------------------------- panel
@dataclass
class Panel:
    """One target's residual and every series a scientist may read while explaining it."""

    target: str
    times: np.ndarray
    epsilon: np.ndarray
    columns: dict[str, np.ndarray] = field(default_factory=dict)
    meta: dict[str, Variable] = field(default_factory=dict)
    regime: np.ndarray | None = None
    session: np.ndarray | None = None
    peers: dict[str, np.ndarray] = field(default_factory=dict)
    horizon: str = "H1"
    source: str = UNMEASURED
    residual_discovery_id: str = ""
    unmeasured: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.times = np.asarray(self.times)
        self.epsilon = np.asarray(self.epsilon, dtype=float)
        for name, values in list(self.columns.items()):
            self.columns[name] = np.asarray(values, dtype=float)

    @property
    def n(self) -> int:
        return int(self.epsilon.size)

    @property
    def names(self) -> list[str]:
        return sorted(self.columns)

    def matrix(self, names: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
        """(n x k) column matrix and the names, in a fixed order. NaNs are left in place."""
        use = names if names is not None else self.names
        if not use:
            return np.empty((self.n, 0), dtype=float), []
        return np.column_stack([self.columns[c] for c in use if c in self.columns]), \
            [c for c in use if c in self.columns]

    def mint(self, name: str, values: np.ndarray, variable: Variable | None = None) -> str:
        """Add a DERIVED column. This is how a tradition invents a new state variable.

        Each tradition runs on its OWN VIEW of the panel (`math_lab._copy_panel`), so minting is
        private within a pass and no two threads race on the same dict. The variable reaches the
        other thirteen the honest way: it is published as a representation under
        `data/representations/mathlab/`, and next pass's panel builder loads it as a column for
        everyone. That is what makes the civilization a civilization rather than fourteen scripts.
        """
        series = np.asarray(values, dtype=float)
        if series.size != self.n:
            raise ValueError(f"minted column {name!r} has {series.size} rows, panel has {self.n}")
        self.columns[name] = series
        self.meta[name] = variable or Variable(name=name, dataset=f"mathlab:{name}",
                                               source="derived")
        return name

    def eras(self, k: int = 4) -> np.ndarray:
        """Contiguous era labels 0..k-1 over time: the environments invariance is tested across."""
        k = max(2, int(k))
        if self.n < k:
            return np.zeros(self.n, dtype=int)
        return np.minimum((np.arange(self.n) * k) // self.n, k - 1)

    def split(self, train_frac: float = 0.6) -> tuple[np.ndarray, np.ndarray]:
        """A TIME-ORDERED split with an embargo. Never a shuffle: the rows are a path."""
        cut = int(self.n * float(train_frac))
        embargo = min(24, max(1, self.n // 50))
        train = np.arange(0, max(0, cut))
        test = np.arange(min(self.n, cut + embargo), self.n)
        return train, test

    def note(self, what: str, why: str) -> None:
        self.unmeasured.append(f"{what}: {why}")
