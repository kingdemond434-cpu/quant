"""A culture-stamped registry row reaches the judge's docket with its culture AND its lineage.

The Tier S cross-culture test (#113) groups verdicts by `source_culture` and by the producer that
minted the cell. `docket_feed._row` used to drop both: the SELECT named eleven columns and the
four culture fields and `lineage_json` were never read, so every docket row arrived culture-blind
and parentless and the test had nothing to group by.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from libs.moat import docket_feed as DF
from libs.moat import registry as R


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    p = tmp_path / "alpha_registry.sqlite"
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(p)
    yield p
    R.set_path(None)


def test_a_culture_stamped_row_reaches_the_docket_with_all_four_fields_and_lineage(
        reg: Path) -> None:
    lineage = {"producer": "swarm:KR:fx:H1:asia_momentum", "parent_family": "asia_momentum"}
    cid, _ = R.enqueue_candidate(
        family="asia_momentum", symbol="USDKRW", params={"rr": 1.5}, origin="TEST",
        source_culture="KR/ko", participant_structure="retail_heavy",
        failure_mode_hypothesis="Korean retail chases the open and exhausts by lunch.",
        crowding_prior="low", lineage_json=json.dumps(lineage))
    conn = R.connect()
    try:
        rows = [r for r in DF.candidate_rows(conn) if r["candidate_id"] == cid]
    finally:
        conn.close()
    assert len(rows) == 1
    row = rows[0]
    assert row["source_culture"] == "KR/ko"
    assert row["participant_structure"] == "retail_heavy"
    assert row["failure_mode_hypothesis"] == (
        "Korean retail chases the open and exhausts by lunch.")
    assert row["crowding_prior"] == "low"
    assert row["culture_derivation"]["source_culture"] == "declared"
    assert json.loads(row["lineage_json"]) == lineage


def test_an_unstamped_row_carries_unmeasured_never_a_guess_and_no_empty_lineage(
        reg: Path) -> None:
    cid, _ = R.enqueue_candidate(family="carry", symbol="EURUSD", params={}, origin="TEST")
    conn = R.connect()
    try:
        row = next(r for r in DF.candidate_rows(conn) if r["candidate_id"] == cid)
    finally:
        conn.close()
    for f in ("source_culture", "participant_structure", "failure_mode_hypothesis",
              "crowding_prior"):
        assert f in row
    assert row["crowding_prior"] in ("low", "medium", "high", "UNMEASURED")
    assert "lineage_json" not in row


def test_a_registry_without_the_columns_still_feeds() -> None:
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("create table research_candidates(seq integer primary key, id text, "
                 "symbol text, family text, params_json text, chart text, origin text, "
                 "mechanism text, grid_cell text, score real, created_at text, "
                 "content_hash text, judged_at text, status text)")
    conn.execute("insert into research_candidates(id,symbol,family,params_json) "
                 "values('c1','EURUSD','carry','{}')")
    rows = list(DF.candidate_rows(conn))
    assert len(rows) == 1 and "lineage_json" not in rows[0] and "source_culture" not in rows[0]
