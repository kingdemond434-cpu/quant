"""The lineage bridge builds the descent DAG from the research store in generation order: a child
recorded before its parent still lands, an orphan whose parent is absent is DROPPED and counted
(never given a fabricated root), first write wins, and crossover refuses with fewer than two."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.research_os import lineage_bridge as lb
from libs.research_os import store


@pytest.fixture(autouse=True)
def _db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "research_os.sqlite"
    monkeypatch.setattr(store, "DB", db)
    return db


def _hyp(hid: str, gen: int, parents: list[str] | None = None, mech: str = "m",
         spec: dict | None = None) -> None:
    store.record_hypothesis(hypothesis_id=hid, mechanism=mech, coordinate=f"c/{hid}",
                            parent_ids=parents or [], generation=gen, spec=spec or {})


def _fail(hid: str, state: str, step: str) -> None:
    with store.connect() as c:
        c.execute("INSERT INTO failures (ts, hypothesis_id, state, next_action) "
                  "VALUES ('t', ?, ?, ?)", (hid, state, step))


def test_empty_store_builds_an_empty_dag_and_crossover_refuses() -> None:
    dag, stats = lb.build_dag()
    assert len(dag.nodes) == 0 and stats == {"nodes": 0, "dropped_orphans": 0}
    out = lb.crossover()
    assert out["pairs"] == [] and out["n_pairs"] == 0 and "fewer than two" in out["why"]


def test_generation_order_orphans_duplicates_and_bad_json() -> None:
    _hyp("child", 1, ["root"], mech="carry", spec={"mutation": "shift_hour"})
    _hyp("root", 0, mech="breakout")
    _hyp("orphan", 2, ["nowhere"])
    _hyp("root", 0, mech="IGNORED")                       # first write wins
    with store.connect() as c:                            # unparseable parents and spec
        c.execute("INSERT INTO hypotheses (ts, hypothesis_id, mechanism, coordinate, parent_ids, "
                  "generation, spec) VALUES ('t', 'odd', 'x', 'c', '{bad', 0, 'nope')")
    _fail("child", "FALSIFIED", "timing")
    store.record_experiment(hypothesis_id="root", exp_r_gross=0.2, exp_r_net=0.1, passed=True)
    dag, stats = lb.build_dag()
    assert stats == {"nodes": 3, "dropped_orphans": 1}
    assert set(dag.nodes) == {"root", "child", "odd"}
    child, root, odd = dag.nodes["child"], dag.nodes["root"], dag.nodes["odd"]
    assert child.parents == ("root",) and child.generation == 1
    assert child.mutation_operation == "shift_hour"
    assert child.failing_step == "timing" and child.failure_class == "FALSIFIED"
    assert root.mechanism == "breakout" and root.furthest_stage == "FORWARD_ENROLLED"
    assert root.survived is False and child.furthest_stage == "IDEA"
    assert odd.parents == () and odd.mutation_operation == ""


def test_crossover_with_two_lineages_reports_its_pairs_and_stats() -> None:
    _hyp("a", 0, mech="breakout")
    _hyp("b", 0, mech="carry")
    out = lb.crossover(seed=1, k=3)
    assert out["nodes"] == 2 and out["dropped_orphans"] == 0
    assert out["n_pairs"] == len(out["pairs"]) <= 3
    assert "exonerated" in out["why"]
