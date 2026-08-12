"""DEEPSEEK SECOND FLYWHEEL -- the local core. Mandate III, IV, V, VIII, IX, X, CLXXVII, CXCV.

WHAT THIS IS. DeepSeek's IDENTITY IS LOCAL; OpenRouter is only an inference backend (IV). So
everything that constitutes the agent -- the policy gate, cold-context construction, sealing,
role allocation, cost accounting, the authority fences -- lives here and runs on the desk. Only
model inference leaves the box.

THE FIVE THINGS THIS REFUSES, each of which would turn a second flywheel into a second desk:

  * PROMOTING ANYTHING. CXCV-12/13/14/15: DeepSeek cannot promote a survivor, allocate capital,
    override policy, or merge authoritative code. The fences are functions that return REFUSED
    with a reason, not comments asking nicely. Stage-B forward clocks remain the sole promotion
    authority, exactly as they are for Claude.
  * RUNNING ON STALE POLICY. CXCV-4/5: the canonical policy hash is verified BEFORE every cycle
    and a mismatch fails VISIBLY. A research agent running yesterday's rules produces findings
    nobody can attribute to a ruleset.
  * A CONTAMINATED COLD PHASE. VIII: Phase A sees raw state only -- never Claude's opinion,
    Codex's conclusion, GPT's ranking, Kimi's interpretation, or a prior DeepSeek narrative. The
    cold context is FILTERED and the filter is tested, because independence asserted in a
    docstring is not independence.
  * UNSEALED COMPARISON. Phase A output is hashed and sealed BEFORE Phase B may look at anybody
    else's conclusions. Without the seal there is no way to tell an independent rediscovery from
    an agreement written after reading the answer -- and that distinction is the entire value of
    running a second brain.
  * SILENT IDENTITY SUBSTITUTION. IV: if the DeepSeek model is unavailable, record
    MODEL_UNAVAILABLE and preserve experiment integrity. Quietly serving the request from Claude
    or GPT would corrupt the one measurement the second flywheel exists to produce -- whether
    DeepSeek finds things Claude did not.

A DARK SEAT IS NOT A FAILURE. With no OPENROUTER_API_KEY the cycle reports DARK and exits 0. The
desk's improvement rate must never depend on a credential, and an organ that hard-fails on a
missing key is an organ that takes the whole scheduler down with it.

AUTHORITY: RESEARCH GENERATION ONLY -- everything it produces enters the SAME canonical empirical
engine as every other candidate, with no shortcut and no parallel registry.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CONTAMINATION_KEYS",
    "ESCALATION_STATES",
    "INHERITED_REGISTRIES",
    "SEED_ROLES",
    "cold_context",
    "escalation_mix",
    "fence",
    "inheritance_check",
    "policy_gate",
    "seal",
    "seat_state",
]

_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "data/deepseek_evidence.jsonl"
SEALS = "data/deepseek_seals"

#: X. Roles are SEEDS, not permanent bureaucracy -- spawnable, splittable, mergeable, retirable.
#: They live here as DATA so adding one is a row rather than a branch, and so the allocator can
#: rank them by measured marginal contribution (CXCV-26) instead of by the order somebody typed
#: them. No role is sacred.
SEED_ROLES: tuple[tuple[str, str], ...] = (
    ("cold_alpha_inventor", "economically plausible hypotheses from first principles"),
    ("survivor_assassin", "attack every survivor: leakage, hidden beta, overfit, crowding, cost, "
                          "capacity, tails, dependence, execution, decay"),
    ("graveyard_resurrection", "reopen rejected research after new data/regimes/venues/methods"),
    ("regime_specialist", "conditional alpha, transitions, interactions, lifecycle"),
    ("validation_red_team", "attack CPCV, walk-forward, lockbox, FDR, PBO, effective sample "
                            "size, timestamping, cost realism, false-negative gates"),
    ("multilingual_intelligence", "mine CN/KR/JP/RU/PT/ES/AR/TR/VI/ID/HI ecosystems"),
    ("cross_domain_transfer", "information theory, control theory, network science, causal "
                              "inference, econometrics, OR, survival analysis, queueing"),
    ("execution_tca_challenger", "venue routing, maker/taker, queue, fill probability, impact, "
                                 "adverse selection, latency, fees, rebates"),
    ("portfolio_allocator_challenger", "does this deserve the next unit of risk?"),
    ("replication_brain", "reproduce claimed discoveries independently"),
    ("contrarian_brain", "strongest coherent alternative explanation"),
    ("research_factory_optimizer", "wasted tests, stranded data, unwired modules, bottlenecks"),
    ("external_replication_factory", "papers, AI/RL/LLM trading research, competitions, repos"),
    ("unknown_unknown_explorer", "search beyond the current ontology"),
    ("negative_space_miner", "low-coverage cells across data x mechanism x asset x venue x "
                             "horizon x regime x representation x execution x label"),
    ("proprietary_state_factory", "fuse public sources + archives + own execution footprint"),
    ("data_exhaustion_agent", "is each dataset's plausible information exhausted?"),
    ("source_ecosystem_expander", "source -> author -> repos -> citations -> datasets -> local "
                                  "equivalents -> upstream/downstream"),
    ("historical_backfill_hunter", "lawful historical versions of ephemeral information"),
    ("failure_science_agent", "classify failures: mechanism, regime, proxy, sample, execution, "
                              "crowding, break, data defect, test defect, selection, capacity"),
    ("experiment_designer", "the cheapest decisive experiment"),
    ("natural_experiment_hunter", "fee changes, outages, margin changes, listings, spec changes, "
                                  "protocol changes, ETF events, exogenous shocks"),
    ("data_integrity_red_team", "attack timestamps, revisions, gaps, survivorship, mappings, "
                                "clocks, backfills, duplicates, historical availability"),
    ("alpha_recombination", "recombine fragments of survivors, failures, datasets, regimes"),
    ("near_survivor_repair", "minimum defensible modification separating false negative from "
                             "genuine failure"),
    ("alpha_uniqueness_decomposer", "incremental information or repackaged exposures?"),
    ("portfolio_complementarity_hunter", "alpha in the portfolio's current weakness states"),
    ("capital_displacement_researcher", "what could displace the weakest unit of risk?"),
    ("alpha_decay_scientist", "persistence, decay, recurrence"),
    ("research_debt_hunter", "generated-but-untested, tested-but-unclassified, "
                             "data-without-consumers, failures-without-attribution, unwired code"),
    ("research_saturation_detector", "diminishing marginal information; reopen on change"),
    ("knowledge_compression_agent", "compress failure clusters into reusable knowledge"),
    ("research_technology_hunter", "superior data systems, labels, representations, search, "
                                   "validation, portfolio, execution, autonomous-R&D methods"),
    ("competitor_capability_intelligence", "lawful public capability signals -- never secrets"),
    ("model_agent_challenger", "test DeepSeek/Qwen/GPT/Kimi/Claude/future models continuously"),
)

#: IV. Bulk/deep split by state. NOT SACRED -- the mandate says so explicitly, and these are
#: starting points the allocator is expected to move on measured $/validated-information-gain.
ESCALATION_STATES: dict[str, tuple[float, float]] = {
    "LOW_VALUE": (0.97, 0.03),
    "NORMAL": (0.90, 0.10),
    "MAJOR_DISCOVERY": (0.70, 0.30),
    "CRITICAL_HIGH_VOI": (0.50, 0.50),
}

#: VIII/IX. Context keys that carry ANOTHER AGENT'S CONCLUSION. Phase A must never see these.
#: Note what is NOT here: measured metrics, raw evidence, schemas and portfolio state are all
#: FACTS and belong in the cold context. The filter removes interpretations, not information --
#: a cold phase starved of facts produces uninformed guesses, not independent ones.
CONTAMINATION_KEYS: tuple[str, ...] = (
    "claude_opinion", "claude_conclusion", "claude_rationale", "claude_ranking",
    "codex_conclusion", "codex_rationale", "gpt_ranking", "gpt_recommendation", "gpt_opinion",
    "kimi_interpretation", "kimi_findings", "consensus", "consensus_summary", "agent_summary",
    "previous_deepseek_conclusion", "prior_conclusion", "desired_answer", "expected_answer",
    "recommendation", "verdict_hint", "research_brief", "peer_rationale",
)

#: CXCV-12..15. What DeepSeek may never do, whatever any model response says.
_FENCED: dict[str, str] = {
    "promote_survivor": "CXCV-12. Promotion authority is the Stage-B forward clock alone, for "
                        "every agent. A second promoter is a second statistical universe",
    "allocate_capital": "CXCV-13. Capital allocation is the principal's and the portfolio "
                        "engine's; a research agent that can size is not a research agent",
    "override_policy": "CXCV-14. The canonical policy hierarchy is authoritative over every "
                       "agent including this one",
    "merge_authoritative_code": "CXCV-15. Merging into authoritative code is outside this "
                                "agent's authority",
    "loosen_statistical_gate": "standing desk law: alpha stays 0.05 and no gate is loosened to "
                               "manufacture a hit, by any agent, ever",
    "raise_leverage_or_size": "R0143 size fence. Size and leverage decisions are the principal's",
    "touch_deadman_switch": "scripts/run_deadman_switch.py is Tier-3 NEVER-TOUCH",
}


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class Seat:
    """Whether inference is reachable at all, and on which identity."""

    lit: bool
    provider: str = "openrouter"
    bulk_model: str = ""
    deep_model: str = ""
    why: str = ""
    env_var: str = "OPENROUTER_API_KEY"


def seat_state(env: dict[str, str] | None = None) -> Seat:
    """IV + the dark-seat rule. A missing key is a REPORTED state, never an exception.

    Model IDs are read from the environment and never hardcoded: the mandate is explicit that
    historical DeepSeek model IDs must not be assumed still valid, and a stale constant here
    would silently route the second flywheel to a model that no longer exists.
    """
    e = dict(os.environ if env is None else env)
    key = e.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return Seat(lit=False, why=(
            "DARK: OPENROUTER_API_KEY is not set. This is a REPORTED STATE and exit 0 -- the "
            "desk's improvement rate must not depend on a credential, and an organ that "
            "hard-fails on a missing key takes the scheduler down with it"))
    return Seat(
        lit=True,
        provider=e.get("DEEPSEEK_PROVIDER", "openrouter"),
        bulk_model=e.get("DEEPSEEK_BULK_MODEL", ""),
        deep_model=e.get("DEEPSEEK_DEEP_MODEL", ""),
        why="seat lit",
    )


def policy_gate(root: Path | None = None) -> dict[str, Any]:
    """CXCV-4/5 + CLXXVIII. Verify canonical policy BEFORE any consequential work.

    Delegates to libs.ops.canonical_policy.resolve() -- the SAME resolver Claude and Codex use,
    which is the whole point of CXCV-27/38: a second agent resolving policy its own way would
    prove nothing about inheritance. A resolver import failure is itself a REFUSAL, never a pass:
    "we could not check" and "it checks out" are different answers.
    """
    try:
        from libs.ops import canonical_policy
    except ImportError as exc:
        return {"ok": False, "verdict": "RESOLVER_UNAVAILABLE",
                "why": f"cannot import the canonical resolver ({exc}); refusing to run "
                       "consequential work on unverified policy. UNKNOWN is not a pass"}
    res = canonical_policy.resolve(root)
    verdict = str(res.get("verdict", "MISSING_POLICY"))
    return {
        "ok": verdict == "RESOLVED",
        "verdict": verdict,
        "policy_hash": res.get("canonical_policy_hash"),
        "version": res.get("canonical_policy_version"),
        "detail": res,
        "why": ("canonical policy resolved; the cycle may proceed" if verdict == "RESOLVED" else
                f"policy verdict {verdict} -- FAILING VISIBLY rather than researching under rules "
                "nobody can attribute the findings to (CXCV-5)"),
    }


def cold_context(state: dict[str, Any]) -> dict[str, Any]:
    """VIII PHASE A. Strip every other agent's CONCLUSION, keep every FACT.

    The distinction is the design. Measured survivor metrics, near-survivor data, graveyard
    EVIDENCE, portfolio state, execution facts, regime measurements and schemas are all facts and
    stay. Opinions, rankings, rationales and consensus summaries go. A cold phase starved of facts
    would produce uninformed guesses rather than independent ones, which is a different and
    equally useless thing.
    """
    kept: dict[str, Any] = {}
    removed: list[str] = []
    for k, v in (state or {}).items():
        low = str(k).strip().lower()
        if low in CONTAMINATION_KEYS or any(
                low.endswith("_" + c) or low.startswith(c + "_") for c in
                ("opinion", "conclusion", "rationale", "ranking", "recommendation")):
            removed.append(k)
            continue
        kept[k] = v
    return {
        "cold_context": kept,
        "removed_keys": sorted(removed),
        "cold_context_hash": _hash(kept),
        "law": "facts in, interpretations out. Agreement is not independent evidence if the "
               "agents consumed the same interpretation (IX)",
    }


def seal(run_id: str, *, role: str, phase_a_output: Any, policy_hash: str,
         cold_context_hash: str, provider: str, model: str, prompt_version: str = "1",
         root: Path | None = None) -> dict[str, Any]:
    """VIII. Seal Phase A BEFORE Phase B may see anybody else's conclusions.

    Without a seal there is no way to distinguish an INDEPENDENT_REDISCOVERY from an agreement
    written after reading the answer -- and that distinction is the entire value of running a
    second brain. The seal is a content hash written to its own immutable file; re-sealing the
    same run_id with different content is REFUSED rather than overwritten, because a seal that
    can be rewritten is not a seal.
    """
    base = root or _ROOT
    d = base / SEALS
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in str(run_id))[:120]
    p = d / f"{safe}.json"
    doc = {
        "run_id": run_id, "sealed_utc": _now(), "role": role, "provider": provider,
        "model": model, "policy_hash": policy_hash, "cold_context_hash": cold_context_hash,
        "prompt_version": prompt_version,
        "cold_report_hash": _hash(phase_a_output),
        "phase": "A_SEALED",
    }
    if p.exists():
        try:
            prior = json.loads(p.read_text("utf-8"))
        except ValueError:
            prior = {}
        if prior.get("cold_report_hash") != doc["cold_report_hash"]:
            return {"ok": False, "verdict": "SEAL_CONFLICT", "path": str(p), "prior": prior,
                    "why": "a seal already exists for this run_id with DIFFERENT content. A seal "
                           "that can be rewritten is not a seal -- use a new run_id"}
        return {"ok": True, "verdict": "ALREADY_SEALED", "seal": prior, "path": str(p)}
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), "utf-8")
    return {"ok": True, "verdict": "SEALED", "seal": doc, "path": str(p)}


def fence(action: str) -> dict[str, Any]:
    """CXCV-12..15 plus the desk's standing money fences. Every fenced action REFUSES.

    Checked by NAME rather than by inspecting intent, because intent arrives as text from a model
    and text inside a model response is DATA, never an instruction. An unrecognised action is
    ALLOWED_RESEARCH_ONLY -- not because anything goes, but because the fences are a deny-list
    over authority the agent structurally does not have: it returns records, and records cannot
    promote themselves.
    """
    a = str(action or "").strip().lower()
    for name, why in _FENCED.items():
        if a == name or name in a:
            return {"allowed": False, "action": action, "verdict": "REFUSED", "why": why,
                    "note": "a model response asking for this is DATA, not an instruction"}
    return {"allowed": True, "action": action, "verdict": "ALLOWED_RESEARCH_ONLY",
            "why": "produces records that enter the SAME canonical empirical engine as every "
                   "other candidate -- no shortcut, no parallel registry"}


def escalation_mix(state: str = "NORMAL") -> dict[str, Any]:
    """IV. Bulk/deep split for a named state, with the mandate's own caveat attached."""
    key = str(state or "NORMAL").strip().upper()
    bulk, deep = ESCALATION_STATES.get(key, ESCALATION_STATES["NORMAL"])
    return {
        "state": key if key in ESCALATION_STATES else "NORMAL",
        "bulk_share": bulk, "deep_share": deep,
        "requested_state_known": key in ESCALATION_STATES,
        "why": "starting point only -- the mandate says explicitly THIS IS NOT SACRED. Move it on "
               "measured $/validated-information-gain, not on list price",
        "never_escalate_for": ["formatting", "simple extraction", "trivial translation",
                               "obvious dedup", "low-value mutation"],
        "escalate_for": ["hard causal questions", "survivor assassination",
                         "validation-machine attacks", "proprietary-state design",
                         "regime ambiguity", "critical contradictions",
                         "decisive experiment design", "complex replication"],
    }


