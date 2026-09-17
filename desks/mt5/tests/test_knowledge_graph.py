"""W2 knowledge graph: leads, the sources that produced them, and the cells they became.

Every path is monkeypatched onto a tmp tree, so the suite never reads or writes the desk's own
intelligence roots, hypothesis ledger, graph store, cursor or report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import knowledge_graph as kg  # noqa: E402

from libs.research import lead_schema as ls  # noqa: E402

PAPER_URL = "https://www.aqr.com/tsmom"
PAPER_CLAIM = ("Gold rises after a 12-month positive excess return in 62% of months, and the "
               "moving-average cross is the executable proxy.")

PAPER_ROW = {"kind": "hypothesis", "family": "trend_ma_cross", "symbols": ["XAUUSD"],
             "source": "literature", "title": "Time series momentum in metals and indices",
             "text": PAPER_CLAIM, "url": PAPER_URL, "found_at": "2026-09-10T08:00:00+00:00",
             "published_time": "2012-01-01T00:00:00+00:00"}

FORUM_ROWS = [
    {"source": "reddit", "title": "gold thread",
     "text": f"I read {PAPER_URL} and gold falls after a 12-month positive excess return, so "
             "short it into the fix.",
     "symbols": ["XAUUSD"], "patterns": ["momentum"], "found_at": "2026-09-11T09:00:00+00:00"},
    {"source": "reddit", "title": "repost", "text": PAPER_CLAIM, "symbols": ["XAUUSD"],
     "patterns": ["momentum"], "found_at": "2026-09-11T09:30:00+00:00"},
]

#: A claim nobody has tested, on a mechanism no cell in the fixture names.
CARRY_ROW = {"source": "七禾网", "kind": "story_mechanism", "title": "rebar basis",
             "description": "Rebar basis converges the week before rollover and shorting the "
                            "near contract wins 62% of the time over three sessions.",
             "symbols": ["XAGUSD"], "mechanism_class": "carry", "language": "zh",
             "ground": "七禾网", "ground_kind": "web",
             "url": "https://www.7hcn.com/article/1",
             "available_time": "2026-09-12T00:00:00+00:00"}


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


def _cells(tmp: Path, rows) -> Path:
    graph = tmp / "hypothesis_graph.jsonl"
    _jsonl(graph, rows)
    return graph


def _cell(cell_id: str, parent: str, fate: str = "CERTIFIED", family: str = "trend_ma_cross",
          symbol: str = "XAUUSD", gates: dict | None = None) -> dict:
    return {"id": cell_id, "region": f"{symbol}.{family}{{}}", "symbol": symbol, "family": family,
            "params": {}, "source": "miner:literature", "parent": parent, "fate": fate,
            "why": "fixture", "gates": gates or {}, "at": "2026-09-12T00:00:00+00:00"}


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole synthetic desk: two intelligence roots, a hypothesis ledger, a frontier queue."""
    intel = tmp_path / "intelligence"
    _write(intel / "literature" / "discoveries_1.json", [PAPER_ROW])
    _write(intel / "reddit" / "discoveries_1.json", FORUM_ROWS)
    _write(intel / "china" / "discoveries_1.json", [CARRY_ROW])
    _jsonl(tmp_path / "frontier_queue.jsonl",
           [{"at": "2026-09-05T21:23:30+00:00", "candidate_id": "F-1", "state": "DISCOVERED",
             "firm": "Two Sigma", "capability": "OPS",
             "source_url": "https://example.invalid/post",
             "claim": "market makers know where SPY will trade by 10am",
             "evidence_grade": "D", "source_kind": "public_forum"}])
    monkeypatch.setattr(kg, "STORE", tmp_path / "data" / "graph.json")
    monkeypatch.setattr(kg, "CURSOR", tmp_path / "data" / "cursor.json")
    monkeypatch.setattr(kg, "REPORT", tmp_path / "reports" / "KNOWLEDGE_GRAPH.json")
    monkeypatch.setattr(kg, "INTEL_ROOTS", (intel,))
    monkeypatch.setattr(kg, "HYPOTHESIS_GRAPH", tmp_path / "hypothesis_graph.jsonl")
    monkeypatch.setattr(kg, "FRONTIER_QUEUE", tmp_path / "frontier_queue.jsonl")
    monkeypatch.setattr(kg, "UNIVERSE", tmp_path / "universe.json")
    _write(tmp_path / "universe.json", {"XAUUSD": {"asset_class": "metal"},
                                        "XAGUSD": {"asset_class": "metal"}})
    return tmp_path


