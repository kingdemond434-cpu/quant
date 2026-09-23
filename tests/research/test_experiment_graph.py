"""The experiment memory graph: nodes over the registry (never beside it), lineage edges,
verdicts with their failed assumptions, and the never-tried query the proposers read."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.moat import registry as R
from libs.research import experiment_graph as G
from libs.research.experiment_spec import DataSnapshot, ExperimentSpec


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


def _spec(eid: str, *, family: str = "carry_unwind", symbol: str = "AUDJPY",
          model: str = "ols", chart: str = "H1", regime: str = "high_vol",
          mechanism: str = "carry unwind", parents: tuple[str, ...] = ()) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id=eid, kind="world_lead", family=family, symbols=(symbol,), model=model,
        representation="positioning", chart=chart, regime=regime, horizon="1d",
        mechanism=mechanism, method="deep_forest", source="src_1", generator="deep_forest_miner",
        falsifier="later bars stop clearing the gates", parents=parents,
        data_snapshot=DataSnapshot(vintage="2026-09-01", datasets=("bars.parquet",),
                                   pit_status="bars"))


def test_the_graph_is_the_registry_and_not_a_store_beside_it(reg: Path) -> None:
    G.upsert(_spec("exp_a"))
    conn = R.connect()
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "experiments" in tables and "research_credit" in tables
        assert int(conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]) == 1
    finally:
        conn.close()
    # and no second database file was created next to it
    assert sorted(p.name for p in reg.glob("*.sqlite")) == ["alpha_registry.sqlite"]


def test_upsert_is_idempotent_and_writes_lineage_edges(reg: Path) -> None:
    eid, created = G.upsert(_spec("exp_a"), candidate_id="cand_a")
    assert (eid, created) == ("exp_a", True)
    _, again = G.upsert(_spec("exp_a"), candidate_id="cand_a")
    assert again is False
    G.upsert(_spec("exp_b", parents=("exp_a",)), candidate_id="cand_b")
    kids = G.children_of("exp_a")
    assert any(e["to_id"] == "exp_b" for e in kids)
    assert any(e["from_id"] == "exp_a" for e in G.parents_of("exp_b"))


def test_a_verdict_carries_the_assumptions_that_failed_with_it(reg: Path) -> None:
    G.upsert(_spec("exp_a"))
    assert G.record_verdict("exp_a", "REJECTED",
                            failed_assumptions=["cost_killed:spread", "horizon:M15"],
                            forward_r=-1.5) is True
    n = G.node("exp_a")
    assert n is not None and n["verdict"] == "REJECTED" and n["forward_r"] == -1.5
    assert G.failed_assumptions() == {"cost_killed:spread": 1, "horizon:M15": 1}
    with pytest.raises(ValueError, match="not one of"):
        G.record_verdict("exp_a", "MAYBE")


def test_never_tried_is_the_complement_over_measured_axis_domains(reg: Path) -> None:
    """The desk has run ols@H1 and ridge@M15 on one mechanism; the two CROSS cells are new."""
    G.upsert(_spec("exp_1", model="ols", chart="H1"), candidate_id="c1")
    G.upsert(_spec("exp_2", model="ridge", chart="M15"), candidate_id="c2")
    G.record_verdict("exp_1", "SURVIVED")
    q = G.never_tried(mechanism="carry unwind", axes=("model", "chart"))
    assert q["n_cells"] == 4 and q["n_tried"] == 2 and q["n_untried"] == 2
    got = {(u["model"], u["chart"]) for u in q["untried"]}
    assert got == {("ols", "M15"), ("ridge", "H1")}
    assert q["coverage"] == 0.5


def test_an_axis_with_no_observed_value_is_unmeasured_and_never_a_blank_cell(reg: Path) -> None:
    G.upsert(_spec("exp_1", model=""))
    q = G.never_tried(axes=("model", "chart"))
    assert q["unmeasured_axes"] == ["model"]
    assert q["axes"] == ["chart"]
    with pytest.raises(ValueError, match="unknown axes"):
        G.never_tried(axes=("not_an_axis",))


def test_surviving_mechanisms_is_what_a_proposer_iterates(reg: Path) -> None:
    G.upsert(_spec("exp_1", mechanism="carry unwind"))
    G.upsert(_spec("exp_2", mechanism="gap decay"))
    G.record_verdict("exp_1", "SURVIVED")
    rows = G.surviving_mechanisms()
    assert [r["mechanism_id"] for r in rows] == ["carry unwind"]


def test_refresh_copies_the_gauntlets_own_verdict_onto_the_node(reg: Path) -> None:
    cid, _ = R.enqueue_candidate(family="carry_unwind", symbol="AUDJPY", params={},
                                 origin="DESK", candidate_id="cand_x")
    G.upsert(_spec("exp_a"), candidate_id=cid)
    R.mark_candidate(cid, "rejected", rejection_reason="cost_killed", failure_class="cost_killed")
    out = G.refresh()
    assert out["nodes"] == 1 and out["updated"] == 1 and out["orphans"] == 0
    n = G.node("exp_a")
    assert n is not None and n["verdict"] == "REJECTED"
    assert "cost_killed" in str(n["failed_assumptions_json"])
    # a node with no cell is a real defect, counted, never a silent zero
    G.upsert(_spec("exp_orphan"))
    assert G.refresh()["orphans"] == 1


def test_census_reports_the_axis_domains_the_query_can_search(reg: Path) -> None:
    G.upsert(_spec("exp_1"))
    c = G.census()
    assert c["nodes"] == 1 and c["by_kind"] == {"world_lead": 1}
    assert c["by_verdict"] == {"UNJUDGED": 1}
    assert c["axis_domain_sizes"]["model"] == 1 and c["axis_domain_sizes"]["symbol"] == 1
    assert c["edges"] >= 1