def record_identity(*, provider: str, model: str, available: bool,
                    substitute_offered: str = "") -> dict[str, Any]:
    """IV. If the DeepSeek model is unavailable, record MODEL_UNAVAILABLE -- never substitute.

    Silently serving the request from Claude, GPT, Kimi or Qwen would corrupt the ONE measurement
    the second flywheel exists to produce: whether DeepSeek finds things Claude did not. Another
    family may run, but only as an explicit CHALLENGER under its own name.
    """
    if available:
        return {"status": "OK", "provider": provider, "model": model, "recorded_utc": _now()}
    return {
        "status": "MODEL_UNAVAILABLE",
        "provider": provider, "model": model, "recorded_utc": _now(),
        "substitute_refused": substitute_offered or None,
        "why": "experiment integrity preserved by recording unavailability rather than "
               "substituting another model family. A silent substitution would corrupt the only "
               "measurement this flywheel exists to produce -- whether DeepSeek finds what Claude "
               "did not. Another family may run, but only as an explicit CHALLENGER under its "
               "own name",
    }


@dataclass
class CycleReport:
    """One hourly cycle's outcome (V). Deliberately serialisable and small."""

    started_utc: str
    seat: str
    policy: str
    roles_run: list[str] = field(default_factory=list)
    findings: int = 0
    blocked: list[str] = field(default_factory=list)
    why: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"started_utc": self.started_utc, "seat": self.seat, "policy": self.policy,
                "roles_run": self.roles_run, "findings": self.findings,
                "blocked": self.blocked, "why": self.why}


