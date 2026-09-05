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

    @property
    def id(self) -> str:
        return node_id(self.symbol, self.family, self.params)

    @property
    def region(self) -> str:
        return region_key(self.symbol, self.family, self.params)

    def to_row(self) -> dict[str, Any]:
        return {"id": self.id, "region": self.region, "symbol": self.symbol,
                "family": self.family, "params": self.params, "source": self.source,
                "parent": self.parent, "fate": self.fate, "why": self.why, "gates": self.gates,
                "at": self.at or datetime.now(tz=UTC).isoformat()}


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
        return {"region": key, "n_failed": len(rows),
                "gates_failed": sorted({g for r in rows for g, v in (r.get("gates") or {}).items()
                                        if isinstance(v, dict) and v.get("passed") is False}),
                "last_why": (rows[-1].get("why") if rows else "")}

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
        for r in cur.values():
            by_fate[r.get("fate", "?")] = by_fate.get(r.get("fate", "?"), 0) + 1
            s = by_source.setdefault(str(r.get("source") or "?"), {})
            s[r.get("fate", "?")] = s.get(r.get("fate", "?"), 0) + 1
        return {"nodes": len(cur), "by_fate": by_fate, "by_source": by_source,
                "buried_regions": len(self.buried())}


def record_candidates(cands: Iterable[dict[str, Any]], source: str,
                      graph: Graph | None = None) -> int:
    """Register newly compiled candidates as BORN, with the miner row that produced each."""
    g = graph or Graph()
    n = 0
    for c in cands:
        parent = hashlib.sha256(json.dumps({"u": c.get("source_url"), "t": c.get("source_title"),
                                            "s": c.get("source")}, sort_keys=True,
                                           default=str).encode()).hexdigest()[:16]
        # THE CANDIDATE'S OWN SOURCE WINS. The compiler registers every candidate it admits, and
        # stamping them all "miner_candidate_compiler" erased which proposer found each one --
        # the bandit's per-arm evidence and the research P&L attribute by this field.
        g.append(Node(symbol=str(c.get("symbol")), family=str(c.get("family")),
                      params=dict(c.get("params") or {}),
                      source=str(c.get("source") or source), parent=parent,
                      fate=BORN, why=str(c.get("mechanism_note") or "")[:200]))
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
        g.append(Node(symbol=str(v.get("sym") or v.get("symbol")), family=str(v.get("family")),
                      params=dict(v.get("params") or {}), source=str(v.get("hunt") or "gauntlet"),
                      fate=CERTIFIED if passed_all else FAILED,
                      why=("passed all gates" if passed_all else
                           f"failed {', '.join(failed) or 'unmeasured'}"), gates=gates))
        n += 1
    return n
