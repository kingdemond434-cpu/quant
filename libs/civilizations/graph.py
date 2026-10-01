"""THE CANONICAL KNOWLEDGE GRAPH every civilization writes into, and the ingest of what exists.

Nodes: source, repo, paper, author, artifact, mechanism, operator, field, failure, method,
component, dataset, strategy. Edges: implements, cites, authored_by, derived_from, forks,
tested_by, blocks, substitutes, mentions. One SQLite file (desks/mt5/data/civilizations/
knowledge.db), idempotent upserts, so a 24/7 resident that sees the same item twice records it
once and a new edge from a later pass is simply added.

INGEST, DON'T RESTART (zuck 2026-09-30): the ~87 BRAIN-hunter artifacts under `data/
brain_hunter_*` and the 168 firm-mining discoveries under `desks/mt5/data/intelligence/
firm_mining/` are read into the graph with a STATUS each:

    covered | partially_covered | requires_replication | superseded | failed | needs_new_data |
    converted_to_cell | validated | rejected

assigned by named rules over the artifact's own words (the evidence is stored on the node), so a
future pass builds from what is already known instead of re-mining it.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES: tuple[str, ...] = ("covered", "partially_covered", "requires_replication",
                             "superseded", "failed", "needs_new_data", "converted_to_cell",
                             "validated", "rejected")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id TEXT PRIMARY KEY, kind TEXT NOT NULL, civilization TEXT, label TEXT,
    status TEXT, doc TEXT, first_seen TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS edges (
    src TEXT NOT NULL, rel TEXT NOT NULL, dst TEXT NOT NULL, first_seen TEXT,
    PRIMARY KEY (src, rel, dst));
CREATE INDEX IF NOT EXISTS nodes_kind ON nodes(kind);
CREATE INDEX IF NOT EXISTS nodes_civ ON nodes(civilization);
"""


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class KnowledgeGraph:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(str(self.path), timeout=30)
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def node(self, node_id: str, kind: str, *, civilization: str = "", label: str = "",
             status: str = "", doc: Mapping[str, Any] | None = None) -> bool:
        """Upsert. True when the node is new."""
        now = _now()
        with self._conn() as c:
            cur = c.execute("SELECT 1 FROM nodes WHERE node_id=?", (node_id,)).fetchone()
            if cur is None:
                c.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                          (node_id, kind, civilization, label[:300], status,
                           json.dumps(dict(doc or {}), default=str)[:20000], now, now))
                return True
            c.execute("UPDATE nodes SET last_seen=?, status=COALESCE(NULLIF(?, ''), status) "
                      "WHERE node_id=?", (now, status, node_id))
            return False

    def edge(self, src: str, rel: str, dst: str) -> bool:
        with self._conn() as c:
            cur = c.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?)",
                            (src, rel, dst, _now()))
            return cur.rowcount > 0

    def counts(self) -> dict[str, Any]:
        with self._conn() as c:
            kinds = dict(c.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall())
            civs = dict(c.execute("SELECT COALESCE(civilization,''), COUNT(*) FROM nodes "
                                  "GROUP BY civilization").fetchall())
            st = dict(c.execute("SELECT COALESCE(status,''), COUNT(*) FROM nodes "
                                "WHERE kind='artifact' GROUP BY status").fetchall())
            n_edges = c.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        return {"nodes_by_kind": kinds, "nodes_by_civilization": civs,
                "artifact_status": st, "edges": n_edges}

    def nodes(self, kind: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT node_id, civilization, label, status, doc FROM nodes "
                             "WHERE kind=?", (kind,)).fetchall()
        return [{"node_id": r[0], "civilization": r[1], "label": r[2], "status": r[3],
                 "doc": json.loads(r[4] or "{}")} for r in rows]


# ------------------------------------------------------------------------------ status rules
STATUS_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("superseded", re.compile(r"(?<![A-Za-z])VOID(?![A-Za-z])|superseded|replaced by|"
                              r"calendar bug", re.I)),
    ("rejected", re.compile(r"\bREFUTED\b|\brejected\b|\bkilled\b|no edge|not significant|"
                            r"\bDEAD\b|fails? (every|all|the gate)", re.I)),
    ("failed", re.compile(r"\bFAILED\b|could not (be )?(run|read|reproduce)|error:", re.I)),
    ("validated", re.compile(r"\bvalidated\b|\bsurviv(es|ed|or)\b|\bCONFIRMED\b|\bheld\b", re.I)),
    ("converted_to_cell", re.compile(r"\bmt5_translation\b|\"cells\"|\bdonat(ed|ion)\b|"
                                     r"\"kind\": \"hypothesis\"", re.I)),
    ("needs_new_data", re.compile(r"needs? (new )?data|not on (the )?box|UNMEASURED|"
                                  r"no (bars|data) for|data (absent|missing)", re.I)),
    ("requires_replication", re.compile(r"replicat|re-?run|reproduc", re.I)),
    ("partially_covered", re.compile(r"next_unexhausted_ground|unexhausted|partial|"
                                     r"remaining", re.I)),
)


