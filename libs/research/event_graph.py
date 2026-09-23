"""THE CROSS-MARKET EVENT / KNOWLEDGE GRAPH (LAWS 5m: "the Cross-Market Event Graph with a
Causal/Mechanism Adjudicator"). Pure and typed: no file, no registry, no bars in here.

ONE DYNAMIC GRAPH over events, entities (actors), industries, commodities, countries, currencies,
rates, shipping / supply-chain flows, macro series and MT5 assets, whose edges carry a MECHANISM,
a claimed SIGN, a HORIZON and one of three EVIDENCE STATES:

    HYPOTHESIS          declared by an ontology, a country pack or a story; nothing measured it
    MEASURED_ELSEWHERE  a public study, another desk's number or a pack's cited measurement
    DESK_MEASURED       this desk measured it on its own bars/series (event_graph_lab)

A propagation path is event -> entity -> industry -> commodity -> country -> currency -> asset
(port closure -> copper shipment delay -> inventory expectations -> copper curve -> Chile terms
of trade -> CLP proxies); the ladder is a SCORE on a path, never a constraint, because the
interesting chains skip rungs (a sanction reaches an exotic pair in one hop).

IT REDECLARES NOTHING. The event kinds, their transmission edges, the country and commodity
tables come from `libs.research.event_ontology`; the transmission seeds come from the country
packs through `transmission_engine.seed_edges` (the lab hands the rows in); measured causal edges
come from the world causal graph. This module only knows how to hold them together, walk them,
read centrality / contagion / community change off them, and turn EVERY EDGE into a testable
hypothesis with a falsifier and competing explanations -- the candidate contract of LAWS 5k.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from libs.research import event_ontology as eo

KINDS: tuple[str, ...] = ("event", "entity", "shipping", "industry", "commodity", "country",
                          "currency", "rate", "series", "asset")
#: The canonical propagation ladder, used to SCORE a path's shape (share of hops that descend
#: the ladder). It is not a constraint: see the module docstring.
LADDER: dict[str, int] = {k: i for i, k in enumerate(KINDS)}

HYPOTHESIS = "HYPOTHESIS"
MEASURED_ELSEWHERE = "MEASURED_ELSEWHERE"
DESK_MEASURED = "DESK_MEASURED"
EVIDENCE_STATES: tuple[str, ...] = (HYPOTHESIS, MEASURED_ELSEWHERE, DESK_MEASURED)
EVIDENCE_RANK: dict[str, int] = {s: i for i, s in enumerate(EVIDENCE_STATES)}
#: Prior weight of an edge with no measured strength, by evidence state. A DESK_MEASURED edge
#: always carries its own |strength|; these are what the walkers use before that exists.
EVIDENCE_WEIGHT: dict[str, float] = {HYPOTHESIS: 0.25, MEASURED_ELSEWHERE: 0.5,
                                     DESK_MEASURED: 1.0}
UNMEASURED = "UNMEASURED"
SIGNS: tuple[str, ...] = ("+", "-", "?")
HORIZONS: tuple[str, ...] = (*eo.HORIZONS, "?")

MAX_PATHS = 200
MAX_HOPS = 6
#: Betweenness is exact below this many nodes and sampled (first K sources by id) above it, so a
#: graph that grows with every country pack never turns a reading into a minute of CPU.
BETWEENNESS_EXACT_NODES = 1_500
BETWEENNESS_SAMPLE = 300

RULE = ("one graph, three evidence states, a hypothesis at every edge; nothing declared here that "
        "the ontology, the packs or the causal graph already declare")


def _slug(text: str) -> str:
    return "_".join(str(text or "").strip().lower().replace("/", " ").replace(":", " ").split())


def node_id(kind: str, name: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"unknown node kind {kind!r}; one of {KINDS}")
    return f"{kind}:{_slug(name)}"


def edge_id(src: str, dst: str, mechanism: str) -> str:
    return hashlib.sha1(f"{src}|{dst}|{_slug(mechanism)}".encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    label: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "label": self.label, "attrs": dict(self.attrs)}


@dataclass
class Edge:
    """One directed claim: `src` moves `dst` through `mechanism`."""

    id: str
    src: str
    dst: str
    mechanism: str
    sign: str = "?"
    horizon: str = "?"
    evidence: str = HYPOTHESIS
    strength: float | None = None
    lag: float | None = None
    origin: str = ""
    measured_at: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def weight(self) -> float:
        """|strength| when measured, the evidence prior otherwise -- never zero, never above 1."""
        if self.strength is not None and self.evidence == DESK_MEASURED:
            return max(0.01, min(1.0, abs(float(self.strength))))
        return EVIDENCE_WEIGHT.get(self.evidence, EVIDENCE_WEIGHT[HYPOTHESIS])

    def to_row(self) -> dict[str, Any]:
        return {"id": self.id, "src": self.src, "dst": self.dst, "mechanism": self.mechanism,
                "sign": self.sign, "horizon": self.horizon, "evidence": self.evidence,
                "strength": self.strength, "lag": self.lag, "origin": self.origin,
                "measured_at": self.measured_at, "detail": dict(self.detail)}


Path = list[Edge]


class EventGraph:
    """The graph. Idempotent adds; evidence only ever RISES on a re-declared edge."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self._out: dict[str, list[str]] = defaultdict(list)
        self._in: dict[str, list[str]] = defaultdict(list)

    # ------------------------------------------------------------------ building
    def add_node(self, kind: str, name: str, label: str = "", **attrs: Any) -> Node:
        nid = node_id(kind, name)
        have = self.nodes.get(nid)
        if have is not None:
            merged = dict(have.attrs)
            merged.update({k: v for k, v in attrs.items() if v is not None})
            node = Node(nid, kind, have.label or label or str(name), merged)
        else:
            node = Node(nid, kind, label or str(name),
                        {k: v for k, v in attrs.items() if v is not None})
        self.nodes[nid] = node
        return node

    def add_edge(self, src: str, dst: str, mechanism: str, *, sign: str = "?",
                 horizon: str = "?", evidence: str = HYPOTHESIS, strength: float | None = None,
                 lag: float | None = None, origin: str = "",
                 detail: Mapping[str, Any] | None = None) -> Edge:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError(f"edge {src} -> {dst}: both nodes must exist before the edge")
        if src == dst:
            raise ValueError(f"self-edge refused on {src}")
        if evidence not in EVIDENCE_STATES:
            raise ValueError(f"evidence {evidence!r} not one of {EVIDENCE_STATES}")
        if sign not in SIGNS:
            raise ValueError(f"sign {sign!r} not one of {SIGNS}")
        if horizon not in HORIZONS:
            raise ValueError(f"horizon {horizon!r} not one of {HORIZONS}")
        eid = edge_id(src, dst, mechanism)
        have = self.edges.get(eid)
        if have is None:
            edge = Edge(eid, src, dst, mechanism, sign, horizon, evidence, strength, lag, origin,
                        "", dict(detail or {}))
            self.edges[eid] = edge
            self._out[src].append(eid)
            self._in[dst].append(eid)
            return edge
        # A re-declaration never DOWNGRADES evidence and never erases a desk measurement.
        if EVIDENCE_RANK[evidence] > EVIDENCE_RANK[have.evidence]:
            have.evidence, have.strength, have.origin = evidence, strength, origin or have.origin
            if sign != "?":
                have.sign = sign
        elif EVIDENCE_RANK[evidence] == EVIDENCE_RANK[have.evidence]:
            if have.strength is None and strength is not None:
                have.strength = strength
            if have.sign == "?" and sign != "?":
                have.sign = sign
        if have.horizon == "?" and horizon != "?":
            have.horizon = horizon
        if have.lag is None and lag is not None:
            have.lag = lag
        if detail:
            have.detail.update(dict(detail))
        return have

    def set_measurement(self, eid: str, *, strength: float, sign: str, measured_at: str = "",
                        evidence: str = DESK_MEASURED, detail: Mapping[str, Any] | None = None
                        ) -> Edge:
        """What the lab writes after measuring an edge on the desk's own series."""
        edge = self.edges[eid]
        if evidence not in EVIDENCE_STATES:
            raise ValueError(f"evidence {evidence!r} not one of {EVIDENCE_STATES}")
        edge.strength = float(strength)
        edge.sign = sign if sign in SIGNS else "?"
        edge.measured_at = measured_at or _now()
        if EVIDENCE_RANK[evidence] >= EVIDENCE_RANK[edge.evidence]:
            edge.evidence = evidence
        if detail:
            edge.detail.update(dict(detail))
        return edge

    # ------------------------------------------------------------------ walking
    def out_edges(self, nid: str) -> list[Edge]:
        return [self.edges[e] for e in self._out.get(nid, ())]

    def in_edges(self, nid: str) -> list[Edge]:
        return [self.edges[e] for e in self._in.get(nid, ())]

    def nodes_of_kind(self, kind: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind == kind]

    def propagation_paths(self, start: str, *, terminal_kind: str = "asset",
                          max_hops: int = MAX_HOPS, limit: int = MAX_PATHS) -> list[Path]:
        """Every simple path from `start` that ends on a `terminal_kind` node, shortest first,
        strongest first within a length. Bounded by `limit` so a hub never explodes the walk."""
        if start not in self.nodes:
            return []
        out: list[Path] = []
        stack: list[tuple[str, Path, frozenset[str]]] = [(start, [], frozenset([start]))]
        while stack and len(out) < limit * 4:
            node, path, seen = stack.pop()
            if path and self.nodes[node].kind == terminal_kind:
                out.append(path)
            if len(path) >= max_hops:
                continue
            for e in sorted(self.out_edges(node), key=lambda x: -x.weight):
                if e.dst in seen:
                    continue
                stack.append((e.dst, [*path, e], seen | {e.dst}))
        out.sort(key=lambda p: (len(p), -path_strength(p)))
        return out[:limit]

    def find_chain(self, start: str, end: str, *, max_hops: int = MAX_HOPS) -> Path | None:
        """The shortest directed chain from `start` to `end`, or None."""
        if start not in self.nodes or end not in self.nodes:
            return None
        prev: dict[str, Edge] = {}
        seen = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])
        while queue:
            node, depth = queue.popleft()
            if node == end:
                path: Path = []
                cur = end
                while cur != start:
                    e = prev[cur]
                    path.append(e)
                    cur = e.src
                path.reverse()
                return path
            if depth >= max_hops:
                continue
            for e in self.out_edges(node):
                if e.dst not in seen:
                    seen.add(e.dst)
                    prev[e.dst] = e
                    queue.append((e.dst, depth + 1))
        return None

    # ------------------------------------------------------------------ readings
    def centrality(self) -> dict[str, dict[str, float]]:
        """Weighted degree and (exact or sampled) betweenness per node."""
        ids = sorted(self.nodes)
        deg: dict[str, float] = dict.fromkeys(ids, 0.0)
        for e in self.edges.values():
            deg[e.src] += e.weight
            deg[e.dst] += e.weight
        between: dict[str, float] = dict.fromkeys(ids, 0.0)
        sources = ids if len(ids) <= BETWEENNESS_EXACT_NODES else ids[:BETWEENNESS_SAMPLE]
        for s in sources:                                        # Brandes, unweighted hops
            order: list[str] = []
            preds: dict[str, list[str]] = defaultdict(list)
            sigma: dict[str, float] = defaultdict(float)
            dist: dict[str, int] = {s: 0}
            sigma[s] = 1.0
            queue: deque[str] = deque([s])
            while queue:
                v = queue.popleft()
                order.append(v)
                for e in self.out_edges(v):
                    w = e.dst
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)
            delta: dict[str, float] = defaultdict(float)
            for w in reversed(order):
                for v in preds[w]:
                    if sigma[w] > 0:
                        delta[v] += sigma[v] / sigma[w] * (1.0 + delta[w])
                if w != s:
                    between[w] += delta[w]
        top = max(between.values()) if between else 0.0
        scale = 1.0 / top if top > 0 else 0.0
        return {n: {"degree": round(deg[n], 4), "betweenness": round(between[n] * scale, 4)}
                for n in ids}

    def contagion(self, seeds: Mapping[str, float], *, decay: float = 0.6,
                  hops: int = 6) -> dict[str, float]:
        """How far a shock at `seeds` reaches: value x edge weight x decay per hop, the MAX over
        routes kept per node (a node reached twice is reached, not doubly reached).

        SIX HOPS BY DEFAULT, because the textbook chain this graph exists to walk -- event ->
        shipping -> commodity -> country -> currency -> asset -- is five edges long, and a
        four-hop default stopped exactly one node short of the asset (measured 2026-09-22:
        `asset:usdclp` absent from the reach of a planted port closure)."""
        level: dict[str, float] = {n: float(v) for n, v in seeds.items() if n in self.nodes}
        frontier = dict(level)
        for _ in range(max(0, hops)):
            nxt: dict[str, float] = {}
            for nid, val in frontier.items():
                for e in self.out_edges(nid):
                    got = val * e.weight * decay
                    if got > level.get(e.dst, 0.0) + 1e-12:
                        level[e.dst] = got
                        nxt[e.dst] = got
            if not nxt:
                break
            frontier = nxt
        return {k: round(v, 6) for k, v in sorted(level.items(), key=lambda kv: -kv[1])}

    def communities(self, *, iterations: int = 20) -> dict[str, str]:
        """Deterministic label propagation over the undirected, weighted view."""
        ids = sorted(self.nodes)
        label = {n: n for n in ids}
        nbrs: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for e in self.edges.values():
            nbrs[e.src].append((e.dst, e.weight))
            nbrs[e.dst].append((e.src, e.weight))
        for _ in range(max(1, iterations)):
            changed = False
            for n in ids:
                if not nbrs[n]:
                    continue
                score: dict[str, float] = defaultdict(float)
                for m, w in nbrs[n]:
                    score[label[m]] += w
                best = min(score.items(), key=lambda kv: (-kv[1], kv[0]))[0]
                if best != label[n]:
                    label[n] = best
                    changed = True
            if not changed:
                break
        return label

    def community_change(self, previous: Mapping[str, str] | None,
                         current: Mapping[str, str] | None = None) -> dict[str, Any]:
        """Which nodes changed community since the previous reading. With no previous reading
        the answer is UNMEASURED, not zero change."""
        cur = dict(current if current is not None else self.communities())
        if not previous:
            return {"status": UNMEASURED, "moved": [], "share_moved": None,
                    "n_communities": len(set(cur.values())),
                    "why": "no previous community reading to compare against"}
        # Communities are named by a representative node, so compare PARTITIONS, not labels.
        def groups(lbl: Mapping[str, str]) -> dict[str, frozenset[str]]:
            g: dict[str, set[str]] = defaultdict(set)
            for n, c in lbl.items():
                g[c].add(n)
            return {c: frozenset(m) for c, m in g.items()}
        old_g, new_g = groups(previous), groups(cur)
        old_of = {n: old_g[c] for n, c in previous.items()}
        moved = sorted(n for n, c in cur.items()
                       if n in old_of and old_of[n] != new_g[c])
        common = [n for n in cur if n in previous]
        return {"status": "MEASURED", "moved": moved[:200],
                "n_moved": len(moved),
                "share_moved": (round(len(moved) / len(common), 4) if common else None),
                "n_communities": len(new_g), "n_communities_before": len(old_g),
                "new_nodes": len([n for n in cur if n not in previous])}

    def readings(self) -> dict[str, Any]:
        by_kind: dict[str, int] = defaultdict(int)
        for n in self.nodes.values():
            by_kind[n.kind] += 1
        by_ev: dict[str, int] = dict.fromkeys(EVIDENCE_STATES, 0)
        for e in self.edges.values():
            by_ev[e.evidence] += 1
        cent = self.centrality()
        top = sorted(cent.items(), key=lambda kv: (-kv[1]["betweenness"], -kv[1]["degree"]))
        return {"n_nodes": len(self.nodes), "n_edges": len(self.edges),
                "nodes_by_kind": dict(sorted(by_kind.items())), "edges_by_evidence": by_ev,
                "top_central": [{"node": n, **c} for n, c in top[:20]]}

    # ------------------------------------------------------------------ hypotheses
    def hypotheses(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        """One testable hypothesis PER EDGE, terminal asset edges first. Every row carries its
        falsifier and its competing explanations, which is the candidate contract (LAWS 5k)."""
        rows = [edge_hypothesis(e, self) for e in self.edges.values()]
        rows.sort(key=lambda r: (not r["testable"], -r["prior_weight"], r["edge_id"]))
        return rows if limit is None else rows[:limit]

    # ------------------------------------------------------------------ persistence
    def to_doc(self) -> dict[str, Any]:
        return {"at": _now(), "rule": RULE, "kinds": list(KINDS),
                "evidence_states": list(EVIDENCE_STATES),
                "nodes": [n.to_row() for n in sorted(self.nodes.values(), key=lambda n: n.id)],
                "edges": [e.to_row() for e in sorted(self.edges.values(), key=lambda e: e.id)]}

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any] | None) -> EventGraph:
        g = cls()
        if not doc:
            return g
        for row in doc.get("nodes") or []:
            if isinstance(row, Mapping) and row.get("kind") in KINDS:
                g.nodes[str(row["id"])] = Node(str(row["id"]), str(row["kind"]),
                                              str(row.get("label") or ""),
                                              dict(row.get("attrs") or {}))
        for row in doc.get("edges") or []:
            if not isinstance(row, Mapping):
                continue
            src, dst = str(row.get("src") or ""), str(row.get("dst") or "")
            if src not in g.nodes or dst not in g.nodes or src == dst:
                continue
            e = Edge(str(row.get("id") or edge_id(src, dst, str(row.get("mechanism") or ""))),
                     src, dst, str(row.get("mechanism") or ""),
                     str(row.get("sign") or "?"), str(row.get("horizon") or "?"),
                     str(row.get("evidence") or HYPOTHESIS),
                     _float_or_none(row.get("strength")), _float_or_none(row.get("lag")),
                     str(row.get("origin") or ""), str(row.get("measured_at") or ""),
                     dict(row.get("detail") or {}))
            if e.evidence not in EVIDENCE_STATES or e.sign not in SIGNS \
                    or e.horizon not in HORIZONS:
                continue
            g.edges[e.id] = e
            g._out[src].append(e.id)
            g._in[dst].append(e.id)
        return g


