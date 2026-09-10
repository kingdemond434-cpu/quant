"""Every hypothesis with its parent and its fate, so the desk stops re-proposing what it buried.

TWO GRAPHS IN ONE LEDGER.

ANCESTRY. Each candidate records where it came from -- the miner row, the proposer sweep, the
deepening task, the certificate it descended from -- as a parent hash. That is what turns
"survivor count" into a lineage: a family that certifies only through one source, a source that
only ever produces one family, a descendant that outlives its parent. `research_queue.json`
already carries a `geneology_id` on 47,150 rows; this is that field made universal and joined
to outcomes.

NEGATIVE KNOWLEDGE. Every cell the gauntlet judged and failed is indexed by (symbol, family,
parameter region). Before a proposer or the compiler admits a candidate, it asks whether the desk
has already buried that region, and how many times. `funnel_census` knows cross_asset_residual
failed 348 times as a FAMILY; this knows that XAUUSD.cross_asset_residual with lookback in
[200, 300) and entry_z in [2, 2.5) failed six times and why. A candidate that lands in a buried
region is not rejected -- the compiler still decides -- but it is CHARGED: the ledger reports the
prior failures and the caller's deflation can count them.

APPEND-ONLY. A node is never edited; a new fate is a new row with the same node id. The current
state of a hypothesis is the last row about it, and its history is every row.

TYPED EDGES (2026-09-08). Until this date the only edge was the scalar `parent` hash, so a
question like "which hypotheses use the COT vintage on JPY crosses" could not be asked of the
ledger at all. Each row now carries `edges: list[dict]`, every edge `{"type", "to"}` plus any
detail, and the types are the ones the compiler's candidates already carry the facts for:

    applies_to_symbol   -> symbol:<SYM>                 from the candidate's `symbol`
    uses_data           -> data:<name>                  from params.input_source, factor_symbols,
                                                        input_symbol, peer_symbol, factors
    mutated_from        -> <parent certificate key>     from `parent` / evidence.parent, with the
                                                        named operator so mutation_yield can bill
    sourced_from        -> url:<source_url>             from the miner row's `source_url`

A row written before this field existed has no `edges` key and reads as []; nothing about the
30,313 existing rows changes. `Graph.query` filters the current state by edge type, target,
symbol, family and fate.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "desks" / "mt5" / "data" / "hypothesis_graph.jsonl"

#: How a parameter is coarsened into a region, per parameter name. Anything not listed is
#: bucketed by its exact value -- most params are discrete already.
REGION_WIDTH: dict[str, float] = {
    "lookback": 100, "beta_win": 100, "window": 250, "refit_days": 100,
    "entry_z": 0.5, "entry_p_leave": 0.1, "hold_bars": 4, "lead_bars": 2,
    "ttl_bars": 24, "stop_atr": 0.5, "rr": 0.5, "min_age": 5,
}

BORN, JUDGED, CERTIFIED, FAILED, RETIRED, BURIED = (
    "BORN", "JUDGED", "CERTIFIED", "FAILED", "RETIRED", "BURIED")

#: The typed edges a row may carry. Anything else on an edge is detail, never a new type.
USES_DATA, APPLIES_TO_SYMBOL, MUTATED_FROM, SOURCED_FROM = (
    "uses_data", "applies_to_symbol", "mutated_from", "sourced_from")
EDGE_TYPES: tuple[str, ...] = (USES_DATA, APPLIES_TO_SYMBOL, MUTATED_FROM, SOURCED_FROM)
#: Parameter names whose VALUE names a dataset or an input series the hypothesis reads.
DATA_PARAMS: tuple[str, ...] = ("input_source", "factor_symbols", "input_symbol",
                                "peer_symbol", "factors")


@dataclass(frozen=True)
class Node:
    symbol: str
    family: str
    params: dict[str, Any]
    source: str = ""
    parent: str = ""
    fate: str = BORN
    why: str = ""
    gates: dict[str, Any] = field(default_factory=dict)
    at: str = ""
    #: Typed edges (`edges_for`). Absent on rows written before 2026-09-08, which read as [].
    edges: list[dict[str, Any]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return node_id(self.symbol, self.family, self.params)

    @property
    def region(self) -> str:
        return region_key(self.symbol, self.family, self.params)

    def to_row(self) -> dict[str, Any]:
        row = {"id": self.id, "region": self.region, "symbol": self.symbol,
               "family": self.family, "params": self.params, "source": self.source,
               "parent": self.parent, "fate": self.fate, "why": self.why, "gates": self.gates,
               "at": self.at or datetime.now(tz=UTC).isoformat(),
               "edges": [dict(e) for e in self.edges]}
        profile = death_profile(self.gates, self.fate)
        if profile:
            row["death"] = profile
        return row


#: The numeric reading each gate leaves behind, and where it sits inside that gate's dict.
#: Tier-1 item A3: the burial record kept symbol/family/params/region/source/parent/fate/why and
#: the whole `gates` blob, so WHAT it died of was a prose string and HOW BADLY was buried inside
#: a nested dict nothing read. A generator asking "has this region been tried, and how close did
#: it come?" could get the first answer and never the second, so a cell that missed the deflated
#: Sharpe by a hair and one that failed every gate were the same row to the novelty gate.
#: The ten gates in the order external_gauntlet runs them, plus the two pre-gates and the
#: observations check. THE ORDER IS SEPARATE FROM THE READINGS because two gates refuse without
#: leaving a number -- `economic_prior` and `symbol_eligibility` are terminal Gate-1 rejections
#: -- and deriving the order from the readings table put them last, so a cell rejected before it
#: was ever built was reported as dying of its deflated Sharpe.
GATE_ORDER = ("symbol_eligibility", "economic_prior", "observations", "in_sample_screen",
              "deflated_sharpe", "pbo", "reality_check_spa", "cpcv", "walk_forward",
              "stress_costs", "lockbox", "expected_value")

_READINGS = {
    "deflated_sharpe": ("dsr", ("dsr", "value", "deflated_sharpe")),
    "in_sample_screen": ("sharpe", ("sharpe", "value", "sharpe_ratio")),
    "pbo": ("pbo", ("pbo", "value")),
    "reality_check_spa": ("spa_p", ("p_value", "p", "value")),
    "cpcv": ("cpcv_oos_sharpe", ("mean_oos_sharpe", "oos_sharpe", "value")),
    "walk_forward": ("wf_oos_sharpe", ("oos_sharpe", "value")),
    "stress_costs": ("cost_stress_mean", ("mean", "value")),
    "lockbox": ("lockbox_sharpe", ("lockbox_sharpe", "value")),
    "expected_value": ("ev", ("ev", "mean", "value")),
    "observations": ("days", ("days",)),
}


def death_profile(gates: dict[str, Any], fate: str) -> dict[str, Any]:
    """What this cell died of, with the numbers -- not a sentence.

    Returns {} for a fate that is not a death and for a gates blob with nothing in it, so an
    absent profile means "never judged", never "judged and fine". `terminal_gate` is the FIRST
    gate that refused in the ten-gate order, because that is the one a generator must beat;
    `passed` names the gates it did clear, which is where the idea worked.

    ABSENT BY CONSTRUCTION, and named rather than omitted: a correlation profile against the live
    book cannot be computed here (the gauntlet judges a cell against its own returns, never
    against the book), so `correlation_profile` reads ABSENT until an organ that holds both
    writes it.
    """
    if fate not in (FAILED, BURIED, RETIRED) or not isinstance(gates, dict) or not gates:
        return {}
    passed, failed, readings = [], [], {}
    for name, g in gates.items():
        if not isinstance(g, dict):
            continue
        if g.get("passed") is True:
            passed.append(name)
        elif g.get("passed") is False:
            failed.append(name)
        spec = _READINGS.get(name)
        if spec:
            key, fields = spec
            for f in fields:
                v = g.get(f)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    readings[key] = round(float(v), 6)
                    break
    terminal = next((k for k in GATE_ORDER if k in failed), failed[0] if failed else "")
    return {"terminal_gate": terminal, "failed": sorted(failed), "passed": sorted(passed),
            "n_gates": len(passed) + len(failed), "readings": readings,
            "unmeasured": bool(gates.get("observations", {}).get("passed") is False),
            "correlation_profile": ("ABSENT: the gauntlet judges a cell against its own returns, "
                                    "never against the live book"),
            "sample_days": readings.get("days")}


def edges_for(symbol: str, params: dict[str, Any], *, parent: str = "", operator: str = "",
              source_url: str = "") -> list[dict[str, Any]]:
    """The typed edges a candidate's own fields imply. Deterministic, deduplicated, ordered.

    Nothing here is inferred: every edge names a field the caller already carried. A candidate
    with no `input_source`, no factor list and no parent gets exactly one edge -- its symbol --
    and that is the honest graph of it.
    """
    out: list[dict[str, Any]] = []
    sym = str(symbol or "").strip().upper()
    if sym:
        out.append({"type": APPLIES_TO_SYMBOL, "to": f"symbol:{sym}"})
    seen: set[str] = set()
    for name in DATA_PARAMS:
        v = (params or {}).get(name)
        if v is None or v == "" or v == []:
            continue
        values = v if isinstance(v, (list, tuple)) else [v]
        for x in values:
            to = f"data:{str(x).strip()}"
            if to in seen or to == "data:":
                continue
            seen.add(to)
            out.append({"type": USES_DATA, "to": to, "via": name})
    if parent:
        e: dict[str, Any] = {"type": MUTATED_FROM, "to": str(parent)}
        if operator:
            e["operator"] = str(operator)
        out.append(e)
    if source_url:
        out.append({"type": SOURCED_FROM, "to": f"url:{str(source_url).strip()}"})
    return out


def edges_of(row: dict[str, Any]) -> list[dict[str, Any]]:
    """A row's typed edges; [] for the rows written before the field existed."""
    e = row.get("edges") if isinstance(row, dict) else None
    return [x for x in e if isinstance(x, dict)] if isinstance(e, list) else []


