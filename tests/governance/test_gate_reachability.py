"""GATE REACHABILITY (L1.49) -- the tests that fail if the fence stops seeing unrun gates.

WHY THESE ASSERTIONS AND NOT "IT RETURNS A DICT". This fence exists because every other gate
instrument on the desk reads a per-gate TALLY, and a gate that never ran emits no row to tally.
So the load-bearing behaviours are the ones a naive test would miss:

  * a gate declared in code but ABSENT from the tally must still be graded (the whole point);
  * an empty ledger must read UNMEASURED, never OK (L1.28a) -- an unmeasured thing that reports
    fine is the defect this desk keeps re-finding;
  * the declaration scraper must not invent gates. Its first version regex-matched neighbouring
    dict keys and reported `n`, `note` and `survivor_indices` as zero-bit gates; a fence that
    cries wolf is acknowledged into silence within a week;
  * the production-setter search must not count `data/rollback/*/tests/**` as production. Its
    first version did, and reported all eight permanently-unsatisfiable governance gates as
    satisfiable -- the exact failure the fence was written to catch, inside the fence itself.

Both directions are asserted throughout: the fence must FIRE on a broken tree and stay quiet on a
healthy one, because a detector that cannot be silenced carries as little information as one that
never speaks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.check_gate_reachability import (
    build_report,
    declared_gates,
    governance_fields,
    observed,
)

_ROOT = Path(__file__).resolve().parents[2]


def _tree(root: Path, *, survivors: int = 0, tested: int = 434,
          hist: dict[str, int] | None = None) -> Path:
    """A miniature repo with one gauntlet, one post-promote gate and one governance verdict."""
    (root / "libs/autodiscovery").mkdir(parents=True, exist_ok=True)
    (root / "libs/signal_engine").mkdir(parents=True, exist_ok=True)
    (root / "web").mkdir(parents=True, exist_ok=True)
    (root / "libs/autodiscovery/validation.py").write_text(
        "def validate():\n"
        "    n = 3\n"
        "    note = 'not a gate'\n"
        "    gates = {\n"
        '        "dsr": True,\n'
        '        "economic_mechanism": True,\n'
        "    }\n"
        '    gates["stationary"] = True\n'
        "    return gates, n, note\n", "utf-8")
    (root / "libs/autodiscovery/orchestrator.py").write_text(
        'reason = "failed: regime_robustness (edge confined to one volatility regime)"\n', "utf-8")
    (root / "libs/signal_engine/governance.py").write_text(
        "class GovernanceVerdict:\n"
        "    dsr_pass: bool = False\n"
        "    structural_break_pass: bool = False\n"
        "def gate(v):\n"
        "    return bool(v.dsr_pass and v.structural_break_pass)\n", "utf-8")
    (root / "web/autodiscovery_crypto.json").write_text(json.dumps({
        "cumulative_tested": tested, "cumulative_survivors": survivors,
        "rejection_by_gate": hist if hist is not None else {"dsr": tested},
    }), "utf-8")
    return root


# --- the scraper must find real gates and invent none -------------------------------------

def test_declares_gauntlet_conditional_and_post_promote(tmp_path):
    d = declared_gates(_tree(tmp_path))
    assert d["dsr"] == "unconditional"
    assert d["stationary"] == "conditional"
    assert d["regime_robustness"] == "post-promote"


def test_does_not_invent_gates_from_neighbouring_locals(tmp_path):
    """Regression: the first version reported `n` and `note` as zero-bit gates."""
    d = declared_gates(_tree(tmp_path))
    assert "n" not in d and "note" not in d


def test_live_repo_still_declares_the_two_post_promote_gates():
    """Fails if the orchestrator's execution-gap / regime gates are unwired or renamed."""
    d = declared_gates(_ROOT)
    assert d.get("execution_gap") == "post-promote"
    assert d.get("regime_robustness") == "post-promote"


