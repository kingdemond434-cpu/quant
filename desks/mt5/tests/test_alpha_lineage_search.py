"""A genealogy that reports the wrong gap sends the desk's next hour to ground it already covered.

This organ's whole value is that it can say which MOVES were never made, so the failure mode that
matters is not a crash -- it is a confident finding that is false. Each test below plants a forest
where the answer is known by construction and asserts the organ reads it back:

  * THE FOREST IS THE PARENT EDGES. A parent this record does not hold is a VIRTUAL root (the
    miner's own seed string), and the strategies sharing one are the finding -- dropping them
    would delete the sixth finding entirely.
  * AN EDGE IS CLASSIFIED, NOT COUNTED. `transfer`, `session` and `parameter_neighbourhood` are
    three different moves and a forest of 35,199 rows can be one move repeated; the axes with NO
    edge are the report, and a family whose session axis WAS walked must not appear under it.
  * THE ABANDONED BRANCH IS AN UPPER BOUND. Wilson's, above the family median, no descendants,
    older than the window. A FAILED leaf sits AT the median of a family of failures and is not a
    finding; the certified leaf nobody ever mutated is.
  * THE NEIGHBOURHOOD IS THE FAMILY'S OWN DECLARED GRID. Not a guess at bounds -- a family with
    no declared grid is UNMEASURED and is never reported as explored.
  * IT DONATES NOTHING. Every finding is a DISCOVERY in state UNPROCESSED naming the parent cell
    and the untried move, and a second run on an unchanged forest records nothing new.

The forest is small and entirely on tmp_path, and every family name is a REAL desk family so the
mechanism vocabulary under test is `axis_registry`'s own.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

als = pytest.importorskip("research.alpha_lineage_search", reason="the organ ships with the desk")
ar = pytest.importorskip("research.axis_registry")
reg = pytest.importorskip("libs.moat.registry")

NOW = datetime.now(tz=UTC)


def _at(days: float) -> str:
    return (NOW - timedelta(days=days)).isoformat()


def node(nid: str, parent: str, symbol: str, family: str, params: dict[str, Any], fate: str,
         days: float) -> dict[str, Any]:
    return {"id": nid, "parent": parent, "symbol": symbol, "family": family, "params": params,
            "fate": fate, "source": "test", "at": _at(days), "gates": {}}


#: THE PLANTED FOREST. Three roots, twelve nodes, and every finding is true by construction.
#:
#:   trend_ma_cross  r1 -> t1 (transfer), t2 (session), t3 (parameter_neighbourhood)
#:                   so six of the nine axes have NO edge, and `session` must NOT be one of them
#:   turn_of_month   tmR -> tm1..tm4, every edge a HORIZON move, every node XAUUSD, session all
#:                   tm3 is CERTIFIED and childless: the branch abandoned above its family median
#:   level_breakout  r2 -> s1 (same family), s2 (overnight_gap_decay) -- one ancestor, two
#:                   families, which is the pair the allocator sizes as independent
FOREST: list[dict[str, Any]] = [
    node("r1", "seed:miner", "XAUUSD", "trend_ma_cross", {"ttl_bars": 12}, "FAILED", 60),
    node("t1", "r1", "XAGUSD", "trend_ma_cross", {"ttl_bars": 12}, "FAILED", 55),
    node("t2", "r1", "XAUUSD", "trend_ma_cross", {"ttl_bars": 12, "session": "asia"}, "FAILED", 55),
    node("t3", "r1", "XAUUSD", "trend_ma_cross", {"ttl_bars": 12, "fast_ema": 20}, "FAILED", 55),
    node("tmR", "seed:tom", "XAUUSD", "turn_of_month", {"days_before": 2, "ttl_bars": 48},
         "FAILED", 60),
    node("tm1", "tmR", "XAUUSD", "turn_of_month", {"days_before": 2, "ttl_bars": 24}, "FAILED", 40),
    node("tm2", "tmR", "XAUUSD", "turn_of_month", {"days_before": 2, "ttl_bars": 96}, "FAILED", 40),
    node("tm3", "tmR", "XAUUSD", "turn_of_month", {"days_before": 2, "ttl_bars": 6},
         "CERTIFIED", 30),
    node("tm4", "tmR", "XAUUSD", "turn_of_month", {"days_before": 2, "ttl_bars": 72}, "FAILED", 40),
    node("r2", "seed:mix", "EURUSD", "level_breakout", {"ttl_bars": 12}, "FAILED", 60),
    node("s1", "r2", "GBPUSD", "level_breakout", {"ttl_bars": 12}, "FAILED", 50),
    node("s2", "r2", "EURUSD", "overnight_gap_decay", {"ttl_bars": 8}, "FAILED", 50),
]
#: The family's OWN declared grid. `turn_of_month` reached days_before=2 and ttl_bars in
#: {6,24,48,72,96}; 1 and 3 and 120 are cells its own bounds name and the docket never built.
GRIDS: dict[str, dict[str, list[Any]]] = {
    "turn_of_month": {"days_before": [1, 2, 3], "ttl_bars": [24, 48, 120]},
}
VERDICTS = [{"cell": "t1", "sym": "XAGUSD", "family": "trend_ma_cross", "passed": False,
             "terminal_gate": "deflated_sharpe"},
            {"cell": "t2", "sym": "XAUUSD", "family": "trend_ma_cross", "passed": False,
             "terminal_gate": "in_sample_screen"}]
SHADOW = {"XAUUSD.turn_of_month.asia": {"n": 14, "status": "ACTIVE"}}


@pytest.fixture
def lineage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The planted forest, a fresh registry with no backup to restore from, declared grids."""
    graph = tmp_path / "hypothesis_graph.jsonl"
    graph.write_text("".join(json.dumps(r) + "\n" for r in FOREST), "utf-8")
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    ledger.write_text("".join(json.dumps(r) + "\n" for r in VERDICTS), "utf-8")
    shadow = tmp_path / "shadow_state.json"
    shadow.write_text(json.dumps(SHADOW), "utf-8")
    monkeypatch.setattr(als, "GRAPH", graph)
    monkeypatch.setattr(als, "GATE_LEDGER", ledger)
    monkeypatch.setattr(als, "SHADOW", shadow)
    monkeypatch.setattr(als, "OUT", tmp_path / "reports" / "ALPHA_LINEAGE.json")
    monkeypatch.setattr(als, "declared_grids", lambda: {k: dict(v) for k, v in GRIDS.items()})
    monkeypatch.setattr(reg, "BACKUP", tmp_path / "no_backup")
    reg.set_path(tmp_path / "alpha_registry.sqlite")
    reg.upsert_card("sleeve:gold", name="gold", market="XAUUSD", category="sleeve", status="live")
    yield tmp_path
    reg.set_path(None)


