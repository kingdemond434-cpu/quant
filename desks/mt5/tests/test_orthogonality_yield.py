"""Compute follows BOTH signals -- orthogonality and certificates -- and starves nothing.

The principal's order of 2026-09-23: "compute should always go more to discovering things which
produce orthogonality along with ones who produce the most certis." These tests pin the two
properties that make that safe to obey: every factor is one-sided (so steering can never become
starving), and an UNMEASURED producer is never scored as a failing one.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import orthogonality_yield as oy  # noqa: E402


def _registry(tmp: Path, rows: list[tuple[str, str, str]]) -> Path:
    db = tmp / "reg.sqlite"
    con = sqlite3.connect(db)
    con.execute("create table research_candidates "
                "(family text, symbol text, horizon text)")
    con.executemany("insert into research_candidates values (?,?,?)", rows)
    con.commit()
    con.close()
    return db


def _ledger(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "gate.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_volume_alone_buys_no_orthogonality(tmp_path: Path) -> None:
    """A producer minting near-identical cells scores below one that opens new ground.

    THE MEASUREMENT THIS PINS. On the trading box `cross_asset_residual` held 59,912 raw cells
    over 548 distinct ground cells -- 109 near-copies each -- and its leave-one-out contribution
    to the grid's effective rank was 0.0000. Volume is not information, and a score that could be
    bought with volume would send the judge's hour straight back to the duplicate mill.
    """
    rows = [("dupe", "eurusd", "h1")] * 500
    rows += [("spanner", f"sym{i}", "h1") for i in range(40)]
    rows += [("spanner2", f"other{i}", "h4") for i in range(40)]
    db = _registry(tmp_path, rows)
    led = _ledger(tmp_path, [])
    doc = oy.signals(db=db, ledger=led)
    by = {r["family"]: r for r in doc["producers"]}
    assert by["dupe"]["raw_cells"] == 500
    assert by["dupe"]["ground_cells"] == 1
    assert by["spanner"]["raw_cells"] == 40
    # 500 cells on one ground cell must not outrank 40 cells spanning 40.
    assert by["dupe"]["marginal_rank"] < by["spanner"]["marginal_rank"]
    assert by["dupe"]["orthogonality_factor"] <= by["spanner"]["orthogonality_factor"]


def test_no_factor_ever_falls_below_par(tmp_path: Path) -> None:
    """THE EXPLORATION FLOOR, in the only form an allocator can hold it.

    Every factor this module emits is >= 1.0, so the ranking it feeds can be LIFTED and never
    reduced; `judge_coverage.allocate` then hands every family holding backlog its equal share of
    FLOOR_SHARE before any of this is consulted. Steering compute toward what works must never
    become starving what has not been tried.
    """
    rows = [("a", "eurusd", "h1")] * 50 + [("b", f"s{i}", "h1") for i in range(30)]
    rows += [("c", "gbpusd", "h4")] * 3
    db = _registry(tmp_path, rows)
    led = _ledger(tmp_path, [
        {"family": "a", "passed": False, "downstream_status": None} for _ in range(400)
    ] + [{"family": "b", "passed": True, "downstream_status": None}])
    doc = oy.signals(db=db, ledger=led)
    assert doc["verdict"] == "MEASURED"
    for row in doc["producers"]:
        assert row["orthogonality_factor"] >= oy.PAR, row
        assert row["certificate_factor"] >= oy.PAR, row
        assert row["orthogonality_factor"] <= oy.CEIL
        assert row["certificate_factor"] <= oy.CEIL


def test_unmeasured_is_never_scored_as_a_zero(tmp_path: Path) -> None:
    """A producer no judge has reached has NO certificate rate -- not a rate of zero (L1.28a).

    This is the failure mode that turns a yield-steered allocator into a machine that converges on
    the few things it already knows: score the unjudged as zero-yield and they are never judged,
    which keeps them unjudged. `certs_per_judge_hour` must be None, the state must say UNMEASURED,
    and the certificate factor must sit at par rather than at the bottom of the distribution.
    """
    db = _registry(tmp_path, [("seen", "eurusd", "h1"), ("unseen", "audcad", "h4")])
    led = _ledger(tmp_path, [{"family": "seen", "passed": True, "downstream_status": None},
                             {"family": "seen", "passed": False, "downstream_status": None}])
    doc = oy.signals(db=db, ledger=led)
    by = {r["family"]: r for r in doc["producers"]}
    assert by["unseen"]["state"] == "UNMEASURED"
    assert by["unseen"]["certs_per_judge_hour"] is None
    assert by["unseen"]["certificate_factor"] == oy.PAR
    assert by["unseen"]["judged"] == 0
    # and it still earns its orthogonality lift on the axis that CAN be measured for it
    assert by["unseen"]["orthogonality_factor"] >= oy.PAR


def test_not_run_rows_are_not_counted_as_judged(tmp_path: Path) -> None:
    """A cell the build budget never reached is not a measured failure.

    `external_gauntlet` stamps `NOT_RUN*` when it ran out of budget before computing the cell.
    Counting those as judged would manufacture a MEASURED_ZERO out of an absence and then spend
    the ranking on it.
    """
    db = _registry(tmp_path, [("f", "eurusd", "h1")])
    led = _ledger(tmp_path, [
        {"family": "f", "passed": False, "downstream_status": "NOT_RUN_UNTRADEABLE_SYMBOL"}
        for _ in range(100)])
    doc = oy.signals(db=db, ledger=led)
    by = {r["family"]: r for r in doc["producers"]}
    assert by["f"]["judged"] == 0
    assert by["f"]["not_run"] == 100
    assert by["f"]["state"] == "UNMEASURED"


def test_a_zero_is_diagnosed_not_pooled(tmp_path: Path) -> None:
    """The 23 zero-pass families are not one thing, and the score must not treat them alike.

    A family at 0 of 3 has told the desk nothing; a family at 0 of 399 has told it something. Both
    keep their floor -- the diagnosis costs a producer only its LIFT -- but the two states are
    published separately so a reader can see which zero is evidence.
    """
    pooled = 0.02
    assert oy.diagnose("thin", judged=3, certs=0, pooled=pooled)[0] == "UNDER_JUDGED"
    assert oy.diagnose("thick", judged=4000, certs=0, pooled=pooled)[0] == "MEASURED_ZERO"
    assert oy.diagnose("none", judged=0, certs=0, pooled=pooled)[0] == "UNMEASURED"
    assert oy.diagnose("good", judged=100, certs=3, pooled=pooled)[0] == "CERTIFYING"


def test_banned_family_is_expected_zero_and_draws_no_lift() -> None:
    """`discovered` is permanently banned, so its zero is EXPECTED and never read as a dead
    mechanism -- and it must not be handed a lift it could only spend on quota it cannot have."""
    state, why = oy.diagnose("discovered", judged=39128, certs=17, pooled=0.0005)
    assert state == "BANNED"
    assert "EXPECTED" in why


def test_the_factor_is_monotone_so_ordering_survives_the_clip() -> None:
    """Distinct signals must get distinct factors.

    `judge_coverage.allocate` walks the ranking in ORDER. The first real pass used a ratio to the
    cross-producer mean and nine producers came back clipped at exactly the ceiling, which hands
    the ordering of that whole group back to the term that was blind to orthogonality. A factor
    that ties distinct readings is a measurement that gets discarded where it was meant to bite.
    """
    pop = [0.0, 0.0, 0.1, 0.2, 0.5, 0.9]
    f = [oy._factor(v, pop)[0] for v in (0.0, 0.1, 0.2, 0.5, 0.9)]
    assert f == sorted(f)
    assert len(set(f)) == len(f), f
    assert f[0] == oy.PAR
    assert max(f) <= oy.CEIL
    assert oy._factor(None, pop) == (oy.PAR, 0.0)


def test_an_absent_report_leaves_every_producer_at_par(tmp_path: Path) -> None:
    """An unmeasured signal must never silently demote anyone: no artifact means no factors, and
    `judge_coverage.rank_by_value` is then exactly what it was before this module existed."""
    assert oy.published_factors(tmp_path / "nope.json") == {}
    doc = oy.signals(db=tmp_path / "nope.sqlite", ledger=tmp_path / "nope.jsonl")
    assert doc["verdict"] == "UNMEASURED"
    assert doc["factors"] == {}


def test_ranking_is_lifted_and_never_reduced(tmp_path: Path) -> None:
    """The wired end: factors multiply `ev_per_cell` upward, so no family's expected value --
    and therefore no family's place in the queue -- is ever reduced by this measurement."""
    from research import judge_coverage as jc
    backlog = {"a": 10, "b": 10}
    rows = [{"family": "a", "timeframe": "H1"}, {"family": "b", "timeframe": "H1"}]
    base = {r["family"]: r["ev_per_cell"] for r in jc.rank_by_value(backlog, rows, 100)}
    table = {"a": {"orthogonality_factor": 2.0, "certificate_factor": 1.5,
                   "marginal_rank": 0.5, "certs_per_judge_hour": 9.0, "state": "CERTIFYING"},
             "b": {"orthogonality_factor": 1.0, "certificate_factor": 1.0,
                   "marginal_rank": 0.0, "certs_per_judge_hour": None, "state": "UNMEASURED"}}
    orig = jc.producer_signals
    try:
        jc.producer_signals = lambda *a, **k: table  # type: ignore[assignment]
        lifted = {r["family"]: r for r in jc.rank_by_value(backlog, rows, 100)}
    finally:
        jc.producer_signals = orig  # type: ignore[assignment]
    for fam in ("a", "b"):
        assert lifted[fam]["ev_per_cell"] >= base[fam]
    assert lifted["a"]["ev_per_cell"] == base["a"] * 2.0 * 1.5
    assert lifted["b"]["ev_per_cell"] == base["b"]
    assert lifted["b"]["producer_state"] == "UNMEASURED"


def test_the_leg_is_registered_on_a_clock() -> None:
    """UNWIRED OR IDLE IS A DEFECT (III.16): a measurement nothing runs is not a measurement."""
    cyc = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("orthogonality_yield"' in cyc
    assert '"orthogonality_yield": 300' in cyc
    layers = (ROOT / "libs" / "research" / "layers.py").read_text(encoding="utf-8")
    assert '"orthogonality_yield":' in layers
