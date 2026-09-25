"""THE PRODUCERS PANEL MUST CARRY WHAT EACH PRODUCER MADE, NOT ONLY WHAT IT COST.

Measured 2026-09-24 on the trading box: the panel listed 1,981 producers, every row carrying a
compute figure and `UNMEASURED` in all five columns beside it. The desk therefore knew exactly
what each organ SPENT and nothing about what it PRODUCED -- the wrong half of the pair to have,
and the exact input a compute-steering organ needs. The cause was not a missing measurement: the
census held four of the five numbers, nested inside `funnel`, while `desk_dashboard_state`
reads the TOP LEVEL of each row. One level of nesting, five blank columns, 1,981 rows.

These tests pin the contract that closes it, end to end:

  * every producer row publishes all six panel columns AT THE LEVEL THE PANEL READS;
  * a producer the registry scanned and did not find gets a MEASURED ZERO -- a finding -- while a
    producer on a host whose registry would not open stays UNMEASURED (L1.28a, both directions);
  * desk machinery reads NOT_REGIONAL and a namespaced regional name reaches its region, so
    `unattributed` means what it says;
  * the panel's feed publishes EVERY row;
  * per-producer measurement coverage is a ratchet, and it may never be raised by shrinking the
    producer count.
"""
from __future__ import annotations

import importlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

pc = importlib.import_module("desks.mt5.research.productivity_census")
dds = importlib.import_module("desks.mt5.research.desk_dashboard_state")
fence = importlib.import_module("scripts.check_productivity_census")


# --------------------------------------------------------------------------------- fixtures