def node_id(symbol: str, family: str, params: dict[str, Any]) -> str:
    payload = json.dumps({"s": str(symbol).upper(), "f": family, "p": params},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _bucket(name: str, value: Any) -> str:
    w = REGION_WIDTH.get(name)
    if w is None or not isinstance(value, (int, float)) or isinstance(value, bool):
        return json.dumps(value, sort_keys=True, default=str)
    lo = (float(value) // w) * w
    return f"[{lo:g},{lo + w:g})"


def region_key(symbol: str, family: str, params: dict[str, Any]) -> str:
    parts = ",".join(f"{k}={_bucket(k, v)}" for k, v in sorted((params or {}).items()))
    return f"{str(symbol).upper()}.{family}{{{parts}}}"


class Graph:
    """The ledger with a read cache keyed on (mtime, size): the backfilled graph holds ~47,000
    rows, and the deepening worker asks `prior_failures` once per queued task, so re-parsing
    the file per question would be O(tasks x rows). An append invalidates the cache."""

    def __init__(self, path: Path = LEDGER) -> None:
        self.path = path
        self._stamp: tuple[float, int] | None = None
        self._rows: list[dict[str, Any]] = []
        self._current: dict[str, dict[str, Any]] | None = None
        self._buried: dict[str, list[dict[str, Any]]] | None = None

    def append(self, node: Node) -> dict[str, Any]:
        row = node.to_row()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        self._stamp = None
        return row

    def rows(self) -> list[dict[str, Any]]:
        try:
            st = self.path.stat()
            stamp = (st.st_mtime, st.st_size)
        except OSError:
            return []
        if self._stamp != stamp:
            try:
                self._rows = [json.loads(ln) for ln in self.path.read_text("utf-8").splitlines()
                              if ln.strip()]
            except (OSError, ValueError):
                self._rows = []
            self._stamp = stamp
            self._current = None
            self._buried = None
        return self._rows

    def current(self) -> dict[str, dict[str, Any]]:
        """Last row per node id -- the present fate of every hypothesis ever recorded."""
        rows = self.rows()
        if self._current is None:
            out: dict[str, dict[str, Any]] = {}
            for r in rows:
                out[str(r.get("id"))] = r
            self._current = out
        return self._current

    def buried(self) -> dict[str, list[dict[str, Any]]]:
        """region -> the FAILED/BURIED rows in it. This is the negative-knowledge index."""
        cur = self.current()
        if self._buried is None:
            out: dict[str, list[dict[str, Any]]] = {}
            for r in cur.values():
                if r.get("fate") in (FAILED, BURIED):
                    out.setdefault(str(r.get("region")), []).append(r)
            self._buried = out
        return self._buried

    def prior_failures(self, symbol: str, family: str, params: dict[str, Any]) -> dict[str, Any]:
        """What the desk already knows about this region. Empty means: never tried."""
        key = region_key(symbol, family, params)
        rows = self.buried().get(key, [])
        # HOW CLOSE IT CAME, NOT JUST THAT IT DIED (A3). A region whose best deflated Sharpe was
        # 0.94 against a 0.95 bar is a different object from one that failed every gate, and a
        # novelty gate that cannot tell them apart discards the desk's most promising ground.
        profiles = [p for p in (r.get("death") or death_profile(r.get("gates") or {},
                                                                str(r.get("fate") or ""))
                                for r in rows) if p]
        terminal: dict[str, int] = {}
        best: dict[str, float] = {}
        for p in profiles:
            t = str(p.get("terminal_gate") or "")
            if t:
                terminal[t] = terminal.get(t, 0) + 1
            for k, v in (p.get("readings") or {}).items():
                if isinstance(v, (int, float)):
                    best[k] = max(best.get(k, float(v)), float(v))
        return {"region": key, "n_failed": len(rows),
                "gates_failed": sorted({g for r in rows for g, v in (r.get("gates") or {}).items()
                                        if isinstance(v, dict) and v.get("passed") is False}),
                "last_why": (rows[-1].get("why") if rows else ""),
                "terminal_gates": dict(sorted(terminal.items(), key=lambda kv: -kv[1])),
                "best_readings": {k: round(v, 6) for k, v in sorted(best.items())},
                "profiles": len(profiles)}

    def lineage(self, node_id_: str) -> list[dict[str, Any]]:
        """Walk parents back to the root. A cycle or a missing parent ends the walk."""
        cur = self.current()
        out, seen = [], set()
        n = cur.get(node_id_)
        while n and n["id"] not in seen:
            out.append(n)
            seen.add(n["id"])
            n = cur.get(str(n.get("parent") or ""))
        return out

    def census(self) -> dict[str, Any]:
        cur = self.current()
        by_fate: dict[str, int] = {}
        by_source: dict[str, dict[str, int]] = {}
        by_edge: dict[str, int] = {}
        with_edges = 0
        for r in cur.values():
            by_fate[r.get("fate", "?")] = by_fate.get(r.get("fate", "?"), 0) + 1
            s = by_source.setdefault(str(r.get("source") or "?"), {})
            s[r.get("fate", "?")] = s.get(r.get("fate", "?"), 0) + 1
            es = edges_of(r)
            with_edges += int(bool(es))
            for e in es:
                t = str(e.get("type") or "?")
                by_edge[t] = by_edge.get(t, 0) + 1
        return {"nodes": len(cur), "by_fate": by_fate, "by_source": by_source,
                "buried_regions": len(self.buried()),
                # Nodes written before 2026-09-08 carry no edges; the count says how much of
                # the graph is typed rather than pretending the whole ledger is.
                "nodes_with_edges": with_edges, "by_edge_type": by_edge}

    def query(self, *, edge_type: str | None = None, to: str | None = None,
              symbol: str | None = None, family: str | None = None,
              fate: str | None = None) -> list[dict[str, Any]]:
        """Current-state rows matching every given filter; an omitted filter matches all.

        `edge_type` keeps rows carrying at least one edge of that type; `to` narrows to edges
        whose target is that string or starts with it (`data:` for every dataset edge,
        `symbol:USDJPY` for one instrument). `symbol` is matched case-insensitively.
        """
        if edge_type is not None and edge_type not in EDGE_TYPES:
            raise ValueError(f"unknown edge type {edge_type!r}; expected one of {EDGE_TYPES}")
        sym = str(symbol).upper() if symbol is not None else None
        out: list[dict[str, Any]] = []
        for r in self.current().values():
            if sym is not None and str(r.get("symbol") or "").upper() != sym:
                continue
            if family is not None and str(r.get("family") or "") != family:
                continue
            if fate is not None and str(r.get("fate") or "") != fate:
                continue
            if edge_type is not None or to is not None:
                hit = False
                for e in edges_of(r):
                    if edge_type is not None and e.get("type") != edge_type:
                        continue
                    target = str(e.get("to") or "")
                    if to is not None and not (target == to or target.startswith(to)):
                        continue
                    hit = True
                    break
                if not hit:
                    continue
            out.append(r)
        return out


def _candidate_parent_key(c: dict[str, Any]) -> tuple[str, str]:
    """(certificate key the candidate was stepped from, operator) or ("", "").

    The distiller and the mutation proposers carry both on `evidence`; a candidate may also
    carry `parent` at the top level. A parent that is only the miner-row hash (below) is NOT a
    mutation and gets no `mutated_from` edge.
    """
    _ev = c.get("evidence")
    ev: dict[str, Any] = _ev if isinstance(_ev, dict) else {}
    parent = c.get("parent") or ev.get("parent") or ""
    op = c.get("operator") or ev.get("operator") or ""
    return str(parent or ""), str(op or "")


def record_candidates(cands: Iterable[dict[str, Any]], source: str,
                      graph: Graph | None = None) -> int:
    """Register newly compiled candidates as BORN, with the miner row that produced each."""
    g = graph or Graph()
    n = 0
    for c in cands:
        parent = hashlib.sha256(json.dumps({"u": c.get("source_url"), "t": c.get("source_title"),
                                            "s": c.get("source")}, sort_keys=True,
                                           default=str).encode()).hexdigest()[:16]
        params = dict(c.get("params") or {})
        mut_parent, op = _candidate_parent_key(c)
        # THE CANDIDATE'S OWN SOURCE WINS. The compiler registers every candidate it admits, and
        # stamping them all "miner_candidate_compiler" erased which proposer found each one --
        # the bandit's per-arm evidence and the research P&L attribute by this field.
        g.append(Node(symbol=str(c.get("symbol")), family=str(c.get("family")),
                      params=params,
                      source=str(c.get("source") or source), parent=parent,
                      fate=BORN, why=str(c.get("mechanism_note") or "")[:200],
                      edges=edges_for(str(c.get("symbol")), params, parent=mut_parent,
                                      operator=op,
                                      source_url=str(c.get("source_url") or ""))))
        n += 1
    return n


def record_verdicts(verdicts: Iterable[dict[str, Any]], graph: Graph | None = None) -> int:
    """Record gauntlet outcomes. A cell that fails any gate is FAILED with the gates it failed."""
    g = graph or Graph()
    n = 0
    for v in verdicts:
        gates = v.get("gates") or {}
        passed_all = bool(gates) and all(isinstance(x, dict) and x.get("passed") is True
                                         for x in gates.values())
        failed = [k for k, x in gates.items() if isinstance(x, dict) and x.get("passed") is False]
        sym = str(v.get("sym") or v.get("symbol"))
        params = dict(v.get("params") or {})
        g.append(Node(symbol=sym, family=str(v.get("family")),
                      params=params, source=str(v.get("hunt") or "gauntlet"),
                      fate=CERTIFIED if passed_all else FAILED,
                      why=("passed all gates" if passed_all else
                           f"failed {', '.join(failed) or 'unmeasured'}"), gates=gates,
                      edges=edges_for(sym, params)))
        n += 1
    return n