def forest() -> dict[str, Any]:
    return als.build_forest(FOREST)


def by_family(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {r["family"]: r for r in rows}


# ------------------------------------------------------------------ the forest
def test_the_forest_is_built_from_the_parent_edges(lineage: Any) -> None:
    f = forest()
    assert len(f["nodes"]) == 12
    assert f["depth_max"] == 1
    assert set(f["roots"]) == {"seed:miner", "seed:tom", "seed:mix"}
    assert sorted(f["children"]["r1"]) == ["t1", "t2", "t3"]
    assert f["nodes"]["tm3"]["root"] == "seed:tom" and f["nodes"]["tm3"]["children"] == []
    assert f["n_parent_refs"] == 12 and f["n_parent_resolved"] == 9


def test_a_parent_the_record_does_not_hold_is_a_virtual_root(lineage: Any) -> None:
    """The miner's seed string is kept, not dropped: the strategies sharing it ARE the finding."""
    f = forest()
    assert f["nodes"]["r1"]["virtual_parent"] == "seed:miner"
    assert f["nodes"]["r1"]["root"] == "seed:miner"
    assert f["nodes"]["t1"]["root"] == "seed:miner" and f["nodes"]["t1"]["depth"] == 1


@pytest.mark.parametrize(("parent", "child", "axis"), [
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"ttl_bars": 12}},
     {"symbol": "Y", "family": "f", "chart": "H1", "session": "all", "params": {"ttl_bars": 12}},
     "transfer"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "f", "chart": "H4", "session": "all", "params": {}}, "transfer"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "asia", "params": {}}, "session"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"ttl_bars": 12}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"ttl_bars": 24}},
     "horizon"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"side_mode": "r"}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"side_mode": "m"}},
     "inverse"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all",
      "params": {"vol_filter": "high"}}, "regime"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"wait_bars": 4}},
     "execution"),
    ({"symbol": "X", "family": "level_breakout", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "cross_asset_residual", "chart": "H1", "session": "all",
      "params": {}}, "residual"),
    ({"symbol": "X", "family": "level_breakout", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "ensemble", "chart": "H1", "session": "all", "params": {}},
     "interaction"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"fast_ema": 9}},
     "parameter_neighbourhood"),
    ({"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"a": 1}},
     {"symbol": "X", "family": "f", "chart": "H1", "session": "all", "params": {"a": 1}}, "none"),
])
def test_classify_edge_names_the_transformation(parent: dict, child: dict, axis: str) -> None:
    assert als.classify_edge(parent, child) == axis


def test_wilson_upper_is_a_bound_and_absent_for_no_evidence() -> None:
    assert als.wilson_upper(0, 0) is None
    assert als.wilson_upper(1, 1) == pytest.approx(1.0)
    assert 0.7 < (als.wilson_upper(0, 1) or 0) < 0.85
    assert (als.wilson_upper(1, 5) or 0) < (als.wilson_upper(0, 1) or 0)


