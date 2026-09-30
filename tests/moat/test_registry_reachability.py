"""THE JUDGEABLE POPULATION: the identity ceiling, the lease, and the path into the judge's file.

Traced end to end on the trading box 2026-09-24 and pinned here, because every clause was a
number that looked like a slow clock and was actually a structural cap:

  * `candidate_identity_index` built `symbol|family|session` with `setdefault` over ORDER BY seq,
    so the OLDEST row owned each identity forever -- 16,216 identities against 356,087 candidates,
    95.4% of the population unreachable by any verdict however much compute was spent;
  * the only door out of the database was a 276-row-per-hour lease (12 x 23 departments) against
    that same population -- 54 days for one pass, against a population that grows faster;
  * the sealed gauntlet reads `data/hypotheses/external_survivors.json` and never opens the
    registry, so a registry cell had no path to a judge at all.

These tests fail if any of the three is reintroduced.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from libs.moat import docket_feed as DF
from libs.moat import registry as R


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "alpha_registry.sqlite"
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(p)
    yield p
    R.set_path(None)


def _mint(conn: sqlite3.Connection, n: int, *, family: str = "carry", symbol: str = "EURUSD",
          session: str = "") -> list[str]:
    """`n` candidates that differ ONLY in their parameters -- the collision the ceiling created."""
    out = []
    for i in range(n):
        cid, _ = R.enqueue_candidate(family=family, symbol=symbol, params={"rr": 1.0 + i},
                                     origin="TEST", session=session, chart="H1", conn=conn)
        out.append(cid)
    return out


def test_parameterised_variants_are_each_reachable(reg: Path) -> None:
    """THE CEILING. 50 cells of one symbol|family|session used to collapse onto ONE identity."""
    conn = R.connect()
    try:
        ids = _mint(conn, 50)
        conn.commit()
        idx = R.candidate_identity_index(conn)
    finally:
        conn.close()
    assert len(ids) == 50, "the fixture must mint 50 distinct candidates"
    # The coarse tier still holds one entry -- that tier IS symbol|family|selector and always was.
    assert len(idx["exact"]) == 1
    # The spec tier is the fix: the parameters are in the key, so every variant is reachable.
    assert len(idx["spec"]) == 50, (
        "each parameterisation must own its own identity; a key without params is a first-come "
        "lock, not an identity")
    assert set(idx["spec"].values()) == set(ids)
    assert set(idx["ids"]) == set(ids)


def test_spec_key_is_the_judges_own_graph_id(reg: Path) -> None:
    """The spec key is `hypothesis_graph.node_id`, which is what the sealed gauntlet stamps on
    every verdict as `graph_id` -- the same string by construction, never by agreement."""
    from libs.research.hypothesis_graph import node_id
    conn = R.connect()
    try:
        cid, _ = R.enqueue_candidate(family="carry", symbol="EURUSD", params={"rr": 2.0},
                                     origin="TEST", conn=conn)
        conn.commit()
        idx = R.candidate_identity_index(conn)
    finally:
        conn.close()
    gid = node_id("EURUSD", "carry", {"rr": 2.0})
    assert idx["spec"].get(gid) == cid
    # A verdict carrying that graph_id now joins the registry's own row instead of dangling.
    got, how = R.verdict_candidate({"cell": "EURUSD.carry.p=deadbeef", "graph_id": gid,
                                    "sym": "EURUSD", "family": "carry"}, {}, idx)
    assert (got, how) == (cid, "graph_id_spec")


def test_a_dangling_graph_id_is_never_reported_as_a_join(reg: Path) -> None:
    """Measured on the box over the last 20,000 verdicts: 19,211 were recorded as `graph_id`
    joins and only 2,614 named a row that exists -- 16,611 false joins."""
    conn = R.connect()
    try:
        R.enqueue_candidate(family="carry", symbol="EURUSD", params={"rr": 2.0}, origin="TEST",
                            conn=conn)
        conn.commit()
        idx = R.candidate_identity_index(conn)
    finally:
        conn.close()
    _, how = R.verdict_candidate({"cell": "NOSUCH.nofamily.p=1", "graph_id": "not_a_real_id",
                                 "sym": "NOSUCH", "family": "nofamily"}, {}, idx)
    assert how == "graph_id_unjoined", how


def test_a_dangling_graph_id_never_marks_a_sibling_judged(reg: Path) -> None:
    """THE REFUSAL THAT PROTECTS THE FEED. A stamp naming a rule this file does not hold is
    evidence the registry never saw the cell. Joining it to a sibling of the same
    symbol|family|selector would mark a candidate judged that no judge looked at -- and the
    docket feed would then stop offering it, so the cell would never BE judged."""
    conn = R.connect()
    try:
        ids = _mint(conn, 6)                 # six EURUSD|carry| siblings, all unjudged
        conn.commit()
        idx = R.candidate_identity_index(conn)
    finally:
        conn.close()
    got, how = R.verdict_candidate(
        {"cell": "EURUSD.carry.p=abc", "graph_id": "a_rule_this_registry_does_not_hold",
         "sym": "EURUSD", "family": "carry"}, {}, idx)
    assert how == "graph_id_unjoined", how
    assert got not in ids, "no sibling may absorb a verdict that was not passed on it"


def test_coarse_identity_prefers_an_unjudged_row(reg: Path) -> None:
    """A triple with many holders must not hand every verdict to the same one forever."""
    conn = R.connect()
    try:
        ids = _mint(conn, 3)
        R.mark_candidate(ids[0], "judged", judged_at="2026-09-24T00:00:00+00:00", conn=conn)
        conn.commit()
        idx = R.candidate_identity_index(conn)
    finally:
        conn.close()
    assert idx["exact"]["eurusd|carry|"] in ids[1:], (
        "the judged incumbent must be displaced by a row still waiting for a verdict")


# ------------------------------------------------------------------------------- the lease
def test_lease_is_measured_from_the_judge_and_never_shrinks(tmp_path: Path) -> None:
    led = tmp_path / "gate_verdict_ledger.jsonl"
    with led.open("w", encoding="utf-8") as fh:
        for i in range(900):
            fh.write(json.dumps({"cell": f"c{i}", "at": "2026-09-22T22:00:0" + str(i % 10)}) + "\n")
        for i in range(10):
            fh.write(json.dumps({"cell": f"d{i}", "at": "2026-09-23T05:00:00"}) + "\n")
    consumed, how = R.judge_consumption_per_hour(led)
    assert consumed == 900, how
    per_dept, why = R.lease_size(23, path=led)
    assert per_dept * 23 >= 900, why
    assert per_dept * 23 >= R.LEASE_FLOOR, "the lease may never fall below the historic one"


def test_lease_floors_when_the_judge_is_unmeasurable(tmp_path: Path) -> None:
    consumed, how = R.judge_consumption_per_hour(tmp_path / "absent.jsonl")
    assert consumed == 0 and how.startswith("UNMEASURED"), how
    per_dept, why = R.lease_size(23, path=tmp_path / "absent.jsonl")
    assert per_dept * 23 >= R.LEASE_FLOOR, why


def test_claim_is_set_based_and_claims_exactly_what_it_returned(reg: Path) -> None:
    conn = R.connect()
    try:
        _mint(conn, 40)
        conn.commit()
        rows = R.claim_candidates("discovery", 25, conn=conn)
        assert len(rows) == 25
        claimed = {str(r[0]) for r in conn.execute(
            "SELECT id FROM research_candidates WHERE status='claimed'")}
        assert claimed == {str(r["id"]) for r in rows}
        assert int(conn.execute("SELECT COUNT(*) FROM research_candidates WHERE status='queued'"
                                ).fetchone()[0]) == 15
    finally:
        conn.close()


# --------------------------------------------------------------- the path into the judge's file
def test_registry_cells_reach_the_docket_stamped(reg: Path) -> None:
    from libs.data.pit import is_stamped
    conn = R.connect()
    try:
        _mint(conn, 5, symbol="EURUSD")
        _mint(conn, 2, symbol="NOTTRADEABLE")
        R.enqueue_candidate(family="discovered", symbol="EURUSD", params={"f": 1}, origin="TEST",
                            conn=conn)
        conn.commit()
        rows, census = DF.feed(conn, tradeable={"EURUSD": "EURUSD"},
                               banned=frozenset({"discovered"}))
    finally:
        conn.close()
    assert census["status"] == "MEASURED", census
    assert census["refused_unstamped"] == 0, census
    assert len(rows) == 5, "untradeable symbols and live-banned families do not reach the judge"
    assert all(is_stamped(r) for r in rows), "the gauntlet's PIT ratchet refuses unstamped rows"
    assert {r["symbol"] for r in rows} == {"EURUSD"}
    assert all(r["source"] == DF.SOURCE for r in rows)


def test_judged_cells_are_not_re_fed(reg: Path) -> None:
    conn = R.connect()
    try:
        ids = _mint(conn, 4)
        R.mark_candidate(ids[0], "judged", judged_at="2026-09-24T00:00:00+00:00", conn=conn)
        R.mark_candidate(ids[1], "survived", survived=1, conn=conn)
        conn.commit()
        rows, _ = DF.feed(conn, tradeable={"EURUSD": "EURUSD"})
    finally:
        conn.close()
    assert {r["candidate_id"] for r in rows} == set(ids[2:])


def test_feed_is_wired_into_the_one_writer_of_the_judges_input() -> None:
    """UNWIRED IS A DEFECT (III.16). The seam is `merge_hypotheses`, the only writer of
    `external_survivors.json`; the sealed gauntlet is never edited and never imported."""
    src = (Path(__file__).resolve().parents[2] / "desks" / "mt5" / "research"
           / "merge_hypotheses.py").read_text(encoding="utf-8")
    assert "from libs.moat.docket_feed import feed" in src
    assert "alpha_registry" in src
    gauntlet = (Path(__file__).resolve().parents[2] / "libs" / "moat"
                / "docket_feed.py").read_text(encoding="utf-8")
    assert "import external_gauntlet" not in gauntlet


def test_the_two_regional_families_are_declared_or_refused() -> None:
    """`exogenous_conditioner` is REGISTERED (432 registry cells, a real series, a real rule);
    `regional_information` is NOT, and that is a decision with a reason, not an oversight."""
    import sys
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    for p in (str(desk),):
        if p not in sys.path:
            sys.path.insert(0, p)
    from mt5desk import families_orthogonal as FO
    assert "exogenous_conditioner" in FO.ORTHOGONAL_FAMILIES
    assert "exogenous_conditioner" in FO.FAMILY_INPUTS
    assert "regional_information" not in FO.ORTHOGONAL_FAMILIES, (
        "its cells declare no series, no column and no rule (pit_status UNMEASURED at birth); "
        "implementing one would invent a mechanism its producer never declared")


def test_exogenous_conditioner_refuses_without_its_series(tmp_path: Path) -> None:
    import sys

    import pandas as pd
    desk = Path(__file__).resolve().parents[2] / "desks" / "mt5"
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    idx = pd.date_range("2026-01-01", periods=300, freq="h", tz="UTC")
    bars = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}, index=idx)
    assert family_exogenous_conditioner(bars, source="nosuchpack", signal="x",
                                        series_root=tmp_path) == [], (
        "a conditioner with no series is not a momentum family; it says nothing")
