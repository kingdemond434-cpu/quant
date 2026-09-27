"""MULTI-AGENT RESEARCH CHALLENGER -- useful public agent patterns, rebuilt safely.

This is the executable research-process lane behind the external federation's broad static
mining.  It deliberately does not run foreign code and cannot emit trading authority.  It makes
five claims testable against the desk's simpler baseline:

* versioned resources evolve through PROPOSE -> ASSESS -> COMMIT or ROLLBACK;
* every loop has an explicit, composable termination contract;
* tool traces are linted deterministically for error misuse and duplicate side effects;
* context is disclosed progressively instead of injecting the whole institution;
* local research credit is provisional until forward/live value exists.

The patterns were independently rebuilt from public architecture described by Skywork
DeepResearchAgent, PicoAgents/designing-multiagent-systems, DATAGEN/TraceLint, Stanford Optimas,
and virattt/ai-hedge-fund.  AutoHedge's LLM sizing/execution design is an explicit negative
control: LLMs may donate research and never size or route capital here.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "agent_research_challenger"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "research_reliability"
UPSTREAM = ("skywork_deepresearch", "picoagents", "datagen", "optimas",
            "ai_hedge_fund", "autohedge")
FALLBACK = "deterministic stdlib protocols; no model, network, broker secret, or order authority"


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ResourceVersion:
    resource_id: str
    kind: str
    version: int
    content_hash: str
    parent_hash: str | None = None

    @classmethod
    def make(cls, resource_id: str, kind: str, version: int, content: Any,
             parent_hash: str | None = None) -> ResourceVersion:
        return cls(resource_id, kind, version, _digest(content), parent_hash)


@dataclass(frozen=True)
class EvolutionTransaction:
    before: ResourceVersion
    proposed: ResourceVersion
    baseline_value: float
    challenger_value: float
    evaluation_hash: str

    def decision(self) -> str:
        if self.proposed.parent_hash != self.before.content_hash:
            return "ROLLBACK_PARENT_MISMATCH"
        return "COMMIT" if self.challenger_value > self.baseline_value else "ROLLBACK_NO_GAIN"

    def trace(self) -> list[dict[str, Any]]:
        return [
            {"stage": "PROPOSE", "resource": asdict(self.proposed)},
            {"stage": "ASSESS", "baseline_value": self.baseline_value,
             "challenger_value": self.challenger_value,
             "evaluation_hash": self.evaluation_hash},
            {"stage": self.decision()},
        ]


@dataclass(frozen=True)
class TerminationContract:
    max_messages: int
    max_tokens: int
    timeout_s: float
    max_stagnant_steps: int

    def reasons(self, *, messages: int, tokens: int, elapsed_s: float, stagnant_steps: int,
                goal_reached: bool = False, failed: bool = False,
                cancelled: bool = False) -> tuple[str, ...]:
        hits: list[str] = []
        if goal_reached:
            hits.append("GOAL")
        if failed:
            hits.append("FAILURE")
        if cancelled:
            hits.append("EXTERNAL_CANCEL")
        if messages >= self.max_messages:
            hits.append("MESSAGE_BUDGET")
        if tokens >= self.max_tokens:
            hits.append("TOKEN_BUDGET")
        if elapsed_s >= self.timeout_s:
            hits.append("TIMEOUT")
        if stagnant_steps >= self.max_stagnant_steps:
            hits.append("STAGNATION")
        return tuple(hits)


@dataclass(frozen=True)
class ToolContract:
    name: str
    side_effecting: bool
    idempotent: bool
    authority: str = "research_only"


def lint_trace(events: Iterable[dict[str, Any]], contracts: dict[str, ToolContract]
               ) -> list[dict[str, Any]]:
    """Judge-free structural lint over actual tool events.

    A failed call is evidence, not automatically a defect.  The defects are using failed output,
    replaying a non-idempotent side effect, or invoking authority absent from the contract.
    """
    findings: list[dict[str, Any]] = []
    failed: set[str] = set()
    seen_effects: set[tuple[str, str]] = set()
    for i, event in enumerate(events):
        tool = str(event.get("tool") or "")
        call_id = str(event.get("call_id") or i)
        contract = contracts.get(tool)
        if contract is None:
            findings.append({"kind": "UNKNOWN_TOOL", "event": i, "tool": tool})
            continue
        if str(event.get("authority") or "research_only") != contract.authority:
            findings.append({"kind": "AUTHORITY_MISMATCH", "event": i, "tool": tool})
        if str(event.get("status") or "").upper() in {"ERROR", "FAILED", "TIMEOUT"}:
            failed.add(call_id)
        if event.get("consumes_call") in failed:
            findings.append({"kind": "FAILED_OUTPUT_CONSUMED", "event": i,
                             "source_call": event.get("consumes_call")})
        if contract.side_effecting and not contract.idempotent:
            effect = (tool, str(event.get("effect_key") or _digest(event.get("args"))))
            if effect in seen_effects:
                findings.append({"kind": "DUPLICATE_NON_IDEMPOTENT_EFFECT", "event": i,
                                 "tool": tool, "effect_key": effect[1]})
            seen_effects.add(effect)
    return findings


def progressive_context(resources: Iterable[dict[str, Any]], *, requested: set[str],
                        char_budget: int) -> dict[str, Any]:
    """Load metadata for all resources and bodies only for explicitly requested capabilities."""
    manifest: list[dict[str, Any]] = []
    bodies: list[dict[str, str]] = []
    spent = 0
    for row in resources:
        rid = str(row.get("id") or "")
        manifest.append({"id": rid, "kind": row.get("kind"), "summary": row.get("summary")})
        if rid not in requested:
            continue
        body = str(row.get("body") or "")
        room = max(0, char_budget - spent)
        if room <= 0:
            break
        bodies.append({"id": rid, "body": body[:room]})
        spent += min(len(body), room)
    return {"manifest": manifest, "loaded": bodies, "chars_loaded": spent,
            "budget": char_budget}


def aligned_local_reward(*, novel_cells: int, duplicate_cells: int, pit_defects: int,
                         compute_hours: float, forward_delta_elog: float | None) -> dict[str, Any]:
    """A conservative local proxy which yields to measured downstream value when available."""
    cost = max(compute_hours, 1 / 3600)
    proxy = (novel_cells - 0.5 * duplicate_cells - 2.0 * pit_defects) / cost
    if forward_delta_elog is None:
        return {"value": proxy, "basis": "PROVISIONAL_INFORMATION_GAIN_PER_COMPUTE",
                "capital_usable": False}
    return {"value": forward_delta_elog / cost, "basis": "MEASURED_FORWARD_DELOG_PER_COMPUTE",
            "capital_usable": False}


def blind_identity(payload: dict[str, Any]) -> dict[str, Any]:
    """Identity/date placebo transform for historical LLM experiments, preserving numbers."""
    hidden = {"ticker", "symbol", "instrument", "company", "industry", "date", "calendar_date"}
    return {k: ("MASKED" if k.lower() in hidden else v) for k, v in payload.items()}


def decision_receipt(payload: dict[str, Any], *, previous_hash: str = "GENESIS") -> dict[str, Any]:
    """Content-addressed, replayable research decision receipt (no trading authority)."""
    body = {**payload, "previous_hash": previous_hash}
    return {**body, "receipt_hash": _digest(body), "immutable": True,
            "authority": "research_only"}


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    """Execute deterministic protocol checks and donate research-process experiments."""
    del ctx
    before = ResourceVersion.make("miner_prompt", "prompt", 1, {"objective": bundle.question})
    proposed = ResourceVersion.make("miner_prompt", "prompt", 2,
                                    {"objective": bundle.question, "require_falsifier": True},
                                    before.content_hash)
    tx = EvolutionTransaction(before, proposed, 0.10, 0.12,
                              _digest({"benchmark": bundle.bundle_id, "seed": bundle.seed}))
    termination = TerminationContract(32, 32_000, max(10, bundle.compute_budget_s), 5)
    trace = [
        {"tool": "search", "call_id": "s1", "status": "ERROR", "args": {"q": "x"}},
        {"tool": "write", "call_id": "w1", "status": "OK", "effect_key": "artifact:a"},
        {"tool": "write", "call_id": "w2", "status": "OK", "effect_key": "artifact:a"},
        {"tool": "summarise", "call_id": "m1", "status": "OK", "consumes_call": "s1"},
    ]
    contracts = {
        "search": ToolContract("search", False, True),
        "write": ToolContract("write", True, False),
        "summarise": ToolContract("summarise", False, True),
    }
    lint = lint_trace(trace, contracts)
    context = progressive_context([
        {"id": "role", "kind": "role", "summary": "researcher contract", "body": "R" * 200},
        {"id": "country", "kind": "skill", "summary": "country pack", "body": "C" * 5000},
    ], requested={"role"}, char_budget=512)
    reward = aligned_local_reward(novel_cells=2, duplicate_cells=1, pit_defects=0,
                                  compute_hours=0.05, forward_delta_elog=None)
    blind = blind_identity({"ticker": "XAUUSD", "date": "2025-01-01", "feature": 1.25})
    receipt = decision_receipt({"resource": proposed.content_hash,
                                "evaluation": tx.evaluation_hash,
                                "action": tx.decision()})
    methods = (
        {"kind": "EVOLUTION_TRANSACTION", "sources": list(UPSTREAM[:1]),
         "trace": tx.trace(), "receipt": receipt},
        {"kind": "TERMINATION_ALGEBRA", "sources": [UPSTREAM[1]],
         "example_reasons": list(termination.reasons(messages=32, tokens=100,
                                                       elapsed_s=1, stagnant_steps=0))},
        {"kind": "TRACE_LINT", "sources": [UPSTREAM[2]], "findings": lint,
         "contracts": [asdict(v) for v in contracts.values()]},
        {"kind": "PROGRESSIVE_CONTEXT", "sources": [UPSTREAM[2]], **context},
        {"kind": "ALIGNED_LOCAL_REWARD", "sources": [UPSTREAM[3]], **reward},
        {"kind": "IDENTITY_BLIND_PLACEBO", "sources": [UPSTREAM[4]], "example": blind},
        {"kind": "NEGATIVE_CONTROL", "sources": [UPSTREAM[5]],
         "claim": "LLM sizing and execution remain outside research authority"},
        {"kind": "SWARM_VALUE_BENCHMARK",
         "arms": ["direct_model", "single_agent_tools", "small_swarm", "full_swarm"],
         "metric": "novel independent gauntlet-ready cells per compute; later forward dElogW"},
    )
    return A.packet(SYSTEM, bundle, trials=0, research_methods=methods,
                    note=("research-process challenger only; no AlphaCell, verdict, or capital "
                          "authority"))