def _judge_input(path: Path, candidate_ids: list[str]) -> None:
    """The file the sealed gauntlet opens, in the shape `libs/moat/docket_feed` writes it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        [{"symbol": "XAUUSD", "family": "formula", "params": {}, "timeframe": "H1",
          "source": "moat_registry", "candidate_id": cid} for cid in candidate_ids]),
        encoding="utf-8")


def _registry(path: Path, rows: list[dict[str, Any]]) -> None:
    """A registry with the two tables the cell columns are derived from, and nothing else.

    Deliberately minimal: every other query in `measure_registry` is wrapped so a missing table
    contributes nothing, which is itself the behaviour a partial registry must have.
    """
    con = sqlite3.connect(path)
    con.execute("create table discoveries (discovery_id text primary key, generator text, "
                "content_hash text, region text)")
    con.execute("create table research_candidates (id text primary key, generator text, "
                "content_hash text, grid_cell text, mechanism text, status text, "
                "donated_cell text, judged_at text, terminal_gate text, survived int, "
                "family text, discovery_id text, region text)")
    for i, r in enumerate(rows):
        did = r.get("discovery_id")
        if did:
            con.execute("insert or ignore into discoveries values (?,?,?,?)",
                        (did, r.get("discovery_generator"), f"dh{i}", r.get("region")))
        con.execute("insert into research_candidates values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"c{i}", r.get("generator"), f"h{i}", r.get("grid_cell") or f"g{i}",
                     r.get("mechanism") or "m", r.get("status") or "queued",
                     r.get("donated_cell"), r.get("judged_at"), r.get("terminal_gate"), 0,
                     r.get("family"), did, r.get("region")))
    con.commit()
    con.close()


@pytest.fixture()
def census_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every path the census reads at `tmp_path`, and neutralise the compute ledger."""
    reports = tmp_path / "reports"
    reports.mkdir()
    monkeypatch.setattr(pc, "PRODUCER_CENSUS", reports / "PRODUCER_CENSUS.json")
    monkeypatch.setattr(pc, "COMPONENT_REGISTRY", reports / "COMPONENT_REGISTRY.json")
    monkeypatch.setattr(pc, "UNIVERSAL_SURVIVORS", reports / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(pc, "SLEEVE_REGISTRY", tmp_path / "sleeve_registry.json")
    monkeypatch.setattr(pc, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(pc, "ATTRIBUTION", reports / "ATTRIBUTION_COVERAGE.json")
    monkeypatch.setattr(pc, "PRODUCER_YIELD", reports / "PRODUCER_YIELD.json")
    monkeypatch.setattr(pc, "REGISTRY_DB", tmp_path / "alpha_registry.sqlite")
    monkeypatch.setattr(pc, "JUDGE_INPUT", tmp_path / "external_survivors.json")
    monkeypatch.setattr(pc, "measure_compute", lambda _d: {
        "available": True, "why": "", "hours": {"alpha_evolution": {"hours": 7.83, "runs": 4}},
        "window_days": 7.0, "n_runs_priced": 1})
    return tmp_path


def _roster(tmp_path: Path, rows: list[dict[str, Any]]) -> None:
    (tmp_path / "reports" / "PRODUCER_CENSUS.json").write_text(
        json.dumps({"generated_utc": "2026-09-24T00:00:00+00:00", "rows": rows}),
        encoding="utf-8")


def _yield_artifact(tmp_path: Path, added: dict[str, float]) -> None:
    (tmp_path / "reports" / "PRODUCER_YIELD.json").write_text(json.dumps({
        "generated_utc": "2026-09-24T00:00:00+00:00",
        "cells_owed": {
            "window_hours": 24.0,
            "breadth": {"available": True, "total": 2.0},
            "producers": [{"producer": k, "key": k, "orthogonality_added": v}
                          for k, v in added.items()],
        }}), encoding="utf-8")


# ------------------------------------------------------- the six columns, where the panel reads

def test_every_row_publishes_all_six_panel_columns(census_env: Path) -> None:
    """The defect itself: five of six columns lived only inside `funnel` and never rendered."""
    _roster(census_env, [
        {"producer": "alpha_evolution", "kind": "seat", "clock": "hourly_cycle:alpha_evolution"},
        {"producer": "quiet_organ", "kind": "library", "clock": "hourly_cycle:quiet_organ"},
    ])
    _registry(census_env / "alpha_registry.sqlite", [
        {"generator": "alpha_evolution", "grid_cell": "x", "judged_at": "2026-09-24T00:00:00"},
        {"generator": "alpha_evolution", "grid_cell": "y"},
    ])
    _yield_artifact(census_env, {"alpha_evolution": 0.42, "quiet_organ": 0.0})
    _judge_input(census_env / "external_survivors.json", ["c0", "c1"])

    census = pc.build()
    assert census["registry_available"] is True
    rows = {r["key"]: r for r in census["producers"]}
    assert set(pc.PANEL_COLUMNS) == {"cells", "unique_cells", "cells_reached_judge",
                                     "cells_judged", "certificates", "orthogonality_added",
                                     "compute_hours"}
    for key, row in rows.items():
        for col in pc.PANEL_COLUMNS:
            assert col in row, f"{key} does not publish `{col}` at the level the panel reads"
            assert isinstance(row[col], (int, float)), (
                f"{key}.{col} is {row[col]!r}: the registry was scanned, so this is a measured "
                "number or a measured zero, never UNMEASURED")
    assert rows["alpha_evolution"]["cells"] == 2
    assert rows["alpha_evolution"]["unique_cells"] == 2
    assert rows["alpha_evolution"]["cells_reached_judge"] == 2
    assert rows["alpha_evolution"]["reach_cause"].startswith("REACHING")
    assert rows["alpha_evolution"]["cells_judged"] == 1
    assert rows["alpha_evolution"]["orthogonality_added"] == 0.42
    assert rows["alpha_evolution"]["compute_hours"] == pytest.approx(7.83)
    cov = census["measurement_coverage"]
    assert all(v["coverage"] == 1.0 for v in cov["columns"].values())
    assert cov["fully_measured_rows"] == cov["n_producers"] == 2


def test_a_producer_the_registry_did_not_find_is_a_measured_zero(census_env: Path) -> None:
    """Scanned and absent is a FINDING with its compute beside it, never an absence."""
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat",
                          "clock": "hourly_cycle:alpha_evolution"}])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "someone_else"}])

    row = next(r for r in pc.build()["producers"] if r["key"] == "alpha_evolution")
    assert row["cells"] == 0 and row["unique_cells"] == 0 and row["cells_judged"] == 0
    assert row["compute_hours"] == pytest.approx(7.83), (
        "the whole point: a measured zero of output standing beside a measured compute cost")
    assert any(z["key"] == "alpha_evolution" for z in pc.build()["zero_cell_compute"])


def test_no_registry_keeps_every_cell_stage_unmeasured(census_env: Path) -> None:
    """The other direction of L1.28a: nothing was scanned, so nothing may read as a zero."""
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat", "clock": "hourly"}])
    # no registry file written at all
    census = pc.build()
    assert census["registry_available"] is False
    row = next(r for r in census["producers"] if r["key"] == "alpha_evolution")
    for col in ("cells", "unique_cells", "cells_judged"):
        assert row[col] == "UNMEASURED", f"{col} claimed a zero on a host that never looked"
    assert row["compute_hours"] == pytest.approx(7.83)
    assert census["measurement_coverage"]["columns"]["cells"]["coverage"] == 0.0