def _build(**kw):
    return kg.build(**kw)


def _paper_cell_key() -> str:
    return ls.row_cell_key(PAPER_ROW, "literature")


# ------------------------------------------------------------------ nodes and edges

def test_nodes_and_edges_are_built_from_the_real_intake_shapes(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, _cursor, report = _build()
    assert report["by_node_type"]["lead"] > 0
    assert report["by_node_type"]["source"] >= 4, "literature, reddit, 七禾网, the frontier row"
    assert report["by_node_type"]["instrument"] >= 2, "XAUUSD and XAGUSD"
    assert report["by_node_type"]["mechanism"] >= 2
    assert report["by_node_type"]["cell"] == 1 and report["by_node_type"]["outcome"] == 1
    for edge_type in (kg.CLAIMS, kg.NAMES, kg.PRODUCED, kg.BECAME, kg.JUDGED, kg.TESTED_BY):
        assert report["by_edge_type"][edge_type] > 0, edge_type
    assert report["rule"] == kg.RULE
    assert all(n["type"] in kg.NODE_TYPES for n in store["nodes"].values())
    assert all(e["type"] in kg.EDGE_TYPES for e in store["edges"].values())


def test_an_axis_a_row_declares_becomes_a_node_and_an_edge(desk) -> None:
    _write(desk / "intelligence" / "kimi" / "discoveries_1.json",
           [{"source": "kimi", "title": "t", "text": "XAUUSD rises into the fix in 62% of days.",
             "symbols": ["XAUUSD"], "session": "london", "timeframe": "M15",
             "mechanism_class": "session"}])
    store, _c, report = _build()
    assert report["by_node_type"]["axis"] >= 2
    assert "axis:session=london" in store["nodes"] and "axis:chart=M15" in store["nodes"]
    assert report["by_edge_type"][kg.ON_AXIS] >= 2


def test_became_is_resolved_from_the_compilers_own_parent_hash(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key()),
                  _cell("c2", "a-hash-no-lead-carries", fate="FAILED")])
    store, _c, report = _build()
    became = [e for e in store["edges"].values() if e["type"] == kg.BECAME]
    assert len(became) == 1, "one cell names a lead the desk holds; the other names nothing"
    assert became[0]["dst"] == "cell:c1"
    assert store["nodes"][became[0]["src"]]["attrs"]["kind"] == "paper"
    assert report["cells"]["BECAME"] == 1


def test_a_cell_read_before_its_lead_still_gets_its_became_edge(desk, tmp_path) -> None:
    """The two organs run on different clocks; an unlucky order must not cost provenance."""
    empty = tmp_path / "empty"
    empty.mkdir()
    graph = _cells(desk, [_cell("c1", _paper_cell_key())])
    store, cursor, _r = _build(roots=(empty,), graph_path=graph)
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, cursor)
    assert not [e for e in store["edges"].values() if e["type"] == kg.BECAME]
    assert store["index"]["cell_parents"], "the cell is remembered as waiting for its lead"

    store2, _c2, report2 = _build()
    became = [e for e in store2["edges"].values() if e["type"] == kg.BECAME]
    assert len(became) == 1 and became[0]["dst"] == "cell:c1"
    assert report2["cells"]["became_resolved_late"] == 1


def test_judged_carries_the_gate_the_cell_died_at(desk) -> None:
    _cells(desk, [_cell("c9", _paper_cell_key(), fate="FAILED",
                        gates={"economic_prior": {"passed": False}})])
    store, _c, _r = _build()
    judged = [e for e in store["edges"].values() if e["type"] == kg.JUDGED]
    assert len(judged) == 1
    assert judged[0]["dst"] == "outcome:FAILED"
    assert judged[0]["attrs"]["gate"] == "economic_prior"


# ------------------------------------------------------------------ incremental and bounded

def test_the_cursor_means_the_second_pass_reads_nothing_new(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, cursor, report = _build()
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, cursor)
    assert report["intake"]["rows_read"] == 5

    _store2, cursor2, report2 = _build()
    assert report2["intake"]["rows_read"] == 0, "every row was already processed"
    assert report2["cells"]["rows_read"] == 0, "the ledger resumes from its byte offset"
    assert report2["n_nodes"] == report["n_nodes"], "nothing new, nothing lost"
    assert cursor2["n_rows_seen"] == 5


