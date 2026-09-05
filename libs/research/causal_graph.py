"""THE WORLD CAUSAL GRAPH -- the world's data as one graph of X_t -> Y_{t+h} edges, so the desk
can discover second- and third-order links rather than only direct predictors.

THE ORDER (principal, 2026-09-05): "Build the world's data into one causal graph. Nodes:
country, central bank, yield curve, currency, commodity, equity index, volatility, physical
market, futures market, flow, positioning, event, MT5 instrument. Edges X_t -> Y_{t+h} storing
direction, lag, state dependence, nonlinearity, stability, causal plausibility, incremental
information, decay. Examples: China physical gold -> SGE premium -> XAUUSD; Australia commodity
data -> iron/copper -> AUD -> AUDJPY; US CPI -> 2Y yield -> USD -> gold. The machine should
discover second- and third-order links, not merely direct predictors."

WHAT THE DESK ALREADY HAD, AND WHAT THIS ADDS. `libs.research.lead_lag` measures ONE HOP between
two instruments' H1 bars (lag, t, vol-state split, quarter-sign stability, out-of-sample
log-score) and `desks/mt5/research/cross_asset_graph.py` turns the strong hops into cells. That
is a flat list of instrument pairs: it cannot say that copper reaches AUDJPY through AUD, nor
that a Chinese premium reaches XAUUSD through the metal, because nothing in it names a node
that is not a Fusion symbol. This module is the graph those hops live in. Its estimators are
deliberately close cousins of lead_lag's -- the same alignment, the same vol split -- with three
things lead_lag does not do: a BLOCK-BOOTSTRAP confidence interval rather than a t-statistic
(the desk's returns are fat-tailed and its t-tests have certified 420 edges and kept 0), an
INCREMENTAL-INFORMATION test (does X_{t-h} add to Y's own lags, with a permutation p-value), and
a MULTIPLICITY CHARGE over every (pair, lag) cell ever tested that widens the admission interval
and is never loosened.

TWO LAYERS OF NODE. World nodes are namespaced by kind (`commodity:gold`, `currency:AUD`,
`yield:US2Y`, `positioning:COT_gold`, `event:US_CPI`, `cb:FED`) and are independent of what any
broker quotes. MT5 instruments are bare Fusion symbol names and may only exist when
`universe.json` quotes them -- `instrument_nodes()` is the sole source of those ids. A world node
is attached to the instrument that prices it by a STRUCTURAL edge (`commodity:gold -> XAUUSD`,
lag 0): a definition, not a claim, so it needs no measurement and does not count toward a path's
order. A world edge between two nodes that both have such a proxy is MEASURED through the proxy
series, and the evidence says so.

THE PRIOR TABLE. The three example chains and the standard FX / metals / energy / rates chains
are seeded as PLAUSIBLE_UNMEASURED edges with a hand-written plausibility and the reason. A chain
therefore exists in the graph before any data has proved it, the report shows which chains are
measured, and a measured edge that contradicts its prior is visible as exactly that -- the prior
is kept beside the measurement, never overwritten by it.

ADMISSION IS ONE RULE. An edge is ADMITTED when its block-bootstrap interval for the correlation
at the chosen lag, widened by Bonferroni over every (pair, lag) cell the graph has charged,
excludes zero AND the incremental-information test says X adds to Y's own lags. Everything else
that was measured is RECORDED_NOT_ADMITTED with the reason on the edge. Nothing here proposes,
sizes or trades: the graph's consumer is `state_vector_build`, which reads admitted upstream
nodes as CONDITIONING HINTS, and the allocator still owns every decision.

numpy only for the estimators; the graph itself is stdlib. No network, no I/O beyond
`instrument_nodes()` reading the universe file it is handed.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np

__all__ = [
    "ADMITTED",
    "ALPHA",
    "KINDS",
    "MAX_LAG",
    "MIN_N",
    "PLAUSIBLE_UNMEASURED",
    "PRIOR_CHAINS",
    "PRIOR_EDGES",
    "PRIOR_NODES",
    "PROXIES",
    "RECORDED_NOT_ADMITTED",
    "STRUCTURAL",
    "CausalGraph",
    "Edge",
    "Node",
    "deflated_z",
    "incremental_information",
    "instrument_nodes",
    "lagged_xcorr",
    "measure_edge",
    "nonlinearity",
    "seed_priors",
    "stability",
    "state_dependence",
]

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_JSON = ROOT / "desks" / "mt5" / "data" / "universe" / "universe.json"

#: The node kinds the order names. `mt5_instrument` ids come from universe.json and nowhere else.
KINDS: tuple[str, ...] = (
    "country", "central_bank", "yield_curve", "currency", "commodity", "equity_index",
    "volatility", "physical_market", "futures_market", "flow", "positioning", "event",
    "mt5_instrument",
)
MT5 = "mt5_instrument"

#: Edge statuses. STRUCTURAL is a definition (a proxy or a membership), never a lead-lag claim.
PLAUSIBLE_UNMEASURED = "PLAUSIBLE_UNMEASURED"
ADMITTED = "ADMITTED"
RECORDED_NOT_ADMITTED = "RECORDED_NOT_ADMITTED"
STRUCTURAL = "STRUCTURAL"
MEASURED = frozenset({ADMITTED, RECORDED_NOT_ADMITTED})

#: Two-sided level of the admission interval BEFORE the multiplicity charge widens it.
ALPHA = 0.05
#: Aligned observations below which an edge is not measured at all. The same floor lead_lag
#: uses for its verdicts, so a pair too short for one is too short for the other.
MIN_N = 500
#: Lags searched, in bars of the pair's clock. Six, as lead_lag: a lead longer than a session on
#: H1 bars is a different (daily) hypothesis and belongs on the daily clock.
MAX_LAG = 6
N_BOOT = 200
N_PERM = 200
#: Most recent aligned observations used by the estimators. Bounds the bootstrap's memory on a
#: swapless 4 GB box; the block bootstrap over 20k H1 bars is already ~2.5 years of hours.
MAX_N = 20_000
#: Own lags of Y the incremental-information test conditions on.
OWN_LAGS = 3
#: Observations a regime bucket needs before its correlation is reported.
MIN_STATE_N = 60
#: Paths returned per (src, dst) query, longest-first pruning is the caller's job.
MAX_PATHS = 200

_EPS = 1e-12


# ==================================================================================== nodes
@dataclass(frozen=True)
class Node:
    """One thing in the world. `country` is an ISO-ish code or empty; `unit` is what a series
    of it would be denominated in; `source` says where a series of it would come from."""

    id: str
    kind: str
    country: str = ""
    unit: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"node {self.id!r}: unknown kind {self.kind!r}; known: {KINDS}")
        if not self.id:
            raise ValueError("node id must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Node:
        return cls(id=str(d["id"]), kind=str(d["kind"]), country=str(d.get("country") or ""),
                   unit=str(d.get("unit") or ""), source=str(d.get("source") or ""))


def instrument_nodes(universe_path: Path = UNIVERSE_JSON) -> dict[str, Node]:
    """Every MT5 instrument node, from universe.json ONLY. Empty when the file is unreadable --
    an absent universe is no instruments, never a guessed list."""
    try:
        doc = json.loads(Path(universe_path).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, Node] = {}
    if not isinstance(doc, dict):
        return out
    for sym, row in doc.items():
        if not isinstance(row, dict) or not isinstance(sym, str) or not sym:
            continue
        out[sym] = Node(id=sym, kind=MT5, country="",
                        unit=str(row.get("currency_profit") or ""),
                        source=f"fusion:{row.get('asset_class') or ''}")
    return out


# ==================================================================================== edges
@dataclass
class Edge:
    """X_t -> Y_{t+lag}. The measured fields are zero until the edge is measured; `plausibility`
    is the prior and survives measurement; `status` and `reason` say what the measurement did."""

    src: str
    dst: str
    lag: int
    direction: str = "unknown"          # "same" | "opposite" | "unknown"
    strength: float = 0.0               # correlation of X_t with Y_{t+lag} at the chosen lag
    stability: float = 0.0              # rolling-window sign agreement in [0, 1]
    state_dependence: float = 0.0       # spread of |strength| across regime labels
    nonlinearity: float = 0.0           # max(0, |spearman| - |pearson|)
    plausibility: float = 0.0           # the hand-written prior in [0, 1]
    incremental_info: float = 0.0       # deltaR2 of X_{t-lag} over Y's own lags
    decay_cls: str = ""                 # information class of X (libs.research.information_decay)
    n: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)
    clock: str = ""                     # the clock the lag is counted in ("H1", "D1", "W1")
    status: str = PLAUSIBLE_UNMEASURED
    reason: str = ""
    measured_at: str = ""

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.src, self.dst, int(self.lag))

    @property
    def measured(self) -> bool:
        return self.status in MEASURED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Edge:
        return cls(
            src=str(d["src"]), dst=str(d["dst"]), lag=int(d.get("lag") or 0),
            direction=str(d.get("direction") or "unknown"),
            strength=float(d.get("strength") or 0.0), stability=float(d.get("stability") or 0.0),
            state_dependence=float(d.get("state_dependence") or 0.0),
            nonlinearity=float(d.get("nonlinearity") or 0.0),
            plausibility=float(d.get("plausibility") or 0.0),
            incremental_info=float(d.get("incremental_info") or 0.0),
            decay_cls=str(d.get("decay_cls") or ""), n=int(d.get("n") or 0),
            evidence=dict(d.get("evidence") or {}), clock=str(d.get("clock") or ""),
            status=str(d.get("status") or PLAUSIBLE_UNMEASURED),
            reason=str(d.get("reason") or ""), measured_at=str(d.get("measured_at") or ""))


def _cell(src: str, dst: str, lag: int) -> str:
    return f"{src}|{dst}|{int(lag)}"


def _carry_prior(src_ev: dict[str, Any], dst_ev: dict[str, Any]) -> None:
    """Every `prior_*` field (why, direction, source) survives onto the edge that replaces the
    prior, so a measurement that contradicts its prior is visible as exactly that."""
    for k, v in src_ev.items():
        if k.startswith("prior_") and k not in dst_ev:
            dst_ev[k] = v


# ================================================================================ the graph
class CausalGraph:
    """Nodes, edges keyed by (src, dst, lag), and the multiplicity ledger of every cell tested.

    `instrument_ids`, when given, is the ONLY set of ids an `mt5_instrument` node may take:
    a node claiming to be a Fusion instrument the universe does not quote is refused, which is
    what keeps a foreign alias (COPPER, DXY, HG) from becoming a node the desk cannot trade.
    """

    def __init__(self, instrument_ids: Iterable[str] | None = None) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[tuple[str, str, int], Edge] = {}
        self.instrument_ids: frozenset[str] | None = (
            frozenset(instrument_ids) if instrument_ids is not None else None)
        #: Every (src, dst, lag) cell ever charged. A SET: re-measuring the same cell with more
        #: data is the same hypothesis, not a new one, so the charge is the size of the
        #: hypothesis space actually searched -- and it never shrinks.
        self.cells: set[str] = set()
        self.seed_notes: list[str] = []

    # ------------------------------------------------------------------------------- nodes
    def add_node(self, node: Node) -> Node:
        """Idempotent. An instrument node outside the universe is refused."""
        if node.kind == MT5 and self.instrument_ids is not None \
                and node.id not in self.instrument_ids:
            raise ValueError(f"{node.id!r} is not a Fusion symbol in universe.json -- an MT5 "
                             "instrument node may only carry a name the desk can quote")
        have = self.nodes.get(node.id)
        if have is None:
            self.nodes[node.id] = node
            return node
        if have.kind != node.kind:
            raise ValueError(f"node {node.id!r} already exists as {have.kind}, not {node.kind}")
        return have

    def instrument_nodes(self) -> list[Node]:
        return sorted((n for n in self.nodes.values() if n.kind == MT5), key=lambda n: n.id)

    # ------------------------------------------------------------------------------- edges
    def add_edge(self, edge: Edge) -> Edge:
        """Merge on (src, dst, lag). The rules, each of which protects something:

        - a measurement replaces a measurement (the newer one saw more bars) and replaces a
          prior, but the prior's plausibility and reason are KEPT on the measured edge;
        - a prior never overwrites a measurement: seeding is idempotent across hourly runs;
        - a prior's lag is a HINT: the measurement lands at the lag the data chose, and the
          unmeasured prior for the same (src, dst) is folded into it rather than left beside
          it as a second edge that looks unmeasured;
        - a structural edge is a definition and is never replaced by anything.
        """
        for nid in (edge.src, edge.dst):
            if nid not in self.nodes:
                raise KeyError(f"edge {edge.src}->{edge.dst}: node {nid!r} is not in the graph")
        have = self.edges.get(edge.key)
        if have is not None and have.status == STRUCTURAL:
            return have
        if not edge.measured and edge.status != STRUCTURAL:
            # a prior arriving: fill what the existing edge for this pair lacks, no more
            target = have if have is not None else self.measured_edge(edge.src, edge.dst)
            if target is None:
                self.edges[edge.key] = edge
                return edge
            if target.plausibility <= 0.0 < edge.plausibility:
                target.plausibility = edge.plausibility
            if not target.decay_cls:
                target.decay_cls = edge.decay_cls
            if not target.clock:
                target.clock = edge.clock
            _carry_prior(edge.evidence, target.evidence)
            return target
        if edge.status == STRUCTURAL:
            if have is None:
                self.edges[edge.key] = edge
                return edge
            return have
        # a measurement: absorb every unmeasured prior for the pair, then replace
        for prior in [e for e in self.edges.values()
                      if e.src == edge.src and e.dst == edge.dst and not e.measured
                      and e.status != STRUCTURAL]:
            if edge.plausibility <= 0.0 < prior.plausibility:
                edge.plausibility = prior.plausibility
            _carry_prior(prior.evidence, edge.evidence)
            if prior.lag != edge.lag:
                edge.evidence.setdefault("prior_lag", prior.lag)
            del self.edges[prior.key]
        have = self.edges.get(edge.key)
        if have is not None:
            if edge.plausibility <= 0.0 < have.plausibility:
                edge.plausibility = have.plausibility
            _carry_prior(have.evidence, edge.evidence)
            if have.measured and have.measured_at and not edge.evidence.get("previous"):
                edge.evidence["previous"] = {"status": have.status, "strength": have.strength,
                                             "n": have.n, "measured_at": have.measured_at}
        self.edges[edge.key] = edge
        return edge

    def measured_edge(self, src: str, dst: str) -> Edge | None:
        """The measured edge for a pair, whatever lag the data chose; None when unmeasured."""
        best = None
        for e in self.edges.values():
            if e.src == src and e.dst == dst and e.measured and (
                    best is None or e.measured_at > best.measured_at):
                best = e
        return best

    def merge(self, other: CausalGraph) -> None:
        for node in other.nodes.values():
            self.add_node(node)
        for edge in other.edges.values():
            self.add_edge(edge)
        self.cells |= other.cells
        self.seed_notes.extend(n for n in other.seed_notes if n not in self.seed_notes)

    def edge(self, src: str, dst: str, lag: int) -> Edge | None:
        return self.edges.get((src, dst, int(lag)))

    def edges_from(self, src: str) -> list[Edge]:
        return [e for e in self.edges.values() if e.src == src]

    def edges_into(self, dst: str) -> list[Edge]:
        return [e for e in self.edges.values() if e.dst == dst]

    # ------------------------------------------------------------------------ multiplicity
    def charge(self, src: str, dst: str, lags: Iterable[int]) -> int:
        """Charge every (src, dst, lag) cell about to be tested. Returns the ledger size."""
        for lag in lags:
            self.cells.add(_cell(src, dst, int(lag)))
        return len(self.cells)

    @property
    def multiplicity(self) -> int:
        return len(self.cells)

    # ------------------------------------------------------------------------------- paths
    def paths(self, src: str, dst: str, max_order: int = 3, *,
              admitted_only: bool = False) -> list[list[Edge]]:
        """Every simple chain from `src` to `dst` with at most `max_order` NON-structural edges.

        Structural edges (a commodity to the instrument that prices it) are free: they change
        the name of a node, not the order of the claim. With `admitted_only` every claim edge on
        the path must be ADMITTED -- that is the chain the state builder may condition on.
        """
        out: list[list[Edge]] = []
        by_src: dict[str, list[Edge]] = {}
        for e in self.edges.values():
            by_src.setdefault(e.src, []).append(e)

        def walk(node: str, path: list[Edge], order: int, seen: set[str]) -> None:
            if len(out) >= MAX_PATHS:
                return
            for e in sorted(by_src.get(node, ()), key=lambda x: (x.dst, x.lag)):
                if e.dst in seen:
                    continue
                if admitted_only and e.status not in (ADMITTED, STRUCTURAL):
                    continue
                cost = 0 if e.status == STRUCTURAL else 1
                if order + cost > max_order:
                    continue
                nxt = [*path, e]
                if e.dst == dst:
                    if nxt:
                        out.append(nxt)
                    continue
                walk(e.dst, nxt, order + cost, seen | {e.dst})

        walk(src, [], 0, {src})
        out.sort(key=lambda p: (path_order(p), -abs(path_strength(p))))
        return out

    def upstream(self, dst: str, max_order: int = 3, *, admitted_only: bool = True
                 ) -> list[dict[str, Any]]:
        """Every chain ending at `dst`, summarised for a consumer: the source node, the nodes on
        the way, the total lag when the clocks agree, the SLOWEST decay class on the chain (a
        chain's information ages at the rate of its slowest link) and the product strength."""
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for src in self.nodes:
            if src == dst:
                continue
            for p in self.paths(src, dst, max_order, admitted_only=admitted_only):
                if path_order(p) == 0:
                    continue                     # a proxy alone is a name, not a claim
                key = (*(e.src for e in p), dst, *(str(e.lag) for e in p))
                if key in seen:
                    continue
                seen.add(key)
                out.append(summarise_path(p))
        out.sort(key=lambda d: (d["order"], -abs(d["strength"])))
        return out

    # ------------------------------------------------------------------------------ counts
    def counts(self) -> dict[str, int]:
        claim = [e for e in self.edges.values() if e.status != STRUCTURAL]
        return {
            "nodes": len(self.nodes),
            "instrument_nodes": sum(1 for n in self.nodes.values() if n.kind == MT5),
            "edges": len(claim),
            "structural_edges": len(self.edges) - len(claim),
            "admitted": sum(1 for e in claim if e.status == ADMITTED),
            "recorded_not_admitted": sum(1 for e in claim if e.status == RECORDED_NOT_ADMITTED),
            "plausible_unmeasured": sum(1 for e in claim if e.status == PLAUSIBLE_UNMEASURED),
            "multiplicity_charged": len(self.cells),
        }

    def chain_status(self, chains: dict[str, tuple[str, ...]] | None = None
                     ) -> dict[str, dict[str, Any]]:
        """Per named chain: whether every claim edge on it exists, is measured, is admitted."""
        out: dict[str, dict[str, Any]] = {}
        for name, nodes in (chains or PRIOR_CHAINS).items():
            hops: list[dict[str, Any]] = []
            for a, b in pairwise(nodes):
                cands = [e for e in self.edges.values() if e.src == a and e.dst == b]
                best = None
                for e in cands:
                    rank = (e.status == ADMITTED, e.status == STRUCTURAL, e.measured,
                            abs(e.strength))
                    if best is None or rank > best[0]:
                        best = (rank, e)
                hops.append({"src": a, "dst": b, "status": best[1].status if best else "MISSING",
                             "lag": best[1].lag if best else None,
                             "strength": best[1].strength if best else None})
            claims = [h for h in hops if h["status"] != STRUCTURAL]
            out[name] = {
                "nodes": list(nodes), "hops": hops,
                "seeded": all(h["status"] != "MISSING" for h in hops),
                "measured": bool(claims) and all(h["status"] in MEASURED for h in claims),
                "admitted": bool(claims) and all(h["status"] == ADMITTED for h in claims),
            }
        return out

    # -------------------------------------------------------------------------------- json
    def to_json(self) -> dict[str, Any]:
        return {
            "version": 1,
            "generated_utc": datetime.now(tz=UTC).isoformat(),
            "counts": self.counts(),
            "nodes": [n.to_dict() for n in sorted(self.nodes.values(), key=lambda n: n.id)],
            "edges": [e.to_dict() for e in sorted(self.edges.values(), key=lambda e: e.key)],
            "cells_charged": sorted(self.cells),
            "seed_notes": list(self.seed_notes),
        }

    @classmethod
    def from_json(cls, doc: dict[str, Any],
                  instrument_ids: Iterable[str] | None = None) -> CausalGraph:
        g = cls(instrument_ids=instrument_ids)
        for nd in doc.get("nodes") or []:
            try:
                g.add_node(Node.from_dict(nd))
            except (KeyError, ValueError) as exc:
                g.seed_notes.append(f"dropped node {nd!r}: {exc}")
        for ed in doc.get("edges") or []:
            try:
                g.add_edge(Edge.from_dict(ed))
            except (KeyError, ValueError) as exc:
                g.seed_notes.append(f"dropped edge {ed.get('src')}->{ed.get('dst')}: {exc}")
        g.cells = {str(c) for c in (doc.get("cells_charged") or [])}
        for note in doc.get("seed_notes") or []:
            if str(note) not in g.seed_notes:
                g.seed_notes.append(str(note))
        return g

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1, default=str), "utf-8")

    @classmethod
    def load(cls, path: Path, instrument_ids: Iterable[str] | None = None) -> CausalGraph:
        doc = json.loads(Path(path).read_text("utf-8"))
        if not isinstance(doc, dict):
            raise ValueError(f"{path}: not a causal-graph document")
        return cls.from_json(doc, instrument_ids=instrument_ids)