def test_orthogonality_absent_is_unmeasured_with_a_reason(census_env: Path) -> None:
    """The one column with an outside source says WHY when it has none. Never a silent zero."""
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat", "clock": "hourly"}])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "alpha_evolution"}])
    census = pc.build()
    row = next(r for r in census["producers"] if r["key"] == "alpha_evolution")
    assert row["orthogonality_added"] == "UNMEASURED"
    why = census["orthogonality"]["why"]
    assert "PRODUCER_YIELD" in why and "UNMEASURED" in why
    assert "check_producer_yield" in why, "an UNMEASURED verdict must name its remedy"


# ------------------------------------------------- REACHED THE JUDGE: the stage nobody measured

def test_a_producer_whose_cells_reach_no_judge_is_a_named_defect(census_env: Path) -> None:
    """THE MATHS LAB'S DEFECT, IN ONE TEST.

    8,677 objects generated, 33 donated, 51 candidate rows stamped `donated` -- and for a long
    time not one of them in any file the sealed gauntlet opens. `gauntlet_submitted` said the
    producer had submitted, because `gauntlet_submitted` reads a status the producer sets on
    ITSELF. Only the judge's own input file can answer whether a cell is in front of a judge, and
    a producer that spent compute and reached it with nothing must say so by name.
    """
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat", "clock": "hourly"}])
    _registry(census_env / "alpha_registry.sqlite", [
        {"generator": "alpha_evolution", "grid_cell": "a", "status": "donated"},
        {"generator": "alpha_evolution", "grid_cell": "b", "status": "donated"},
    ])
    # the judge's input names a DIFFERENT candidate: the file is readable, so this is a measured
    # zero for this producer and not an UNMEASURED one
    _judge_input(census_env / "external_survivors.json", ["someone_elses_cell"])

    census = pc.build()
    row = next(r for r in census["producers"] if r["key"] == "alpha_evolution")
    assert row["cells"] == 2, "the cells exist"
    assert row["funnel"]["gauntlet_submitted"] == 2, "and the producer says it submitted them"
    assert row["cells_reached_judge"] == 0, "and not one of them is in front of a judge"
    assert row["reach_cause"].startswith("NOT_REACHING"), row["reach_cause"]
    assert row["ratios"]["reach_ratio"] == 0.0

    reach = census["reach"]
    assert reach["cells_generated"] == 2 and reach["cells_reached_judge"] == 0
    assert reach["reach_ratio"] == 0.0
    assert reach["n_not_reaching"] == 1
    assert reach["not_reaching"][0]["producer"] == "alpha_evolution"
    assert reach["judge_input"]["status"] == "MEASURED"


def test_an_unreadable_judge_input_is_unmeasured_and_never_zero(census_env: Path) -> None:
    """L1.28a in the direction that matters: `nobody reached` and `we did not look` differ."""
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat", "clock": "hourly"}])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "alpha_evolution"}])
    # no judge input file written at all
    census = pc.build()
    row = next(r for r in census["producers"] if r["key"] == "alpha_evolution")
    assert row["cells_reached_judge"] == "UNMEASURED"
    assert row["reach_cause"].startswith("UNMEASURED")
    assert census["reach"]["judge_input"]["status"] == "UNMEASURED"
    assert "not readable" in str(census["reach"]["judge_input"].get("why"))


def test_a_readable_judge_input_with_no_candidate_ids_is_still_unmeasured(
        census_env: Path) -> None:
    """THE BUG THIS COLUMN ALMOST SHIPPED WITH, caught on the build box before it landed.

    `external_survivors.json` here is 76 MB and names ZERO registry candidate ids, because the
    registry feed has never run on this host. The file opened, so `status` was MEASURED, so
    every one of 1,653 producers got a measured zero and the coverage ratchet recorded 1.00 for
    a column that had measured nothing. A file that opened is not a measurement; a file that
    named something is. Both conditions, or UNMEASURED.
    """
    _roster(census_env, [{"producer": "alpha_evolution", "kind": "seat", "clock": "hourly"}])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "alpha_evolution"}])
    (census_env / "external_survivors.json").write_text(
        json.dumps([{"sym": "XAUUSD", "family": "carry", "params": {}}]), encoding="utf-8")

    census = pc.build()
    row = next(r for r in census["producers"] if r["key"] == "alpha_evolution")
    assert row["cells_reached_judge"] == "UNMEASURED", (
        "a judge input that opened but named no candidate is not a desk where nobody reached")
    assert row["reach_cause"].startswith("UNMEASURED")
    assert census["reach"]["judge_input"]["reach_measurable"] is False
    assert census["measurement_coverage"]["columns"]["cells_reached_judge"]["coverage"] == 0.0