#: CXCV-38. The canonical registries DeepSeek INHERITS. Every one is written by the pre-DeepSeek
#: machinery and READ here -- listing them is what makes "no parallel registry" checkable rather
#: than promised. A DeepSeek-only copy of any of these would be a second statistical universe
#: assembled one well-meaning convenience at a time.
INHERITED_REGISTRIES: tuple[tuple[str, str], ...] = (
    ("data/edge_intake.jsonl", "universal edge intake -- every discovery's disposition"),
    ("data/alpha_lifecycle.jsonl", "conditional-survivor + hibernation state"),
    ("docs/research/capability_challengers.jsonl", "elite-factory capability challengers"),
    ("docs/research/research_auction.jsonl", "research-capital auction decisions"),
    ("docs/research/free_substitute_comparisons.json", "paid/free substitution verdicts"),
    ("docs/research/blowup_library.jsonl", "failure / blow-up negative memory"),
    ("docs/graveyard.md", "permanent rejection memory"),
    ("docs/research/recommendation_ledger.json", "the desk's open recommendation queue"),
)

#: Paths a DeepSeek implementation must NEVER create. Each would shadow an inherited registry.
_FORBIDDEN_PARALLELS: tuple[str, ...] = (
    "data/deepseek_edge_intake.jsonl",
    "data/deepseek_lifecycle.jsonl",
    "data/deepseek_survivors.jsonl",
    "data/deepseek_graveyard.jsonl",
    "docs/research/deepseek_recommendation_ledger.json",
    "data/deepseek_auction.jsonl",
)


