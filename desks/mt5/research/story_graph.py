"""THE STORY LAYER of the knowledge graph: documents, events and stories, and the typed edges
between them (DATA-29).

WHY IT EXISTS. The lead graph (`knowledge_graph.py`) knows that five sources telling one research
claim are one claim with five witnesses. The news stream did not have the same arithmetic one
level up. A wire that is re-filed by forty aggregators, a ministry that revises a figure, a
skirmish that becomes a war and a denial of yesterday's headline are each a DIFFERENT relation
between documents, and the desk needs to know which, because only some of them are evidence:

    document --REPORTS-->     event       a document's claim about one (kind, entities) event
    event    --IN_STORY-->    story       events grouped over time by shared entities
    document --FOLLOW_UP-->   document    a later document on the same event
    document --CORROBORATES-> document    an INDEPENDENT source repeating the claim
    document --CONTRADICTS--> document    the opposite direction, or a denial
    document --REVISES-->     document    the same event with changed figures
    document --ESCALATES-->   document    severity or scope rose past the story's running peak
    document --DUPLICATES-->  document    a near-verbatim copy with the same figures
    event    --FOLLOW_UP-->   event       a new event joining a running story

COPIES ARE NOT INDEPENDENT EVIDENCE. A document that copies an earlier one, whether it is
syndicated, re-filed or a fingerprint-identical item the stream already collapsed, joins that
document's EVIDENCE UNIT. A story's `independent_sources` counts the distinct sources behind its
evidence units, not its documents. Forty aggregators carrying one Reuters line therefore count as
one source. A second outlet that wrote its own account counts as two.

The relations are read off DATA-30's novelty components (`event_ontology.novelty_components`)
computed against the event's own earlier documents: `confirmation` for CORROBORATES,
`contradiction` for CONTRADICTS and `revision` for REVISES. One definition of each relation
serves the whole desk.

It scores nothing and sizes nothing. Stdlib plus the ontology, persisted inside the knowledge
graph's own store (`data/knowledge_graph/graph.json`) and reported in `KNOWLEDGE_GRAPH.json`
under `stories`.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from libs.research import event_ontology as eo

NODE_DOCUMENT, NODE_EVENT, NODE_STORY = "document", "event", "story"
STORY_NODE_TYPES = (NODE_DOCUMENT, NODE_EVENT, NODE_STORY)
REPORTS, IN_STORY, FOLLOW_UP = "REPORTS", "IN_STORY", "FOLLOW_UP"
CORROBORATES, REVISES, ESCALATES = "CORROBORATES", "REVISES", "ESCALATES"
#: Shared with the lead graph: the same words mean the same relation at both levels.
DUPLICATES, CONTRADICTS = "DUPLICATES", "CONTRADICTS"
STORY_EDGE_TYPES = (REPORTS, IN_STORY, FOLLOW_UP, CORROBORATES, REVISES, ESCALATES)

#: A story goes quiet after this many hours with no new event on any of its entities. The next
#: event on those entities opens a NEW story rather than reviving one from last month.
STORY_GAP_H = 7 * 24.0
#: Earlier documents of one event each new document is compared against (the newest N). Pairwise
#: work is quadratic, and hitting the bound is counted in the report.
MAX_EVENT_DOCS = 60
#: Document nodes the store holds. Past it the stalest STORIES leave whole, with their events,
#: documents and edges, and the eviction is counted.
MAX_DOCUMENTS = 40_000
#: Rise over the story's running peak severity that counts as an escalation.
ESCALATION_STEP = 0.1
#: Story rows the report names (the counts cover every story).
REPORT_STORIES = 25
DOC_TEXT_CHARS = 400


def _parse(ts: Any) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)


def _hash(*parts: Any) -> str:
    blob = "\x00".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def document_id(row: Mapping[str, Any]) -> str:
    ref = (row.get("item_id") or row.get("doc_id") or row.get("observation_id")
           or _hash(row.get("source_id"), row.get("title") or row.get("claim"), row.get("at")))
    return f"{NODE_DOCUMENT}:{ref}"


def _index(store: dict[str, Any]) -> dict[str, Any]:
    index: dict[str, Any] = store["index"]
    for key in ("story_of_event", "event_docs", "entity_stories", "doc_fps"):
        index.setdefault(key, {})
    store["counts"].setdefault("evicted_stories", 0)
    return index


def _as_row(node_id: str, node: Mapping[str, Any]) -> dict[str, Any]:
    """A stored document node, back in the shape `novelty_components` reads."""
    a = node.get("attrs") or {}
    return {"doc_id": node_id, "claim": node.get("label") or "", "kind": a.get("kind"),
            "entities": a.get("entities") or [], "event_id": a.get("event_id"),
            "source_id": a.get("source_id"), "figures": a.get("figures") or [],
            "direction": a.get("direction"), "stance": a.get("stance"),
            "severity": a.get("severity")}


def _story_for(store: dict[str, Any], eid: str, ents: Iterable[str], at: datetime | None
               ) -> tuple[str, bool]:
    """(story node id, whether it is new). An event keeps its story; a new event joins the most
    recently active story on any of its entities, unless that story has gone quiet."""
    index = _index(store)
    known = index["story_of_event"].get(eid)
    if known and known in store["nodes"]:
        return known, False
    best, best_at = "", None
    for ent in ents:
        sid = index["entity_stories"].get(ent)
        node = store["nodes"].get(sid or "")
        if node is None:
            continue
        last = _parse(node["attrs"].get("last_at"))
        if at is not None and last is not None and (at - last).total_seconds() > STORY_GAP_H * 3600:
            continue
        if best_at is None or (last is not None and last > best_at):
            best, best_at = str(sid), last
    if best:
        return best, False
    return f"{NODE_STORY}:{_hash(eid, at.isoformat() if at else '')}", True


def _bump(node: dict[str, Any], key: str, by: int = 1) -> None:
    node["attrs"][key] = int(node["attrs"].get(key, 0)) + by


def ingest_document(store: dict[str, Any], row: Mapping[str, Any], *, add_node: Any,
                    add_edge: Any, new_edge: Any) -> dict[str, int]:
    """One news-event row into the story layer. Idempotent: a re-read row changes nothing.

    The three graph writers are the knowledge graph's own (`add_node`, `add_edge`, `new_edge`),
    so a story node obeys the same caps, first-seen rules and edge identity as a lead node.
    """
    made = dict.fromkeys((*STORY_EDGE_TYPES, DUPLICATES, CONTRADICTS, "documents", "copies",
                          "new_stories", "event_docs_capped"), 0)
    did = document_id(row)
    if did in store["nodes"]:
        return made
    index = _index(store)
    kind = str(row.get("kind") or "other")
    ents = sorted({str(e).strip().upper() for e in (row.get("entities") or ()) if str(e).strip()})
    eid = str(row.get("id") or row.get("event_id") or eo.event_id(kind, ents))
    at_s = str(row.get("knowable_at") or row.get("at") or row.get("seen_at") or store["at"])
    at = _parse(at_s)
    text = str(row.get("claim") or row.get("title") or row.get("text") or "")
    source = str(row.get("source_id") or "")
    severity = eo.severity_level({**row, "kind": kind, "entities": ents, "claim": text})
    figures = row.get("figures")
    if not isinstance(figures, list):
        figures = [list(f) for f in eo.figures_in(text)]
    doc_row = {"doc_id": did, "claim": text, "kind": kind, "entities": ents, "event_id": eid,
               "source_id": source, "figures": figures, "direction": row.get("direction"),
               "stance": row.get("stance"), "severity": severity}

    # The event, and the story it belongs to.
    event_node_id = f"{NODE_EVENT}:{eid}"
    # Existing story-layer nodes are read, never re-added: `add_node` overwrites attributes with
    # any non-empty value, and a running peak or a first_at must not be reset by the next row.
    event_node = store["nodes"].get(event_node_id) or add_node(
        store, event_node_id, NODE_EVENT, f"{kind} {','.join(ents)}", kind=kind,
        entities=ents, first_at=at_s)
    story_id, new_story = _story_for(store, eid, ents, at)
    story = store["nodes"].get(story_id) or add_node(
        store, story_id, NODE_STORY, f"{kind} {','.join(ents)}".strip(), first_at=at_s,
        last_at=at_s)
    sa = story["attrs"]
    for key in ("entities", "kinds", "sources"):
        sa.setdefault(key, [])
    if new_story:
        made["new_stories"] += 1
    joined_story = index["story_of_event"].get(eid) != story_id
    if joined_story:
        prior_events = [e for e, s in index["story_of_event"].items() if s == story_id]
        index["story_of_event"][eid] = story_id
        add_edge(store, event_node_id, story_id, IN_STORY)
        _bump(story, "events")
        if prior_events:
            latest = f"{NODE_EVENT}:{prior_events[-1]}"
            if new_edge(store, event_node_id, latest, FOLLOW_UP, level="event"):
                made[FOLLOW_UP] += 1
                _bump(story, "follow_ups")
    for ent in ents:
        index["entity_stories"][ent] = story_id
    last = _parse(sa.get("last_at"))
    if at is not None and (last is None or at >= last):
        sa["last_at"] = at_s
    for ent in ents:
        if ent not in sa["entities"]:
            sa["entities"].append(ent)
    if kind not in sa["kinds"]:
        sa["kinds"].append(kind)
    event_node["attrs"]["last_at"] = at_s

    # The document, compared against the event's earlier documents.
    prior_ids = [d for d in index["event_docs"].get(eid, []) if d in store["nodes"]]
    priors = [_as_row(d, store["nodes"][d]) for d in prior_ids]
    comps = eo.novelty_components(doc_row, priors)
    fp = str(row.get("fingerprint") or "")
    copy_of = index["doc_fps"].get(fp) if fp else None
    if copy_of not in store["nodes"]:
        copy_of = None
    sem = comps["semantic"]
    if copy_of is None and priors and sem.get("nearest"):
        nearest = str(sem["nearest"])
        near_node = store["nodes"].get(nearest)
        if near_node is not None and eo.is_copy(
                float(sem.get("similarity") or 0.0),
                [tuple(f) for f in figures],
                [tuple(f) for f in (near_node["attrs"].get("figures") or [])]):
            copy_of = nearest
    unit = (store["nodes"][copy_of]["attrs"].get("unit") or copy_of) if copy_of else did
    vector = {k: v.get("score") for k, v in comps.items()}
    add_node(store, did, NODE_DOCUMENT, text[:DOC_TEXT_CHARS], kind=kind, entities=ents,
             event_id=eid, story_id=story_id, source_id=source, seen_at=at_s,
             figures=figures, direction=doc_row["direction"] or comps["contradiction"].get(
                 "direction"), stance=doc_row["stance"] or comps["policy_state"].get("stance"),
             severity=severity, unit=unit, copy_of=copy_of or "", novelty_vector=vector,
             copies=int(row.get("copies") or 0))
    made["documents"] += 1
    add_edge(store, did, event_node_id, REPORTS)
    if source:
        sid = f"source:{source}"
        add_node(store, sid, "source", source)
        add_edge(store, sid, did, "PRODUCED", kind="news")
    # A syndicated copy the stream collapsed before the log is a document too, never a source.
    extra = max(0, int(row.get("copies") or 0))
    _bump(story, "documents", 1 + extra)
    made["copies"] += extra
    _bump(story, "copies", extra)
    if fp:
        index["doc_fps"].setdefault(fp, did)

    if copy_of:
        if new_edge(store, did, copy_of, DUPLICATES, similarity=sem.get("similarity")):
            made[DUPLICATES] += 1
        made["copies"] += 1
        _bump(story, "copies")
    else:
        _bump(story, "evidence_units")
        if source and source not in sa["sources"]:
            sa["sources"].append(source)
        independent = [p for p in prior_ids if not store["nodes"][p]["attrs"].get("copy_of")]
        if independent and new_edge(store, did, independent[-1], FOLLOW_UP, level="document"):
            made[FOLLOW_UP] += 1
            _bump(story, "follow_ups")
        conf = comps["confirmation"]
        if conf.get("score") == 1.0:
            # One CORROBORATES edge per earlier EVIDENCE UNIT, to the unit's original: agreeing
            # with a wire and its three syndications is agreeing with one source, once.
            units: list[str] = []
            for ref in conf.get("confirms") or []:
                node = store["nodes"].get(str(ref))
                if node is None:
                    continue
                root = str(node["attrs"].get("unit") or ref)
                root_node = store["nodes"].get(root)
                if (root_node is not None and root not in units
                        and root_node["attrs"].get("source_id") != source):
                    units.append(root)
            for root in units:
                if new_edge(store, did, root, CORROBORATES):
                    made[CORROBORATES] += 1
                    _bump(story, "corroborations")
        con = comps["contradiction"]
        if (con.get("score") == 1.0 and con.get("contradicts") in store["nodes"]
                and new_edge(store, did, str(con["contradicts"]), CONTRADICTS,
                             direction=f"{con.get('prior')} vs {con.get('direction')}")):
            made[CONTRADICTS] += 1
            _bump(story, "contradictions")
        rev = comps["revision"]
        if ((rev.get("score") or 0.0) >= 0.6 and rev.get("revised_ref") in store["nodes"]
                and new_edge(store, did, str(rev["revised_ref"]), REVISES,
                             before=rev.get("before"), after=rev.get("after"),
                             worded=rev.get("worded"))):
            made[REVISES] += 1
            _bump(story, "revisions")

    # Escalation: past the story's running peak by a step, or the same peak reaching further.
    peak = float(sa.get("peak_severity") or 0.0)
    peak_doc = str(sa.get("peak_doc") or "")
    peak_node = store["nodes"].get(peak_doc)
    peak_ents = set(peak_node["attrs"].get("entities") or []) if peak_node else set()
    wider = bool(peak_node) and severity >= peak and bool(set(ents) - peak_ents)
    rose = severity >= peak + ESCALATION_STEP or wider
    if (peak_node is not None and not copy_of and rose
            and new_edge(store, did, peak_doc, ESCALATES, severity_from=peak,
                         severity_to=severity, new_entities=sorted(set(ents) - peak_ents))):
        made[ESCALATES] += 1
        _bump(story, "escalations")
    if peak_node is None or severity > peak or (wider and not copy_of):
        sa["peak_severity"], sa["peak_doc"] = severity, did

    docs = index["event_docs"].setdefault(eid, [])
    docs.append(did)
    if len(docs) > MAX_EVENT_DOCS:
        del docs[0:len(docs) - MAX_EVENT_DOCS]
        made["event_docs_capped"] = 1
    return made


def evict_stories(store: dict[str, Any], keep: int | None = None) -> int:
    """The stalest stories out whole when documents pass the cap. Counted, never silent."""
    keep = MAX_DOCUMENTS if keep is None else keep
    nodes = store["nodes"]
    n_docs = sum(1 for n in nodes.values() if n["type"] == NODE_DOCUMENT)
    if n_docs <= keep:
        return 0
    stories = sorted((str(n["attrs"].get("last_at") or ""), sid) for sid, n in nodes.items()
                     if n["type"] == NODE_STORY)
    doomed_stories: set[str] = set()
    freed = 0
    by_story: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        if n["type"] == NODE_DOCUMENT:
            by_story.setdefault(str(n["attrs"].get("story_id") or ""), []).append(nid)
    for _last, sid in stories:
        if n_docs - freed <= keep:
            break
        doomed_stories.add(sid)
        freed += len(by_story.get(sid, []))
    index = _index(store)
    doomed_events = {e for e, s in index["story_of_event"].items() if s in doomed_stories}
    doomed = set(doomed_stories) | {f"{NODE_EVENT}:{e}" for e in doomed_events}
    for sid in doomed_stories:
        doomed.update(by_story.get(sid, []))
    for nid in doomed:
        nodes.pop(nid, None)
    store["edges"] = {k: e for k, e in store["edges"].items()
                      if e["src"] not in doomed and e["dst"] not in doomed}
    index["story_of_event"] = {e: s for e, s in index["story_of_event"].items()
                               if s not in doomed_stories}
    index["event_docs"] = {e: d for e, d in index["event_docs"].items() if e not in doomed_events}
    index["entity_stories"] = {k: s for k, s in index["entity_stories"].items()
                               if s not in doomed_stories}
    index["doc_fps"] = {k: d for k, d in index["doc_fps"].items() if d not in doomed}
    store["counts"]["evicted_stories"] = int(store["counts"]["evicted_stories"]) + len(
        doomed_stories)
    return len(doomed_stories)


_COUNTS = ("documents", "evidence_units", "copies", "events", "follow_ups", "corroborations",
           "contradictions", "revisions", "escalations")


def story_rows(store: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every story with its counts, most documents first. Independent sources are the distinct
    sources behind EVIDENCE UNITS, never the number of documents."""
    out = []
    for sid, node in store["nodes"].items():
        if node["type"] != NODE_STORY:
            continue
        a = node["attrs"]
        row = {"story_id": sid, "label": node.get("label") or "", "first_at": a.get("first_at"),
               "last_at": a.get("last_at"), "kinds": list(a.get("kinds") or []),
               "entities": list(a.get("entities") or []),
               "independent_sources": len(a.get("sources") or []),
               "peak_severity": a.get("peak_severity")}
        row.update({k: int(a.get(k, 0)) for k in _COUNTS})
        out.append(row)
    out.sort(key=lambda r: (-r["documents"], str(r["story_id"])))
    return out


def story_report(store: Mapping[str, Any], made: Mapping[str, int], *, rows_read: int,
                 log_present: bool) -> dict[str, Any]:
    stories = story_rows(store)
    docs = sum(r["documents"] for r in stories)
    units = sum(r["evidence_units"] for r in stories)
    return {
        "rule": ("copies are not independent evidence: a story counts its independent sources "
                 "behind evidence units, never its documents"),
        "event_log": ("present" if log_present
                      else "absent: the story layer is UNMEASURED, not empty"),
        "rows_read": int(rows_read),
        "n_stories": len(stories),
        "documents": docs, "evidence_units": units,
        "copy_collapse": round(docs / units, 3) if units else eo.UNMEASURED,
        "edges_made_this_pass": {k: int(v) for k, v in made.items()},
        "evicted_stories": int(store["counts"].get("evicted_stories", 0)),
        "stories": stories[:REPORT_STORIES],
    }