def _float_or_none(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and v == v else None


def path_strength(path: Sequence[Edge]) -> float:
    s = 1.0
    for e in path:
        s *= e.weight
    return s


def ladder_score(path: Sequence[Edge], graph: EventGraph) -> float:
    """Share of hops that descend the canonical ladder; 1.0 is the textbook chain."""
    if not path:
        return 0.0
    down = 0
    for e in path:
        if LADDER[graph.nodes[e.src].kind] <= LADDER[graph.nodes[e.dst].kind]:
            down += 1
    return round(down / len(path), 4)


def summarise_path(path: Sequence[Edge], graph: EventGraph) -> dict[str, Any]:
    nodes = [path[0].src, *(e.dst for e in path)] if path else []
    return {"signature": " -> ".join(nodes), "n_hops": len(path),
            "strength": round(path_strength(path), 6),
            "ladder_score": ladder_score(path, graph),
            "evidence": [e.evidence for e in path],
            "weakest": (min(path, key=lambda e: e.weight).id if path else None),
            "all_desk_measured": bool(path) and all(e.evidence == DESK_MEASURED for e in path)}


def edge_hypothesis(edge: Edge, graph: EventGraph) -> dict[str, Any]:
    """The claim an edge makes, written as a candidate: cause, effect, sign, horizon, the test
    that would kill it and the explanations it must beat. Direction-agnostic when the sign is
    unknown: the falsifier is then "no effect at all", never "the wrong sign"."""
    src, dst = graph.nodes[edge.src], graph.nodes[edge.dst]
    horizon = edge.horizon if edge.horizon != "?" else "days"
    sign_txt = {"+": "the same direction", "-": "the opposite direction",
                "?": "either direction"}[edge.sign]
    symbol = str(dst.attrs.get("symbol") or "") if dst.kind == "asset" else ""
    falsifier = (f"measured on the desk's own series, the effect of {src.label} on {dst.label} "
                 f"at horizon {horizon} has p >= 0.05 under a circular-block permutation null"
                 + (", or its sign opposes the claim" if edge.sign != "?" else "")
                 + "; or the effect is explained by a common factor (USD, global risk), by "
                 f"{dst.label}'s own persistence, or by reverse causation")
    competing = [
        f"a common factor moves both {src.label} and {dst.label}",
        f"reverse causation: {dst.label} leads {src.label}",
        f"{dst.label}'s own persistence explains the move ({src.label} adds nothing)",
        "the information is already priced by the time it is observable",
    ]
    return {
        "edge_id": edge.id, "cause": edge.src, "effect": edge.dst,
        "claim": (f"{src.label} moves {dst.label} in {sign_txt} over {horizon} through "
                  f"{edge.mechanism or 'an undeclared mechanism'}"),
        "mechanism": edge.mechanism, "sign": edge.sign, "horizon": horizon,
        "lag": edge.lag, "evidence": edge.evidence, "strength": edge.strength,
        "prior_weight": edge.weight, "origin": edge.origin,
        "falsifier": falsifier, "competing": competing,
        "testable": dst.kind == "asset" and bool(symbol),
        "symbol": symbol, "symbols": [symbol] if symbol else [],
        "source_selector": str(src.attrs.get("selector") or ""),
        "target_selector": str(dst.attrs.get("selector") or ""),
    }


# ======================================================================= ingestion (pure)
def _asset_node(graph: EventGraph, symbol: str, universe: Mapping[str, str] | None) -> Node:
    cls = (universe or {}).get(symbol.upper(), "")
    return graph.add_node("asset", symbol.upper(), symbol.upper(), symbol=symbol.upper(),
                          asset_class=cls or None, selector=f"sym:{symbol.upper()}")


def seed_from_ontology(graph: EventGraph, *, universe: Mapping[str, str] | None = None,
                       ontology: Mapping[str, Any] | None = None,
                       countries: Sequence[Any] | None = None,
                       commodities: Sequence[Any] | None = None) -> int:
    """The event ontology's kinds, edges, countries and commodities, as graph structure.

    `universe` is symbol -> asset_class from MetaTrader's registry. When it is given, an anchor
    the broker does not list is dropped (the graph never names a symbol Fusion does not trade);
    an edge whose anchors are all absent falls back to a `class:` selector node, which is the
    vocabulary the atlases already resolve.
    """
    onto = ontology if ontology is not None else eo.ONTOLOGY
    ctry = list(countries if countries is not None else eo.COUNTRIES)
    comm = list(commodities if commodities is not None else eo.COMMODITIES)
    known = {s.upper() for s in (universe or {})}
    n0 = len(graph.edges)

    def usable(symbol: str) -> bool:
        return not known or symbol.upper() in known

    for cid, spec in onto.items():
        ev = graph.add_node("event", cid, str(getattr(spec, "gloss", cid)),
                            scheduled=bool(getattr(spec, "scheduled", False)))
        for edge in getattr(spec, "edges", ()):
            anchors = [a for a in edge.anchors if usable(a)]
            targets = ([_asset_node(graph, a, universe) for a in anchors] or
                       [graph.add_node("asset", f"class:{edge.asset_class}",
                                       f"class:{edge.asset_class}",
                                       selector=f"class:{edge.asset_class}",
                                       asset_class=edge.asset_class)])
            for t in targets:
                graph.add_edge(ev.id, t.id, edge.note or f"{cid} transmits to {edge.asset_class}",
                               horizon=edge.horizon, evidence=HYPOTHESIS,
                               origin="event_ontology",
                               detail={"state_vars": list(edge.state_vars),
                                       "asset_class": edge.asset_class})
    for c in comm:
        cn = graph.add_node("commodity", c.commodity_id, c.commodity_id,
                            asset_class=c.asset_class)
        for ind in c.industries:
            i = graph.add_node("industry", ind, ind)
            graph.add_edge(cn.id, i.id, "input cost", sign="-", horizon="weeks",
                           origin="event_ontology")
        for a in c.anchors:
            if usable(a):
                graph.add_edge(cn.id, _asset_node(graph, a, universe).id, "price of",
                               sign="+", horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology",
                               detail={"why": "the anchor IS the commodity's traded price"})
    for k in ctry:
        kn = graph.add_node("country", k.code, k.code, currency=k.currency)
        cur = graph.add_node("currency", k.currency, k.currency)
        graph.add_edge(kn.id, cur.id, "terms of trade and rate expectations", horizon="days",
                       origin="event_ontology")
        for cid in k.exports:
            if node_id("commodity", cid) in graph.nodes:
                graph.add_edge(node_id("commodity", cid), kn.id, "export revenue", sign="+",
                               horizon="days", origin="event_ontology")
        for cid in k.imports:
            if node_id("commodity", cid) in graph.nodes:
                graph.add_edge(node_id("commodity", cid), kn.id, "import bill", sign="-",
                               horizon="days", origin="event_ontology")
        for idx in k.indices:
            if usable(idx):
                graph.add_edge(kn.id, _asset_node(graph, idx, universe).id, "equity index",
                               sign="+", horizon="hours", origin="event_ontology")
        for r in k.rates:
            rn = graph.add_node("rate", r, r)
            graph.add_edge(kn.id, rn.id, "sovereign curve", horizon="hours",
                           origin="event_ontology")
            if usable(r):
                graph.add_edge(rn.id, _asset_node(graph, r, universe).id, "quoted as", sign="+",
                               horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology")
        for ind in k.industries:
            graph.add_edge(graph.add_node("industry", ind, ind).id, kn.id, "domestic industry",
                           sign="+", horizon="weeks", origin="event_ontology")
        if universe:
            for sym in sorted(s for s, cls in universe.items()
                              if k.currency in s.upper() and str(cls).lower().startswith("forex")
                              )[:eo.MAX_ASSETS_PER_EDGE]:
                graph.add_edge(cur.id, _asset_node(graph, sym, universe).id, "currency leg",
                               sign="?", horizon="minutes", evidence=MEASURED_ELSEWHERE,
                               origin="event_ontology")
    return len(graph.edges) - n0


def _endpoint(graph: EventGraph, selector: str, universe: Mapping[str, str] | None,
              country: str = "") -> Node | None:
    """`sym:X` is an asset, `series:name` a macro series, anything else is not an endpoint."""
    kind, _, name = str(selector or "").partition(":")
    if kind == "sym" and name:
        return _asset_node(graph, name, universe)
    if kind == "series" and name:
        return graph.add_node("series", name, name, selector=f"series:{name}",
                              country=country or None)
    return None


def seed_from_transmission(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                           universe: Mapping[str, str] | None = None) -> int:
    """The transmission engine's seed rows (`transmission_engine.seed_edges`: the packs'
    `transmission_edges_seed`, the declared channels, the actor atlas), as
    country -> actor -> flow -> endpoint chains. A row the engine measured and ADMITTED lands
    DESK_MEASURED with its strength; a measured-but-not-admitted row stays a hypothesis and says
    so in its detail; a row carrying `evidence_state` from a pack keeps that state."""
    n0 = len(graph.edges)
    for row in rows:
        src = _endpoint(graph, str(row.get("source") or ""), universe,
                        str(row.get("from_country") or ""))
        dst = _endpoint(graph, str(row.get("target") or f"sym:{row.get('asset') or ''}"),
                        universe, str(row.get("to_country") or ""))
        if dst is None:
            continue
        raw_ev = row.get("evidence")
        ev: Mapping[str, Any] = raw_ev if isinstance(raw_ev, Mapping) else {}
        state = str(row.get("evidence_state") or HYPOTHESIS)
        if state not in EVIDENCE_STATES:
            state = HYPOTHESIS
        admitted = bool(ev.get("admitted"))
        if row.get("measured") and admitted:
            state = DESK_MEASURED
        strength = _float_or_none(row.get("strength")) if row.get("measured") else None
        sign = "?" if strength is None else ("+" if strength > 0 else "-")
        lag = _float_or_none(row.get("lag_days"))
        origin = str(row.get("origin") or "transmission_engine")
        detail = {"why": str(ev.get("why") or ""), "admitted": admitted,
                  "measured": bool(row.get("measured")), "edge_id": row.get("id"),
                  "constraint": str(row.get("constraint") or "")}
        chain: list[Node] = []
        fc = str(row.get("from_country") or "").strip()
        if fc and fc != "global":
            chain.append(graph.add_node("country", fc, fc))
        actor = str(row.get("actor") or "").strip()
        if actor:
            chain.append(graph.add_node("entity", actor[:80], actor[:80]))
        flow = str(row.get("flow") or "").strip()
        if flow:
            chain.append(graph.add_node("shipping", flow[:80], flow[:80]))
        if src is not None and (not chain or chain[-1].id != src.id):
            chain.append(src)
        prev: Node | None = None
        for node in chain:
            if prev is not None and prev.id != node.id:
                graph.add_edge(prev.id, node.id, "forces" if prev.kind != "shipping"
                               else "observable of", horizon="days", origin=origin,
                               detail={"constraint": detail["constraint"]})
            prev = node
        if prev is not None and prev.id != dst.id:
            graph.add_edge(prev.id, dst.id, flow or "transmission", sign=sign,
                           horizon="days", evidence=state, strength=strength, lag=lag,
                           origin=origin, detail=detail)
    return len(graph.edges) - n0


_CAUSAL_KIND: dict[str, str] = {"cb": "entity", "positioning": "series", "rate": "rate",
                                "series": "series", "macro": "series", "flow": "shipping"}


def seed_from_causal_edges(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                           universe: Mapping[str, str] | None = None) -> int:
    """The world causal graph's measured edges (src, dst, lag, direction, strength, status).
    ADMITTED is DESK_MEASURED; a recorded-but-not-admitted edge is kept as a HYPOTHESIS carrying
    its number, because "measured and found nothing" is negative knowledge worth a node."""
    n0 = len(graph.edges)
    for row in rows:
        s, d = str(row.get("src") or ""), str(row.get("dst") or "")
        if not s or not d or s == d:
            continue

        def node_for(name: str) -> Node:
            prefix, _, rest = name.partition(":")
            kind = _CAUSAL_KIND.get(prefix) if rest else None
            if kind:
                return graph.add_node(kind, rest, name, selector=name)
            return _asset_node(graph, name, universe)

        a, b = node_for(s), node_for(d)
        raw_ev = row.get("evidence")
        ev: Mapping[str, Any] = raw_ev if isinstance(raw_ev, Mapping) else {}
        status = str(row.get("status") or ev.get("status") or "").upper()
        admitted = status == "ADMITTED" or bool(ev.get("admitted"))
        strength = _float_or_none(row.get("strength"))
        direction = str(row.get("direction") or "")
        sign = "+" if direction == "same" else "-" if direction == "opposite" else "?"
        lag = _float_or_none(row.get("lag"))
        cls = str(row.get("decay_cls") or "")
        horizon = ("days" if "D1" in cls or "W1" in cls else "hours" if cls else "?")
        graph.add_edge(a.id, b.id, str(ev.get("prior_mechanism_class") or "measured lead"),
                       sign=sign if admitted else "?", horizon=horizon,
                       evidence=DESK_MEASURED if admitted else HYPOTHESIS,
                       strength=strength if admitted else None, lag=lag,
                       origin="world_causal_graph",
                       detail={"admitted": admitted, "recorded_strength": strength,
                               "n": row.get("n"), "stability": row.get("stability")})
    return len(graph.edges) - n0


def seed_from_events(graph: EventGraph, rows: Iterable[Mapping[str, Any]], *,
                     limit: int = 500) -> int:
    """Observed event instances (kind, entities, at) as nodes: instance -> its kind (so the
    kind's transmission edges apply) and instance -> every named country / commodity."""
    n0 = len(graph.edges)
    taken = 0
    for row in rows:
        kind = str(row.get("kind") or "").strip().lower()
        if not kind or kind not in eo.ONTOLOGY:
            continue
        at = str(row.get("at") or row.get("seen_at") or row.get("knowable_at") or "")
        ents = [str(e) for e in (row.get("entities") or ()) if str(e).strip()]
        key = hashlib.sha1(f"{kind}|{at}|{'|'.join(sorted(ents))}".encode()).hexdigest()[:10]
        inst = graph.add_node("event", f"{kind} {key}", f"{kind}@{at or 'undated'}",
                              kind_id=kind, at=at or None, instance=True)
        kind_node = graph.add_node("event", kind, kind)
        graph.add_edge(inst.id, kind_node.id, "instance of", horizon="minutes",
                       evidence=DESK_MEASURED, strength=1.0, origin="events")
        for e in ents:
            nid = node_id("country", e) if node_id("country", e) in graph.nodes else (
                node_id("commodity", e) if node_id("commodity", e) in graph.nodes else "")
            if nid:
                graph.add_edge(inst.id, nid, "names", horizon="minutes", evidence=DESK_MEASURED,
                               strength=1.0, origin="events")
        taken += 1
        if taken >= limit:
            break
    return len(graph.edges) - n0


def render(doc: Mapping[str, Any]) -> str:
    r = doc.get("readings") or {}
    return json.dumps({"n_nodes": r.get("n_nodes"), "n_edges": r.get("n_edges"),
                       "edges_by_evidence": r.get("edges_by_evidence")}, sort_keys=True)