def artifact_status(name: str, text: str) -> tuple[str, list[str]]:
    """(primary status, every status whose rule fired). First rule in STATUS_RULES wins."""
    hay = f"{name}\n{text[:400_000]}"
    fired = [s for s, rx in STATUS_RULES if rx.search(hay)]
    return (fired[0] if fired else "covered"), (fired or ["covered"])


FIRM_WORDS: dict[str, re.Pattern[str]] = {
    "aqr": re.compile(r"\bAQR\b|Asness|Moskowitz|Pedersen|Frazzini", re.I),
    "man_ahl": re.compile(r"\bMan AHL\b|\bAHL\b|Man Group|Man Institute", re.I),
    "bridgewater": re.compile(r"Bridgewater|Dalio|All Weather|Pure Alpha|Daily Observations",
                              re.I),
    "renaissance": re.compile(r"Renaissance|Medallion|Simons|Laufer|Berlekamp", re.I),
    "two_sigma": re.compile(r"Two Sigma", re.I),
    "deshaw": re.compile(r"D\.?\s?E\.? Shaw", re.I),
    "winton": re.compile(r"\bWinton\b|David Harding", re.I),
    "market_makers": re.compile(r"Jane Street|\bXTX\b|Citadel Securities|\bVirtu\b|Optiver",
                               re.I),
    "ubiquant": re.compile(r"Ubiquant|九坤", re.I),
    "jpx": re.compile(r"\bJPX\b|Japan Exchange Group", re.I),
    "g_research": re.compile(r"G-Research", re.I),
    "worldquant": re.compile(r"WorldQuant|\bBRAIN\b|Alpha\s?#?101|101 Formulaic", re.I),
    "quantconnect": re.compile(r"QuantConnect|\bLEAN\b", re.I),
}


def civilizations_named(text: str) -> list[str]:
    return [k for k, rx in FIRM_WORDS.items() if rx.search(text or "")]


def ingest_brain_artifacts(kg: KnowledgeGraph, root: Path) -> dict[str, Any]:
    """Every `data/brain_hunter_*` file -> one artifact node with its status and evidence."""
    stat: Counter[str] = Counter()
    n = 0
    for fp in sorted(Path(root).glob("data/brain_hunter_*")):
        try:
            text = fp.read_text("utf-8", errors="replace")
        except OSError:
            continue
        n += 1
        primary, fired = artifact_status(fp.name, text)
        stat[primary] += 1
        m = re.match(r"brain_hunter_(s\d+[a-z]?)_?(.*)\.(json|py)$", fp.name)
        session = m.group(1) if m else ""
        topic = (m.group(2) if m else fp.stem).replace("_", " ")
        nid = f"artifact:brain_hunter:{fp.name}"
        kg.node(nid, "artifact", civilization="worldquant", label=topic, status=primary,
                doc={"path": str(fp.relative_to(root)), "session": session,
                     "statuses": fired, "kind": "script" if fp.suffix == ".py" else "finding",
                     "bytes": fp.stat().st_size,
                     "also_names": [c for c in civilizations_named(text) if c != "worldquant"]})
        for c in civilizations_named(text):
            if c != "worldquant":
                kg.edge(nid, "mentions", f"civilization:{c}")
    return {"artifacts": n, "by_status": dict(stat)}


def ingest_firm_discoveries(kg: KnowledgeGraph, root: Path) -> dict[str, Any]:
    """The 2026-09-27 firm-mining discoveries (already read by the compiler through
    data/intelligence/**): one mechanism node each, attributed to every firm it names."""
    by_civ: Counter[str] = Counter()
    n = 0
    for fp in sorted(Path(root).glob("desks/mt5/data/intelligence/firm_mining/*.json")):
        try:
            doc = json.loads(fp.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc.get("discoveries") if isinstance(doc, Mapping) else doc
        cluster = str(doc.get("cluster") or fp.stem) if isinstance(doc, Mapping) else fp.stem
        for i, r in enumerate(rows or []):
            if not isinstance(r, Mapping):
                continue
            n += 1
            text = json.dumps(r, default=str)
            civs = civilizations_named(text) or ["unattributed"]
            nid = f"mechanism:firm_mining:{fp.stem}:{i}"
            kg.node(nid, "mechanism", civilization=civs[0],
                    label=str(r.get("mechanism") or "")[:200], status="converted_to_cell",
                    doc={"family": r.get("family"), "params": r.get("params"),
                         "symbols": r.get("symbols"), "cluster": cluster,
                         "path": str(fp.relative_to(root)), "civilizations": civs})
            for c in civs:
                by_civ[c] += 1
                kg.edge(nid, "attributed_to", f"civilization:{c}")
            if r.get("family"):
                kg.edge(nid, "implements", f"family:{r.get('family')}")
    return {"mechanisms": n, "by_civilization": dict(by_civ)}


def ingest_all(kg: KnowledgeGraph, root: Path) -> dict[str, Any]:
    return {"brain_artifacts": ingest_brain_artifacts(kg, root),
            "firm_discoveries": ingest_firm_discoveries(kg, root), "graph": kg.counts()}


def iter_json_rows(path: Path) -> Iterable[dict[str, Any]]:
    try:
        with Path(path).open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    yield row
    except OSError:
        return