# ------------------------------------------------------------------ the six findings
def test_untried_mutations_names_only_the_axes_with_no_edge(lineage: Any) -> None:
    rep = als.build(dry_run=True)
    rows = by_family(rep["untried_mutations"])
    assert set(rows) == {"trend_ma_cross", "turn_of_month"}
    assert set(rows["trend_ma_cross"]["untried"]) == {"inverse", "horizon", "regime", "residual",
                                                      "interaction", "execution"}
    assert set(rows["trend_ma_cross"]["tried"]) == {"transfer", "session",
                                                    "parameter_neighbourhood"}
    assert set(rows["turn_of_month"]["untried"]) == set(als.MUTATION_AXES) - {"horizon"}
    assert rows["trend_ma_cross"]["mechanism"] == "trend_persistence"
    assert rows["trend_ma_cross"]["example_cell"] in {"r1", "t1", "t2", "t3"}


def test_a_record_whose_parents_never_resolve_measures_its_writer_not_the_search(
        lineage: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Measured on this tree: 0 of 35,199 parent references resolve. With no edge anywhere every
    axis reads as untried under every mechanism, which is true of the file and false of the desk,
    so the finding is UNMEASURED and the writer is named instead."""
    orphans = [{**r, "parent": f"seed:{r['id']}"} for r in FOREST]
    graph = tmp_path / "orphans.jsonl"
    graph.write_text("".join(json.dumps(r) + "\n" for r in orphans), "utf-8")
    monkeypatch.setattr(als, "GRAPH", graph)
    rep = als.build(dry_run=True)
    assert rep["n_parent_refs"] == 12 and rep["n_parent_resolved"] == 0
    assert rep["untried_mutations"] == []
    what = {u["what"] for u in rep["unmeasured"]}
    assert "no parent reference resolves to a node" in what
    assert "untried_mutations not searched" in what


def test_a_family_with_too_few_cells_is_not_a_claim_about_the_search(lineage: Any) -> None:
    """`level_breakout` has two nodes; 'never tried' on two cells measures nothing."""
    rep = als.build(dry_run=True)
    assert "level_breakout" not in by_family(rep["untried_mutations"])


def test_the_abandoned_branch_is_above_its_family_median_with_no_descendants(lineage: Any) -> None:
    """tm3 is CERTIFIED and childless for 30 days; its FAILED siblings sit AT the median."""
    rep = als.build(dry_run=True)
    rows = rep["abandoned_branches"]
    assert [r["cell"] for r in rows] == ["tm3"]
    r = rows[0]
    assert r["family"] == "turn_of_month" and r["fate"] == "CERTIFIED"
    assert r["posterior_upper"] > r["family_median"]
    assert r["age_days"] >= als.ABANDON_DAYS
    assert "nothing has descended from it" in r["why"]


def test_a_recent_branch_is_not_abandoned(lineage: Any) -> None:
    """Abandonment is a decision about TIME as well as evidence."""
    rep = als.build(dry_run=True, abandon_days=365.0)
    assert rep["abandoned_branches"] == []


def test_unexplored_neighbourhoods_come_from_the_familys_own_declared_grid(lineage: Any) -> None:
    rep = als.build(dry_run=True)
    rows = by_family(rep["unexplored_neighbourhoods"])
    assert set(rows) == {"turn_of_month"}
    gaps = {g["knob"]: g["untried"] for g in rows["turn_of_month"]["gaps"]}
    assert gaps == {"days_before": [1, 3], "ttl_bars": [120]}


def test_a_family_with_no_declared_grid_is_unmeasured_not_explored(
        lineage: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(als, "declared_grids", dict)
    rep = als.build(dry_run=True)
    assert rep["unexplored_neighbourhoods"] == []
    assert any(u["what"] == "no declared parameter grids" for u in rep["unmeasured"])


def test_a_mechanism_tested_on_one_asset_only_is_named(lineage: Any) -> None:
    rep = als.build(dry_run=True)
    rows = by_family(rep["single_asset_mechanisms"])
    assert set(rows) == {"turn_of_month"}
    assert rows["turn_of_month"]["symbol"] == "XAUUSD" and rows["turn_of_month"]["n_nodes"] == 5
    assert rows["turn_of_month"]["mechanism"] == "calendar_seasonality"


def test_a_mechanism_tested_in_one_session_only_is_named(lineage: Any) -> None:
    """`trend_ma_cross` HAS an asia child, so it must not appear here."""
    rep = als.build(dry_run=True)
    rows = by_family(rep["single_session_mechanisms"])
    assert set(rows) == {"turn_of_month"}
    assert rows["turn_of_month"]["session"] == "all"


def test_strategies_sharing_an_ancestor_are_named_with_their_families(lineage: Any) -> None:
    rep = als.build(dry_run=True)
    rows = rep["shared_ancestors"]
    assert [r["root"] for r in rows] == ["seed:mix"]
    assert rows[0]["families"] == {"level_breakout": 2, "overnight_gap_decay": 1}
    assert rows[0]["n_descendants"] == 3


# ------------------------------------------------------------------ the record it leaves
def test_every_finding_becomes_an_unprocessed_discovery_naming_the_untried_move(
        lineage: Any) -> None:
    rep = als.build(dry_run=False)
    rows = reg.discoveries(state="UNPROCESSED")
    assert len(rows) == rep["discoveries_recorded"] > 0
    assert {r["source_type"] for r in rows} == {"lineage"}
    assert {r["origin"] for r in rows} == {"MOAT"}
    kinds = {json.loads(r["payload_json"])["finding"] for r in rows}
    assert kinds == {"untried_mutation", "abandoned_branch", "unexplored_neighbourhood",
                     "single_asset_mechanism", "single_session_mechanism", "shared_ancestor"}
    one = next(r for r in rows
               if json.loads(r["payload_json"])["finding"] == "untried_mutation")
    payload = json.loads(one["payload_json"])
    assert payload["parent_cell"] in {"r1", "t1", "t2", "t3", "tmR", "tm1", "tm2", "tm3", "tm4"}
    assert payload["untried_move"]["axis"] in als.MUTATION_AXES
    assert json.loads(one["exact_rule"])["axis"] == payload["untried_move"]["axis"]


def test_a_rerun_on_an_unchanged_forest_records_nothing_new(lineage: Any) -> None:
    """Idempotence is the REGISTRY's, by content hash -- not a flag this organ carries."""
    first = als.build(dry_run=False)
    before = reg.discoveries(state="UNPROCESSED")
    second = als.build(dry_run=False)
    assert first["discoveries_recorded"] > 0
    assert second["discoveries_recorded"] == 0
    assert second["discoveries_existing"] == first["discoveries_recorded"]
    assert len(reg.discoveries(state="UNPROCESSED")) == len(before)


def test_it_donates_no_cell_of_its_own(lineage: Any) -> None:
    """A finding about the SEARCH is not a hypothesis about a market; the compiler closes it."""
    als.build(dry_run=False)
    assert reg.candidates() == []
    assert "donate" not in dir(als)


def test_the_parent_cell_edge_is_written_into_the_provenance_dag(lineage: Any) -> None:
    als.build(dry_run=False)
    edges = reg.descendants_of("cell", "tm3")
    assert any(e["to_kind"] == "discovery" and e["relation"] == "lineage:abandoned_branch"
               for e in edges)


def test_the_other_three_records_are_read_and_reported(lineage: Any) -> None:
    rep = als.build(dry_run=True)
    assert rep["terminal_gates"] == {"deflated_sharpe": 1, "in_sample_screen": 1}
    assert rep["forward_families"] == ["turn_of_month"]
    assert rep["card_events"] >= 1


def test_absent_sources_are_unmeasured_not_zero(
        lineage: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(als, "GRAPH", tmp_path / "nothing.jsonl")
    rep = als.build(dry_run=True)
    assert rep["n_nodes"] == 0 and rep["untried_mutations"] == []
    assert any(u["what"] == "nothing.jsonl absent" and "UNMEASURED" in u["why"]
               for u in rep["unmeasured"])


def test_the_budget_stop_names_the_findings_it_did_not_search(lineage: Any) -> None:
    rep = als.build(dry_run=True, budget_s=-1.0)
    assert all(rep[name] == [] for name in als.FINDINGS)
    stopped = {u["what"] for u in rep["unmeasured"]}
    assert stopped >= {f"{name} not searched" for name in als.FINDINGS}


# ------------------------------------------------------------------ the CLI
def test_the_cli_dry_run_writes_nothing_and_records_nothing(lineage: Any) -> None:
    assert als.main(["--dry-run"]) == 0
    assert not als.OUT.exists()
    assert reg.discoveries() == []


def test_the_cli_writes_the_report_with_every_finding_and_the_rule(lineage: Any) -> None:
    assert als.main([]) == 0
    doc = json.loads(als.OUT.read_text("utf-8"))
    assert doc["n_nodes"] == 12 and doc["n_roots"] == 3 and doc["depth_max"] == 1
    assert doc["n_parent_refs"] == 12 and doc["n_parent_resolved"] == 9
    for name in als.FINDINGS:
        assert name in doc
    assert doc["discoveries_recorded"] > 0
    assert doc["rule"].startswith("the desk's own record is the cheapest unexplored ground")
    assert doc["edges_by_axis"]["horizon"] == 4