def test_the_id_scan_survives_a_chunk_boundary(tmp_path: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """A candidate id split across two reads must still be found, or reach silently under-counts."""
    path = tmp_path / "judge.json"
    _judge_input(path, [f"cand_{i:06d}" for i in range(400)])
    monkeypatch.setattr(pc, "_CHUNK", 137)          # force many boundaries mid-record
    found, meta = pc._judge_input_ids(path)
    assert meta["status"] == "MEASURED"
    assert len(found) == 400 and "cand_000399" in found


def test_reach_rising_fails_the_fence_and_falling_ratchets(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The order is 100%; the fence holds the line so a new producer cannot land unwired."""
    def _census(n_not_reaching: int) -> dict[str, Any]:
        doc = _coverage(1000, 1.0)
        doc["reach"] = {
            "judge_input": {"status": "MEASURED", "candidate_ids": 12},
            "cells_generated": 100, "cells_donated": 80,
            "cells_reached_judge": 60, "cells_judged": 10, "reach_ratio": 0.6,
            "n_not_reaching": n_not_reaching,
            "not_reaching": [{"producer": f"p{i}", "cells": 5} for i in range(n_not_reaching)],
        }
        return doc

    _fence_env(tmp_path, monkeypatch, _census(9),
               {"hosts": {"BUILDBOX": {"not_reaching_best": 4}}})
    failures = fence.check()["failures"]
    assert failures and "reach NO judge" in failures[0] and "up from the recorded best 4" in \
        failures[0]

    _fence_env(tmp_path, monkeypatch, _census(2),
               {"hosts": {"BUILDBOX": {"not_reaching_best": 4}}})
    verdict = fence.check(tighten=True)
    assert not verdict["failures"], "an improvement is never a failure"
    rat = json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))
    assert rat["hosts"]["BUILDBOX"]["not_reaching_best"] == 2, "the debt ratchets DOWN only"


def test_a_named_reason_is_the_only_way_past_a_reach_regression(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = _coverage(1000, 1.0)
    doc["reach"] = {"judge_input": {"status": "MEASURED"}, "cells_generated": 1,
                    "cells_donated": 1, "cells_reached_judge": 0, "cells_judged": 0,
                    "reach_ratio": 0.0, "n_not_reaching": 40, "not_reaching": []}
    _fence_env(tmp_path, monkeypatch, doc,
               {"hosts": {"BUILDBOX": {"not_reaching_best": 4,
                                       "reach_regression_reason": "the registry was rebuilt on "
                                                                  "2026-09-24 and the merge has "
                                                                  "not run since"}}})
    assert not fence.check()["failures"]


def test_dropping_the_reach_block_after_it_existed_is_a_regression(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fence_env(tmp_path, monkeypatch, _coverage(1000, 1.0),
               {"hosts": {"BUILDBOX": {"not_reaching_best": 4}}})
    verdict = fence.check()
    assert verdict["failures"] and "REGRESSION" in verdict["failures"][0]
    assert verdict["reach"]["verdict"] == "UNMEASURED"


# ---------------------------------------------------------------------------------- the region

def test_desk_machinery_is_not_regional_and_a_namespaced_name_reaches_its_region(
        census_env: Path) -> None:
    """`unattributed` for everything was the defect; NOT_REGIONAL is the verdict for machinery."""
    _roster(census_env, [
        {"producer": "executable:scripts/acquire_data.py", "kind": "executable",
         "clock": "hourly"},
        {"producer": "discovery_compiler", "kind": "generator", "clock": "hourly"},
        {"producer": "japan_gotobi", "kind": "seat", "clock": "hourly"},
    ])
    _registry(census_env / "alpha_registry.sqlite", [
        {"generator": "forest_runner:china:academic", "grid_cell": "a"},
        {"generator": "miner:asia:rba_tables", "grid_cell": "b"},
    ])
    rows = {r["key"]: r for r in pc.build()["producers"]}

    # `_norm` collapses a path-shaped producer onto its stem, exactly as the registry key does
    assert rows["acquire_data"]["region"] == pc.NOT_REGIONAL
    assert rows["acquire_data"]["region_route"] == "roster_kind:executable"
    assert rows["discovery_compiler"]["region"] == pc.NOT_REGIONAL
    assert rows["japan_gotobi"]["region"] == "Japan"
    # the namespace ladder: neither the whole string nor its head is a region token
    assert rows["forest_runner:china:academic"]["region"] == "China"
    assert rows["forest_runner:china:academic"]["region_route"] == "namespace"
    for row in rows.values():
        assert row["region"] != pc.UNATTRIBUTED, row["producer"]
        assert row["region_route"], "every region must name the route that reached it"


def test_not_regional_rolls_up_into_its_own_bucket(census_env: Path) -> None:
    """A verdict filed under `unattributed` is a gap the desk does not have."""
    _roster(census_env, [{"producer": "discovery_compiler", "kind": "generator",
                          "clock": "hourly"}])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "discovery_compiler"}])
    census = pc.build()
    assert pc.NOT_REGIONAL in pc.ROLLUP_BUCKETS
    assert census["by_region"][pc.NOT_REGIONAL]["producers"] == 1
    assert census["by_region"][pc.UNATTRIBUTED]["producers"] == 0
    assert census["measurement_coverage"]["region"]["coverage"] == 1.0


# ----------------------------------------------------------------- the panel publishes them all

def test_the_panel_feed_publishes_every_row_and_renders_every_column(
        census_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """60 of 1,981 published with 1,921 withheld was itself a measurement gap."""
    _roster(census_env, [{"producer": f"p{i:04d}", "kind": "library", "clock": "hourly"}
                         for i in range(200)])
    _registry(census_env / "alpha_registry.sqlite", [{"generator": "p0007", "grid_cell": "z"}])
    _yield_artifact(census_env, {f"p{i:04d}": 0.1 for i in range(200)})
    out = tmp_path / "desks" / "mt5" / "reports" / "PRODUCTIVITY_CENSUS.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pc.build(), default=str), encoding="utf-8")

    monkeypatch.setattr(dds, "ROOT", tmp_path)
    panel = dds._producers(deadline=float("inf"))
    assert panel["n_rows"] == 200 and len(panel["rows"]) == 200
    assert panel["rows_truncated"] == 0
    for row in panel["rows"]:
        for col in ("cells", "unique_cells", "cells_judged", "certificates",
                    "orthogonality_added", "compute_hours"):
            assert row[col] != "UNMEASURED", (
                f"{row['producer']}.{col} still renders UNMEASURED: the panel reads the row's "
                "top level and the census must publish there")
        assert row["region"] == pc.NOT_REGIONAL


# ------------------------------------------------------------------------------- the ratchet

def _fence_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
               census: dict[str, Any], ratchet: dict[str, Any]) -> None:
    cpath, rpath = tmp_path / "CENSUS.json", tmp_path / "ratchet.json"
    cpath.write_text(json.dumps(census), encoding="utf-8")
    rpath.write_text(json.dumps(ratchet), encoding="utf-8")
    monkeypatch.setattr(fence, "CENSUS", cpath)
    monkeypatch.setattr(fence, "RATCHET", rpath)
    monkeypatch.setattr(fence, "BLOCKERS", tmp_path / "blockers.json")
    monkeypatch.setattr(fence, "ROOT", tmp_path)


def _coverage(n: int, cells: float, region: float = 1.0,
              host: str = "BUILDBOX") -> dict[str, Any]:
    from datetime import UTC, datetime
    covered = round(n * region)
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": host,
        "zero_cell_compute": [],
        "measurement_coverage": {
            "n_producers": n,
            "columns": {"cells": {"measured": int(n * cells), "of": n, "coverage": cells,
                                  "nonzero": 1}},
            "region": {"coverage": region, "regional": 0, "not_regional": covered, "of": n,
                       "unattributed": n - covered},
            "fully_measured_rows": int(n * cells),
        },
    }


def test_coverage_falling_fails_the_fence(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    _fence_env(tmp_path, monkeypatch, _coverage(1000, 0.5),
               {"columns_best": {"cells": 1.0}, "n_producers_best": 1000})
    verdict = fence.check()
    assert verdict["failures"], "a coverage regression must fail"
    assert "cells" in verdict["failures"][0] and "ratchet rises only" in verdict["failures"][0]


def test_coverage_may_not_be_raised_by_shrinking_the_denominator(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The rule that matters most: never improve a ratio by removing producers (L1.50)."""
    _fence_env(tmp_path, monkeypatch, _coverage(12, 1.0),
               {"columns_best": {"cells": 1.0}, "n_producers_best": 1000})
    verdict = fence.check()
    assert verdict["failures"]
    assert "removing producers from the denominator" in verdict["failures"][0]


def test_seeding_an_empty_ratchet_is_not_a_failure(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    _fence_env(tmp_path, monkeypatch, _coverage(1000, 1.0), {})
    verdict = fence.check(tighten=True)
    assert not verdict["failures"]
    rat = json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))
    mine = rat["hosts"]["BUILDBOX"]
    assert mine["columns_best"]["cells"] == 1.0 and mine["n_producers_best"] == 1000
    assert mine["seeded"], "a seeded ratchet records when its baseline was taken"


def test_one_hosts_bar_is_never_another_hosts_bar(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Two machines, two registries, two rosters -- and one file in the repository.

    The trading box censused 1,998 producers on the day this landed and the build box 1,653. A
    shared `n_producers_best` would have the box raise the bar and the build box then fail the
    denominator clause for being a different computer, which is the same mistake as sizing a
    memory floor off the other box. Each host ratchets against its own history.
    """
    _fence_env(tmp_path, monkeypatch, _coverage(1653, 1.0, host="BUILDBOX"),
               {"hosts": {"TRADINGBOX": {"n_producers_best": 1998,
                                         "columns_best": {"cells": 1.0},
                                         "measured_best": {"cells": 1998}}}})
    verdict = fence.check(tighten=True)
    assert not verdict["failures"], "a smaller host must not fail against a bigger host's bar"
    assert verdict["ratchet_host"] == "BUILDBOX"
    rat = json.loads((tmp_path / "ratchet.json").read_text(encoding="utf-8"))
    assert rat["hosts"]["TRADINGBOX"]["n_producers_best"] == 1998, "the other host is untouched"
    assert rat["hosts"]["BUILDBOX"]["n_producers_best"] == 1653


def test_new_producers_may_dilute_the_share_but_never_the_count(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A growing desk must not fail its own gate for growing.

    The registry gained five producers between two runs of this census while it was being
    written. A share-only ratchet fails on the ARRIVAL OF NEW WORK, which is how a gate comes to
    be switched off. So the roster growing is allowed to dilute the share -- and the COUNT of
    producers measured still may not fall, which is the half that cannot be gamed.
    """
    # 1000 producers all measured -> 1100 producers, 1000 still measured: share 1.0 -> 0.909
    grown = _coverage(1100, 1000 / 1100)
    _fence_env(tmp_path, monkeypatch, grown,
               {"columns_best": {"cells": 1.0}, "measured_best": {"cells": 1000},
                "n_producers_best": 1000})
    assert not fence.check()["failures"], "growth is not a regression"

    # same roster size, 100 producers stopped being measured: that IS a regression
    shrunk = _coverage(1100, 900 / 1100)
    _fence_env(tmp_path, monkeypatch, shrunk,
               {"columns_best": {"cells": 1.0}, "measured_best": {"cells": 1000},
                "n_producers_best": 1100})
    failures = fence.check()["failures"]
    assert failures and "measuring FEWER producers" in failures[0]


def test_a_region_that_became_unattributed_again_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fence_env(tmp_path, monkeypatch, _coverage(1000, 1.0, region=0.5),
               {"columns_best": {"cells": 1.0}, "measured_best": {"cells": 1000},
                "n_producers_best": 1000, "region_coverage_best": 0.93,
                "region_measured_best": 930})
    failures = fence.check()["failures"]
    assert failures and "region coverage fell" in failures[0]


def test_a_named_regression_reason_is_the_only_way_past(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The escape hatch is a SENTENCE, never a lowered bar or a smaller roster."""
    _fence_env(tmp_path, monkeypatch, _coverage(1000, 0.2),
               {"columns_best": {"cells": 1.0}, "measured_best": {"cells": 1000},
                "n_producers_best": 1000,
                "regression_reason": "the registry was rebuilt on 2026-09-24; cells reattribute "
                                     "over the next hourly pass"})
    assert not fence.check()["failures"]


def test_dropping_the_coverage_block_after_it_existed_is_a_regression(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence where a measurement stood is the failure this whole pass exists to prevent."""
    census = _coverage(1000, 1.0)
    del census["measurement_coverage"]
    _fence_env(tmp_path, monkeypatch, census,
               {"columns_best": {"cells": 1.0}, "n_producers_best": 1000})
    verdict = fence.check()
    assert verdict["failures"] and "REGRESSION" in verdict["failures"][0]
    assert verdict["coverage"]["verdict"] == "UNMEASURED"