def test_max_rows_bounds_one_pass_and_the_bound_is_reported(desk) -> None:
    _cells(desk, [])
    store, cursor, report = _build(max_rows=2)
    assert report["intake"]["rows_read"] == 2
    assert report["intake"]["bound_hit"] is True
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, cursor)
    _s2, _c2, report2 = _build(max_rows=100)
    assert report2["intake"]["rows_read"] == 3, "the deferred rows waited, they were not dropped"
    assert report2["intake"]["bound_hit"] is False


def test_a_rewritten_ledger_is_re_read_from_the_top(desk) -> None:
    graph = _cells(desk, [_cell("c1", _paper_cell_key())])
    rows, offset = kg.iter_graph_rows(graph, 0, 10)
    assert len(rows) == 1 and offset > 0
    assert kg.iter_graph_rows(graph, offset, 10) == ([], offset)
    _jsonl(graph, [_cell("c2", "x")])
    again, _o = kg.iter_graph_rows(graph, 10_000, 10)
    assert len(again) == 1, "an offset past the end means the file was rewritten: start over"


def test_eviction_is_bounded_and_counted(desk, monkeypatch) -> None:
    monkeypatch.setattr(kg, "MAX_LEAD_NODES", 2)
    store, _c, report = _build()
    assert report["by_node_type"]["lead"] == 2
    assert any("evicted" in note for note in report["unmeasured"])
    assert store["counts"]["evicted_leads"] >= 1
    assert all(e["src"] in store["nodes"] and e["dst"] in store["nodes"]
               for e in store["edges"].values()), "no edge points at an evicted node"


# ------------------------------------------------------------------ claim-level edges

def test_five_sources_repeating_one_claim_are_one_node_with_five_witnesses(desk) -> None:
    for i, seat in enumerate(("fxblue", "mql5", "tradingview", "quant_se", "youtube")):
        _write(desk / "intelligence" / seat / "discoveries_1.json",
               [{"source": seat, "title": f"t{i}", "text": PAPER_CLAIM, "symbols": ["XAUUSD"],
                 "found_at": "2026-09-13T00:00:00+00:00"}])
    store, _c, report = _build()
    node_id = kg.lead_node_id(ls.from_intelligence_row(PAPER_ROW, seat="literature").dedupe_key())
    node = store["nodes"][node_id]
    assert node["attrs"]["n_mentions"] == 7, "paper + reddit repost + five more tellings"
    produced = [e for e in store["edges"].values()
                if e["type"] == kg.PRODUCED and e["dst"] == node_id]
    assert len(produced) == 7, "one PRODUCED edge per source, one node for the claim"
    assert report["n_claim_mentions"] > report["n_claims_distinct"]
    assert node["attrs"]["kind"] == "paper", "the first telling's kind is not overwritten"


def test_a_near_duplicate_claim_gets_a_duplicates_edge(desk) -> None:
    _write(desk / "intelligence" / "mql5" / "discoveries_1.json",
           [{"source": "mql5", "title": "t", "symbols": ["XAUUSD"],
             "text": PAPER_CLAIM.replace("62%", "62% of the time"),
             "found_at": "2026-09-13T00:00:00+00:00"}])
    store, _c, report = _build()
    dups = [e for e in store["edges"].values() if e["type"] == kg.DUPLICATES]
    assert dups, "same words, one token apart: a near-duplicate, not a second claim"
    assert dups[0]["attrs"]["cosine"] > kg.DUP_COSINE
    assert report["claim_links"][kg.DUPLICATES] >= 1


def test_opposite_claims_on_one_mechanism_and_instrument_contradict(desk) -> None:
    store, _c, report = _build()
    contra = [e for e in store["edges"].values() if e["type"] == kg.CONTRADICTS]
    assert contra, "'gold rises' and 'gold falls' on the same mechanism is a contradiction"
    assert "+1" in contra[0]["attrs"]["direction"] or "-1" in contra[0]["attrs"]["direction"]
    assert report["claim_links"][kg.CONTRADICTS] >= 1