# --- unsatisfiable detection --------------------------------------------------------------

def test_flags_required_true_field_with_no_production_setter(tmp_path):
    gov = governance_fields(_tree(tmp_path))
    assert gov["structural_break_pass"]["has_production_setter"] is False


def test_rollback_snapshot_is_not_a_production_setter(tmp_path):
    """Regression: a copy of tests/ under data/rollback made every gate look satisfiable."""
    root = _tree(tmp_path)
    snap = root / "data/rollback/20260101T000000_x/tests/signal_engine"
    snap.mkdir(parents=True)
    (snap / "conftest.py").write_text("v = dict(structural_break_pass=True)\n", "utf-8")
    assert governance_fields(root)["structural_break_pass"]["has_production_setter"] is False


def test_real_setter_under_a_production_root_clears_the_flag(tmp_path):
    root = _tree(tmp_path)
    (root / "scripts").mkdir(exist_ok=True)
    (root / "scripts/emit.py").write_text("v = dict(structural_break_pass=True)\n", "utf-8")
    assert governance_fields(root)["structural_break_pass"]["has_production_setter"] is True


# --- classification -----------------------------------------------------------------------

def test_post_promote_gate_with_no_survivors_is_a_dead_branch(tmp_path):
    rep = build_report(_tree(tmp_path, survivors=0))
    assert rep["status"] == "DEAD-BRANCH"
    assert "regime_robustness" in rep["dead_branches"]


def test_gate_absent_from_tally_but_evaluated_reads_zero_bit(tmp_path):
    rep = build_report(_tree(tmp_path, survivors=1))
    assert rep["gates"]["economic_mechanism"]["state"] == "ZERO-BIT"
    assert "economic_mechanism" in rep["zero_bit"]


def test_gate_with_rejections_reads_firing(tmp_path):
    rep = build_report(_tree(tmp_path, survivors=1))
    assert rep["gates"]["dsr"]["state"] == "FIRING"


def test_conditional_gate_is_reported_not_failed(tmp_path):
    """A conditional gate's silence is ambiguous, so it must not drive the status."""
    rep = build_report(_tree(tmp_path, survivors=1, hist={"dsr": 434, "economic_mechanism": 5}))
    assert rep["gates"]["stationary"]["state"] == "NEVER-EXERCISED"
    assert "stationary" not in rep["dead_branches"] + rep["zero_bit"] + rep["unsatisfiable"]


# --- the refusal path (L1.28a) ------------------------------------------------------------

def test_empty_ledger_reads_unmeasured_never_ok(tmp_path):
    rep = build_report(_tree(tmp_path, tested=0, hist={}))
    assert rep["status"] == "UNMEASURED"
    assert rep["status"] != "OK"


def test_sample_below_floor_reads_unmeasured(tmp_path):
    rep = build_report(_tree(tmp_path, tested=5, hist={"dsr": 5}))
    assert rep["status"] == "UNMEASURED"


def test_unmeasured_says_it_cleared_nothing(tmp_path):
    rep = build_report(_tree(tmp_path, tested=0, hist={}))
    assert "not a pass" in rep["next_action"].lower()


# --- the live tree ------------------------------------------------------------------------

def test_live_repo_currently_reports_the_defect():
    """The first run found real defects; this fails if they are silently 'fixed' by unwiring."""
    rep = build_report(_ROOT)
    assert rep["status"] != "UNMEASURED", "the live ledger should be measurable"
    assert set(rep["dead_branches"]) >= {"execution_gap", "regime_robustness"}


@pytest.mark.parametrize("key", ["status", "next_action", "gates", "law"])
def test_artifact_carries_its_contract(key):
    assert key in build_report(_ROOT)


def test_observed_unions_tally_and_is_read_only(tmp_path):
    hist, tested, survivors = observed(_tree(tmp_path, tested=100, hist={"dsr": 100}))
    assert hist["dsr"] == 100 and tested == 100 and survivors == 0