def path_order(path: Sequence[Edge]) -> int:
    return sum(1 for e in path if e.status != STRUCTURAL)


def path_strength(path: Sequence[Edge]) -> float:
    s = 1.0
    for e in path:
        if e.status == STRUCTURAL:
            s *= -1.0 if e.direction == "opposite" else 1.0
        else:
            s *= e.strength
    return s


def summarise_path(path: Sequence[Edge]) -> dict[str, Any]:
    claims = [e for e in path if e.status != STRUCTURAL]
    clocks = {e.clock for e in claims if e.clock}
    slowest = ""
    slowest_hl = -1.0
    for e in claims:
        hl = _half_life(e.decay_cls)
        if hl > slowest_hl:
            slowest, slowest_hl = e.decay_cls, hl
    return {
        "src": path[0].src, "dst": path[-1].dst,
        "nodes": [path[0].src, *(e.dst for e in path)],
        "lags": [e.lag for e in path],
        "lag_total": sum(e.lag for e in claims) if len(clocks) <= 1 else None,
        "clock": next(iter(clocks)) if len(clocks) == 1 else ("mixed" if clocks else ""),
        "order": path_order(path),
        "strength": round(path_strength(path), 6),
        "decay_cls": slowest,
        "statuses": [e.status for e in path],
        "admitted": all(e.status in (ADMITTED, STRUCTURAL) for e in path),
        "measured": all(e.status in MEASURED or e.status == STRUCTURAL for e in path)
        and bool(claims),
        "min_plausibility": min((e.plausibility for e in claims), default=0.0),
    }


