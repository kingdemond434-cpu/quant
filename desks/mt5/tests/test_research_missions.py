"""The portfolio creates research missions (acceptance property AP4).

AUDIT P17 (2026-09-08): `research_requests` named the heat gap and the allocator's `opportunity`
block named the unfunded heat by session and family, and neither reached the deepening queue --
the one place research is actually worked from.

What is pinned:

  * a heat gap becomes a mission of kind "mission" with a stable, readable `mission_id`, the
    exposure that is missing, the heat gap, an issue stamp, and the allocator's own reading;
  * dark bands and (capped) empty cells are missions too; a fully funded book issues no heat_gap
    mission but still names its dark bands;
  * mission ids are identical across reruns, so the worker bills a mission once;
  * the queue write goes through the shared writer and replaces ONLY this source's rows;
  * RESEARCH_MISSIONS.json lists the open missions and the candidates tagged to each, and says
    exactly why the tagged list is empty when the compiler drops the tag.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.regime_coverage as rc  # noqa: E402
from research import portfolio_gap as pg  # noqa: E402

OPP = {"opportunity_density": 0.0123, "n_positive_marginal": 7, "n_funded": 3,
       "heat_gap": 0.09,
       "positive_marginal_by_session": {"asia": 0.008, "london_am": 0.003},
       "positive_marginal_by_family": {"overnight": 0.007, "gold": 0.004},
       "research_request": ["9.00% of the heat target is unfundable by the current library at "
                            "its per-sleeve bounds"]}


def _alloc(book: dict[str, float], target: float = 0.20, total: float | None = None,
           opportunity: dict | None = OPP) -> dict:
    d = {"book": book, "marginal_delta_elog": {},
         "heat": {"target": target, "total": target if total is None else total}}
    if opportunity is not None:
        d["opportunity"] = opportunity
    return d


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(pg, "OUT", tmp_path / "portfolio_gap.json")
    monkeypatch.setattr(pg, "ALLOC", tmp_path / "pf_allocation.json")
    monkeypatch.setattr(pg, "SURVIVORS", tmp_path / "absent_survivors.json")
    monkeypatch.setattr(pg, "MISSIONS_OUT", tmp_path / "RESEARCH_MISSIONS.json")
    monkeypatch.setattr(pg, "CANDIDATE_STORES", (tmp_path / "deepened_candidates.json",
                                                 tmp_path / "miner_candidates.json"))
    monkeypatch.setattr(rc, "QUEUE", tmp_path / "queue.json")

    class Desk:
        root = tmp_path

        def queue(self, rows: list[dict]) -> None:
            (tmp_path / "queue.json").write_text(json.dumps({"tasks": rows}), "utf-8")

        def read_queue(self) -> list[dict]:
            p = tmp_path / "queue.json"
            return json.loads(p.read_text("utf-8"))["tasks"] if p.exists() else []

        def missions_report(self) -> dict:
            return json.loads((tmp_path / "RESEARCH_MISSIONS.json").read_text("utf-8"))

    return Desk()


# ------------------------------------------------------------------------------- the missions
def test_a_heat_gap_becomes_a_mission_with_the_fields_the_queue_needs() -> None:
    alloc = _alloc({"gold_asia": 0.11}, target=0.20, total=0.11)
    doc = pg.build(alloc, [])
    at = datetime(2026, 9, 8, 12, tzinfo=UTC)
    ms = pg.missions(doc, alloc, now=at)
    head = ms[0]
    assert head["kind"] == "mission" and head["mission_kind"] == "heat_gap"
    assert head["source"] == "portfolio_gap" and head["status"] is None
    assert head["mission_id"] == "mission:heat_gap:any:any"
    assert head["exposure_missing"] == {"session": "any", "family": "any", "state": "any"}
    assert head["heat_gap"] == pytest.approx(0.09) and head["priority"] == 1
    assert head["issued_at"] == at.isoformat()
    assert head["target_heat"] == 0.20 and head["held_heat"] == 0.11
    # the allocator's own reading rides on every mission
    opp = head["opportunity"]
    assert opp["positive_marginal_by_session"] == OPP["positive_marginal_by_session"]
    assert opp["positive_marginal_by_family"] == OPP["positive_marginal_by_family"]
    assert head["opportunity"]["allocator_heat_gap"] == 0.09
    assert "asia +8.00e-03" in head["description"] and "overnight +7.00e-03" in head["description"]
    assert "MT5/Fusion" in head["description"] and "re-parameterisation" in head["description"]
    assert "funds nothing" in head["rule"]
    # dark bands follow: gold_asia funds the 04-08 band and the other five are dark
    dark = [m for m in ms if m["mission_kind"] == "dark_band"]
    assert [m["exposure_missing"]["session"] for m in dark] == ["00-04", "08-12", "12-16",
                                                                "16-20", "20-24"]
    assert dark[0]["mission_id"] == "mission:dark_band:00-04:any" and dark[0]["priority"] == 2
    assert all(m["opportunity"] == head["opportunity"] for m in ms)


def test_a_fully_funded_book_issues_no_heat_gap_mission_but_still_names_its_dark_bands() -> None:
    alloc = _alloc({"gold_asia": 0.20}, target=0.20, total=0.20)
    ms = pg.missions(pg.build(alloc, []), alloc)
    assert all(m["mission_kind"] != "heat_gap" for m in ms)
    assert sum(1 for m in ms if m["mission_kind"] == "dark_band") == 5
    assert all(m["heat_gap"] == 0.0 for m in ms)


def test_empty_cells_are_missions_up_to_the_cap_and_keyed_on_band_and_family() -> None:
    sv = [{"symbol": "X", "family": f"fam{i}", "window": "asia", "state": "", "side": ""}
          for i in range(5)]
    alloc = _alloc({"gold_asia": 0.20}, target=0.20, total=0.20)
    doc = pg.build(alloc, sv)
    assert len(doc["empty_cells"]) > pg.MAX_EMPTY_CELL_MISSIONS
    ms = [m for m in pg.missions(doc, alloc) if m["mission_kind"] == "empty_cell"]
    assert len(ms) == pg.MAX_EMPTY_CELL_MISSIONS
    first = doc["empty_cells"][0]
    assert ms[0]["mission_id"] == f"mission:empty_cell:{first['band']}:{first['family']}"
    assert ms[0]["exposure_missing"] == {"session": first["band"], "family": first["family"],
                                         "state": "any"}
    assert ms[0]["priority"] == 3


def test_mission_ids_are_stable_across_reruns_and_unique_within_one() -> None:
    alloc = _alloc({"gold_asia": 0.11}, target=0.20, total=0.11)
    doc = pg.build(alloc, [])
    a = [m["mission_id"] for m in pg.missions(doc, alloc)]
    b = [m["mission_id"] for m in pg.missions(doc, alloc, now=datetime(2027, 1, 1, tzinfo=UTC))]
    assert a == b and len(set(a)) == len(a)
    titles = [m["title"] for m in pg.missions(doc, alloc)]
    assert len(set(titles)) == len(titles), "the worker keys a task on its title"


def test_no_opportunity_block_is_named_not_faked() -> None:
    alloc = _alloc({"gold_asia": 0.11}, target=0.20, total=0.11, opportunity=None)
    (m,) = [x for x in pg.missions(pg.build(alloc, []), alloc) if x["mission_kind"] == "heat_gap"]
    assert m["opportunity"]["positive_marginal_by_session"] == {}
    assert "no opportunity block" in m["opportunity"]["basis"]
    assert "no session carries positive unfunded marginal" in m["description"]


# ------------------------------------------------------------------------------- the artifact
def test_write_missions_replaces_only_its_own_queue_rows_and_reports_the_tagging_gap(desk):
    alloc = _alloc({"gold_asia": 0.11}, target=0.20, total=0.11)
    doc = pg.build(alloc, [])
    desk.queue([{"source": "alpha_breadth", "kind": "empty_alpha_cluster", "title": "keep me"},
                {"source": "portfolio_gap", "kind": "mission", "title": "stale mission"}])
    rep = pg.write_missions(doc, alloc)
    assert rep["queue"]["written"] is True and rep["queue"]["n_tasks"] == rep["n_open"]
    q = desk.read_queue()
    assert [t["title"] for t in q if t["source"] == "alpha_breadth"] == ["keep me"]
    mine = [t for t in q if t["source"] == "portfolio_gap"]
    assert len(mine) == rep["n_open"] and all(t["kind"] == "mission" for t in mine)
    assert "stale mission" not in {t["title"] for t in mine}
    saved = desk.missions_report()
    assert saved["n_open"] == rep["n_open"] and saved["by_kind"]["heat_gap"] == 1
    assert saved["by_kind"]["dark_band"] == 5
    assert set(saved["candidates_by_mission"]) == {m["mission_id"] for m in saved["missions"]}
    assert saved["n_candidates_tagged"] == 0
    assert saved["candidate_stores"]["deepened_candidates.json"]["present"] is False
    assert "miner_candidate_compiler._candidate" in saved["tagging_note"]
    assert "row.get('mission_id')" in saved["tagging_note"]


def test_candidates_that_carry_a_mission_id_are_listed_under_their_mission(desk):
    alloc = _alloc({"gold_asia": 0.11}, target=0.20, total=0.11)
    doc = pg.build(alloc, [])
    (desk.root / "deepened_candidates.json").write_text(json.dumps({"candidates": [
        {"symbol": "EURNOK", "family": "overnight_gap_decay", "params": {"k": 1},
         "source": "miner:portfolio_gap", "mission_id": "mission:heat_gap:any:any"},
        {"symbol": "USDJPY", "family": "carry", "source": "miner:x",
         "mission_id": "mission:dark_band:00-04:any"},
        {"symbol": "GBPUSD", "family": "f", "source": "miner:y"},                # untagged
        {"symbol": "AUDNZD", "family": "g", "mission_id": "mission:closed:never:any"},
    ]}), "utf-8")
    (desk.root / "miner_candidates.json").write_text(json.dumps([{"symbol": "Z"}]), "utf-8")
    rep = pg.write_missions(doc, alloc, write_queue=False)
    assert rep["queue"]["written"] is False and "disabled" in rep["queue"]["why"]
    assert desk.read_queue() == []
    assert rep["n_candidates_tagged"] == 2 and rep["tagging_note"] is None
    (c,) = rep["candidates_by_mission"]["mission:heat_gap:any:any"]
    assert c["symbol"] == "EURNOK" and c["store"] == "deepened_candidates.json"
    assert c["params"] == {"k": 1}
    assert rep["candidates_by_mission"]["mission:dark_band:00-04:any"][0]["symbol"] == "USDJPY"
    assert rep["candidate_stores"]["deepened_candidates.json"] == {
        "present": True, "candidates": 4, "with_mission_id": 3}
    assert rep["candidate_stores"]["miner_candidates.json"]["with_mission_id"] == 0


def test_main_writes_the_gap_the_missions_and_the_queue(desk, capsys):
    (desk.root / "pf_allocation.json").write_text(
        json.dumps(_alloc({"gold_asia": 0.11}, target=0.20, total=0.11)), "utf-8")
    assert pg.main() == 0
    assert (desk.root / "portfolio_gap.json").exists()
    rep = desk.missions_report()
    assert rep["n_open"] >= 6 and rep["queue"]["written"] is True
    assert len([t for t in desk.read_queue() if t["source"] == "portfolio_gap"]) == rep["n_open"]
    out = capsys.readouterr().out
    assert "missions:" in out and "RESEARCH_MISSIONS.json" in out
    # no allocation: the gap is UNMEASURED and no mission is invented
    (desk.root / "pf_allocation.json").unlink()
    (desk.root / "RESEARCH_MISSIONS.json").unlink()
    assert pg.main() == 2
    assert not (desk.root / "RESEARCH_MISSIONS.json").exists()
