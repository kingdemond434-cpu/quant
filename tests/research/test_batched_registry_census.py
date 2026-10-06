"""Bulk evidence reads must preserve provenance and measured/unknown counts exactly."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from libs.moat import registry as R
from libs.research import regional_parity as RP


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        "CREATE TABLE provenance(id TEXT, from_kind TEXT, from_id TEXT, "
        "to_kind TEXT, to_id TEXT, detail TEXT);"
        "CREATE INDEX ix_prov_to ON provenance(to_kind,to_id);"
        "CREATE TABLE caller_state(value TEXT);"
    )
    yield connection
    connection.close()


def plant(connection, parent, child, number):
    connection.execute("INSERT INTO provenance VALUES (?,?,?,?,?,?)",
                       (str(number), *parent, *child, "detail preserved"))


@pytest.mark.parametrize("depth", [0, 1, 2, 8, 12])
def test_batch_matches_individual_walks_with_duplicates_cycles_and_shared_ancestors(
    database, depth
):
    edges = [(("discovery", "d"), ("cell", "a")),
             (("source", "s"), ("cell", "a")),
             (("discovery", "d"), ("cell", "b")),
             (("source", "s"), ("discovery", "d")),
             (("source", "s"), ("discovery", "d")),
             (("cell", "a"), ("source", "s"))]
    for number, (parent, child) in enumerate(edges):
        plant(database, parent, child, number)
    for number in range(10):
        plant(database, ("chain", str(number + 1)), ("chain", str(number)), number + 20)
    nodes = [("cell", "a"), ("cell", "b"), ("cell", "missing"), ("chain", "0")]
    expected = {node: R.provenance_of(*node, depth=depth, conn=database) for node in nodes}
    graph = R.provenance_graph(nodes, depth=depth, conn=database)
    for node in nodes:
        assert R.walk_provenance_graph(graph, *node, depth=depth) == expected[node]
    assert database.execute("SELECT name FROM sqlite_temp_master").fetchall() == []
    assert database.in_transaction  # caller's inserts remain uncommitted
    database.rollback()
    assert database.execute("SELECT COUNT(*) FROM provenance").fetchone()[0] == 0


def test_graph_error_does_not_commit_or_rollback_caller_state(database):
    database.execute("INSERT INTO caller_state VALUES ('pending')")
    database.execute("DROP TABLE provenance")
    with pytest.raises(sqlite3.OperationalError):
        R.provenance_graph([("cell", "a")], conn=database)
    assert database.in_transaction
    assert database.execute("SELECT value FROM caller_state").fetchone()[0] == "pending"
    assert database.execute("SELECT name FROM sqlite_temp_master").fetchall() == []


@pytest.mark.parametrize("missing", [None, "sources", "discoveries", "research_candidates",
                                     "created_at", "compiled_cells"])
def test_grouped_region_counts_match_native_sql_even_with_partial_schema(
    database, tmp_path, missing
):
    database.executescript(
        "CREATE TABLE sources(country TEXT, first_seen TEXT);"
        "CREATE TABLE discoveries(generator TEXT, created_at TEXT, generated_cells INTEGER, "
        "compiled_cells INTEGER, queued_cells INTEGER, tested_cells INTEGER);"
        "CREATE TABLE research_candidates(generator TEXT);"
    )
    at = datetime(2026, 10, 5, tzinfo=UTC)
    cutoff = (at - timedelta(days=RP.DISCOVERY_WINDOW_DAYS)).isoformat()
    for country in ("JP", "japan", "AE", None, "mena", "MENA"):
        database.execute("INSERT INTO sources VALUES (?,?)", (country, at.isoformat()))
    for generator in ("japan:one", "other:JAPAN:one", "other:mena", "MENA:one", None,
                      "none", "japan:mena:one", "south_asia:one", "southXasia:one"):
        database.execute("INSERT INTO discoveries VALUES (?,?,?,?,?,?)",
                         (generator, at.isoformat(), 1, None, 0, 0))
        database.execute("INSERT INTO discoveries VALUES (?,?,?,?,?,?)",
                         (generator, "2020-01-01", 0, 0, 0, 0))
        database.execute("INSERT INTO research_candidates VALUES (?)", (generator,))
    if missing in ("sources", "discoveries", "research_candidates"):
        database.execute(f"DROP TABLE {missing}")
    elif missing:
        database.execute(f"ALTER TABLE discoveries DROP COLUMN {missing}")
    expected = {fid: RP.region_signals(fid, database, now=at, reports_dir=tmp_path)
                for fid in RP.F.FORESTS}
    with RP._regional_census(database, cutoff) as census:
        for fid in RP.F.FORESTS:
            assert RP.region_signals(fid, database, now=at, reports_dir=tmp_path,
                                     _census=census) == expected[fid]
    assert database.execute("SELECT name FROM sqlite_temp_master").fetchall() == []
    assert database.in_transaction


def test_no_registry_remains_unmeasured():
    with RP._regional_census(None, "2026-01-01") as census:
        assert census is None


def test_shared_tail_credit_matches_original_walk_with_root_cycles(database, monkeypatch):
    from desks.mt5.research import research_roi as roi

    for number, (parent, child) in enumerate([
        (("mechanism", "shared"), ("cell", "a")),
        (("mechanism", "shared"), ("cell", "b")),
        (("source", "s"), ("mechanism", "shared")),
        (("discovery", "d"), ("mechanism", "shared")),
        (("discovery", "d"), ("mechanism", "shared")),
        (("cell", "a"), ("discovery", "d")),
        (("source", "t"), ("cell", "a")),
    ]):
        plant(database, parent, child, number)
    original = R.provenance_of
    rows = {"candidates": [{"id": cid, "symbol": "USDJPY", "family": "carry"}
                            for cid in ("a", "b")]}
    survivors = [{"cell": cid, "symbol": "USDJPY", "family": "carry"}
                 for cid in ("a", "b", "recipe")]
    values = {"a": .1, "b": .2, "recipe": .3}
    expected = roi.credit_walk(database, rows, survivors, values)
    monkeypatch.setattr(R, "provenance_of", lambda kind, cid, **kwargs:
                        original(kind, cid, conn=database))
    fallback = roi.credit_walk(None, rows, survivors, values)
    assert expected == fallback
    assert expected["by_source"]["s"]["survivors"] == 3
    assert expected["by_source"]["t"]["survivors"] == 3
    assert expected["by_discovery"]["d"] == 8


def test_prefix_tail_credit_deduplicates_sources_but_not_discovery_edges(database, monkeypatch):
    from desks.mt5.research import research_roi as roi

    serial = 0
    for cid in (str(i) for i in range(40)):
        for parent in (("source", "overlap"), ("discovery", "direct"),
                       ("mechanism", "shared")):
            plant(database, parent, ("cell", cid), serial)
            serial += 1
    for parent in (("source", "overlap"), ("source", "tail-only"),
                   ("discovery", "direct"), ("discovery", "direct")):
        plant(database, parent, ("mechanism", "shared"), serial)
        serial += 1
    candidates = [{"id": str(i), "symbol": "USDJPY", "family": "carry",
                   "source_id": "overlap", "generator": "g"} for i in range(40)]
    survivors = [{"cell": str(i), "symbol": "USDJPY", "family": "carry"}
                 for i in range(40)]
    values = {str(i): i / 1000 for i in range(40)}
    actual = roi.credit_walk(database, {"candidates": candidates}, survivors, values)
    original = R.provenance_of
    monkeypatch.setattr(R, "provenance_of", lambda kind, cid, **kwargs:
                        original(kind, cid, conn=database))
    reference = roi.credit_walk(None, {"candidates": candidates}, survivors, values)
    assert actual == reference
    assert actual["by_discovery"]["direct"] == 120
    assert actual["by_source"]["overlap"]["survivors"] == 40
    assert actual["by_source"]["tail-only"]["survivors"] == 40
    assert actual["by_source"]["overlap"]["cells"] == [str(i) for i in range(25)]
    assert actual["by_source"]["overlap"]["max_hops"] == 1
    assert actual["by_source"]["tail-only"]["max_hops"] == 5


@pytest.mark.parametrize("seed", range(10))
def test_credit_summary_matches_original_bfs_for_branching_duplicate_cyclic_graphs(
        database, monkeypatch, seed):
    import random

    from desks.mt5.research import research_roi as roi

    rng = random.Random(seed)
    nodes = [("cell", str(i)) for i in range(6)]
    nodes += [("mechanism", str(i)) for i in range(8)]
    nodes += [("source", str(i)) for i in range(4)]
    nodes += [("discovery", str(i)) for i in range(5)]
    for serial in range(95):
        child = rng.choice(nodes)
        parent = rng.choice(nodes)
        plant(database, parent, child, serial)
    candidates = [{"id": str(i), "symbol": "USDJPY", "family": "carry",
                   "source_id": str(i % 4), "generator": str(i % 3)} for i in range(6)]
    survivors = [{"cell": str(i), "symbol": "USDJPY", "family": "carry"}
                 for i in range(6)]
    survivors += [{"cell": "recipe", "symbol": "USDJPY", "family": "carry"}]
    values = {row["cell"]: rng.uniform(-0.2, 0.3) for row in survivors}
    actual = roi.credit_walk(database, {"candidates": candidates}, survivors, values)
    original = R.provenance_of
    monkeypatch.setattr(R, "provenance_of", lambda kind, cid, **kwargs:
                        original(kind, cid, conn=database))
    reference = roi.credit_walk(None, {"candidates": candidates}, survivors, values)
    assert actual == reference


def test_roi_history_count_only_preserves_exact_limits_and_missing_tables(database):
    from desks.mt5.research import research_roi as roi

    database.execute("CREATE TABLE trials_ledger(id TEXT, payload TEXT)")
    database.executemany("INSERT INTO trials_ledger VALUES (?, ?)",
                         [(str(i), "large-unused-payload") for i in range(200003)])
    database.executemany("INSERT INTO provenance(id) VALUES (?)",
                         [(str(i),) for i in range(400003)])
    full = roi.registry_rows(database)
    statements = []
    database.set_trace_callback(statements.append)
    compact = roi.registry_rows(database, history_rows=False)
    counts = roi.registry_history_counts(database)
    database.set_trace_callback(None)
    assert counts == {"trials": len(full["trials"]), "provenance": len(full["provenance"])}
    assert counts == {"trials": 200000, "provenance": 400000}
    assert compact == {name: rows for name, rows in full.items()
                       if name not in ("trials", "provenance")}
    assert not any("SELECT * FROM trials_ledger" in sql or
                   "SELECT * FROM provenance" in sql for sql in statements)
    database.execute("DROP TABLE trials_ledger")
    assert roi.registry_history_counts(database) == {"trials": 0, "provenance": 400000}
