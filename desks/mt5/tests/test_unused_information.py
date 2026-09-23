"""The unused-information miner, against a whole desk planted in a tmp tree.

Every assertion is about a verdict the ARTIFACT publishes -- a register a reader can act on, a
priority they can rank by, an `unmeasured` row that names the file this box does not hold. The
planted tree is built so the answer is known before the code runs: ONE series whose path a family
declares (USED), ONE whose path nothing declares (UNUSED), an axis with real breadth and depth so
its price has to beat a bare axis value, and three sources deliberately absent so `unmeasured` has
to name them rather than resolve to a clean zero.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import unused_information as ui  # noqa: E402

#: The family declarations the planted desk is judged against. `contract_terms` is declared;
#: nothing here mentions a triangle, a BIS policy rate or a Tokyo fixing.
PLANTED_FAMILIES = {"carry": ("contract/swap terms", "data/tape/contract_terms"),
                    "vol_transition": ("price only", None)}


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


@pytest.fixture
def rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """A desk in a tmp tree: five sources present, three deliberately absent, one tmp registry."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    axes = data / "axes"

    _write(reports / "MOAT_SERIES.json", {"at": "2026-09-17T00:00:00+00:00", "series": [
        {"name": "financing_tape", "kind": "raw", "moat_class": "high", "owner": "tape.py",
         "path_pattern": "data/tape/contract_terms/<YYYY-MM-DD>.parquet",
         "instruments": 40, "days": 100, "moat_score": 300.0},
        {"name": "triangle_executable", "kind": "derived", "moat_class": "medium",
         "owner": "triangle_tape.py", "path_pattern": "data/tape/triangle_executable.json",
         "instruments": 12, "days": 60, "moat_score": 90.0},
    ]})
    _write(axes / "bis.json", {"axis": "policy", "id": "bis_policy_rates", "source": "bis",
                               "at": "2026-09-12T00:00:00+00:00", "n_rows": 464803,
                               "n_symbols": 3, "symbols": ["EURUSD", "AUDJPY", "GBPUSD"],
                               "rows": [{"symbol": "EURUSD", "knowable_at": "2016-01-01"}]})
    _write(reports / "AXIS_REGISTRY.json", {"axes": {
        "mechanism": {"carry": 12, "breakout_liquidity": 4, "UNKNOWN": 9},
        "information_source": {"price_only": 20, "microstructure": 2},
        "instrument": {"XAUUSD": 33},   # SKIP_AXES: an instrument list is not an information axis
    }})
    _write(data / "forced_flow_calendar.json", {"n_events": 3, "events": [
        {"date": "2025-01-31", "kind": "month_end", "name": "month_end_2025-01-31",
         "instruments": ["EURUSD", "XAUUSD"]},
        {"date": "2026-01-30", "kind": "month_end", "name": "month_end_2026-01-30",
         "instruments": ["EURUSD"]},
        {"date": "2026-02-02", "kind": "fixing", "name": "tokyo_0955_2026-02-02",
         "instruments": ["AUDJPY"]},
    ]})
    _write(reports / "CAUSAL_LAB.json", {"n_edges": 1, "edges": [
        {"from": "cot.USDJPY", "to": "bis.GBPUSD", "lag": 3, "n": 497, "q": 3e-05,
         "klass": "OBSERVATIONAL"}]})
    _write(reports / "STANDING_QUESTIONS.json", {"questions": {"Q1": {"status": "OK", "n": 2,
        "findings": [{"target": "CHFNOK", "feature": "clock_hour_01", "category": "clock",
                      "lift": 4.49, "p_perm": 0.005, "n_bars": 19999}]}},
        "no_family": [{"question": "Q1", "why": "clock_hour_01 sits at 4.49x"}]})
    _write(reports / "markout.json", {"at": "2026-09-08T00:00:00+00:00", "usable": False,
                                      "n_matched": 0, "n_unfilled_intents": 28,
                                      "edge_share": None, "why": "no matched pairs yet"})
    # The graph's ONE tested cell trades carry on EURUSD; nothing in it names a triangle.
    graph = data / "hypothesis_graph.jsonl"
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_text("\n".join(json.dumps(r) for r in [
        {"id": "c1", "symbol": "EURUSD", "family": "carry", "params": {"lookback": 120},
         "region": "EURUSD.carry{}", "source": "miner:planted", "fate": "JUDGED",
         "gates": {"validity": True}},
        {"id": "c2", "symbol": "XAUUSD", "family": "vol_transition", "params": {},
         "region": "XAUUSD.vol_transition{}", "source": "miner:planted", "fate": "BORN",
         "gates": {}},
    ]) + "\n", encoding="utf-8")
    _write(data / "sleeves.json", {"sleeves": [
        {"name": "eur_carry_asia", "symbol": "EURUSD", "family": "carry", "timeframe": "H1",
         "session": "asia", "status": "LIVE"},
        {"name": "retired_one", "symbol": "XAUUSD", "family": "triangle", "status": "RETIRED"},
    ]})

    for name, value in (("DATA", data), ("REPORTS", reports), ("AXES_DIR", axes),
                        ("MOAT_SERIES", reports / "MOAT_SERIES.json"),
                        ("AXIS_REGISTRY", reports / "AXIS_REGISTRY.json"),
                        ("FORCED_FLOW", data / "forced_flow_calendar.json"),
                        ("CAUSAL_LAB", reports / "CAUSAL_LAB.json"),
                        ("CAUSAL_GRAPH", reports / "WORLD_CAUSAL_GRAPH.json"),   # absent
                        ("RESIDUAL_QUEUE", reports / "RESIDUAL_QUEUE.json"),     # absent
                        ("STANDING_QUESTIONS", reports / "STANDING_QUESTIONS.json"),
                        ("EXECUTION_ALPHA", reports / "EXECUTION_ALPHA.json"),   # absent
                        ("MARKOUT", reports / "markout.json"),
                        ("WIRING_CEO", reports / "WIRING_CEO.json"),             # absent
                        ("HYPOTHESIS_GRAPH", graph),
                        ("SLEEVES", data / "sleeves.json"),
                        ("OUT", reports / "UNUSED_INFORMATION.json")):
        monkeypatch.setattr(ui, name, value)
    monkeypatch.setattr(ui, "_family_inputs",
                        lambda: (dict(PLANTED_FAMILIES),
                                 ui._tokens(*PLANTED_FAMILIES,
                                            *[x for v in PLANTED_FAMILIES.values() for x in v])))
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield {"tmp": tmp_path, "out": reports / "UNUSED_INFORMATION.json", "reports": reports}
    R.set_path(None)


