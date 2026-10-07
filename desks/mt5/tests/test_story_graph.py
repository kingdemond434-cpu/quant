"""DATA-29: the story layer. Synthetic news-event streams only; every path is a tmp path.

Three properties carry the item: syndicated copies count ONCE as independent evidence, an
escalation chain is detected link by link, and a revision edge carries the revised figure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import knowledge_graph as kg  # noqa: E402
import story_graph as sg  # noqa: E402


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(kg, "STORE", tmp_path / "data" / "graph.json")
    monkeypatch.setattr(kg, "CURSOR", tmp_path / "data" / "cursor.json")
    monkeypatch.setattr(kg, "REPORT", tmp_path / "reports" / "KNOWLEDGE_GRAPH.json")
    monkeypatch.setattr(kg, "INTEL_ROOTS", (tmp_path / "intelligence",))
    monkeypatch.setattr(kg, "HYPOTHESIS_GRAPH", tmp_path / "hypothesis_graph.jsonl")
    monkeypatch.setattr(kg, "FRONTIER_QUEUE", tmp_path / "frontier_queue.jsonl")
    monkeypatch.setattr(kg, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(kg, "NEWS_EVENT_LOG", tmp_path / "events.jsonl")
    return tmp_path


def _doc(n: int, title: str, *, src: str, kind: str = "war_escalation",
         ents: tuple[str, ...] = ("IR",), eid: str = "ev_ir", minute: int = 0,
         **extra: Any) -> dict[str, Any]:
    return {"id": eid, "item_id": f"i{n}", "kind": kind, "entities": list(ents),
            "title": title, "source_id": src, "at": f"2026-10-01T10:{minute:02d}:00+00:00",
            "fingerprint": f"fp{n}", **extra}


def _log(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _story(report: dict[str, Any]) -> dict[str, Any]:
    stories = report["stories"]["stories"]
    assert stories, report["stories"]
    return dict(stories[0])


def test_syndicated_copies_count_once_as_independent_evidence(desk: Path) -> None:
    wire = "Iran seizes an oil tanker in the Strait of Hormuz, navy says"
    _log(desk / "events.jsonl", [
        _doc(1, wire, src="reuters", copies=3),       # three exact copies the stream collapsed
        _doc(2, wire + ".", src="yahoo", minute=1),   # a near-verbatim syndication
        _doc(3, wire, src="msn", minute=2),
        _doc(4, "Tehran's naval forces detain a foreign-flagged tanker near the strait, the "
             "defence ministry confirms", src="afp", minute=3),
    ])
    store, _cursor, report = kg.build()
    s = _story(report)
    assert s["documents"] == 7                         # 4 logged + 3 collapsed copies
    assert s["evidence_units"] == 2
    assert s["independent_sources"] == 2               # reuters and afp, not yahoo or msn
    assert s["copies"] == 5
    assert s["corroborations"] == 1
    assert report["stories"]["copy_collapse"] == 3.5
    dups = [e for e in store["edges"].values() if e["type"] == kg.DUPLICATES]
    assert {e["dst"] for e in dups} == {"document:i1"}
    nodes = store["nodes"]
    assert nodes["document:i2"]["attrs"]["unit"] == "document:i1"


def test_an_escalation_chain_is_detected_link_by_link(desk: Path) -> None:
    _log(desk / "events.jsonl", [
        _doc(1, "Iran and Israel trade threats over the border", src="a",
             kind="political_instability", eid="ev_pol", ents=("IR", "IL")),
        _doc(2, "Israel launches an air strike on Iran", src="b", eid="ev_war",
             ents=("IR", "IL"), minute=5),
        _doc(3, "Full-scale war: Iran fires missiles at Israel and Saudi Arabia, nuclear alert",
             src="c", eid="ev_war", ents=("IR", "IL", "SA"), minute=9),
    ])
    store, _cursor, report = kg.build()
    s = _story(report)
    assert report["stories"]["n_stories"] == 1, "one story across two events"
    assert s["events"] == 2
    assert s["escalations"] == 2
    esc = {(e["src"], e["dst"]) for e in store["edges"].values() if e["type"] == sg.ESCALATES}
    assert esc == {("document:i2", "document:i1"), ("document:i3", "document:i2")}
    last = next(e for e in store["edges"].values()
                if e["type"] == sg.ESCALATES and e["src"] == "document:i3")
    assert last["attrs"]["new_entities"] == ["SA"]
    assert last["attrs"]["severity_to"] > last["attrs"]["severity_from"]
    follow = [e for e in store["edges"].values()
              if e["type"] == sg.FOLLOW_UP and e["attrs"].get("level") == "event"]
    assert [(e["src"], e["dst"]) for e in follow] == [("event:ev_war", "event:ev_pol")]


def test_a_revision_edge_links_the_revised_figure(desk: Path) -> None:
    _log(desk / "events.jsonl", [
        _doc(1, "US Q2 GDP grew 2.1% annualised", src="bea", kind="labour_surprise",
             eid="ev_gdp", ents=("US",)),
        _doc(2, "US Q2 GDP revised down to 1.6% annualised", src="bea", kind="labour_surprise",
             eid="ev_gdp", ents=("US",), minute=30),
    ])
    store, _cursor, report = kg.build()
    (rev,) = [e for e in store["edges"].values() if e["type"] == sg.REVISES]
    assert (rev["src"], rev["dst"]) == ("document:i2", "document:i1")
    assert rev["attrs"]["before"] == [[2.1, "%"]] and rev["attrs"]["after"] == [[1.6, "%"]]
    assert rev["attrs"]["worded"] is True
    s = _story(report)
    assert s["revisions"] == 1 and s["evidence_units"] == 2
    assert s["independent_sources"] == 1, "one agency revising itself is one source"


def test_a_denial_is_a_contradiction_and_a_follow_up(desk: Path) -> None:
    _log(desk / "events.jsonl", [
        _doc(1, "Saudi Arabia raises oil output sharply", src="wire1", kind="supply_disruption",
             eid="ev_sa", ents=("SA",)),
        _doc(2, "Saudi energy ministry denies any change to oil output", src="spa",
             kind="supply_disruption", eid="ev_sa", ents=("SA",), minute=10),
    ])
    store, _cursor, report = kg.build()
    types = {e["type"] for e in store["edges"].values()
             if e["src"] == "document:i2" and e["dst"] == "document:i1"}
    assert {kg.CONTRADICTS, sg.FOLLOW_UP} <= types
    assert _story(report)["contradictions"] == 1


def test_a_reread_log_changes_nothing_and_a_new_row_is_read_once(desk: Path) -> None:
    log = desk / "events.jsonl"
    _log(log, [_doc(1, "Iran seizes a tanker", src="reuters")])
    store, cursor, _report = kg.build()
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, cursor)
    _log(log, [_doc(2, "Iranian navy holds a second tanker", src="afp", minute=4)])
    store2, _cursor2, report2 = kg.build()
    assert report2["stories"]["rows_read"] == 1
    assert _story(report2)["documents"] == 2
    again = sg.ingest_document(store2, _doc(2, "Iranian navy holds a second tanker", src="afp"),
                               add_node=kg.add_node, add_edge=kg.add_edge, new_edge=kg.new_edge)
    assert again["documents"] == 0


def test_an_absent_log_is_unmeasured_not_an_empty_world(desk: Path) -> None:
    _store, _cursor, report = kg.build()
    assert report["stories"]["n_stories"] == 0
    assert "UNMEASURED" in report["stories"]["event_log"]
    assert report["stories"]["copy_collapse"] == "UNMEASURED"
    assert any("story layer is UNMEASURED" in u for u in report["unmeasured"])


def test_a_quiet_story_is_not_revived_a_month_later(desk: Path) -> None:
    old = _doc(1, "Iran seizes a tanker", src="reuters")
    new = _doc(2, "Iran seizes another tanker", src="reuters", eid="ev_ir2")
    new["at"] = "2026-11-15T10:00:00+00:00"
    _log(desk / "events.jsonl", [old, new])
    _store, _cursor, report = kg.build()
    assert report["stories"]["n_stories"] == 2


def test_stale_stories_leave_whole_at_the_cap(desk: Path) -> None:
    rows = [_doc(i, f"Story {i} about Iran", src="s", eid=f"ev{i}", ents=(f"X{i}",))
            for i in range(6)]
    for i, r in enumerate(rows):
        r["at"] = f"2026-10-0{i + 1}T00:00:00+00:00"
    _log(desk / "events.jsonl", rows)
    store, _cursor, _report = kg.build()
    assert sg.evict_stories(store, keep=4) == 2
    left = {n["attrs"]["story_id"] for n in store["nodes"].values() if n["type"] == "document"}
    assert len(left) == 4
    assert all(e["src"] in store["nodes"] and e["dst"] in store["nodes"]
               for e in store["edges"].values())


def _six_stories(desk: Path) -> dict[str, Any]:
    rows = [_doc(i, f"Story {i} about Iran", src="s", eid=f"ev{i}", ents=(f"X{i}",))
            for i in range(6)]
    for i, r in enumerate(rows):
        r["at"] = f"2026-10-0{i + 1}T00:00:00+00:00"
    _log(desk / "events.jsonl", rows)
    store, _cursor, _report = kg.build()
    return store


def test_evicted_stories_are_preserved_whole_in_the_archive(desk: Path) -> None:
    store = _six_stories(desk)
    before_nodes = dict(store["nodes"])
    before_edges = dict(store["edges"])
    archive = desk / "data" / sg.STORY_ARCHIVE_NAME
    assert sg.evict_stories(store, keep=4, archive=archive) == 2
    lines = [json.loads(x) for x in archive.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    archived_nodes = {nid: n for row in lines for nid, n in row["nodes"].items()}
    archived_edges = {k: e for row in lines for k, e in row["edges"].items()}
    # Nothing left the store that the archive does not hold, node for node and edge for edge.
    gone_nodes = set(before_nodes) - set(store["nodes"])
    gone_edges = set(before_edges) - set(store["edges"])
    assert gone_nodes and gone_nodes == set(archived_nodes)
    assert all(archived_nodes[n] == before_nodes[n] for n in gone_nodes)
    assert gone_edges and gone_edges <= set(archived_edges)
    # The two stalest stories are the ones archived, each with its documents and its event.
    kinds = sorted(n["type"] for row in lines for n in row["nodes"].values())
    assert kinds.count("story") == 2 and kinds.count("document") == 2
    assert kinds.count("event") == 2
    assert all(row["index"]["story_of_event"] for row in lines)


def test_a_refused_archive_write_evicts_nothing(desk: Path) -> None:
    store = _six_stories(desk)
    n_nodes, n_edges = len(store["nodes"]), len(store["edges"])
    blocker = desk / "not_a_dir"
    blocker.write_text("x", encoding="utf-8")
    assert sg.evict_stories(store, keep=4, archive=blocker / "archive.jsonl") == 0
    assert (len(store["nodes"]), len(store["edges"])) == (n_nodes, n_edges)
    assert store["counts"]["story_archive_failures"] == 1


def test_build_archives_beside_the_store_and_a_dry_run_writes_nothing(
        desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "MAX_DOCUMENTS", 4)
    _six_stories(desk)  # build() with the real default: archive beside the redirected store
    archive = desk / "data" / sg.STORY_ARCHIVE_NAME
    assert len(archive.read_text(encoding="utf-8").splitlines()) == 2
    archive.unlink()
    kg.build(cursor_path=desk / "data" / "other_cursor.json", archive_stories=False)
    assert not archive.exists()
