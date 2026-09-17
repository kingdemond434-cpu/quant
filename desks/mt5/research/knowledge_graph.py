"""THE KNOWLEDGE GRAPH: what the desk knows about X, where it came from, and what it became.

WHY THIS EXISTS (W2 / Q17 memory banks, principal 2026-09-16). The desk can count candidates,
certificates and dead cells. It could not answer the three questions a research organisation is
made of: what do we know about gold, or about session handover? which ground produced that, and
what has that ground ever produced? what did the claim BECOME -- a cell, a verdict, or nothing at
all for six weeks? `semantic_memory` answers "what is SIMILAR to this"; `hypothesis_graph` answers
"what did this cell descend from" inside the docket. Neither holds a typed edge from a 七禾网
interview to the mechanism it named, to the instrument it named it on, to the cell that tested it,
to the fate that cell met.

HOW A CELL NAMES THE LEAD IT CAME FROM, measured rather than assumed.
`libs/research/hypothesis_graph.record_candidates` stamps every compiled candidate with
`seed_key = sha256({"s": "miner:<source>", "t": title[:300], "u": url})[:16]` -- written into
`parent` alone until 2026-09-17, and into both when the candidate names no parent cell -- and
`lead_schema.row_cell_key` reproduces it exactly (`cell_seed_key` reads it back off a graph row,
`seed_key` first then `parent`). Measured against the live ledger on this box:
142 of 2,431 sampled rows from `cot`, `forexfactory` and `microstructure` resolve to cells that
exist -- so BECAME is a JOIN, not an inference. A lead whose key resolves to nothing is not an
error, it is the backlog, and `unconverted_leads()` is that population by name.

FIVE SOURCES REPEATING ONE STORY ARE ONE CLAIM WITH FIVE WITNESSES (principal 2026-09-16). The
lead node is keyed on `dedupe_key`, so the fifth telling adds a PRODUCED edge rather than a fifth
node, and `n_claim_mentions` against `n_claims_distinct` publishes that collapse -- because "five
independent sources agree" and "we scraped one post five times" must never read the same.

It scores nothing, ranks nothing and kills nothing: a mechanism with leads and no tested cells is
REPORTED, never deprioritised, and an unconverted lead is never dropped. A cursor of processed row
keys makes an hourly run cost the NEW rows only; `--max-rows` bounds one pass and the shortfall is
counted. Stdlib only.

    python desks/mt5/research/knowledge_graph.py [--dry-run] [--max-rows 5000] [--query TERM]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import lead_schema as ls  # noqa: E402

STORE = DESK / "data" / "knowledge_graph" / "graph.json"
CURSOR = DESK / "data" / "knowledge_graph" / "cursor.json"
REPORT = DESK / "reports" / "KNOWLEDGE_GRAPH.json"
INTEL_ROOTS = (DESK / "data" / "intelligence", ROOT / "data" / "intelligence")
HYPOTHESIS_GRAPH = DESK / "data" / "hypothesis_graph.jsonl"
FRONTIER_QUEUE = DESK / "frontier_intel" / "data" / "frontier_queue.jsonl"
SOURCE_REGISTRY = DESK / "data" / "source_registry.json"
UNIVERSE = DESK / "data" / "universe" / "universe.json"

#: Intake rows one pass carries. A bound on MEMORY and on wall clock, not a view of what matters:
#: whatever it defers is COUNTED and waits for the next run rather than being dropped.
MAX_ROWS = 5000
#: Lead nodes the store holds. At the far end the OLDEST leads are evicted with their edges and
#: the eviction is reported -- a store that silently forgets is worse than one that says it did.
MAX_LEAD_NODES = 60_000
MAX_EDGES = 400_000
#: Processed row keys the cursor remembers. Older keys fall off and those rows would be re-read;
#: re-reading is idempotent here (every write is keyed), so the only cost is time.
MAX_CURSOR_KEYS = 250_000
#: Witnesses kept per claim node. The count is exact; the named list is bounded.
MAX_MENTIONS = 25
#: Leads compared for DUPLICATES/CONTRADICTS inside one (instrument, mechanism) bucket. Pairwise
#: work is quadratic, so the bucket is the newest N and the cap being hit is reported.
MAX_BUCKET = 120
DUP_COSINE = 0.9
#: Titles held for DERIVES_FROM citation matching, and the share of a title's tokens a citing
#: claim must carry. 0.6 of eight tokens is five: enough that "momentum" alone is not a citation.
MAX_CITABLE_TITLES = 8000
TITLE_MATCH_SHARE = 0.6
#: Claim text kept on a node: enough to read and to compare, never the document.
NODE_CLAIM_CHARS = 400
#: Rows of the hypothesis ledger one pass reads when it has no offset to resume from.
MAX_GRAPH_LINES = 400_000

NODE_LEAD, NODE_SOURCE, NODE_MECHANISM = "lead", "source", "mechanism"
NODE_INSTRUMENT, NODE_AXIS, NODE_CELL, NODE_OUTCOME = "instrument", "axis", "cell", "outcome"
NODE_TYPES = (NODE_LEAD, NODE_SOURCE, NODE_MECHANISM, NODE_INSTRUMENT, NODE_AXIS, NODE_CELL,
              NODE_OUTCOME)

CLAIMS, NAMES, PRODUCED, BECAME = "CLAIMS", "NAMES", "PRODUCED", "BECAME"
JUDGED, TESTED_BY, ON_AXIS = "JUDGED", "TESTED_BY", "ON_AXIS"
DUPLICATES, CONTRADICTS, DERIVES_FROM = "DUPLICATES", "CONTRADICTS", "DERIVES_FROM"
EDGE_TYPES = (CLAIMS, NAMES, PRODUCED, BECAME, JUDGED, TESTED_BY, ON_AXIS, DUPLICATES,
              CONTRADICTS, DERIVES_FROM)

RULE = ("one lead schema; every lead is linked to what it claimed, where it came from and what "
        "it became")

#: Loose mechanism words (a deep-forest `mechanism_class`, a crawler `pattern`) bridged onto
#: `axis_registry`'s mechanism vocabulary, so a lead's mechanism and a cell's family-derived
#: mechanism meet on ONE id. A token in neither vocabulary keeps its own node and is counted --
#: an unbridged mechanism is a gap in this table, and a gap nobody can name is a gap nobody fixes.
MECH_BRIDGE: dict[str, str] = {
    "momentum": "trend_persistence", "trend": "trend_persistence", "trending": "trend_persistence",
    "breakout": "breakout_liquidity", "range_break": "breakout_liquidity",
    "opening_range": "breakout_liquidity", "liquidity_sweep": "breakout_liquidity",
    "reversion": "range_reversion", "mean_reversion": "range_reversion",
    "reversal": "range_reversion", "revert": "range_reversion", "range": "range_reversion",
    "carry": "carry_rollover", "swap": "carry_rollover", "rollover": "carry_rollover",
    "basis": "carry_rollover", "funding": "carry_rollover",
    "seasonal": "calendar_seasonality", "seasonality": "calendar_seasonality",
    "calendar": "calendar_seasonality", "turn_of_month": "calendar_seasonality",
    "event": "macro_release", "news": "macro_release", "macro": "macro_release",
    "release": "macro_release", "cb_tone": "macro_release",
    "positioning": "positioning_crowding", "cot": "positioning_crowding",
    "crowding": "positioning_crowding", "sentiment": "positioning_crowding",
    "volatility": "volatility_shock", "vol": "volatility_shock", "jump": "volatility_shock",
    "squeeze": "volatility_shock",
    "microstructure": "execution_microstructure", "orderflow": "execution_microstructure",
    "order_flow": "execution_microstructure", "spread": "execution_microstructure",
    "liquidity": "execution_microstructure", "slippage": "execution_microstructure",
    "residual": "relative_value_dislocation", "relative_value": "relative_value_dislocation",
    "correlation": "relative_value_dislocation", "pairs": "relative_value_dislocation",
    "arbitrage": "relative_value_dislocation", "spread_trade": "relative_value_dislocation",
    "regime": "regime_transition", "regime_shift": "regime_transition",
    "session": "session_handover", "overnight": "session_handover", "gap": "session_handover",
    "fix": "fx_fixing_flow", "fixing": "fx_fixing_flow", "london_fix": "fx_fixing_flow",
    "flow": "forced_flow", "forced": "forced_flow", "rebalance": "forced_flow",
    "lead_lag": "cross_market_lead", "leadlag": "cross_market_lead",
}

#: Artifacts at the ROOT of an intelligence tree that are a miner's bookkeeping, not its evidence.
#: The compiler's own exclusion list, kept in step: an EXCLUSION list fails open against a miner
#: nobody has written yet, where an inclusion list failed closed against 583 artifacts.
_OPERATIONAL_STATE = frozenset({
    "blocked_sources.json", "coverage_registry.json", "frontier_coverage.json",
    "frontier_state.json", "identity_graph.json", "seed_miners_state.json",
    "regional_hunters_state.json", "source_populations.json", "anomaly_cursor.json",
    "survivor_funnel.json", "survivor_shortlist.json", "latest_discoveries.json",
})


# ------------------------------------------------------------------ io

def _atomic(path: Path, doc: Any) -> None:
    """Write or leave the previous version intact. Never a half-written graph."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            os.replace(tmp, path)
        except PermissionError:
            # A read-only destination raises WinError 5 on the box and nothing on POSIX. The desk
            # has lost a fix to exactly this before; write through rather than die.
            path.write_text(text, encoding="utf-8")
            Path(tmp).unlink(missing_ok=True)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def blank_store() -> dict[str, Any]:
    return {"at": "", "version": 1, "nodes": {}, "edges": {},
            "index": {"parents": {}, "cell_parents": {}, "urls": {}, "titles": {},
                      "title_heads": {}, "buckets": {}, "cited_urls": {}},
            "counts": {"claim_mentions": 0, "evicted_leads": 0}}