def _item(report: dict, register: str, name: str) -> dict:
    return next(r for r in report["registers"][register] if r["item"] == name)


# ------------------------------------------------------------------------- the consumption --

def test_a_series_a_family_declares_is_used_and_names_where_it_was_found(rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    row = _item(rep, "UNUSED_DATA", "financing_tape")
    assert row["used"] is True
    assert row["evidence"]["matched"] == [{"probe": "contract_terms", "where": "declared"}]
    assert any("declared" in s for s in row["evidence"]["searched"])


def test_a_series_nothing_declares_is_unused_and_carries_the_evidence_of_the_search(
        rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    row = _item(rep, "UNUSED_DATA", "triangle_executable")
    assert row["used"] is False
    assert row["evidence"]["matched"] == []
    assert "triangle_executable" in row["probes"]
    # The three corpora and their sizes are IN the artifact: "unused" is falsifiable, not an
    # opinion -- a reader can re-run the same three searches.
    searched = " ".join(row["evidence"]["searched"])
    assert "declared" in searched and "tested" in searched and "live" in searched
    assert "1 tested cells of 2 graph rows" in searched
    assert "1 LIVE sleeves" in searched


def test_the_live_sleeve_and_the_tested_cell_are_separate_searches(rig: dict) -> None:
    seen, sizes = ui.consumption(deadline=float("inf"))
    assert sizes == {"n_families": 2, "graph_rows": 2, "tested_cells": 1, "live_sleeves": 1}
    assert "eurusd" in seen.corpora["live"] and "eur_carry_asia" in seen.corpora["live"]
    assert "xauusd" not in seen.corpora["live"]          # RETIRED is not consumption
    assert "xauusd" not in seen.corpora["tested"]        # BORN with no gates is not a test
    assert "eurusd" in seen.corpora["tested"]


# ----------------------------------------------------------------------------- the registers --

def test_every_register_is_populated_from_its_own_source(rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    assert set(rep["registers"]) == set(ui.REGISTERS)
    got = {k: {r["source"] for r in v} for k, v in rep["registers"].items()}
    assert got["UNUSED_DATA"] == {"MOAT_SERIES.json"}
    assert got["UNUSED_STATE"] == {"data/axes/bis.json"}
    assert got["UNUSED_FEATURE"] == {"AXIS_REGISTRY.json"}
    assert got["UNUSED_EVENT"] == {"forced_flow_calendar.json"}
    assert got["UNUSED_RELATIONSHIP"] == {"CAUSAL_LAB.json"}
    assert got["UNEXPLAINED_PNL"] == {"STANDING_QUESTIONS.json"}
    assert got["UNEXPLAINED_EXECUTION"] == {"markout.json"}
    # The instrument axis is skipped by declaration -- 300 true negatives are not a register.
    assert not any(r["item"].startswith("instrument=") for r in rep["registers"]["UNUSED_FEATURE"])
    assert {r["item"] for r in rep["registers"]["UNUSED_EVENT"]} == {"month_end", "fixing"}
    assert rep["n_items"] == rep["n_used"] + rep["n_unused"]


def test_an_absent_source_is_unmeasured_by_name_and_never_a_clean_zero(rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    named = {u["what"]: u["why"] for u in rep["unmeasured"]}
    assert "UNUSED_FEATURE:organs" in named and "WIRING_CEO.json" in named["UNUSED_FEATURE:organs"]
    assert "RESIDUAL_QUEUE.json" in named["UNEXPLAINED_PNL:residual_queue"]
    assert "EXECUTION_ALPHA.json" in named["UNEXPLAINED_EXECUTION:execution_alpha"]
    assert "WORLD_CAUSAL_GRAPH.json" in named["UNUSED_RELATIONSHIP:WORLD_CAUSAL_GRAPH.json"]
    # ...and none of them silently produced an item.
    assert not any(r["source"] == "WIRING_CEO.json"
                   for v in rep["registers"].values() for r in v)


# --------------------------------------------------------------------------------- the price --

def test_priority_is_breadth_times_depth_times_moat_over_cost_and_orders_the_top(
        rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    tri = _item(rep, "UNUSED_DATA", "triangle_executable")
    assert tri["information_value"] == pytest.approx(12 * 60 * 90.0)
    assert tri["cost_to_wire"] == ui.COST_TO_WIRE["UNUSED_DATA"]
    assert tri["priority"] == pytest.approx(12 * 60 * 90.0 * 1.0 / (1.0 + 3.0), abs=1e-4)
    # An axis with 3 instruments and years of depth must out-price a bare axis VALUE.
    axis = _item(rep, "UNUSED_STATE", "bis.bis_policy_rates")
    feature = _item(rep, "UNUSED_FEATURE", "mechanism=breakout_liquidity")
    assert axis["priority"] > feature["priority"] > 0
    assert axis["depth_days"] and axis["depth_days"] > 1000
    assert axis["breadth_instruments"] == 3
    tops = [t["priority"] for t in rep["top_priorities"]]
    assert tops == sorted(tops, reverse=True)
    assert all(not _item(rep, t["register"], t["item"])["used"] for t in rep["top_priorities"])


def test_an_unmeasured_depth_or_moat_defaults_to_one_and_never_to_a_flattering_number(
        rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=True)
    feature = _item(rep, "UNUSED_FEATURE", "mechanism=breakout_liquidity")
    assert feature["depth_days"] is None and feature["moat_score"] is None
    assert feature["information_value"] == pytest.approx(1.0)
    assert feature["priority"] == pytest.approx(
        1.0 / (1.0 + ui.COST_TO_WIRE["UNUSED_FEATURE"]), abs=1e-4)


# --------------------------------------------------------------------------- the discoveries --

def test_only_unused_items_above_the_median_become_discoveries(rig: dict) -> None:
    rep = ui.run(budget_s=30, dry_run=False)
    unused = [r for v in rep["registers"].values() for r in v if not r["used"]]
    due = [r for r in unused if r["priority"] > rep["priority_median_unused"]]
    assert due and len(due) < len(unused)                     # the median actually bites
    assert rep["discoveries_recorded"] == len(due)
    rows = R.discoveries()
    assert len(rows) == len(due)
    assert {str(r["state"]) for r in rows} == {"UNPROCESSED"}
    assert {str(r["source_type"]) for r in rows} == {"unused_information"}
    assert {str(r["origin"]) for r in rows} == {"MOAT"}
    payloads = [json.loads(str(r["payload_json"])) for r in rows]
    assert {p["register"] for p in payloads} <= set(ui.REGISTERS)
    assert all({"register", "item", "evidence", "suggested_family_or_axis"} <= set(p)
               for p in payloads)
    # Cells are the compiler's business, not this organ's.
    assert R.candidates() == []
    below = [r for r in unused if r["priority"] <= rep["priority_median_unused"]]
    assert below and not ({p["item"] for p in payloads} & {r["item"] for r in below})


def test_a_used_item_never_becomes_a_discovery(rig: dict) -> None:
    ui.run(budget_s=30, dry_run=False)
    items = {json.loads(str(r["payload_json"]))["item"] for r in R.discoveries()}
    assert "financing_tape" not in items


# ---------------------------------------------------------------------------------- the CLI --

def test_cli_dry_run_writes_no_artifact_and_records_no_discovery(rig: dict,
                                                                 capsys: pytest.CaptureFixture
                                                                 ) -> None:
    assert ui.main(["--dry-run", "--budget-s", "30"]) == 0
    assert not rig["out"].exists()
    assert R.discoveries() == []
    assert "--dry-run: nothing recorded, nothing written" in capsys.readouterr().out


def test_cli_writes_the_artifact_with_every_field_the_readers_expect(rig: dict) -> None:
    assert ui.main(["--budget-s", "30"]) == 0
    doc = json.loads(rig["out"].read_text(encoding="utf-8"))
    assert {"at", "registers", "n_used", "n_unused", "top_priorities", "discoveries_recorded",
            "unmeasured", "rule"} <= set(doc)
    assert doc["rule"] == ui.RULE
    assert set(doc["registers"]) == set(ui.REGISTERS)
    assert doc["discoveries_recorded"] == len(R.discoveries())


def test_the_real_family_declarations_are_readable_on_this_box() -> None:
    """The consumption corpus is only as good as the declarations it reads -- if the desk package
    stops exposing FAMILY_INPUTS, every item on this box would read UNUSED and the register would
    be a list of false positives rather than inventory."""
    families, tokens = ui._family_inputs()
    assert isinstance(families, dict) and isinstance(tokens, set)
    if families:                     # the desk package is importable here; on a bare box it is not
        assert tokens and len(tokens) >= len(families)