def test_a_forum_post_that_pastes_a_papers_url_derives_from_it(desk) -> None:
    store, _c, report = _build()
    derived = [e for e in store["edges"].values() if e["type"] == kg.DERIVES_FROM]
    assert derived, "the reddit post pastes the paper's url: that is a citation"
    # `via` accumulates every signal that found the same citation, so this is a containment
    # test rather than an equality one: whether the title also matched depends on which artifact
    # the newest-first intake happened to read first, and the pasted link does not.
    assert "url" in derived[0]["attrs"]["via"], "the pasted link is the citation"
    paper = kg.lead_node_id(ls.from_intelligence_row(PAPER_ROW, seat="literature").dedupe_key())
    assert any(e["dst"] == paper for e in derived)
    assert report["claim_links"][kg.DERIVES_FROM] >= 1


def test_a_citation_read_before_the_work_it_cites_is_resolved_when_the_work_lands(desk,
                                                                                 tmp_path):
    """Intake is newest-first, so this is the NORMAL order, not the unlucky one."""
    only_forum = tmp_path / "forum_only"
    _write(only_forum / "reddit" / "discoveries_1.json", FORUM_ROWS)
    store, cursor, report = _build(roots=(only_forum,))
    assert report["claim_links"][kg.DERIVES_FROM] == 0
    assert store["index"]["cited_urls"], "the citation is remembered against the url"
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, cursor)

    store2, _c2, report2 = _build()
    assert report2["claim_links"][kg.DERIVES_FROM] >= 1
    assert [e for e in store2["edges"].values() if e["type"] == kg.DERIVES_FROM]


def test_a_forum_post_naming_a_papers_title_derives_from_it(desk) -> None:
    store, _c, _r = _build()
    kg._atomic(kg.STORE, store)
    kg._atomic(kg.CURSOR, _c)
    _write(desk / "intelligence" / "quant_se" / "discoveries_1.json",
           [{"source": "quant_se", "title": "t", "symbols": ["XAUUSD"],
             "text": "Following gold rises after a 12-month positive excess return months, I "
                     "tried the same rule on silver and it held.",
             "found_at": "2026-09-14T00:00:00+00:00"}])
    store2, _c2, _r2 = _build()
    assert any(e["type"] == kg.DERIVES_FROM and e["attrs"].get("via") == "title"
               for e in store2["edges"].values())


# ------------------------------------------------------------------ the queries