def load_store(path: Path | None = None) -> dict[str, Any]:
    """The stored graph, or an empty one. The path resolves against the module global at CALL
    time -- a default bound at definition time cannot be redirected, and a query that silently
    read the desk's real graph while a caller thought it was reading a fixture would be worse
    than a crash."""
    doc = _read_json(path or STORE)
    if not isinstance(doc, dict) or "nodes" not in doc:
        return blank_store()
    blank = blank_store()
    for key, value in blank.items():
        doc.setdefault(key, value)
    for key, value in blank["index"].items():
        doc["index"].setdefault(key, value)
    for key, value in blank["counts"].items():
        doc["counts"].setdefault(key, value)
    return doc


def load_cursor(path: Path | None = None) -> dict[str, Any]:
    doc = _read_json(path or CURSOR)
    if not isinstance(doc, dict):
        return {"at": "", "rows": [], "graph_offset": 0, "graph_size": 0, "n_rows_seen": 0}
    doc.setdefault("rows", [])
    doc.setdefault("graph_offset", 0)
    doc.setdefault("graph_size", 0)
    doc.setdefault("n_rows_seen", 0)
    return doc


# ------------------------------------------------------------------ intake

def row_key(row: Mapping[str, Any]) -> str:
    """The compiler's own exact-content key, so both organs deduplicate the same way."""
    payload = json.dumps(row, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _rows_of(doc: Any) -> list[dict[str, Any]]:
    """The compiler's tolerant unwrapping: a list, a `discoveries` block, or a dict of either."""
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return []
    if isinstance(doc.get("discoveries"), list):
        return [r for r in doc["discoveries"] if isinstance(r, dict)]
    out: list[dict[str, Any]] = []
    for value in doc.values():
        if isinstance(value, dict) and isinstance(value.get("discoveries"), list):
            out.extend(r for r in value["discoveries"] if isinstance(r, dict))
        elif isinstance(value, list):
            out.extend(r for r in value if isinstance(r, dict))
    return out


def intake_paths(roots: Sequence[Path] | None = None,
                 frontier: Path | None = None) -> list[Path]:
    """Every intelligence artifact, NEWEST FIRST, plus the frontier queue. Operational state at a
    tree's root is excluded by name; everything else is read, at any depth."""
    roots = roots if roots is not None else INTEL_ROOTS
    frontier = frontier or FRONTIER_QUEUE
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            if not path.is_file():
                continue
            rel = path.relative_to(root)
            if len(rel.parts) == 1 and rel.name in _OPERATIONAL_STATE:
                continue
            paths.append(path)
    paths.sort(key=lambda p: (-_mtime(p), str(p)))
    if frontier.exists():
        paths.insert(0, frontier)
    return paths


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def iter_intake(paths: Sequence[Path], seen: set[str], max_rows: int) -> Iterator[
        tuple[dict[str, Any], str, str, str]]:
    """(row, seat, run, key) for every UNPROCESSED row, newest artifact first, bounded."""
    n = 0
    for path in paths:
        if n >= max_rows:
            return
        seat = path.parent.name
        run = path.stem
        rows: list[dict[str, Any]]
        if path.suffix == ".jsonl":
            rows = []
            try:
                with path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            parsed = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(parsed, dict):
                            rows.append(parsed)
            except OSError:
                continue
        else:
            rows = _rows_of(_read_json(path))
        for row in rows:
            key = row_key(row)
            if key in seen:
                continue
            seen.add(key)
            yield row, seat, run, key
            n += 1
            if n >= max_rows:
                return


# ------------------------------------------------------------------ the store

#: Attributes a node keeps from its FIRST telling: the language it was first stated in, when it
#: was first seen, and the direction it first asserted. A later witness is recorded as a witness
#: (`mentions`, `kinds`) rather than as a correction.
_FIRST_WINS = ("language", "seen_at", "knowable_at", "first_seen", "direction")

#: A CLAIM'S KIND IS ITS STRONGEST WITNESS, not its first. Intake is newest-artifact-first, so
#: which telling of a story arrives first is an accident of crawl order -- and "a paper and four
#: forum posts say this" must not read as a forum claim because the forum was crawled last night.
KIND_RANK: dict[str, int] = {"paper": 6, "filing": 5, "competition": 4, "data_release": 3,
                             "story": 2, "broker_change": 2, "forum": 1, "other": 0}


def add_node(store: dict[str, Any], node_id: str, node_type: str, label: str,
             **attrs: Any) -> dict[str, Any]:
    """Create or touch a node. An existing node keeps its first-seen `at` and its origin attrs --
    when and how the desk first learned a thing is part of what it knows about it."""
    nodes = store["nodes"]
    node = nodes.get(node_id)
    if node is None:
        node = {"type": node_type, "label": label, "at": store["at"], "attrs": dict(attrs)}
        nodes[node_id] = node
        return node
    node["attrs"].update({k: v for k, v in attrs.items()
                          if v not in (None, "", [], {}) and k not in _FIRST_WINS})
    for key in _FIRST_WINS:
        if key in attrs and node["attrs"].get(key) in (None, "", [], {}):
            node["attrs"][key] = attrs[key]
    if label and not node.get("label"):
        node["label"] = label
    return node


def edge_id(src: str, dst: str, edge_type: str) -> str:
    return hashlib.sha256(f"{src}\x00{edge_type}\x00{dst}".encode()).hexdigest()[:20]


def add_edge(store: dict[str, Any], src: str, dst: str, edge_type: str,
             **attrs: Any) -> str | None:
    """One edge per (src, type, dst). Returns its id, or None when the edge cap is full."""
    if src == dst or src not in store["nodes"] or dst not in store["nodes"]:
        return None
    eid = edge_id(src, dst, edge_type)
    edges = store["edges"]
    if eid in edges:
        edges[eid]["n"] = int(edges[eid].get("n", 1)) + 1
        for key, value in attrs.items():
            if value in (None, ""):
                continue
            if key == "via":
                # TWO SIGNALS FOR ONE EDGE ARE MORE EVIDENCE, NOT A CORRECTION. A post that
                # pastes a paper's link AND names its title cited it twice over; overwriting
                # `via` would throw away the stronger of the two readings at random.
                parts = [p for p in str(edges[eid]["attrs"].get("via") or "").split("+") if p]
                if str(value) not in parts:
                    parts.append(str(value))
                edges[eid]["attrs"]["via"] = "+".join(sorted(parts))
            else:
                edges[eid]["attrs"][key] = value
        return eid
    if len(edges) >= MAX_EDGES:
        return None
    edges[eid] = {"src": src, "dst": dst, "type": edge_type, "at": store["at"], "n": 1,
                  "attrs": dict(attrs)}
    return eid


def new_edge(store: dict[str, Any], src: str, dst: str, edge_type: str, **attrs: Any) -> bool:
    """`add_edge`, answering the question the counters actually ask: is this edge NEW?

    A re-read row must not inflate a report. `add_edge` returns an id whether it created the edge
    or touched one, which reads as "made an edge" at every call site that counts -- so the count
    is taken here, before the write, where the answer is unambiguous.
    """
    fresh = edge_id(src, dst, edge_type) not in store["edges"]
    return add_edge(store, src, dst, edge_type, **attrs) is not None and fresh


def lead_node_id(key: str) -> str:
    return f"{NODE_LEAD}:{key}"


def _mech_id(token: str) -> str:
    norm = str(token or "").strip().lower()
    return f"{NODE_MECHANISM}:{MECH_BRIDGE.get(norm, norm)}" if norm else ""


_FAMILY_MECH: dict[str, str] = {}


def mechanism_of_family(family: str) -> str:
    """The mechanism a family names, from `axis_registry.FAMILY_TABLE` -- the desk's own table.

    Lazily imported and cached: the organ must still build when the desk's research package moves
    or fails to import, and a mechanism it cannot resolve is UNKNOWN and counted, never guessed.
    """
    fam = str(family or "").strip().lower()
    if not fam:
        return ""
    if fam in _FAMILY_MECH:
        return _FAMILY_MECH[fam]
    mech = ""
    try:
        import axis_registry  # type: ignore[import-not-found]
        row = axis_registry.FAMILY_TABLE.get(fam)
        if row:
            mech = str(row[0])
    except Exception:
        mech = ""
    if not mech or mech == "UNKNOWN":
        try:
            import semantic_memory  # type: ignore[import-not-found]
            loose = str(semantic_memory.mechanism_of(fam) or "")
            mech = MECH_BRIDGE.get(loose, loose) if loose != "UNCLASSIFIED" else ""
        except Exception:
            mech = mech or ""
    _FAMILY_MECH[fam] = mech
    return mech


# ------------------------------------------------------------------ ingesting leads

def _bucket_keys(lead: ls.Lead) -> list[str]:
    """The comparison buckets one claim belongs to: its (instrument, mechanism) cell AND the
    instrument alone.

    THE SECOND BUCKET IS THE POINT. Half the rows on this tree name an instrument and no
    mechanism -- a reddit title, an mql5 catalogue line -- and bucketing on the pair alone means
    those claims are never compared with the ones that DO name a mechanism, which is exactly
    where the duplicates and the contradictions live.
    """
    instrument = (lead.instruments[0] if lead.instruments else "").upper()
    mechs = _mechanism_ids_of(lead)
    keys = [f"{instrument}|"]
    if mechs:
        keys.insert(0, f"{instrument}|{mechs[0]}")
    return keys


def _mechanism_ids_of(lead: ls.Lead) -> list[str]:
    out: list[str] = []
    for token in lead.mechanism_ids:
        mid = _mech_id(token)
        if mid and mid not in out:
            out.append(mid)
    if lead.executable:
        mid = _mech_id(mechanism_of_family(str(lead.executable.get("family") or "")))
        if mid and mid not in out:
            out.append(mid)
    return out


def ingest_lead(store: dict[str, Any], lead: ls.Lead) -> tuple[str, bool, int]:
    """One claim into the graph. Returns (node id, whether the CLAIM is new, late citations).

    A repeat telling is not a new node: it adds a witness and a PRODUCED edge from its own source,
    which is how "five grounds agree" stops looking like "one ground scraped five times". And
    intake is newest-artifact-first, so the post citing a paper is usually read BEFORE the paper:
    an unresolvable citation waits against the url and closes the moment that url lands, or
    DERIVES_FROM would only fire when the crawl happened to run backwards.
    """
    key = lead.dedupe_key()
    node_id = lead_node_id(key)
    index = store["index"]
    fresh = node_id not in store["nodes"]
    claim = lead.claim_text[:NODE_CLAIM_CHARS]
    node = add_node(store, node_id, NODE_LEAD, claim,
                    kind=lead.kind, testable=lead.testable, priority=lead.priority,
                    structured_complete=lead.structured_complete,
                    instruments=list(lead.instruments), mechanisms=_mechanism_ids_of(lead),
                    language=lead.language, seen_at=lead.seen_at, knowable_at=lead.knowable_at,
                    axes=dict(lead.axes), asset_classes=list(lead.asset_classes),
                    direction=ls.direction_of(lead.claim_text))
    attrs = node["attrs"]
    kinds = attrs.setdefault("kinds", [])
    if lead.kind not in kinds:
        kinds.append(lead.kind)
    attrs["kind"] = max(kinds, key=lambda k: KIND_RANK.get(k, 0))
    mentions = attrs.setdefault("mentions", [])
    witness = {"lead_id": lead.lead_id, "source_id": lead.source_id, "url": lead.url_or_ref,
               "seen_at": lead.seen_at, "run": lead.provenance.get("run", "")}
    if not any(m.get("lead_id") == lead.lead_id for m in mentions):
        if len(mentions) < MAX_MENTIONS:
            mentions.append(witness)
        attrs["n_mentions"] = int(attrs.get("n_mentions", 0)) + 1
        store["counts"]["claim_mentions"] = int(store["counts"]["claim_mentions"]) + 1
    attrs.setdefault("first_seen", lead.seen_at or store["at"])

    source_id = f"{NODE_SOURCE}:{lead.source_id}"
    add_node(store, source_id, NODE_SOURCE, lead.source_id, seat=lead.provenance.get("seat", ""))
    add_edge(store, source_id, node_id, PRODUCED, kind=lead.kind)

    for mid in _mechanism_ids_of(lead):
        add_node(store, mid, NODE_MECHANISM, mid.split(":", 1)[1])
        add_edge(store, node_id, mid, CLAIMS)
    for symbol in lead.instruments:
        iid = f"{NODE_INSTRUMENT}:{symbol.upper()}"
        add_node(store, iid, NODE_INSTRUMENT, symbol)
        add_edge(store, node_id, iid, NAMES)
    for axis, value in lead.axes.items():
        aid = f"{NODE_AXIS}:{axis}={value}"
        add_node(store, aid, NODE_AXIS, f"{axis}={value}", axis=axis, value=value)
        add_edge(store, node_id, aid, ON_AXIS)

    late = 0
    if lead.url_or_ref:
        for citer in index.setdefault("cited_urls", {}).pop(lead.url_or_ref, []):
            if new_edge(store, citer, node_id, DERIVES_FROM, via="url"):
                late += 1
    cell_key = lead.provenance.get("cell_key", "")
    if cell_key:
        index["parents"][cell_key] = node_id
        keys = attrs.setdefault("cell_keys", [])
        if cell_key not in keys and len(keys) < MAX_MENTIONS:
            keys.append(cell_key)
    if lead.url_or_ref:
        index["urls"].setdefault(lead.url_or_ref, node_id)
    return node_id, fresh, late


def _index_title(store: dict[str, Any], node_id: str, lead: ls.Lead) -> None:
    """Index CITABLE leads by title so a later claim naming one gets a DERIVES_FROM edge.

    Only papers and competition records: those are what a forum post or an EA description cites,
    and indexing every forum line would make the citation test meaningless as well as slow.
    """
    if lead.kind not in ("paper", "competition"):
        return
    index = store["index"]
    if len(index["titles"]) >= MAX_CITABLE_TITLES:
        return
    key = ls.title_key(lead.claim_text)
    tokens = key.split()
    if len(tokens) < 3 or key in index["titles"]:
        return
    index["titles"][key] = node_id
    index["title_heads"].setdefault(tokens[0], [])
    heads = index["title_heads"][tokens[0]]
    if key not in heads and len(heads) < 200:
        heads.append(key)


def link_claims(store: dict[str, Any], node_id: str, lead: ls.Lead) -> dict[str, int]:
    """DUPLICATES, CONTRADICTS and DERIVES_FROM for one claim against what the graph already has.

    Bucketed (see `_bucket_keys`) and capped, because pairwise comparison is quadratic and this
    runs hourly on the box holding the live terminal. A bucket that overflows is a population the
    desk is no longer fully cross-checking, so the cap being reached is reported.
    """
    made = {DUPLICATES: 0, CONTRADICTS: 0, DERIVES_FROM: 0, "bucket_capped": 0}
    index = store["index"]
    nodes = store["nodes"]
    mine = ls.token_set(lead.claim_text)
    my_dir = ls.direction_of(lead.claim_text)
    my_mech = set(_mechanism_ids_of(lead))
    my_instr = {s.upper() for s in lead.instruments}
    compared: set[str] = set()
    for bucket_key in _bucket_keys(lead):
        bucket: list[str] = index["buckets"].setdefault(bucket_key, [])
        for other_id in bucket:
            if other_id == node_id or other_id in compared:
                continue
            compared.add(other_id)
            other = nodes.get(other_id)
            if other is None:
                continue
            theirs = ls.token_set(str(other.get("label") or ""))
            cosine = ls.token_cosine(mine, theirs)
            if cosine > DUP_COSINE:
                if new_edge(store, node_id, other_id, DUPLICATES, cosine=round(cosine, 3)):
                    made[DUPLICATES] += 1
                continue
            their_dir = int(other["attrs"].get("direction") or 0)
            their_mech = set(other["attrs"].get("mechanisms") or [])
            their_instr = {str(s).upper() for s in (other["attrs"].get("instruments") or [])}
            opposed = (my_dir and their_dir and my_dir == -their_dir
                       and (my_mech & their_mech) and (my_instr & their_instr))
            if opposed and new_edge(store, node_id, other_id, CONTRADICTS,
                                    direction=f"{my_dir:+d} vs {their_dir:+d}"):
                made[CONTRADICTS] += 1
        if node_id not in bucket:
            bucket.append(node_id)
            if len(bucket) > MAX_BUCKET:
                del bucket[0:len(bucket) - MAX_BUCKET]
                made["bucket_capped"] = 1

    for url in ls.urls_in_text(lead.claim_text):
        cited = index["urls"].get(url)
        if cited is None:
            waiting = index.setdefault("cited_urls", {}).setdefault(url, [])
            if node_id not in waiting and len(waiting) < 50:
                waiting.append(node_id)
        elif cited != node_id and new_edge(store, node_id, cited, DERIVES_FROM, via="url"):
            made[DERIVES_FROM] += 1
    for token in mine:
        for key in index["title_heads"].get(token, []):
            cited = index["titles"].get(key)
            if not cited or cited == node_id:
                continue
            tokens = key.split()
            need = max(2, math.ceil(TITLE_MATCH_SHARE * len(tokens)))
            if sum(1 for t in tokens if t in mine) >= need and new_edge(
                    store, node_id, cited, DERIVES_FROM, via="title"):
                made[DERIVES_FROM] += 1
    _index_title(store, node_id, lead)
    return made


# ------------------------------------------------------------------ ingesting cells

def _fate_of(row: Mapping[str, Any]) -> str:
    return str(row.get("fate") or "UNKNOWN").upper()


def _failing_gate(row: Mapping[str, Any]) -> str:
    gates = row.get("gates")
    if not isinstance(gates, Mapping):
        return ""
    for name, value in gates.items():
        if isinstance(value, Mapping) and value.get("passed") is False:
            return str(name)
    return ",".join(str(k) for k in list(gates)[:3])


def ingest_cell(store: dict[str, Any], row: Mapping[str, Any]) -> dict[str, int]:
    """One hypothesis-graph row: its cell, its outcome, its mechanism, and the lead it came from."""
    made = {NODE_CELL: 0, BECAME: 0, JUDGED: 0, TESTED_BY: 0}
    cid_raw = str(row.get("id") or "")
    if not cid_raw:
        return made
    node_id = f"{NODE_CELL}:{cid_raw}"
    fresh = node_id not in store["nodes"]
    family = str(row.get("family") or "")
    symbol = str(row.get("symbol") or "")
    add_node(store, node_id, NODE_CELL, str(row.get("region") or cid_raw)[:200],
             family=family, symbol=symbol, fate=_fate_of(row),
             source=str(row.get("source") or ""), at=str(row.get("at") or ""),
             # `semantic_memory` indexes this same row as `hypothesis:<id>`. Carrying its doc id
             # means the lexical, the semantic and the typed memories all name one cell.
             semantic_doc_id=f"hypothesis:{cid_raw}")
    made[NODE_CELL] = 1 if fresh else 0

    outcome_id = f"{NODE_OUTCOME}:{_fate_of(row)}"
    add_node(store, outcome_id, NODE_OUTCOME, _fate_of(row))
    if new_edge(store, node_id, outcome_id, JUDGED, gate=_failing_gate(row),
                why=str(row.get("why") or "")[:200]):
        made[JUDGED] = 1

    mech = mechanism_of_family(family)
    if mech:
        mid = _mech_id(mech)
        add_node(store, mid, NODE_MECHANISM, mech)
        if new_edge(store, mid, node_id, TESTED_BY, family=family):
            made[TESTED_BY] = 1

    # THE SEED, NOT WHATEVER `parent` HOLDS TODAY. Since 2026-09-17 `parent` carries the CELL a
    # candidate was mutated from when the donor named one, and the miner-row sha this join needs
    # lives in `seed_key`; the 35,199 rows written before that date have only `parent`, and
    # `cell_seed_key` reads both in that order so neither generation loses its BECAME edge.
    parent = ls.cell_seed_key(row)
    index = store["index"]
    if parent:
        lead_id = index["parents"].get(parent)
        if lead_id and new_edge(store, lead_id, node_id, BECAME, via="cell_key"):
            made[BECAME] = 1
        elif not lead_id:
            # THE CELL ARRIVED BEFORE THE LEAD. Remembered so the edge is made the moment the
            # lead is read, rather than lost because the two organs ran in an unlucky order.
            waiting = index["cell_parents"].setdefault(parent, [])
            if node_id not in waiting and len(waiting) < 200:
                waiting.append(node_id)
    return made


def resolve_pending(store: dict[str, Any], lead_node_ids: Mapping[str, str]) -> int:
    """BECAME edges for cells that were read BEFORE the lead they came from."""
    made = 0
    index = store["index"]
    for cell_key, node_id in lead_node_ids.items():
        for cell_id in index["cell_parents"].pop(cell_key, []):
            if new_edge(store, node_id, cell_id, BECAME, via="cell_key"):
                made += 1
    return made


def iter_graph_rows(path: Path, offset: int, max_lines: int) -> tuple[list[dict[str, Any]], int]:
    """Hypothesis-graph rows from `offset` bytes on, and the new offset. Append-only by design;
    a file that SHRANK was rewritten, so the offset resets and the whole ledger is re-read."""
    if not path.exists():
        return [], 0
    try:
        size = path.stat().st_size
    except OSError:
        return [], offset
    start = offset if 0 < offset <= size else 0
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(start)
            for line in fh:
                if len(rows) >= max_lines:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
            new_offset = fh.tell()
    except OSError:
        return [], offset
    return rows, new_offset


# ------------------------------------------------------------------ eviction

def evict_leads(store: dict[str, Any], keep: int | None = None) -> int:
    """Oldest claims out, with their edges, when the store is full. Counted, never silent."""
    keep = MAX_LEAD_NODES if keep is None else keep
    leads = [(nid, str(n["attrs"].get("first_seen") or n.get("at") or ""))
             for nid, n in store["nodes"].items() if n["type"] == NODE_LEAD]
    if len(leads) <= keep:
        return 0
    leads.sort(key=lambda pair: pair[1])
    doomed = {nid for nid, _ in leads[:len(leads) - keep]}
    for nid in doomed:
        store["nodes"].pop(nid, None)
    store["edges"] = {eid: e for eid, e in store["edges"].items()
                      if e["src"] not in doomed and e["dst"] not in doomed}
    index = store["index"]
    index["parents"] = {k: v for k, v in index["parents"].items() if v not in doomed}
    index["urls"] = {k: v for k, v in index["urls"].items() if v not in doomed}
    index["cited_urls"] = {u: [n for n in ids if n not in doomed]
                           for u, ids in index.get("cited_urls", {}).items()}
    index["titles"] = {k: v for k, v in index["titles"].items() if v not in doomed}
    live_titles = set(index["titles"])
    index["title_heads"] = {h: [k for k in keys if k in live_titles]
                            for h, keys in index["title_heads"].items()}
    index["buckets"] = {b: [n for n in ids if n not in doomed]
                        for b, ids in index["buckets"].items()}
    store["counts"]["evicted_leads"] = int(store["counts"]["evicted_leads"]) + len(doomed)
    return len(doomed)


# ------------------------------------------------------------------ queries

def _edges_by(store: Mapping[str, Any]) -> tuple[dict[str, list[dict[str, Any]]],
                                                 dict[str, list[dict[str, Any]]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    inc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in store["edges"].values():
        out[edge["src"]].append(edge)
        inc[edge["dst"]].append(edge)
    return out, inc


def what_do_we_know(term: str, store: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Everything the graph holds about a mechanism, an instrument or an axis value.

    Case-folded substring over ids and labels: the desk names one thing three ways (`XAUUSD`,
    `gold`, `黄金`) and a query answering only to the canonical spelling answers to nobody. An
    empty result means these TOKENS are absent, not that the question was never asked.
    """
    g = dict(store) if store is not None else load_store()
    needle = str(term or "").strip().lower()
    answer: dict[str, Any] = {"term": term, "matched": [], "leads": [], "cells": [],
                              "sources": [], "outcomes": {}, "n_leads": 0, "n_cells": 0,
                              "unmeasured": []}
    if not needle:
        answer["unmeasured"].append("empty query term")
        return answer
    matched = [nid for nid, n in g["nodes"].items()
               if n["type"] in (NODE_MECHANISM, NODE_INSTRUMENT, NODE_AXIS)
               and (needle in nid.lower() or needle in str(n.get("label") or "").lower())]
    answer["matched"] = sorted(matched)
    if not matched:
        answer["unmeasured"].append(f"no mechanism, instrument or axis node matches {term!r}")
        return answer
    out, inc = _edges_by(g)
    matched_set = set(matched)
    leads = {e["src"] for nid in matched for e in inc[nid]
             if e["type"] in (CLAIMS, NAMES, ON_AXIS)}
    cells = {e["dst"] for nid in matched for e in out[nid] if e["type"] == TESTED_BY}
    for lid in leads:
        cells |= {e["dst"] for e in out[lid] if e["type"] == BECAME}
    sources = {e["src"] for lid in leads for e in inc[lid] if e["type"] == PRODUCED}
    fates: Counter[str] = Counter()
    for cid in cells:
        node = g["nodes"].get(cid)
        if node:
            fates[str(node["attrs"].get("fate") or "UNKNOWN")] += 1
    answer.update({
        "n_leads": len(leads), "n_cells": len(cells),
        "leads": sorted(({"id": lid, "claim": str(g["nodes"][lid].get("label") or "")[:200],
                          "kind": str(g["nodes"][lid]["attrs"].get("kind") or ""),
                          "testable": bool(g["nodes"][lid]["attrs"].get("testable")),
                          "n_mentions": int(g["nodes"][lid]["attrs"].get("n_mentions") or 0)}
                         for lid in leads if lid in g["nodes"]),
                        key=lambda r: -int(r["n_mentions"]))[:50],
        "cells": sorted(({"id": cid, "family": str(g["nodes"][cid]["attrs"].get("family") or ""),
                          "symbol": str(g["nodes"][cid]["attrs"].get("symbol") or ""),
                          "fate": str(g["nodes"][cid]["attrs"].get("fate") or "")}
                         for cid in cells if cid in g["nodes"]),
                        key=lambda r: str(r["id"]))[:50],
        "sources": sorted(sources),
        "outcomes": dict(fates),
    })
    if not cells:
        answer["unmeasured"].append(f"{len(leads)} lead(s) about {term!r} and no tested cell")
    if matched_set - {e["src"] for e in g["edges"].values()} and not leads:
        answer["unmeasured"].append("matched nodes carry no lead")
    return answer


def lead_yield_by_source(store: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """Per source: leads produced, how many became cells, how many of those were certified.

    A source with no leads is UNMEASURED and its conversion is None, never 0.0 -- 0.0 reads as
    "measured and worthless" and over a short window that is almost always false (L1.28a).
    """
    g = dict(store) if store is not None else load_store()
    out, _incoming = _edges_by(g)
    rows: list[dict[str, Any]] = []
    for nid, node in g["nodes"].items():
        if node["type"] != NODE_SOURCE:
            continue
        leads = [e["dst"] for e in out[nid] if e["type"] == PRODUCED]
        testable = [lid for lid in leads
                    if g["nodes"].get(lid, {}).get("attrs", {}).get("testable")]
        cells: set[str] = set()
        converted = 0
        for lid in leads:
            became = [e["dst"] for e in out[lid] if e["type"] == BECAME]
            if became:
                converted += 1
            cells |= set(became)
        certified = sum(1 for cid in cells
                        if str(g["nodes"].get(cid, {}).get("attrs", {}).get("fate") or "")
                        == "CERTIFIED")
        rows.append({
            "source_id": node.get("label") or nid.split(":", 1)[1],
            "n_leads": len(leads), "n_testable": len(testable),
            "n_leads_converted": converted, "n_cells": len(cells), "n_certified": certified,
            "conversion": round(converted / len(leads), 4) if leads else None,
            "certified_per_lead": round(certified / len(leads), 4) if leads else None,
        })
    rows.sort(key=lambda r: (-(r["n_certified"] or 0), -(r["n_cells"] or 0), -(r["n_leads"] or 0)))
    return rows


def unconverted_leads(kind: str | None = None, store: Mapping[str, Any] | None = None,
                      limit: int = 500) -> list[dict[str, Any]]:
    """Testable leads that became NOTHING: the intake backlog, named rather than estimated.

    The population the compiler could not turn into an executable identity and the deepening queue
    has not cracked. Never pruned: a lead that has waited six weeks IS the measurement.
    """
    g = dict(store) if store is not None else load_store()
    out, _ = _edges_by(g)
    rows: list[dict[str, Any]] = []
    for nid, node in g["nodes"].items():
        if node["type"] != NODE_LEAD or not node["attrs"].get("testable"):
            continue
        if kind and str(node["attrs"].get("kind") or "") != kind:
            continue
        if any(e["type"] == BECAME for e in out[nid]):
            continue
        rows.append({"id": nid, "kind": str(node["attrs"].get("kind") or ""),
                     "claim": str(node.get("label") or "")[:200],
                     "instruments": list(node["attrs"].get("instruments") or []),
                     "mechanisms": list(node["attrs"].get("mechanisms") or []),
                     "priority": str(node["attrs"].get("priority") or ""),
                     "n_mentions": int(node["attrs"].get("n_mentions") or 0),
                     "seen_at": str(node["attrs"].get("seen_at") or ""),
                     "sources": sorted({e["src"].split(":", 1)[1]
                                        for e in g["edges"].values()
                                        if e["dst"] == nid and e["type"] == PRODUCED})})
    rows.sort(key=lambda r: (-int(r["n_mentions"]), str(r["seen_at"])), reverse=False)
    rows.sort(key=lambda r: -int(r["n_mentions"]))
    return rows[:limit]


def mechanism_coverage(store: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Mechanisms the world told this desk about, against the ones it has actually tested."""
    g = dict(store) if store is not None else load_store()
    out, inc = _edges_by(g)
    covered: list[dict[str, Any]] = []
    untested: list[dict[str, Any]] = []
    for nid, node in g["nodes"].items():
        if node["type"] != NODE_MECHANISM:
            continue
        leads = [e["src"] for e in inc[nid] if e["type"] == CLAIMS]
        cells = [e["dst"] for e in out[nid] if e["type"] == TESTED_BY]
        row = {"mechanism": node.get("label") or nid.split(":", 1)[1],
               "n_leads": len(leads), "n_cells": len(cells)}
        (covered if cells else untested).append(row)
    untested = [r for r in untested if r["n_leads"] > 0]
    untested.sort(key=lambda r: -int(r["n_leads"]))
    covered.sort(key=lambda r: -int(r["n_cells"]))
    return {"tested": covered, "leads_but_no_cells": untested,
            "n_mechanisms": len(covered) + len(untested)}


# ------------------------------------------------------------------ build

def build(*, max_rows: int = MAX_ROWS, store_path: Path | None = None,
          cursor_path: Path | None = None, roots: Sequence[Path] | None = None,
          graph_path: Path | None = None, frontier: Path | None = None,
          asset_class_of: Mapping[str, str] | None = None) -> tuple[dict[str, Any],
                                                                    dict[str, Any],
                                                                    dict[str, Any]]:
    """One pass: new intelligence rows in, new hypothesis-graph rows in, report out.

    Paths default to None and resolve against the module global HERE: a default bound at
    definition time cannot be redirected, and a test that thought it had redirected the desk's
    real graph, cursor and report but had not would write over all three.
    """
    store_path = store_path or STORE
    cursor_path = cursor_path or CURSOR
    roots = roots if roots is not None else INTEL_ROOTS
    graph_path = graph_path or HYPOTHESIS_GRAPH
    frontier = frontier or FRONTIER_QUEUE
    store = load_store(store_path)
    cursor = load_cursor(cursor_path)
    store["at"] = _now()
    seen: set[str] = set(cursor["rows"])
    unmeasured: list[str] = []
    if asset_class_of is None:
        registry = _read_json(UNIVERSE, {})
        asset_class_of = ({str(k).upper(): str(v.get("asset_class") or "")
                           for k, v in registry.items() if isinstance(v, dict)}
                          if isinstance(registry, dict) else {})
        if not asset_class_of:
            unmeasured.append("universe.json unreadable: asset classes are UNMEASURED, "
                              "never assumed")

    paths = intake_paths(roots, frontier)
    if not paths:
        unmeasured.append("no intelligence artifact found under either root")
    n_rows = n_new_claims = n_leads = n_invalid = 0
    links = Counter()
    fresh_cell_keys: dict[str, str] = {}
    by_kind: Counter[str] = Counter()
    for row, seat, run, key in iter_intake(paths, seen, max_rows):
        n_rows += 1
        for lead in ls.leads_from_intelligence_row(row, seat=seat, run=run,
                                                   asset_class_of=asset_class_of):
            if ls.validate(lead):
                n_invalid += 1
                continue
            n_leads += 1
            by_kind[lead.kind] += 1
            node_id, fresh, late = ingest_lead(store, lead)
            n_new_claims += 1 if fresh else 0
            links.update(link_claims(store, node_id, lead))
            links[DERIVES_FROM] += late
            cell_key = lead.provenance.get("cell_key", "")
            if cell_key:
                fresh_cell_keys[cell_key] = node_id
        cursor["rows"].append(key)

    rows, offset = iter_graph_rows(graph_path, int(cursor["graph_offset"]), MAX_GRAPH_LINES)
    if not graph_path.exists():
        unmeasured.append(f"{graph_path.name} absent: BECAME and JUDGED are UNMEASURED")
    cells = Counter()
    for row in rows:
        cells.update(ingest_cell(store, row))
    resolved_late = resolve_pending(store, fresh_cell_keys)
    evicted = evict_leads(store)
    if evicted:
        unmeasured.append(f"{evicted} oldest claim node(s) evicted at the {MAX_LEAD_NODES} cap")
    if len(store["edges"]) >= MAX_EDGES:
        unmeasured.append(f"edge cap {MAX_EDGES} reached: new edges are being refused")
    if links.get("bucket_capped"):
        unmeasured.append(f"{links['bucket_capped']} duplicate bucket(s) hit the {MAX_BUCKET} "
                          "comparison cap: older claims in them are no longer cross-checked")

    cursor.update({"at": store["at"], "graph_offset": offset,
                   "graph_size": graph_path.stat().st_size if graph_path.exists() else 0,
                   "n_rows_seen": int(cursor["n_rows_seen"]) + n_rows})
    if len(cursor["rows"]) > MAX_CURSOR_KEYS:
        cursor["rows"] = cursor["rows"][-MAX_CURSOR_KEYS:]

    report = _report(store, unmeasured=unmeasured, n_rows=n_rows, n_leads=n_leads,
                     n_new_claims=n_new_claims, n_invalid=n_invalid, by_kind=dict(by_kind),
                     links=dict(links), cells=dict(cells), resolved_late=resolved_late,
                     n_graph_rows=len(rows), n_paths=len(paths), max_rows=max_rows)
    return store, cursor, report


def _report(store: Mapping[str, Any], **kw: Any) -> dict[str, Any]:
    by_node: Counter[str] = Counter(n["type"] for n in store["nodes"].values())
    by_edge: Counter[str] = Counter(e["type"] for e in store["edges"].values())
    backlog = unconverted_leads(store=store)
    coverage = mechanism_coverage(store)
    yields = lead_yield_by_source(store)
    mentions = int(store["counts"].get("claim_mentions", 0))
    return {
        "at": store["at"],
        "n_nodes": len(store["nodes"]),
        "n_edges": len(store["edges"]),
        "by_node_type": {t: by_node.get(t, 0) for t in NODE_TYPES},
        "by_edge_type": {t: by_edge.get(t, 0) for t in EDGE_TYPES},
        "n_leads_new": int(kw["n_new_claims"]),
        "n_claims_distinct": by_node.get(NODE_LEAD, 0),
        "n_claim_mentions": mentions,
        "mention_collapse": (round(mentions / by_node[NODE_LEAD], 3)
                             if by_node.get(NODE_LEAD) else None),
        "unconverted_testable_leads": len(backlog),
        "unconverted_leads_by_kind": dict(Counter(str(r["kind"]) for r in backlog)),
        "unconverted_leads_sample": backlog[:25],
        "mechanisms_with_leads_but_no_cells": coverage["leads_but_no_cells"][:40],
        "top_sources_by_yield": yields[:25],
        "intake": {"rows_read": int(kw["n_rows"]), "max_rows": int(kw["max_rows"]),
                   "bound_hit": int(kw["n_rows"]) >= int(kw["max_rows"]),
                   "artifacts_visible": int(kw["n_paths"]),
                   "leads_built": int(kw["n_leads"]), "leads_rejected": int(kw["n_invalid"]),
                   "leads_by_kind": kw["by_kind"]},
        "claim_links": kw["links"],
        "cells": {**kw["cells"], "rows_read": int(kw["n_graph_rows"]),
                  "became_resolved_late": int(kw["resolved_late"])},
        "unmeasured": list(kw["unmeasured"]),
        "rule": RULE,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="W2: one lead schema and a typed knowledge graph over it")
    ap.add_argument("--dry-run", action="store_true", help="measure and print, write nothing")
    ap.add_argument("--max-rows", type=int, default=MAX_ROWS,
                    help=f"intelligence rows this pass may read (default {MAX_ROWS})")
    ap.add_argument("--query", default="", metavar="TERM",
                    help="print what the stored graph knows about TERM and exit")
    args = ap.parse_args(argv)

    if args.query:
        answer = what_do_we_know(args.query)
        print(json.dumps(answer, ensure_ascii=False, indent=1, default=str))
        return 0

    store, cursor, report = build(max_rows=max(1, int(args.max_rows)))
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("unconverted_leads_sample", "top_sources_by_yield",
                                   "mechanisms_with_leads_but_no_cells")},
                     ensure_ascii=False, indent=1, default=str))
    if args.dry_run:
        print("dry run: graph, cursor and report left untouched")
        return 0
    _atomic(STORE, store)
    _atomic(CURSOR, cursor)
    _atomic(REPORT, report)
    print(f"knowledge graph: {report['n_nodes']} nodes, {report['n_edges']} edges -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