def _half_life(cls: str) -> float:
    if not cls:
        return -1.0
    try:
        from libs.research.information_decay import REGISTRY
        return float(REGISTRY[cls].half_life_s)
    except (ImportError, KeyError):
        return 0.0


# ============================================================================== estimators
def _pairs(x: np.ndarray, y: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    """(X_t, Y_{t+lag}) with non-finite pairs dropped and the sample capped to the most recent
    MAX_N. Lag 0 is refused: a contemporaneous correlation is not a lead."""
    if lag < 1:
        raise ValueError(f"lag must be >= 1 (got {lag}); X_t -> Y_{{t+h}} needs h >= 1")
    a = np.asarray(x, dtype="float64")
    b = np.asarray(y, dtype="float64")
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("x and y must be aligned 1-d series of the same length")
    if a.size <= lag:
        return np.empty(0), np.empty(0)
    xa, yb = a[:-lag], b[lag:]
    ok = np.isfinite(xa) & np.isfinite(yb)
    xa, yb = xa[ok], yb[ok]
    if xa.size > MAX_N:
        xa, yb = xa[-MAX_N:], yb[-MAX_N:]
    return xa, yb


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 3:
        return 0.0
    ac, bc = a - a.mean(), b - b.mean()
    den = math.sqrt(float(ac @ ac) * float(bc @ bc))
    return float(ac @ bc) / den if den > _EPS else 0.0


def _rank(a: np.ndarray) -> np.ndarray:
    """Ordinal ranks. Ties are not averaged -- returns are continuous, and the cost of a
    tie-aware rank on 20k points every hour buys nothing here."""
    out = np.empty(a.size, dtype="float64")
    out[np.argsort(a, kind="stable")] = np.arange(a.size, dtype="float64")
    return out


def deflated_z(alpha: float, n_tests: int) -> float:
    """The two-sided normal quantile after a Bonferroni charge of `n_tests` cells. Bonferroni
    rather than Holm because the ledger is the WHOLE hypothesis space the graph has searched,
    not a ranked list of survivors, and the bar must not depend on the order cells were run."""
    n = max(1, int(n_tests))
    a = min(max(float(alpha), 1e-12), 0.5) / n
    return float(NormalDist().inv_cdf(1.0 - a / 2.0))


def _block_boot_corr(a: np.ndarray, b: np.ndarray, *, n_boot: int, block: int,
                     rng: np.random.Generator, batch: int = 50) -> np.ndarray:
    """Circular block bootstrap of corr(a, b) over PAIRS, so the dependence inside each series
    and between them is kept within a block. Batched to bound memory."""
    n = a.size
    m = math.ceil(n / block)
    offs = np.arange(block)
    draws = np.empty(n_boot, dtype="float64")
    done = 0
    while done < n_boot:
        k = min(batch, n_boot - done)
        starts = rng.integers(0, n, size=(k, m))
        idx = (starts[:, :, None] + offs[None, None, :]).reshape(k, m * block)[:, :n] % n
        aa = a[idx]
        bb = b[idx]
        aa = aa - aa.mean(axis=1, keepdims=True)
        bb = bb - bb.mean(axis=1, keepdims=True)
        num = (aa * bb).sum(axis=1)
        den = np.sqrt((aa * aa).sum(axis=1) * (bb * bb).sum(axis=1))
        with np.errstate(divide="ignore", invalid="ignore"):
            draws[done:done + k] = np.where(den > _EPS, num / den, 0.0)
        done += k
    return draws


def lagged_xcorr(x: np.ndarray, y: np.ndarray, *, max_lag: int = MAX_LAG,
                 lags: Iterable[int] | None = None, n_boot: int = N_BOOT,
                 block: int | None = None, seed: int = 0, alpha: float = ALPHA,
                 n_tests: int = 1) -> dict[str, Any]:
    """corr(X_t, Y_{t+h}) for each lag with a block-bootstrap interval, raw and DEFLATED.

    `ci` is the percentile interval at `alpha`; `ci_deflated` is the normal-approximation
    interval at alpha / n_tests (a percentile interval cannot resolve alpha/300 from 200 draws,
    and a bar that silently stopped widening at the draw count would loosen with the charge).
    `best` is the lag with the largest |corr|; that choice is what the per-lag charge pays for.
    """
    rng = np.random.default_rng(seed)
    hs = sorted({int(h) for h in (lags if lags is not None else range(1, max_lag + 1))})
    z = deflated_z(alpha, n_tests)
    rows: list[dict[str, Any]] = []
    for h in hs:
        a, b = _pairs(x, y, h)
        n = int(a.size)
        if n < 30:
            rows.append({"lag": h, "corr": 0.0, "n": n, "sd_boot": 0.0, "ci": (0.0, 0.0),
                         "ci_deflated": (0.0, 0.0), "note": "too few aligned pairs"})
            continue
        r = _corr(a, b)
        blk = int(block) if block else max(5, round(n ** (1.0 / 3.0)))
        draws = _block_boot_corr(a, b, n_boot=n_boot, block=blk, rng=rng)
        sd = float(np.std(draws, ddof=1)) if draws.size > 1 else 0.0
        lo, hi = (float(v) for v in np.quantile(draws, [alpha / 2.0, 1.0 - alpha / 2.0]))
        rows.append({"lag": h, "corr": round(r, 6), "n": n, "sd_boot": round(sd, 6),
                     "block": blk, "ci": (round(lo, 6), round(hi, 6)),
                     "ci_deflated": (round(r - z * sd, 6), round(r + z * sd, 6))})
    best = max(rows, key=lambda d: abs(float(d["corr"]))) if rows else {}
    return {"lags": rows, "best": best, "n_tests": int(max(1, n_tests)), "z_deflated": round(z, 4),
            "alpha": alpha}


def incremental_information(x: np.ndarray, y: np.ndarray, lag: int, *, own_lags: int = OWN_LAGS,
                            n_perm: int = N_PERM, seed: int = 0) -> dict[str, Any]:
    """Does X_{t-lag} add to Y's own lags? deltaR2 of the regression of Y_t on
    [1, Y_{t-1..t-p}, X_{t-lag}] over [1, Y_{t-1..t-p}], with a permutation p-value.

    The null is built by CIRCULARLY SHIFTING X (never by shuffling it): a shuffle destroys X's
    own autocorrelation and manufactures significance for any persistent regressor, which is
    the class of false edge a lead-lag search produces most. Frisch-Waugh makes each draw one
    residualisation, so 200 draws over 20k bars cost a few milliseconds.
    """
    rng = np.random.default_rng(seed)
    a = np.asarray(x, dtype="float64")
    b = np.asarray(y, dtype="float64")
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("x and y must be aligned 1-d series of the same length")
    if lag < 1:
        raise ValueError("lag must be >= 1")
    p = max(1, int(own_lags))
    start = max(lag, p)
    n_all = a.size - start
    if n_all < 30:
        return {"delta_r2": 0.0, "n": int(max(0, n_all)), "p_value": 1.0,
                "note": "too few observations"}
    yt = b[start:]
    cols = [np.ones(n_all)]
    for k in range(1, p + 1):
        cols.append(b[start - k:a.size - k])
    xl = a[start - lag:a.size - lag]
    zmat = np.column_stack(cols)
    ok = np.isfinite(yt) & np.isfinite(xl) & np.all(np.isfinite(zmat), axis=1)
    yt, xl, zmat = yt[ok], xl[ok], zmat[ok]
    if yt.size > MAX_N:
        yt, xl, zmat = yt[-MAX_N:], xl[-MAX_N:], zmat[-MAX_N:]
    n = int(yt.size)
    if n < 30:
        return {"delta_r2": 0.0, "n": n, "p_value": 1.0, "note": "too few finite observations"}
    q, _ = np.linalg.qr(zmat)
    ey = yt - q @ (q.T @ yt)
    tss = float(((yt - yt.mean()) ** 2).sum())
    r2_base = 1.0 - float(ey @ ey) / tss if tss > _EPS else 0.0

    def _delta(xv: np.ndarray) -> float:
        ex = xv - q @ (q.T @ xv)
        return _corr(ey, ex) ** 2 * (1.0 - r2_base)

    obs = _delta(xl)
    lo_shift = p + lag + 10
    if n - lo_shift <= lo_shift:
        return {"delta_r2": round(obs, 8), "n": n, "p_value": 1.0, "r2_base": round(r2_base, 6),
                "note": "too short for a circular-shift null"}
    shifts = rng.integers(lo_shift, n - lo_shift, size=int(n_perm))
    null = np.array([_delta(np.roll(xl, int(s))) for s in shifts])
    pv = (1.0 + float((null >= obs).sum())) / (1.0 + null.size)
    return {"delta_r2": round(obs, 8), "n": n, "p_value": round(pv, 4),
            "r2_base": round(r2_base, 6), "null_q95": round(float(np.quantile(null, 0.95)), 8),
            "own_lags": p, "n_perm": int(n_perm)}


def _vol_regime(y: np.ndarray, window: int = 48) -> np.ndarray:
    """HIGH_VOL / LOW_VOL by a trailing standard deviation against its own median -- the split
    lead_lag uses, so a state dependence measured here is comparable with one measured there."""
    b = np.asarray(y, dtype="float64")
    out = np.full(b.size, "UNLABELLED", dtype=object)
    if b.size < window * 2:
        return out
    sq = np.nan_to_num(b) ** 2
    csum = np.cumsum(np.insert(sq, 0, 0.0))
    var = np.full(b.size, np.nan)
    var[window - 1:] = (csum[window:] - csum[:-window]) / window
    vol = np.sqrt(var)
    med = float(np.nanmedian(vol))
    fin = np.isfinite(vol)
    out[fin & (vol > med)] = "HIGH_VOL"
    out[fin & (vol <= med)] = "LOW_VOL"
    return out


def state_dependence(x: np.ndarray, y: np.ndarray, lag: int,
                     regime: Sequence[Any] | np.ndarray | None = None) -> dict[str, Any]:
    """Strength split by a regime label aligned to Y (the label at the TARGET bar's own time).
    Without labels the trailing-vol split stands in and says so. `spread` is max - min of
    |corr| over buckets with at least MIN_STATE_N observations."""
    a = np.asarray(x, dtype="float64")
    b = np.asarray(y, dtype="float64")
    if lag < 1 or a.size <= lag:
        return {"by_state": {}, "spread": 0.0, "basis": "unmeasured"}
    lab = np.asarray(regime if regime is not None else _vol_regime(b), dtype=object)
    if lab.size != b.size:
        raise ValueError("regime labels must align with y")
    xa, yb, lb = a[:-lag], b[lag:], lab[lag:]
    ok = np.isfinite(xa) & np.isfinite(yb)
    xa, yb, lb = xa[ok], yb[ok], lb[ok]
    if xa.size > MAX_N:
        xa, yb, lb = xa[-MAX_N:], yb[-MAX_N:], lb[-MAX_N:]
    by: dict[str, dict[str, Any]] = {}
    for label in sorted({str(v) for v in lb}):
        m = lb == label
        if int(m.sum()) < MIN_STATE_N or label == "UNLABELLED":
            continue
        by[label] = {"corr": round(_corr(xa[m], yb[m]), 6), "n": int(m.sum())}
    strengths = [abs(float(v["corr"])) for v in by.values()]
    spread = (max(strengths) - min(strengths)) if len(strengths) >= 2 else 0.0
    return {"by_state": by, "spread": round(spread, 6),
            "basis": "caller labels" if regime is not None else "trailing-vol median split"}


def stability(x: np.ndarray, y: np.ndarray, lag: int, *, windows: int = 4) -> float:
    """Fraction of contiguous windows whose correlation sign agrees with the full sample's. A
    window with no sign counts as disagreement -- an edge that vanishes for a quarter of its
    history is not stable for that quarter."""
    a, b = _pairs(x, y, lag)
    if a.size < 30 * windows:
        return 0.0
    full = np.sign(_corr(a, b))
    if full == 0:
        return 0.0
    q = a.size // windows
    agree = 0
    for i in range(windows):
        s = np.sign(_corr(a[i * q:(i + 1) * q], b[i * q:(i + 1) * q]))
        agree += int(s == full)
    return round(agree / windows, 4)


def nonlinearity(x: np.ndarray, y: np.ndarray, lag: int) -> dict[str, Any]:
    """A cheap monotone-versus-linear check: rank correlation against Pearson, and the split
    of the linear correlation by the sign of X. `score` = max(0, |spearman| - |pearson|): a
    relationship the ranks see and the line does not."""
    a, b = _pairs(x, y, lag)
    if a.size < 30:
        return {"pearson": 0.0, "spearman": 0.0, "score": 0.0, "sign_asymmetry": 0.0}
    rp = _corr(a, b)
    rs = _corr(_rank(a), _rank(b))
    pos, neg = a > 0, a < 0
    c_pos = _corr(a[pos], b[pos]) if int(pos.sum()) >= 30 else 0.0
    c_neg = _corr(a[neg], b[neg]) if int(neg.sum()) >= 30 else 0.0
    return {"pearson": round(rp, 6), "spearman": round(rs, 6),
            "score": round(max(0.0, abs(rs) - abs(rp)), 6),
            "sign_asymmetry": round(c_pos - c_neg, 6)}


def measure_edge(x: np.ndarray, y: np.ndarray, *, src: str, dst: str, clock: str,
                 decay_cls: str, n_tests: int, max_lag: int = MAX_LAG,
                 lags: Iterable[int] | None = None,
                 regime: Sequence[Any] | np.ndarray | None = None, plausibility: float = 0.0,
                 seed: int = 0, alpha: float = ALPHA, min_n: int = MIN_N, n_boot: int = N_BOOT,
                 n_perm: int = N_PERM, evidence: dict[str, Any] | None = None) -> Edge:
    """Estimate one edge on aligned series and return it ADMITTED or RECORDED_NOT_ADMITTED.

    `n_tests` is the graph's multiplicity ledger AFTER charging this pair's lags -- the caller
    charges first, then measures, so the bar this edge faces already includes itself. The
    admission rule is stated once in the module docstring and applied here; every refusal
    names its reason on the edge.
    """
    ev: dict[str, Any] = dict(evidence or {})
    ev["measured_via"] = ev.get("measured_via") or [src, dst]
    now = datetime.now(tz=UTC).isoformat()
    xc = lagged_xcorr(x, y, max_lag=max_lag, lags=lags, n_boot=n_boot, seed=seed, alpha=alpha,
                      n_tests=n_tests)
    best = xc["best"]
    ev["xcorr"] = xc
    if not best or int(best.get("n") or 0) < min_n:
        n = int(best.get("n") or 0) if best else 0
        return Edge(src=src, dst=dst, lag=int(best.get("lag") or 1) if best else 1,
                    plausibility=plausibility, decay_cls=decay_cls, n=n, evidence=ev,
                    clock=clock, status=RECORDED_NOT_ADMITTED, measured_at=now,
                    reason=f"n={n} aligned pairs below MIN_N={min_n}")
    lag = int(best["lag"])
    r = float(best["corr"])
    lo, hi = (float(v) for v in best["ci_deflated"])
    inc = incremental_information(x, y, lag, n_perm=n_perm, seed=seed)
    sd = state_dependence(x, y, lag, regime)
    stab = stability(x, y, lag)
    nl = nonlinearity(x, y, lag)
    ev["incremental"] = inc
    ev["state"] = sd
    ev["nonlinearity"] = nl
    reasons: list[str] = []
    if lo <= 0.0 <= hi:
        reasons.append(f"deflated CI [{lo:+.4f}, {hi:+.4f}] over {n_tests} charged cells "
                       f"(z={xc['z_deflated']}) includes zero")
    if float(inc["delta_r2"]) <= 0.0:
        reasons.append("adds nothing to Y's own lags (deltaR2 <= 0)")
    elif float(inc["p_value"]) > alpha:
        reasons.append(f"incremental information not distinguishable from a circular-shift "
                       f"null (p={inc['p_value']})")
    edge = Edge(src=src, dst=dst, lag=lag, direction="same" if r > 0 else "opposite",
                strength=round(r, 6), stability=stab, state_dependence=float(sd["spread"]),
                nonlinearity=float(nl["score"]), plausibility=plausibility,
                incremental_info=float(inc["delta_r2"]), decay_cls=decay_cls,
                n=int(best["n"]), evidence=ev, clock=clock,
                status=ADMITTED if not reasons else RECORDED_NOT_ADMITTED,
                reason="; ".join(reasons), measured_at=now)
    return edge


# =================================================================================== priors
#: World nodes: id -> (kind, country, unit, source). Ids are namespaced by kind so no world node
#: can collide with a Fusion symbol.
PRIOR_NODES: dict[str, tuple[str, str, str, str]] = {
    "country:US": ("country", "US", "", "statistical agencies"),
    "country:CN": ("country", "CN", "", "NBS / customs"),
    "country:AU": ("country", "AU", "", "ABS"),
    "country:EU": ("country", "EU", "", "Eurostat"),
    "country:JP": ("country", "JP", "", "MoF / BoJ"),
    "cb:FED": ("central_bank", "US", "bp", "FOMC statements"),
    "cb:ECB": ("central_bank", "EU", "bp", "ECB decisions"),
    "cb:BOJ": ("central_bank", "JP", "bp", "BoJ decisions / MoF intervention"),
    "cb:BOE": ("central_bank", "GB", "bp", "MPC decisions"),
    "cb:RBA": ("central_bank", "AU", "bp", "RBA decisions"),
    "cb:BOC": ("central_bank", "CA", "bp", "BoC decisions"),
    "cb:PBOC": ("central_bank", "CN", "fixing", "CFETS fixing"),
    "yield:US2Y": ("yield_curve", "US", "pct", "UST 2Y"),
    "yield:US10Y": ("yield_curve", "US", "pct", "UST 10Y"),
    "currency:USD": ("currency", "US", "index", "dollar"),
    "currency:EUR": ("currency", "EU", "USD", "euro"),
    "currency:JPY": ("currency", "JP", "USD", "yen"),
    "currency:GBP": ("currency", "GB", "USD", "sterling"),
    "currency:AUD": ("currency", "AU", "USD", "aussie"),
    "currency:NZD": ("currency", "NZ", "USD", "kiwi"),
    "currency:CAD": ("currency", "CA", "USD", "loonie"),
    "currency:CHF": ("currency", "CH", "USD", "franc"),
    "currency:CNH": ("currency", "CN", "USD", "offshore yuan"),
    "currency:NOK": ("currency", "NO", "USD", "krone"),
    "commodity:gold": ("commodity", "", "USD/oz", "LBMA / COMEX"),
    "commodity:silver": ("commodity", "", "USD/oz", "LBMA / COMEX"),
    "commodity:copper": ("commodity", "", "USD/t", "LME / COMEX"),
    "commodity:iron_ore": ("commodity", "", "USD/t", "SGX / DCE"),
    "commodity:brent": ("commodity", "", "USD/bbl", "ICE"),
    "commodity:wti": ("commodity", "", "USD/bbl", "NYMEX"),
    "index:SPX": ("equity_index", "US", "points", "S&P 500"),
    "index:NDX": ("equity_index", "US", "points", "Nasdaq 100"),
    "index:ASX200": ("equity_index", "AU", "points", "S&P/ASX 200"),
    "index:HSI": ("equity_index", "HK", "points", "Hang Seng"),
    "index:NKY": ("equity_index", "JP", "points", "Nikkei 225"),
    "vol:VIX": ("volatility", "US", "pct", "CBOE"),
    "physical:CN_gold_demand": ("physical_market", "CN", "t", "SGE withdrawals / customs"),
    "physical:SGE_premium": ("physical_market", "CN", "USD/oz", "SGE vs London"),
    "futures:COMEX_gold_oi": ("futures_market", "US", "contracts", "COMEX"),
    "futures:LME_copper_stocks": ("futures_market", "GB", "t", "LME warehouse stocks"),
    "flow:GLD_ETF": ("flow", "US", "t", "GLD holdings"),
    "positioning:COT_gold": ("positioning", "US", "contracts", "CFTC gold"),
    "positioning:COT_silver": ("positioning", "US", "contracts", "CFTC silver"),
    "positioning:COT_eur": ("positioning", "US", "contracts", "CFTC eur"),
    "positioning:COT_jpy": ("positioning", "US", "contracts", "CFTC jpy"),
    "positioning:COT_gbp": ("positioning", "US", "contracts", "CFTC gbp"),
    "positioning:COT_aud": ("positioning", "US", "contracts", "CFTC aud"),
    "positioning:COT_nzd": ("positioning", "US", "contracts", "CFTC nzd"),
    "positioning:COT_cad": ("positioning", "US", "contracts", "CFTC cad"),
    "positioning:COT_chf": ("positioning", "US", "contracts", "CFTC chf"),
    "positioning:COT_dxy": ("positioning", "US", "contracts", "CFTC dxy"),
    "positioning:COT_sp500": ("positioning", "US", "contracts", "CFTC sp500"),
    "positioning:COT_nasdaq100": ("positioning", "US", "contracts", "CFTC nasdaq100"),
    "event:US_CPI": ("event", "US", "surprise", "BLS"),
    "event:US_NFP": ("event", "US", "surprise", "BLS"),
    "event:AU_trade_balance": ("event", "AU", "surprise", "ABS"),
    "event:CN_PMI": ("event", "CN", "surprise", "NBS / Caixin"),
}

#: World node -> the Fusion instrument that prices it, and whether the instrument moves the
#: same way ("same") or is the inverse quote ("opposite": USDJPY rises when the yen falls; a
#: bond PRICE rises when its yield falls). Attached only when universe.json quotes the symbol.
PROXIES: tuple[tuple[str, str, str], ...] = (
    ("commodity:gold", "XAUUSD", "same"), ("commodity:silver", "XAGUSD", "same"),
    ("commodity:copper", "XCUUSD", "same"), ("commodity:brent", "XBRUSD", "same"),
    ("commodity:wti", "XTIUSD", "same"),
    ("currency:USD", "USDX", "same"), ("currency:EUR", "EURUSD", "same"),
    ("currency:GBP", "GBPUSD", "same"), ("currency:AUD", "AUDUSD", "same"),
    ("currency:NZD", "NZDUSD", "same"), ("currency:JPY", "USDJPY", "opposite"),
    ("currency:CAD", "USDCAD", "opposite"), ("currency:CHF", "USDCHF", "opposite"),
    ("currency:CNH", "USDCNH", "opposite"), ("currency:NOK", "USDNOK", "opposite"),
    ("yield:US10Y", "UST10Y", "opposite"),
    ("index:SPX", "US500", "same"), ("index:NDX", "NAS100", "same"),
    ("index:ASX200", "AUS200", "same"), ("index:HSI", "HK50", "same"),
    ("index:NKY", "JPN225", "same"),
)

#: Structural memberships: a country publishes its events and hosts its central bank.
MEMBERSHIPS: tuple[tuple[str, str], ...] = (
    ("country:US", "event:US_CPI"), ("country:US", "event:US_NFP"), ("country:US", "cb:FED"),
    ("country:CN", "event:CN_PMI"), ("country:CN", "cb:PBOC"),
    ("country:CN", "physical:CN_gold_demand"),
    ("country:AU", "event:AU_trade_balance"), ("country:AU", "cb:RBA"),
    ("country:EU", "cb:ECB"), ("country:JP", "cb:BOJ"),
)

#: (src, dst, lag, clock, decay_cls of X, direction, plausibility, why). The prior table. Lag
#: is in bars of `clock`; the decay class says how fast X's information ages.
PRIOR_EDGES: tuple[tuple[str, str, int, str, str, str, float, str], ...] = (
    # ---- the principal's three example chains
    ("physical:CN_gold_demand", "physical:SGE_premium", 1, "D1", "etf_flow", "same", 0.8,
     "Chinese physical buying shows up first as the Shanghai premium over London"),
    ("physical:SGE_premium", "commodity:gold", 1, "D1", "etf_flow", "same", 0.6,
     "a persistent SGE premium pulls metal east and bids the London/COMEX price"),
    ("event:AU_trade_balance", "commodity:iron_ore", 1, "D1", "macro_monthly", "same", 0.5,
     "Australia's export receipts are the demand side of the bulk-commodity market"),
    ("event:CN_PMI", "commodity:copper", 1, "D1", "macro_monthly", "same", 0.6,
     "China is half of world copper demand; the PMI is its earliest read"),
    ("commodity:iron_ore", "currency:AUD", 1, "D1", "bar_D1", "same", 0.6,
     "iron ore is Australia's largest export and its terms of trade"),
    ("commodity:copper", "currency:AUD", 1, "H1", "bar_H1", "same", 0.7,
     "AUD is the liquid proxy for industrial-metal demand"),
    ("currency:AUD", "AUDJPY", 1, "H1", "bar_H1", "same", 0.5,
     "AUDJPY is AUDUSD x USDJPY; the cross lags its aussie leg by at most a bar"),
    ("event:US_CPI", "yield:US2Y", 1, "H1", "macro_monthly", "same", 0.9,
     "the 2Y is the market's Fed path and CPI reprices it within the hour"),
    ("yield:US2Y", "currency:USD", 1, "H1", "yield", "same", 0.8,
     "rate differentials drive the dollar; the 2Y is where the differential moves first"),
    ("currency:USD", "commodity:gold", 1, "H1", "bar_H1", "opposite", 0.8,
     "gold is a zero-coupon dollar asset: a stronger dollar is a lower gold price"),
    # ---- rates and central banks
    ("cb:FED", "yield:US2Y", 1, "H1", "cb_decision", "same", 0.9,
     "the front end IS the policy path"),
    ("event:US_NFP", "yield:US2Y", 1, "H1", "macro_monthly", "same", 0.8,
     "payrolls are the other print the Fed path is set by"),
    ("yield:US2Y", "yield:US10Y", 1, "H1", "yield", "same", 0.7,
     "the long end follows the front end up to the term premium"),
    ("yield:US10Y", "commodity:gold", 1, "H1", "yield", "opposite", 0.7,
     "the real 10Y is the yield gold competes with"),
    ("yield:US10Y", "index:NDX", 1, "H1", "yield", "opposite", 0.6,
     "long-duration equities are priced off the long end"),
    ("cb:ECB", "currency:EUR", 1, "H1", "cb_decision", "same", 0.9, "policy: ECB -> EUR"),
    ("cb:BOJ", "currency:JPY", 1, "H1", "cb_decision", "same", 0.9,
     "policy and MoF intervention -> JPY"),
    ("cb:BOE", "currency:GBP", 1, "H1", "cb_decision", "same", 0.9, "policy: BoE -> GBP"),
    ("cb:RBA", "currency:AUD", 1, "H1", "cb_decision", "same", 0.9, "policy: RBA -> AUD"),
    ("cb:BOC", "currency:CAD", 1, "H1", "cb_decision", "same", 0.9, "policy: BoC -> CAD"),
    ("cb:PBOC", "currency:CNH", 1, "H1", "cb_decision", "same", 0.9,
     "the fixing is the band the offshore yuan trades around"),
    # ---- energy
    ("commodity:wti", "commodity:brent", 1, "H1", "bar_H1", "same", 0.8,
     "one crude complex, two benchmarks"),
    ("commodity:brent", "currency:CAD", 1, "H1", "bar_H1", "same", 0.7,
     "Canada is a net crude exporter and CAD tracks the crude it sells"),
    ("commodity:brent", "currency:NOK", 1, "H1", "bar_H1", "same", 0.7,
     "Norway's currency is a claim on North Sea crude revenue"),
    # ---- metals complex
    ("commodity:gold", "commodity:silver", 1, "H1", "bar_H1", "same", 0.8,
     "silver is high-beta gold"),
    ("commodity:copper", "commodity:silver", 1, "H1", "bar_H1", "same", 0.4,
     "half of silver demand is industrial"),
    ("futures:LME_copper_stocks", "commodity:copper", 1, "D1", "etf_flow", "opposite", 0.5,
     "inventory draws tighten the physical market"),
    ("futures:COMEX_gold_oi", "commodity:gold", 1, "D1", "etf_flow", "same", 0.4,
     "open interest rising with price is new money, not short covering"),
    ("flow:GLD_ETF", "commodity:gold", 1, "D1", "etf_flow", "same", 0.6,
     "ETF creations are physical buying by the investor class that sets the marginal price"),
    # ---- risk and volatility
    ("index:SPX", "vol:VIX", 1, "H1", "bar_H1", "opposite", 0.8,
     "implied vol is bid when equities are sold"),
    ("vol:VIX", "currency:JPY", 1, "H1", "bar_H1", "same", 0.7,
     "risk-off unwinds the yen carry: the yen is bought when vol is bid"),
    ("vol:VIX", "currency:CHF", 1, "H1", "bar_H1", "same", 0.6, "the other haven"),
    ("index:SPX", "currency:AUD", 1, "H1", "bar_H1", "same", 0.6,
     "the aussie is the liquid risk currency"),
    ("index:SPX", "index:NKY", 1, "H1", "bar_H1", "same", 0.7,
     "Tokyo opens on New York's close"),
    ("index:SPX", "index:ASX200", 1, "H1", "bar_H1", "same", 0.7,
     "Sydney opens on New York's close"),
    ("index:HSI", "currency:AUD", 1, "H1", "bar_H1", "same", 0.5,
     "Hong Kong is the tradeable China-risk proxy and AUD is its currency"),
    # ---- positioning (weekly; crowded speculators precede reversal, so 'opposite')
    ("positioning:COT_gold", "commodity:gold", 1, "W1", "cot", "opposite", 0.5,
     "crowded speculative longs precede mean reversion"),
    ("positioning:COT_silver", "commodity:silver", 1, "W1", "cot", "opposite", 0.5,
     "crowded speculative longs precede mean reversion"),
    ("positioning:COT_eur", "currency:EUR", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_jpy", "currency:JPY", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_gbp", "currency:GBP", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_aud", "currency:AUD", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_nzd", "currency:NZD", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_cad", "currency:CAD", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_chf", "currency:CHF", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_dxy", "currency:USD", 1, "W1", "cot", "opposite", 0.5, "as gold"),
    ("positioning:COT_sp500", "index:SPX", 1, "W1", "cot", "opposite", 0.4, "as gold"),
    ("positioning:COT_nasdaq100", "index:NDX", 1, "W1", "cot", "opposite", 0.4, "as gold"),
)

#: Named chains the report tracks as seeded / measured / admitted.
PRIOR_CHAINS: dict[str, tuple[str, ...]] = {
    "china_physical_gold": ("physical:CN_gold_demand", "physical:SGE_premium",
                            "commodity:gold", "XAUUSD"),
    "australia_commodities_to_audjpy": ("event:AU_trade_balance", "commodity:iron_ore",
                                        "currency:AUD", "AUDJPY"),
    "china_pmi_copper_aud": ("event:CN_PMI", "commodity:copper", "currency:AUD", "AUDUSD"),
    "us_cpi_2y_usd_gold": ("event:US_CPI", "yield:US2Y", "currency:USD", "commodity:gold",
                           "XAUUSD"),
    "fed_2y_10y_gold": ("cb:FED", "yield:US2Y", "yield:US10Y", "commodity:gold", "XAUUSD"),
    "oil_to_cad": ("commodity:brent", "currency:CAD", "USDCAD"),
    "oil_to_nok": ("commodity:brent", "currency:NOK", "USDNOK"),
    "metals_complex": ("commodity:gold", "commodity:silver", "XAGUSD"),
    "risk_off_yen": ("index:SPX", "vol:VIX", "currency:JPY", "USDJPY"),
    "ny_close_to_tokyo": ("index:SPX", "index:NKY", "JPN225"),
    "cot_gold_reversal": ("positioning:COT_gold", "commodity:gold", "XAUUSD"),
    "gld_flow_gold": ("flow:GLD_ETF", "commodity:gold", "XAUUSD"),
    "ecb_to_eur": ("cb:ECB", "currency:EUR", "EURUSD"),
    "boj_to_yen": ("cb:BOJ", "currency:JPY", "USDJPY"),
}


def seed_priors(graph: CausalGraph, instruments: dict[str, Node] | None = None) -> CausalGraph:
    """Seed the prior table into `graph`, idempotently. Instrument nodes come from
    `instruments` (universe.json via `instrument_nodes`) and a proxy whose symbol the universe
    does not quote is skipped with a note rather than invented."""
    inst = instruments if instruments is not None else {}
    if graph.instrument_ids is None and inst:
        graph.instrument_ids = frozenset(inst)
    for nid, (kind, country, unit, source) in PRIOR_NODES.items():
        graph.add_node(Node(nid, kind, country, unit, source))
    for src, dst in MEMBERSHIPS:
        graph.add_edge(Edge(src=src, dst=dst, lag=0, direction="same", plausibility=1.0,
                            status=STRUCTURAL, reason="membership: the country publishes it"))
    for world, sym, direction in PROXIES:
        node = inst.get(sym)
        if node is None:
            note = f"proxy {world}->{sym} skipped: {sym} is not in universe.json"
            if note not in graph.seed_notes:
                graph.seed_notes.append(note)
            continue
        graph.add_node(node)
        graph.add_edge(Edge(src=world, dst=sym, lag=0, direction=direction, plausibility=1.0,
                            decay_cls="bar_H1", clock="H1", status=STRUCTURAL,
                            reason="proxy: the instrument that prices this node"))
    for src, dst, lag, clock, cls, direction, plaus, why in PRIOR_EDGES:
        if dst not in graph.nodes:
            node = inst.get(dst)
            if node is None:
                note = f"prior {src}->{dst} skipped: {dst} is not in universe.json"
                if note not in graph.seed_notes:
                    graph.seed_notes.append(note)
                continue
            graph.add_node(node)
        graph.add_edge(Edge(src=src, dst=dst, lag=lag, direction=direction, plausibility=plaus,
                            decay_cls=cls, clock=clock,
                            evidence={"prior_why": why, "prior_direction": direction,
                                      "prior_source": "causal_graph.PRIOR_EDGES"},
                            status=PLAUSIBLE_UNMEASURED))
    return graph
