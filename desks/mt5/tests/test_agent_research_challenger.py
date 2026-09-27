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


def test_cell_packet_has_no_capital_or_verdict_authority(tmp_path: Path) -> None:
    bundle = A.ResearchBundle(bundle_id="b", built_at="2026-01-01T00:00:00+00:00",
                              question="q", compute_budget_s=10, seed=1, horizons=("4h",),
                              universe=(), bars={}, costs={}, provenance={})
    pkt = arc.run(bundle, CellContext(tmp_path, budget_s=10))
    assert pkt.system_id == "cell:agent_research_challenger"
    assert pkt.trials_charged == 0
    assert not pkt.candidates
    assert {r["kind"] for r in pkt.research_methods} >= {
        "EVOLUTION_TRANSACTION", "TRACE_LINT", "SWARM_VALUE_BENCHMARK"
    }
