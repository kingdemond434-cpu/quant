"""RANK RECOVERY -- the rank is the same number the fence measures, and depth only ever adds.

The load-bearing test here is `test_gram_identity_matches_the_svd_breadth`: this organ computes
the production effective rank by a different route (trace(G)^2/||G||_F^2 off an inverted index)
because the desk's SVD path cannot run at the grid's current size, and two implementations of one
number are two numbers unless something pins them together. That test is the pin.
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "desks" / "mt5"
for p in (str(ROOT), str(BASE)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.research.sandbox_rotation import breadth  # noqa: E402
from research import rank_recovery as rr  # noqa: E402


# ---------------------------------------------------------------- the measurement is the same one
def test_gram_identity_matches_the_svd_breadth() -> None:
    """The cheap exact path and `sandbox_rotation.breadth` must agree on every shape."""
    rng = random.Random(20260924)  # noqa: S311 -- shapes for a numeric identity
    for _ in range(40):
        producers = rng.randint(1, 9)
        columns = rng.randint(1, 14)
        rows: dict[str, set[str]] = {}
        for i in range(producers):
            cells = {f"c{j}" for j in range(columns) if rng.random() < 0.45}
            if cells:
                rows[f"p{i}"] = cells
        if not rows:
            continue
        gram = rr.effective_rank_of(rows)
        svd = breadth({k: sorted(v) for k, v in rows.items()})["total"]
        # `breadth` publishes 4 decimals; the identity is exact to everything it prints
        assert gram == pytest.approx(float(svd), rel=1e-4, abs=1e-4)


def test_disjoint_rows_are_the_participation_ratio_of_the_counts() -> None:
    """THE WHOLE DIAGNOSIS IN ONE ASSERT: with disjoint producers the rank is a concentration
    measure over cell COUNTS, so volume alone cannot move it."""
    rows = {"a": {f"a{i}" for i in range(10546)}, "b": {f"b{i}" for i in range(4008)},
            "c": {f"c{i}" for i in range(2422)}}
    counts = [len(v) for v in rows.values()]
    total = sum(counts)
    assert rr.effective_rank_of(rows) == pytest.approx(
        total * total / sum(n * n for n in counts), rel=1e-9)


def test_one_producer_reads_one_no_matter_how_many_cells() -> None:
    assert rr.effective_rank_of({"solo": {f"c{i}" for i in range(50_000)}}) == pytest.approx(1.0)


def test_empty_is_zero_never_one() -> None:
    assert rr.effective_rank_of({}) == 0.0
    assert rr.effective_rank_of({"p": set()}) == 0.0


def test_spreading_the_same_cells_raises_the_rank() -> None:
    """The same 300 cells on one producer and on three read 1.0 and 3.0: MORE VARIED, not more."""
    cells = [f"c{i}" for i in range(300)]
    one = {"a": set(cells)}
    three = {"a": set(cells[:100]), "b": set(cells[100:200]), "c": set(cells[200:])}
    assert rr.effective_rank_of(one) == pytest.approx(1.0)
    assert rr.effective_rank_of(three) == pytest.approx(3.0)


def test_production_rank_publishes_what_bounds_it() -> None:
    rows = {"big": {f"c{i}" for i in range(900)}, "small": {"z1", "z2"}}
    got = rr.production_rank(rows)
    assert got["available"] is True
    assert got["producers"] == 2
    assert got["cells"] == 902
    assert got["top_share"] == pytest.approx(900 / 902, rel=1e-3)
    assert got["headroom"] == pytest.approx(2 - float(got["effective_rank"]), abs=1e-3)
    assert got["effective_rank"] == pytest.approx(
        float(got["pr_of_producer_counts"]), rel=1e-3)


def test_production_rank_on_nothing_is_unmeasured_never_zero() -> None:
    got = rr.production_rank({})
    assert got["available"] is False
    assert rr.UNMEASURED in str(got["why"])


# ---------------------------------------------------------------------------- the recovery adds
def _donor(producer: str, family: str, n: int) -> dict[str, object]:
    return {"producer_key": producer, "family": family, "symbol": "EURUSD", "horizon": "sub_1d",
            "params": {"lookback": n}, "mechanism": f"{family} rule {n}",
            "generator": producer, "producer": producer, "discovery_id": None, "region": None}


def test_plan_deepening_picks_the_least_credited_producer() -> None:
    """Balance-greedy is the argmax of d(rank)/d(n_i); the busiest producer must never be first."""
    rows = {"busy": {f"trend|s{i}|sub_1d" for i in range(500)},
            "quiet": {"trend|s0|sub_1d"}}
    pool = {"trend": [_donor("busy", "trend", 1), _donor("quiet", "trend", 2),
                      _donor("idle", "trend", 3)]}
    plan, _census = rr.plan_deepening(rows, pool, rounds=1)
    assert plan, "a grid with three donors per family must have something to carry"
    assert plan[0][1]["producer_key"] == "idle"
    carried = Counter(d["producer_key"] for _c, d in plan)
    assert carried["busy"] <= carried["idle"]


def test_deepening_only_ever_adds_and_raises_the_rank() -> None:
    """THE RULE THIS ORGAN LIVES UNDER: the after-matrix is a superset and the rank only rises."""
    rows = {"busy": {f"trend|s{i}|sub_1d" for i in range(400)},
            "mid": {f"carry|s{i}|sub_1d" for i in range(60)},
            "quiet": {"trend|s0|sub_1d"}}
    pool = {"trend": [_donor("busy", "trend", 1), _donor("quiet", "trend", 2),
                      _donor("idle", "trend", 3), _donor("rare", "trend", 4)],
            "carry": [_donor("mid", "carry", 5), _donor("idle", "carry", 6)]}
    before = rr.production_rank(rows)
    plan, census = rr.plan_deepening(rows, pool, rounds=rr.ROUNDS_PER_PASS)
    after_rows = {k: set(v) for k, v in rows.items()}
    for cell, donor in plan[:int(census["rank_positive"])]:
        after_rows.setdefault(donor["producer_key"], set()).add(cell)
    after = rr.production_rank(after_rows)
    # nothing removed
    for key, cells in rows.items():
        assert cells <= after_rows[key]
    assert after["cells"] > before["cells"]
    assert float(after["effective_rank"]) > float(before["effective_rank"])


def test_a_donor_that_would_only_duplicate_coverage_is_set_aside_with_its_reason() -> None:
    """THE DEFECT THE PLAIN BALANCE-GREEDY HAD. Levelling every producer up on the SAME
    coordinates makes their rows identical, and identical rows span one direction, not many.
    Measured: a 400/60/1 grid lost rank 1.299 -> 1.1281 under load-balancing alone."""
    rows = {"busy": {f"trend|s{i}|sub_1d" for i in range(120)}, "quiet": {"trend|s0|sub_1d"}}
    pool = {"trend": [_donor("busy", "trend", 1), _donor("quiet", "trend", 2)]}
    plan, census = rr.plan_deepening(rows, pool, rounds=8)
    head = int(census["rank_positive"])
    after_rows = {k: set(v) for k, v in rows.items()}
    for cell, donor in plan[:head]:
        after_rows.setdefault(donor["producer_key"], set()).add(cell)
    assert rr.effective_rank_of(after_rows) > rr.effective_rank_of(rows)
    # the rank-neutral donors are COUNTED and still minted, never refused
    assert census["rank_neutral"] > 0
    assert len(plan) == census["planned"] == head + int(census["rank_neutral"])
    assert "never refused" in str(census["rank_neutral_why"])
    assert "never fewer cells" in str(census["rank_neutral_why"])
    assert census["rank_projected"] == pytest.approx(rr.effective_rank_of(after_rows), rel=1e-3)


def test_plan_never_repeats_a_producer_on_one_coordinate() -> None:
    rows = {"a": {"trend|eurusd|sub_1d"}}
    pool = {"trend": [_donor("a", "trend", 1), _donor("b", "trend", 2), _donor("c", "trend", 3)]}
    plan, census = rr.plan_deepening(rows, pool, rounds=6)
    seen: dict[str, set[str]] = {"trend|eurusd|sub_1d": {"a"}}
    for cell, donor in plan:
        assert donor["producer_key"] not in seen.setdefault(cell, set())
        seen[cell].add(donor["producer_key"])
    # ONE coordinate cannot carry a second independent direction, so both donors are rank-neutral
    # -- and both are still in the plan. A metric that cannot see a mechanism never deletes it.
    assert len(plan) == 2, "two uncarried donors exist and both must be carried exactly once"
    assert census["rank_positive"] == 0
    assert census["rank_neutral"] == 2


def test_the_lane_router_decides_which_coordinates_deepen() -> None:
    """A symbol outside the hypothesis lane is not deepened -- the standing two-lane order."""
    rows = {"a": {"trend|eurusd|sub_1d", "trend|apple|sub_1d"}}
    pool = {"trend": [_donor("b", "trend", 1)]}
    plan, _census = rr.plan_deepening(rows, pool, lane={"eurusd"}, rounds=1)
    assert [c for c, _d in plan] == ["trend|eurusd|sub_1d"]


def test_measure_only_writes_nothing() -> None:
    plan = [("trend|eurusd|sub_1d", _donor("b", "trend", 1))]
    got = rr.deepen(plan, write_rows=False)
    assert got["dry_run"] is True
    assert got["planned"] == 1


def test_empty_plan_is_unmeasured_not_a_failure() -> None:
    got = rr.deepen([], write_rows=False)
    assert got["available"] is False
    assert rr.UNMEASURED in str(got["why"])


# --------------------------------- the grid filler's own rank block now says what bounds it
def test_fill_orthogonality_publishes_the_concentration_that_bounds_it() -> None:
    """`independence_intake.fill_orthogonality` must NAME the producer concentration, because a
    reader who sees only `effective_rank` reads volume into a number volume cannot move."""
    from research import independence_intake as ii

    # 32 cells credited to one producer and 2 to another: the shape the grid filler produced.
    created = [("miner:discovery_compiler", "trend", f"s{i}", "sub_1d") for i in range(32)]
    created += [("rare_seat", "carry", f"s{i}", "sub_1d") for i in range(2)]
    got = ii.fill_orthogonality(created)
    assert got["available"] is True
    assert got["producer_rank_is_a_concentration_measure"] is True
    assert got["producer_count_participation_ratio"] == pytest.approx(
        34 * 34 / (32 * 32 + 2 * 2), rel=1e-3)
    assert got["top_producer_share"] == pytest.approx(32 / 34, rel=1e-3)
    assert got["producer_headroom"] > 0
    assert "rank_recovery.py" in str(got["recovered_by"])
    assert "never fewer cells" in str(got["recovered_by"])


# ------------------------------------------------------------------------------- the rails hold
def test_the_pass_bound_cannot_bind() -> None:
    """A bound below the real grid is a throttle wearing a safety's clothes (the filler's lesson).
    The measured occupied grid on the trading box is 42,105 coordinates x 3 donor rounds."""
    assert rr.MAX_DEEPEN_PER_PASS >= 42_105 * rr.ROUNDS_PER_PASS


def test_the_ratchet_is_a_floor_and_records_a_fall(tmp_path: Path) -> None:
    path = tmp_path / "production_rank_ratchet.json"
    rr.ratchet({"available": True, "effective_rank": 9.0},
               {"available": True, "effective_rank": 25.4, "producers": 112, "cells": 81_788},
               path=path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["effective_rank_best"] == pytest.approx(25.4)
    assert "floor and never a cap" in doc["law"]
    fell = rr.ratchet({"available": True, "effective_rank": 25.4},
                      {"available": True, "effective_rank": 7.15, "producers": 20, "cells": 9},
                      path=path)
    assert fell["verdict"] == "REGRESSION"
    assert fell["failures"] and "never fewer cells" in fell["failures"][0]
    # the best never falls with the reading
    kept = json.loads(path.read_text(encoding="utf-8"))["effective_rank_best"]
    assert kept == pytest.approx(25.4)


def test_an_unmeasured_pass_moves_no_ratchet(tmp_path: Path) -> None:
    path = tmp_path / "production_rank_ratchet.json"
    got = rr.ratchet({"available": False}, {"available": False, "why": "UNMEASURED: no registry"},
                     path=path)
    assert got["verdict"] == rr.UNMEASURED
    assert not path.exists()


def test_no_registry_is_unmeasured_never_empty(tmp_path: Path) -> None:
    rows, why = rr._matrix(tmp_path / "absent.sqlite")
    assert rows == {}
    assert why.startswith(rr.UNMEASURED)
    assert rr.donor_pool(tmp_path / "absent.sqlite") == {}


# ------------------------------------------------- the donor pool is per PRODUCER, not per family
def _registry(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("create table research_candidates (seq integer primary key autoincrement, "
                "id text, family text, symbol text, horizon text, params_json text, "
                "mechanism text, generator text, producer text, discovery_id text, "
                "region text, origin text, status text, donated_cell text, content_hash text, "
                "created_at text)")
    con.execute("create table discoveries (discovery_id text, generator text)")
    for i, (fam, gen) in enumerate([("trend", "alpha"), ("trend", "beta"), ("trend", "alpha"),
                                    ("carry", "gamma")]):
        con.execute(
            "insert into research_candidates (id, family, symbol, horizon, params_json, "
            "mechanism, generator, origin, status, created_at) values (?,?,?,?,?,?,?,?,?,?)",
            (f"c{i}", fam, "EURUSD", "sub_1d", json.dumps({"lookback": i + 2}),
             f"{fam} rule", gen, "desk", "queued", "2026-09-24T00:00:00"))
    con.commit()
    con.close()


def test_donor_pool_carries_every_producer_the_family_holds(tmp_path: Path) -> None:
    """independence_intake._donors returns ONE donor per family; this returns one per PRODUCER.
    That difference is the whole rank defect: 957 pairs available, 20 used."""
    db = tmp_path / "alpha_registry.sqlite"
    _registry(db)
    pool = rr.donor_pool(db)
    assert set(pool) == {"trend", "carry"}
    assert {d["producer_key"] for d in pool["trend"]} == {"alpha", "beta"}
    assert len(pool["trend"]) == 2, "one row per (family, producer), never one per family"


def test_the_filler_and_this_organ_are_never_their_own_donors(tmp_path: Path) -> None:
    """A transplant of a transplant credits the desk for its own echo (the filler's own lesson)."""
    db = tmp_path / "alpha_registry.sqlite"
    _registry(db)
    con = sqlite3.connect(db)
    for origin in ("independence_intake", rr.SOURCE):
        con.execute(
            "insert into research_candidates (id, family, symbol, horizon, params_json, "
            "mechanism, generator, origin, status, created_at) values (?,?,?,?,?,?,?,?,?,?)",
            (f"x{origin}", "trend", "GBPUSD", "sub_1d", json.dumps({"lookback": 99}),
             "copy", "echo", origin, "queued", "2026-09-24T01:00:00"))
    con.commit()
    con.close()
    assert "echo" not in {d["producer_key"] for d in rr.donor_pool(db)["trend"]}
