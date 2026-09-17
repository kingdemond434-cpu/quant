"""THE DAILY BUILD ALLOCATOR: where candidates come from, what they cost, and what the
complexity budget does to the ones that would add a permanent subsystem.

Seven sources feed this organ and every one of them may be absent on a given host, so half of
these tests plant an artifact and half deliberately remove one. The R5 triggers get all three
outcomes -- met, measured-and-not-met, and UNMEASURED -- because collapsing the last two into a
single False is exactly the mistake that would build a machine against no data (III.16).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK), str(_DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import build_allocator as ba  # noqa: E402

from libs.moat import registry as R  # noqa: E402

NOW = "2026-09-17T12:00:00+00:00"


def _write(p: Path, payload: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _rent_row(module: str, **kw: Any) -> dict[str, Any]:
    row = {"module": module, "clock": "hourly_cycle:x", "attribution": "credited",
           "compute_h_7d": 1.0, "compute_h_30d": 4.0, "candidates_30d": 20,
           "novel_mechanisms_30d": 2, "admissions_30d": 5, "survivors_30d": 1,
           "defects_30d": 0, "maintenance_commits_30d": 2, "loc": 300, "fan": 2,
           "complexity": 400.0, "roi": 5.0, "verdict": "KEEP", "why": "ok",
           "merge_with": None, "exempt_why": None}
    row.update(kw)
    return row


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic repo with every one of the seven candidate sources present."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "registry.sqlite")
    rp = tmp_path / "desks" / "mt5" / "reports"
    dt = tmp_path / "desks" / "mt5" / "data"

    _write(tmp_path / "docs" / "research" / "tier1_program.json", {"items": [
        {"id": "X1", "status": "PARTIAL", "next_step": "build a residual gate",
         "evidence": ["desks/mt5/research/alpha_miner.py -- MEASURED"]},
        {"id": "X2", "status": "PARTIAL",
         "next_step": "replace the old compiler with one table"},
        {"id": "X3", "status": "LANDED", "next_step": "nothing left"},
        {"id": "X4", "status": "PARTIAL", "next_step": ""},
    ]})
    _write(rp / "WIRING_CEO.json", {"unwired": [
        {"organ": "desks/mt5/research/orphan.py", "lines": 120,
         "suggested_clock": "hourly_cycle:core"}]})
    _write(rp / "MODULE_RENT_RESEARCH.json", {"rows": [
        _rent_row("desks/mt5/research/alpha_miner.py"),
        _rent_row("desks/mt5/research/fat_leg.py", verdict="REDUCE", compute_h_30d=40.0,
                  candidates_30d=1, roi=0.02),
        _rent_row("desks/mt5/research/twin_a.py", verdict="MERGE",
                  merge_with="desks/mt5/research/twin_b.py"),
        _rent_row("desks/mt5/research/miner_candidate_compiler.py", maintenance_commits_30d=3,
                  complexity=1000.0),
    ]})
    _write(rp / "RESEARCH_GAP_MAP.json", {"holes": [
        {"cell": "fx|asia|carry", "status": "DATA_MISSING", "value": 9.0},
        {"cell": "metals|london|breakout", "status": "COVERED", "value": 99.0},
    ]})
    _write(rp / "SCOUT_ROSTER.json", {
        "scouts": [{"name": "s1", "n_sources": 2, "yield": {"leads": 20, "testable": 5}},
                   {"name": "s2", "n_sources": 5, "yield": {"leads": 20, "testable": 5}}],
        "open_beats": [{"ground_or_axis": "lang:ar", "n_grounds": 10, "best_scout": "s1"},
                       {"ground_or_axis": "lang:da", "n_grounds": 1, "best_scout": None}]})
    _write(rp / "ROW_CONVERSION.json", {"n_rows": 1000, "n_candidates": 400})
    _write(dt / "live_ledger.jsonl", {})
    (dt / "live_ledger.jsonl").write_text(
        "\n".join(json.dumps({"sleeve": "gold_asia", "r_multiple": -1.0, "volume": 0.01 * (i + 1)})
                  for i in range(35)), encoding="utf-8")
    _write(rp / "markout.json", {"n_matched": 12, "usable": True})
    _write(rp / "pf_allocation.json", {"armed": True, "regime": {"state": "calm"},
                                       "effective_heat": 0.24})
    _write(dt / "probation_state.json", {"history": {
        "desks/mt5/research/fat_leg.py": {"runs": 9, "clean": 9},
        "desks/mt5/research/twin_a.py": {"runs": 2, "clean": 2}}})
    _write(dt / "auto_legs.json", {"legs": [{"organ": "desks/mt5/research/orphan.py",
                                             "leg": "auto_orphan", "plan": "core"}]})
    # 90 unexplained conversion-debt cells, recorded through the registry's own ledger.
    did, _ = R.record_discovery(source_id="src1", source_type="web", mechanism="carry",
                                origin="EXTERNAL")
    R.set_discovery_state(did, "EXPANDED", possible_cells=100, generated_cells=10,
                          blocked_cells=0)
    yield tmp_path
    R.set_path(None)


# --------------------------------------------------------------------------- the seven sources
def test_every_candidate_source_is_gathered(tree: Path) -> None:
    doc = ba.build(tree, top=100)
    assert set(doc["by_class"]) == {"tier1", "wiring", "reduce", "merge", "data_backfill",
                                    "scout", "compiler_fix", "spec"}
    got = {c["candidate"] for c in doc["ranked"]}
    assert any("X1" in c for c in got) and not any("X3" in c for c in got), "PARTIAL only"
    assert any(c.startswith("wire desks/mt5/research/orphan.py") for c in got)
    assert any("halve the cadence of" in c for c in got)
    assert any("merge desks/mt5/research/twin_a.py" in c for c in got)
    assert any("backfill data for fx|asia|carry" in c for c in got)
    assert not any("metals|london" in c for c in got), "only DATA_MISSING holes are backfilled"
    assert any("add a scout for lang:ar" in c for c in got)
    assert any("fix the compiler: 90 unexplained" in c for c in got)
    assert sum(1 for c in got if c.startswith("build R5 spec")) == len(ba.R5_SPECS)


def test_an_item_with_no_next_step_is_not_a_build_candidate(tree: Path) -> None:
    doc = ba.build(tree, top=100)
    assert not any("X4" in c["candidate"] for c in doc["ranked"])


def test_the_gap_map_absent_is_unmeasured_not_an_empty_backlog(tree: Path) -> None:
    (tree / "desks" / "mt5" / "reports" / "RESEARCH_GAP_MAP.json").unlink()
    doc = ba.build(tree, top=100)
    assert "data_backfill" not in doc["by_class"]
    assert any("gap map" in u and "UNMEASURED" in u for u in doc["unmeasured"])


def test_the_unwired_set_falls_back_to_the_rent_clock_column(tree: Path) -> None:
    (tree / "desks" / "mt5" / "reports" / "WIRING_CEO.json").unlink()
    rp = tree / "desks" / "mt5" / "reports"
    doc = json.loads((rp / "MODULE_RENT_RESEARCH.json").read_text(encoding="utf-8"))
    doc["rows"].append(_rent_row("desks/mt5/research/never_clocked.py", clock="none"))
    _write(rp / "MODULE_RENT_RESEARCH.json", doc)
    out = ba.build(tree, top=100)
    assert any("wire desks/mt5/research/never_clocked.py" in c["candidate"]
               for c in out["ranked"])
    assert any("MODULE_RENT_RESEARCH.json (clock column)" in u for u in out["unmeasured"])


def test_yield_bases_are_named_per_class(tree: Path) -> None:
    doc = ba.build(tree, top=100)
    by = {c["class"]: c for c in doc["ranked"]}
    assert "candidates per compute hour" in by["reduce"]["why"]
    assert "leads per source" in by["scout"]["why"]
    assert "unexplained cells" in by["compiler_fix"]["why"]
    assert "the hole's declared value" in by["data_backfill"]["why"]


# --------------------------------------------------------------------------- the price
def test_priority_is_yield_over_build_plus_maintenance_plus_complexity() -> None:
    idx = {"m.py": {"maintenance_commits_30d": 3, "complexity": 1000.0}}
    c = {"candidate": "x", "class": "scout", "source": "s", "target": "m.py",
         "expected_yield": 8.0, "yield_basis": "b", "replaces": None}
    p = ba.price(c, idx, None, None)
    # cost = 250/100 (class LOC) + 3 commits + 1000/1000 = 6.5
    assert p["cost"] == pytest.approx(6.5)
    assert p["priority"] == pytest.approx(8.0 / 6.5)


def test_a_candidate_with_no_measured_target_falls_back_to_the_class_defaults() -> None:
    c = {"candidate": "x", "class": "wiring", "source": "s", "target": None,
         "expected_yield": 1.0, "yield_basis": "b", "replaces": None}
    p = ba.price(c, {}, None, None)
    # cost = 20/100 + 0 median maintenance + 20/1000
    assert p["cost"] == pytest.approx(0.22)
    assert "no measured target" in p["cost_basis"]


def test_a_spec_is_priced_at_its_own_declared_loc() -> None:
    c = {"candidate": "x", "class": "spec", "source": "s", "target": None, "spec_loc": 450,
         "expected_yield": 0.5, "yield_basis": "b", "replaces": None}
    p = ba.price(c, {}, None, None)
    assert p["build_cost"] == pytest.approx(4.5)
    assert p["delta_complexity_kloc"] == pytest.approx(0.45)


# --------------------------------------------------------------------------- complexity budget
def _permanent(yield_: float, replaces: str | None = None, cls: str = "scout") -> dict[str, Any]:
    c = {"candidate": "x", "class": cls, "source": "s", "target": None,
         "expected_yield": yield_, "yield_basis": "b", "replaces": replaces}
    return ba.apply_complexity_budget(ba.price(c, {}, None, None))


def test_a_non_replacing_subsystem_that_loses_to_lambda_is_filed_as_lab() -> None:
    # a scout is 250 LOC = 0.25 kLOC; LAMBDA = 1.0, so it must promise > 0.25 candidates
    out = _permanent(0.10)
    assert out["stage_if_built"] == "LAB"
    assert out["budget"].startswith("FILED AS LAB")


def test_a_subsystem_that_beats_lambda_keeps_its_stage() -> None:
    out = _permanent(5.0)
    assert out["stage_if_built"] == ba.STAGE_IF_BUILT["scout"] == "SHADOW"
    assert "delta Value" in out["budget"] and "LAB" not in out["budget"]


def test_naming_what_it_replaces_passes_the_budget_without_the_inequality() -> None:
    out = _permanent(0.001, replaces="the broken scout s1")
    assert out["stage_if_built"] == "SHADOW"
    assert out["budget"].startswith("REPLACES")


def test_a_change_to_an_existing_organ_faces_no_complexity_budget() -> None:
    out = _permanent(0.0001, cls="wiring")
    assert out["stage_if_built"] == "SHADOW"
    assert "adds no permanent subsystem" in out["budget"]


def test_the_report_counts_what_the_budget_filed_as_lab(tree: Path) -> None:
    doc = ba.build(tree, top=200)
    assert doc["complexity_budget"]["lambda"] == ba.LAMBDA == 1.0
    assert doc["complexity_budget"]["filed_as_lab"] == sum(
        1 for c in doc["ranked"] if c["stage_if_built"] == "LAB")
    assert set(doc["complexity_budget"]["permanent_classes"]) == set(ba.PERMANENT)


# --------------------------------------------------------------------------- the R5 triggers
def test_all_four_triggers_are_measured_from_their_own_artifacts(tree: Path) -> None:
    t = ba.build(tree, top=100)["triggers"]
    assert t["crowding_decay_monitor"]["met"] is True        # 35 closed trades >= 30
    assert t["meta_labeling"]["met"] is False                # 35 < 200, MEASURED not met
    assert t["capacity_model"]["met"] is True                # markouts + size variation
    assert t["regime_conditioned_sizing"]["met"] is True
    assert "35" in t["crowding_decay_monitor"]["evidence"]


def test_a_measured_trigger_that_is_not_met_is_false_not_unmeasured(tree: Path) -> None:
    dt = tree / "desks" / "mt5" / "data"
    (dt / "live_ledger.jsonl").write_text(
        json.dumps({"sleeve": "gold_asia", "r_multiple": -1.0, "volume": 0.1}), encoding="utf-8")
    t = ba.build(tree, top=100)["triggers"]
    assert t["crowding_decay_monitor"]["met"] is False
    assert "1 closed trades" in t["crowding_decay_monitor"]["evidence"]


def test_an_absent_artifact_makes_its_trigger_unmeasured(tree: Path) -> None:
    (tree / "desks" / "mt5" / "data" / "live_ledger.jsonl").unlink()
    (tree / "desks" / "mt5" / "reports" / "markout.json").unlink()
    (tree / "desks" / "mt5" / "reports" / "pf_allocation.json").unlink()
    t = ba.build(tree, top=100)["triggers"]
    for name in ("crowding_decay_monitor", "meta_labeling", "capacity_model",
                 "regime_conditioned_sizing"):
        assert t[name]["met"] == "UNMEASURED", name
        assert t[name]["evidence"]


def test_capacity_needs_size_variation_as_well_as_markouts(tree: Path) -> None:
    dt = tree / "desks" / "mt5" / "data"
    (dt / "live_ledger.jsonl").write_text(
        "\n".join(json.dumps({"sleeve": "g", "r_multiple": 1.0, "volume": 0.05})
                  for _ in range(40)), encoding="utf-8")
    t = ba.build(tree, top=100)["triggers"]
    assert t["capacity_model"]["met"] is False
    assert "1 distinct fill sizes" in t["capacity_model"]["evidence"]


def test_an_unmet_or_unmeasured_spec_scores_zero_and_a_met_one_carries_the_prior(
        tree: Path) -> None:
    doc = ba.build(tree, top=200)
    specs = {c["candidate"].split()[3]: c for c in doc["ranked"] if c["class"] == "spec"}
    assert specs["crowding_decay_monitor"]["expected_yield"] == pytest.approx(ba.PRIOR)
    assert specs["meta_labeling"]["expected_yield"] == 0.0
    assert specs["meta_labeling"]["trigger_met"] is False


# --------------------------------------------------------------------------- stages
def test_stage_is_lab_without_a_clock() -> None:
    assert ba.stage_of("x.py", {}, {}, "none", 0) == "LAB"
    assert ba.stage_of("x.py", {}, {}, None, 3) == "LAB"


def test_stage_is_shadow_on_probation_or_short_of_the_clean_runs() -> None:
    probation = {"history": {"x.py": {"runs": 3, "clean": 3}}}
    assert ba.stage_of("x.py", probation, {}, "leg", 1) == "SHADOW"
    auto = {"legs": [{"organ": "y.py"}]}
    assert ba.stage_of("y.py", {}, auto, "leg", 1) == "SHADOW"


def test_stage_is_canonical_with_enough_clean_runs_and_a_consumer() -> None:
    probation = {"history": {"x.py": {"runs": 9, "clean": ba.CANONICAL_CLEAN_RUNS}}}
    assert ba.stage_of("x.py", probation, {}, "leg", 1) == "CANONICAL"
    assert ba.stage_of("x.py", probation, {}, "leg", 0) == "SHADOW", "no consumer, no canon"


def test_an_existing_target_carries_its_measured_stage(tree: Path) -> None:
    doc = ba.build(tree, top=200)
    fat = next(c for c in doc["ranked"] if c["class"] == "reduce")
    assert fat["stage_if_built"] == "CANONICAL"          # 9 clean probation runs and a clock
    twin = next(c for c in doc["ranked"] if c["class"] == "merge")
    assert twin["stage_if_built"] == "SHADOW"            # only 2 clean runs


# --------------------------------------------------------------------------- the artifact
def test_dry_run_writes_nothing_and_a_plain_run_writes_the_artifact(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = {"at": NOW, "n_candidates": 1, "elapsed_s": 0.1, "by_class": {"spec": 1},
           "ranked": [{"candidate": "c", "class": "spec", "source": "s", "priority": 1.0,
                       "expected_yield": 0.5, "cost": 0.5, "replaces": None,
                       "stage_if_built": "LAB", "why": "because"}],
           "triggers": {"t": {"met": "UNMEASURED", "evidence": "none"}},
           "complexity_budget": {"lambda": 1.0, "filed_as_lab": 1}, "unmeasured": []}
    out = tmp_path / "BUILD_ALLOCATOR.json"
    monkeypatch.setattr(ba, "OUT", out)
    monkeypatch.setattr(ba, "build", lambda **kw: doc)
    assert ba.main(["--dry-run"]) == 0
    assert not out.exists()
    assert ba.main([]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["n_candidates"] == 1


def test_top_bounds_the_ranking_and_the_order_is_by_priority(tree: Path) -> None:
    doc = ba.build(tree, top=3)
    assert len(doc["ranked"]) == 3 and doc["n_candidates"] > 3
    ps = [c["priority"] for c in doc["ranked"]]
    assert ps == sorted(ps, reverse=True)


def test_the_report_carries_its_rule_and_its_formula(tree: Path) -> None:
    doc = ba.build(tree, top=5)
    assert "only the highest-value machinery gets built" in doc["rule"]
    assert "replaces one or proves its value exceeds its complexity" in doc["rule"]
    assert doc["formula"].startswith("BuildPriority =")
    assert set(doc["stages"]) == {"LAB", "SHADOW", "CANONICAL"}
