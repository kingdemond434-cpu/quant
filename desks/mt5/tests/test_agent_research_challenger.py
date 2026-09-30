from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.sandboxes import CellContext  # noqa: E402
from research.sandboxes import agent_research_challenger as arc  # noqa: E402

from libs.research import adapters as A  # noqa: E402


def test_evolution_transaction_commits_only_measured_gain() -> None:
    one = arc.ResourceVersion.make("x", "prompt", 1, {"a": 1})
    two = arc.ResourceVersion.make("x", "prompt", 2, {"a": 2}, one.content_hash)
    tx = arc.EvolutionTransaction(one, two, 0.1, 0.2, "eval")
    assert tx.decision() == "COMMIT"
    assert arc.EvolutionTransaction(one, two, 0.2, 0.1, "eval").decision() == \
        "ROLLBACK_NO_GAIN"


def test_trace_lint_distinguishes_failed_call_from_mishandling() -> None:
    contracts = {"read": arc.ToolContract("read", False, True),
                 "write": arc.ToolContract("write", True, False)}
    events = [
        {"tool": "read", "call_id": "r", "status": "ERROR"},
        {"tool": "write", "call_id": "w1", "effect_key": "same", "status": "OK"},
        {"tool": "write", "call_id": "w2", "effect_key": "same", "status": "OK",
         "consumes_call": "r"},
    ]
    kinds = {r["kind"] for r in arc.lint_trace(events, contracts)}
    assert kinds == {"FAILED_OUTPUT_CONSUMED", "DUPLICATE_NON_IDEMPOTENT_EFFECT"}


def test_progressive_context_loads_only_requested_body() -> None:
    got = arc.progressive_context([
        {"id": "a", "kind": "role", "summary": "A", "body": "a" * 20},
        {"id": "b", "kind": "skill", "summary": "B", "body": "b" * 20},
    ], requested={"b"}, char_budget=7)
    assert got["chars_loaded"] == 7
    assert got["loaded"] == [{"id": "b", "body": "bbbbbbb"}]
    assert len(got["manifest"]) == 2


def test_holdout_feedback_is_contamination_even_without_raw_rows() -> None:
    result = arc.holdout_exposure([
        {"holdout_id": "2025", "use": "SCORE"},
        {"holdout_id": "2025", "use": "NEXT_EXPERIMENT"},
        {"holdout_id": "2024", "use": "ARCHIVE"},
    ])
    assert result["status"] == "CONTAMINATED"
    assert result["adaptive_reuse"] == {"2025": 2}
    assert result["exposure_count"] == 2


def test_cost_edge_ratio_refuses_missing_or_zero_edge() -> None:
    assert arc.cost_edge_ratio(expected_cost=None, expected_gross_alpha=1)["status"] == \
        "UNMEASURED"
    assert arc.cost_edge_ratio(expected_cost=1, expected_gross_alpha=0)["status"] == \
        "NO_GROSS_EDGE"
    assert arc.cost_edge_ratio(expected_cost=0.2, expected_gross_alpha=-1)["value"] == 0.2


def test_autopilot_selects_independent_value_not_headline_alpha() -> None:
    got = arc.select_next_experiment([
        {"experiment_id": "independent", "expected_delta_elog": 0.02,
         "survival_probability": 0.5, "compute_cost": 1, "data_cost": 0,
         "forward_slot_cost": 0, "independence_gain": 1},
        {"experiment_id": "headline", "expected_delta_elog": 0.2,
         "survival_probability": 0.1, "compute_cost": 2, "data_cost": 1,
         "forward_slot_cost": 1, "independence_gain": 0.1},
        {"experiment_id": "unknown", "expected_delta_elog": None,
         "survival_probability": None, "compute_cost": 1, "data_cost": 0,
         "forward_slot_cost": 0},
    ])
    assert got["selected"]["experiment_id"] == "independent"
    assert got["unresolved"] == ["unknown"]


def test_cell_packet_has_no_capital_or_verdict_authority(tmp_path: Path) -> None:
    bundle = A.ResearchBundle(bundle_id="b", built_at="2026-01-01T00:00:00+00:00",
                              question="q", compute_budget_s=10, seed=1, horizons=("4h",),
                              universe=(), bars={}, costs={}, provenance={})
    pkt = arc.run(bundle, CellContext(tmp_path, budget_s=10))
    assert pkt.system_id == "cell:agent_research_challenger"
    assert pkt.trials_charged == 0
    assert not pkt.candidates
    assert {r["kind"] for r in pkt.research_methods} >= {
        "EVOLUTION_TRANSACTION", "TRACE_LINT", "SWARM_VALUE_BENCHMARK",
        "ADAPTIVE_HOLDOUT_CONTAMINATION", "COST_EDGE_DECAY", "RESEARCH_AUTOPILOT",
        "MARGINAL_BOOK_OBJECTIVE",
    }
