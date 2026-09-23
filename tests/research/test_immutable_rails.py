"""THE EVOLVABLE / IMMUTABLE BOUNDARY (LAWS 5m): a mutation proposal that reaches for a rail is
refused BY NAME, the sealed evaluator is inside the rails, and the boundary is well-formed."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import immutable_rails as IR  # noqa: E402


def _fence():
    spec = importlib.util.spec_from_file_location(
        "_cir", ROOT / "scripts" / "check_immutable_rails.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_proposal_touching_the_gauntlet_or_the_trial_record_is_refused_by_name() -> None:
    v = IR.refuse_proposal({"id": "p1", "touches": [
        {"path": "desks/mt5/scripts/external_gauntlet.py", "symbols": ["run"]},
        {"path": "libs/moat/registry.py", "symbols": ["record_trial", "counts"]},
        {"path": "libs/research/mcts.py", "symbols": ["C_PUCT"]}]})
    assert not v.ok
    refused_paths = {r.path for r in v.refused}
    assert "desks/mt5/scripts/external_gauntlet.py" in refused_paths
    assert "libs/moat/registry.py" in refused_paths
    named = {(r.path, r.symbol) for r in v.refused}
    assert ("libs/moat/registry.py", "record_trial") in named, "the trial record is named"
    assert ("libs/moat/registry.py", "counts") not in named, "an unguarded name is not refused"
    assert "libs/research/mcts.py" in v.allowed, "the evolvable search algorithm is allowed"
    assert any(r.category == "effective_trial_records" for r in v.refused)


def test_a_whole_file_touch_of_a_symbol_scoped_rail_is_read_as_touching_every_symbol() -> None:
    v = IR.check_change_set(["libs/moat/registry.py"])
    assert not v.ok and v.refused[0].symbol is None
    assert "names no symbol" in v.refused[0].why


def test_undeclared_and_evolvable_change_sets() -> None:
    assert not IR.refuse_proposal({"id": "empty"}).ok, "an uncheckable change set is refused"
    v = IR.check_change_set(["desks/mt5/research/research_tree.py", "some/new/organ.py"])
    assert v.ok and "some/new/organ.py" in v.unclassified
    assert IR.classify("desks/mt5/research/research_tree.py").status == IR.EVOLVABLE_STATUS
    assert IR.classify("desks/mt5/research/promoter.py").status == IR.IMMUTABLE_STATUS
    ledger = "desks/mt5/reports/shadow/ledger_XAUUSD_asia.json"
    assert IR.classify(ledger).category == "forward_clocks"
    assert IR.classify("nowhere.py").status == IR.UNCLASSIFIED_STATUS


def test_the_sealed_evaluator_is_inside_the_rails_and_every_law_class_is_anchored() -> None:
    sealed = IR.evaluator_immutable()
    assert len(sealed) >= 18, "the evaluator's tuple loads by path"
    rails = {r.path for r in IR.immutable_rails()}
    assert set(sealed) <= rails
    cats = {r.category for r in IR.immutable_rails()}
    assert set(IR.IMMUTABLE_CATEGORIES) <= cats, "every class LAWS 5m names has a rail"
    assert set(IR.EVOLVABLE) == {
        "hypothesis_generators", "feature_generators", "agent_prompts_programs",
        "model_architectures", "experiment_allocation", "research_code", "representations",
        "search_algorithms", "simulation_populations", "cross_breeding_rules",
        "data_acquisition_priorities", "curricula", "ontologies", "invented_tools"}


def test_the_fence_finds_the_boundary_well_formed_and_reuses_the_evaluators_seal() -> None:
    mod = _fence()
    assert mod.check_boundary() == []
    doc = mod.run()
    assert doc["checks"]["seal"]["status"] in ("HELD", "BROKEN")
    assert doc["checks"]["seal"]["owner"].startswith("scripts/check_immutable_evaluator.py")
    assert doc["n_immutable_rails"] >= 60 and doc["n_evolvable_paths"] >= 40


def test_the_fence_refuses_an_applied_mutation_that_reached_a_rail(tmp_path: Path) -> None:
    mod = _fence()
    ledger = tmp_path / "lineage.jsonl"
    ledger.write_text(
        '{"id": "rev_bad", "applied": true, "touches": [{"path": '
        '"desks/mt5/research/promoter.py", "symbols": ["promote"]}]}\n'
        '{"id": "rev_ok", "applied": true, "touches": [{"path": '
        '"libs/research/program_ir.py", "symbols": ["ROLLING_OPS"]}]}\n'
        '{"id": "rev_refused", "applied": false, "touches": [{"path": '
        '"desks/mt5/scripts/external_gauntlet.py"}]}\n', encoding="utf-8")
    breaches, meta = mod.check_lineage(ledger)
    assert meta == {"status": "MEASURED", "rows": 3, "applied": 2}
    assert len(breaches) == 1 and "rev_bad" in breaches[0]["what"]
    assert "promoter.py" in breaches[0]["what"]