def inheritance_check(root: Path | None = None) -> dict[str, Any]:
    """CXCV-38. Prove DeepSeek INHERITS the pre-DeepSeek capability rather than re-founding it.

    Two halves, and the second is the one with teeth. The first reports which canonical
    registries are READABLE -- a missing one is NOT a failure here, because a registry with no
    rows yet is a desk that has not produced that artifact, not a broken inheritance. The second
    fails on any DEEPSEEK-PREFIXED SHADOW of an inherited registry existing on disk.

    That asymmetry is deliberate. Absence of a canonical file is a fact about the desk's history;
    presence of a parallel one is a fact about this agent's behaviour, and it is the failure mode
    the mandate actually warns about -- a second statistical universe assembled one well-meaning
    convenience at a time.
    """
    base = root or _ROOT
    readable, absent = [], []
    for rel, what in INHERITED_REGISTRIES:
        (readable if (base / rel).exists() else absent).append({"path": rel, "carries": what})
    shadows = [p for p in _FORBIDDEN_PARALLELS if (base / p).exists()]
    return {
        "checked_utc": _now(),
        "inherited_readable": readable,
        "inherited_absent": absent,
        "parallel_registries_found": shadows,
        "ok": not shadows,
        "verdict": ("INHERITS -- reads the canonical registries and founds none of its own"
                    if not shadows else
                    f"PARALLEL REGISTRY DEFECT: {shadows}. DeepSeek must consume existing "
                    "frontier-hunter findings, copy-trader findings, universal edge intake, "
                    "conditional-survivor state, micro-capacity state, free-data state and "
                    "elite-capability challengers WITHOUT creating competing stores (CXCV-38)"),
        "why_absent_is_not_a_failure": "a canonical registry with no rows yet is a desk that has "
                                       "not produced that artifact, not a broken inheritance; a "
                                       "PARALLEL one is this agent misbehaving",
    }