def test_what_do_we_know_answers_with_leads_cells_sources_and_outcomes(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, _c, _r = _build()
    answer = kg.what_do_we_know("XAUUSD", store)
    assert answer["matched"] == ["instrument:XAUUSD"]
    assert answer["n_leads"] >= 2 and answer["n_cells"] == 1
    assert answer["outcomes"] == {"CERTIFIED": 1}
    assert "source:literature" in answer["sources"] and "source:reddit" in answer["sources"]
    assert all("claim" in row and "kind" in row for row in answer["leads"])


def test_what_do_we_know_is_case_folded_and_says_unmeasured_when_it_knows_nothing(desk) -> None:
    store, _c, _r = _build()
    assert kg.what_do_we_know("xauusd", store)["matched"] == ["instrument:XAUUSD"]
    blank = kg.what_do_we_know("platinum", store)
    assert blank["matched"] == [] and blank["n_leads"] == 0
    assert blank["unmeasured"], "absence is a measured answer, never a silent empty set"
    assert kg.what_do_we_know("", store)["unmeasured"]
    carry = kg.what_do_we_know("carry_rollover", store)
    assert carry["n_leads"] == 1 and carry["n_cells"] == 0
    assert any("no tested cell" in note for note in carry["unmeasured"])


def test_lead_yield_by_source_counts_leads_cells_and_certificates(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, _c, _r = _build()
    rows = {r["source_id"]: r for r in kg.lead_yield_by_source(store)}
    assert rows["literature"]["n_leads"] == 1
    assert rows["literature"]["n_cells"] == 1 and rows["literature"]["n_certified"] == 1
    assert rows["literature"]["conversion"] == 1.0
    assert rows["七禾网"]["n_cells"] == 0
    assert rows["七禾网"]["conversion"] == 0.0, "measured: one lead, no cell"
    assert kg.lead_yield_by_source(store)[0]["source_id"] in ("literature", "reddit")


def test_a_source_with_no_leads_is_unmeasured_never_zero(desk) -> None:
    store, _c, _r = _build()
    kg.add_node(store, "source:silent", kg.NODE_SOURCE, "silent")
    row = next(r for r in kg.lead_yield_by_source(store) if r["source_id"] == "silent")
    assert row["n_leads"] == 0
    assert row["conversion"] is None and row["certified_per_lead"] is None


def test_unconverted_leads_names_the_backlog_and_filters_by_kind(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, _c, report = _build()
    backlog = kg.unconverted_leads(store=store)
    ids = {row["id"] for row in backlog}
    paper = kg.lead_node_id(ls.from_intelligence_row(PAPER_ROW, seat="literature").dedupe_key())
    assert paper not in ids, "it became a cell"
    assert all(store["nodes"][i]["attrs"]["testable"] for i in ids)
    assert {row["kind"] for row in backlog} <= set(ls.KINDS)
    stories = kg.unconverted_leads(kind="story", store=store)
    assert stories and all(row["kind"] == "story" for row in stories)
    assert stories[0]["sources"] == ["七禾网"]
    assert report["unconverted_testable_leads"] == len(backlog)
    assert report["unconverted_leads_sample"], "the backlog is NAMED in the report, not counted"


def test_mechanism_coverage_separates_tested_from_merely_claimed(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    store, _c, report = _build()
    coverage = kg.mechanism_coverage(store)
    tested = {row["mechanism"] for row in coverage["tested"]}
    untested = {row["mechanism"] for row in coverage["leads_but_no_cells"]}
    assert "trend_persistence" in tested
    assert "carry_rollover" in untested, "the rebar story named a mechanism nothing has tested"
    assert not tested & untested
    assert [row["mechanism"] for row in report["mechanisms_with_leads_but_no_cells"]]


def test_a_family_is_bridged_onto_the_desks_own_mechanism_vocabulary() -> None:
    assert kg.mechanism_of_family("trend_ma_cross") == "trend_persistence"
    assert kg.mechanism_of_family("session_range_breakout") == "breakout_liquidity"
    assert kg.mechanism_of_family("") == ""
    assert kg._mech_id("momentum") == "mechanism:trend_persistence", "the loose word bridges too"
    assert kg._mech_id("a_word_nobody_registered") == "mechanism:a_word_nobody_registered"


# ------------------------------------------------------------------ the report and the CLI

def test_the_report_carries_every_briefed_field(desk) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    _store, _c, report = _build()
    for field in ("at", "n_nodes", "n_edges", "by_node_type", "by_edge_type", "n_leads_new",
                  "n_claims_distinct", "n_claim_mentions", "unconverted_testable_leads",
                  "mechanisms_with_leads_but_no_cells", "top_sources_by_yield", "unmeasured",
                  "rule"):
        assert field in report, field
    assert set(report["by_node_type"]) == set(kg.NODE_TYPES)
    assert set(report["by_edge_type"]) == set(kg.EDGE_TYPES)
    assert json.loads(json.dumps(report, default=str)), "the report is JSON"


def test_the_cli_writes_the_graph_the_cursor_and_the_report(desk, capsys) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    assert kg.main([]) == 0
    assert kg.STORE.exists() and kg.CURSOR.exists() and kg.REPORT.exists()
    report = json.loads(kg.REPORT.read_text("utf-8"))
    assert report["rule"] == kg.RULE and report["n_nodes"] > 0
    assert "knowledge graph:" in capsys.readouterr().out
    assert json.loads(kg.STORE.read_text("utf-8"))["nodes"]


def test_the_cli_dry_run_measures_and_writes_nothing(desk, capsys) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    assert kg.main(["--dry-run", "--max-rows", "3"]) == 0
    out = capsys.readouterr().out
    assert "dry run" in out and '"n_nodes"' in out
    assert not kg.STORE.exists() and not kg.CURSOR.exists() and not kg.REPORT.exists()


def test_the_cli_query_prints_what_we_know_without_rebuilding(desk, capsys) -> None:
    _cells(desk, [_cell("c1", _paper_cell_key())])
    kg.main([])
    capsys.readouterr()
    assert kg.main(["--query", "XAUUSD"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["term"] == "XAUUSD" and printed["n_leads"] >= 2
    assert printed["matched"] == ["instrument:XAUUSD"]


def test_an_absent_ledger_is_unmeasured_rather_than_a_crash(desk, tmp_path) -> None:
    _store, _c, report = _build(graph_path=tmp_path / "nothing.jsonl")
    assert any("UNMEASURED" in note for note in report["unmeasured"])
    assert report["cells"]["rows_read"] == 0
    assert report["n_nodes"] > 0, "the leads still landed"
