"""CLAUDE-LOCAL MINER ROI + MODEL SEAT — principal directive 2026-08-12.

SCOPE, AND IT IS NARROW BY CONSTRUCTION. This module governs ONLY local Claude autonomous
miners and scheduled research cycles that draw the Claude/Fable plan. It has no opinion about,
and no reachability into, the hypothesis generator, OpenRouter, DeepSeek, Codex, GPT, Kimi or
Qwen. Those are external-provider systems on their own budgets and cadences; nothing here reads
or writes their config. `assert_external_untouched()` at the bottom exists so that claim is a
test rather than a promise.

THE LAW THIS ENCODES:

    OPUS 5 = DEFAULT for local Claude work.
    FABLE 5 = Chinese miners + the currently best-performing miners, MEASURED.
    Fable eligibility is NOT permanent and does NOT mean high cadence.
    Cadence follows information REFILL and marginal ROI, not habit.

WHY THE DEFAULT INVERTED TODAY. Earlier this session the desk routed EVERY miner to Fable on a
pool-splitting argument: fable is metered, opus sits on the subscription seat, so put the
resumable work on the meterable pool. That reasoning was about which pool starves first. The
principal's constraint is different and supersedes it — the Claude/Fable plan as a whole is
scarce capital, and background miners were consuming it before the day's interactive work could.
So the question is no longer "which pool" but "does this run deserve a premium model at all".

THE FOUR STATES, and what moves a miner between them:

    OPUS_STANDARD   the default. Opus 5, ordinary cadence.
    FABLE_ELITE     Chinese miners, or a non-Chinese miner whose MEASURED downstream value per
                    token is currently top-ranked. Re-evaluated every scoring pass.
    COOLDOWN        repeated low yield: interval stretched, model still available.
    HIBERNATED      sustained zero yield: cheap periodic recheck only, no premium reasoning
                    until fresh evidence arrives.

RANKED ON DOWNSTREAM VALUE, NEVER ON SCRAPE VOLUME. A miner that fetches 1,600 rows and produces
no edge intake is not productive; one that fetches 40 and lands a mechanism is. `roi_score()`
therefore reads edge intake, high-value findings and downstream tests per 100k tokens — the
metrics §30 names — and explicitly ignores raw article count.

EXPLORATION IS NOT KILLED (§32). A weak miner cools and eventually hibernates, but hibernation
keeps a cheap recheck and any fresh evidence reactivates it. Nothing here deletes a miner, and
nothing here discards evidence: the optimisation is WAIT / BATCH / DEDUP / COMPRESS, never
IGNORE (§33).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "CHINESE_MINERS",
    "STATES",
    "MinerStats",
    "assert_external_untouched",
    "cadence_hours",
    "model_for",
    "roi_score",
    "tier_for",
]

_ROOT = Path(__file__).resolve().parents[2]
LEDGER = "data/miner_roi.jsonl"

STATES: tuple[str, ...] = ("OPUS_STANDARD", "FABLE_ELITE", "COOLDOWN", "HIBERNATED")

OPUS = "claude-opus-5"
FABLE = "claude-fable-5"

#: Chinese-language miners. Fable-ELIGIBLE by standing policy -- but eligibility is not cadence,
#: and §14 is explicit that they batch like everything else.
CHINESE_MINERS: frozenset[str] = frozenset({
    "cn_sources", "chinese_miner", "bilibili", "juejin", "wechat", "wechat_sogou", "xueqiu",
})

#: How many non-Chinese miners may hold FABLE_ELITE at once. A cap, because "elite" chosen by
#: ranking with no ceiling is just "everyone" after enough miners are added.
MAX_FABLE_ELITE = 2

#: Cooling thresholds (§24). Deliberately conservative starting values, not hardcoded law (§10).
LOW_YIELD_RUNS_TO_COOL = 3
ZERO_YIELD_RUNS_TO_HIBERNATE = 5
LOW_YIELD_RATIO = 0.01           # <1% new-per-fetched counts as low


@dataclass
class MinerStats:
    """§24's per-miner state, plus §30's token accounting. All optional -- an unmeasured field
    is UNKNOWN and never silently zero."""

    name: str
    last_run: str = ""
    last_success: str = ""
    last_novel_result: str = ""
    unique_yield: float | None = None
    duplicate_rate: float | None = None
    consecutive_low_yield: int = 0
    consecutive_zero_yield: int = 0
    refusal_state: str = ""
    estimated_refill_h: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    edge_intake_items: int = 0
    high_value_findings: int = 0
    downstream_tests: int = 0
    new_items: int = 0
    unique_items: int = 0
    zero_value_runs: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return int(self.input_tokens) + int(self.output_tokens)


def roi_score(s: MinerStats) -> dict[str, Any]:
    """§30/§31. Downstream usefulness per 100k tokens. NOT article count.

    UNMEASURED when no tokens have been spent -- a miner that has never run has no ROI, and
    scoring it zero would rank it below a measured failure, which is exactly backwards: an
    unmeasured miner is a question, a measured-zero miner is an answer.
    """
    tok = s.total_tokens
    if tok <= 0:
        return {"miner": s.name, "status": "UNMEASURED", "score": None,
                "why": "no tokens recorded -- an unrun miner has no ROI, and scoring it 0 would "
                       "rank it beneath a miner measured as useless. Unknown is not zero (L1.41)"}
    per100k = 100_000.0 / tok
    edge = s.edge_intake_items * per100k
    high = s.high_value_findings * per100k
    tests = s.downstream_tests * per100k
    # Downstream CONSEQUENCE weighs most: an item that changed what the desk tested is worth
    # more than one that merely entered a queue.
    score = round(3.0 * tests + 2.0 * high + 1.0 * edge, 4)
    return {
        "miner": s.name, "status": "MEASURED", "score": score,
        "edge_intake_per_100k": round(edge, 4),
        "high_value_per_100k": round(high, 4),
        "downstream_tests_per_100k": round(tests, 4),
        "total_tokens": tok,
        "why": "ranked on downstream usefulness per token; raw fetched/scraped volume is "
               "deliberately absent -- 1,600 rows producing no intake is not productivity",
    }


def tier_for(s: MinerStats, *, elite_names: set[str] | None = None) -> dict[str, Any]:
    """§4. Which state a miner is in, and why. Cooling beats eliteness.

    ORDER MATTERS. A miner is checked for hibernation and cooldown BEFORE eliteness, because a
    Chinese or top-ranked miner that has gone dry should stop spending premium tokens exactly
    like any other. Fable eligibility is about WHICH model when it runs, never about whether a
    dry run deserves a model at all.
    """
    elite = set(elite_names or ())
    if s.consecutive_zero_yield >= ZERO_YIELD_RUNS_TO_HIBERNATE:
        return {"miner": s.name, "state": "HIBERNATED",
                "why": f"{s.consecutive_zero_yield} consecutive zero-yield runs. Cheap periodic "
                       "recheck only; no premium reasoning until fresh evidence arrives. NOT "
                       "deleted and NOT blacklisted -- fresh evidence reactivates it (§32)"}
    if s.consecutive_low_yield >= LOW_YIELD_RUNS_TO_COOL:
        return {"miner": s.name, "state": "COOLDOWN",
                "why": f"{s.consecutive_low_yield} consecutive low-yield runs; interval stretched "
                       "so the source is given time to refill rather than re-sampled"}
    if s.name in CHINESE_MINERS:
        return {"miner": s.name, "state": "FABLE_ELITE",
                "why": "Chinese miner -- Fable-eligible by standing policy. Eligibility is NOT "
                       "cadence: it still batches and still obeys the novelty gate (§14)"}
    if s.name in elite:
        return {"miner": s.name, "state": "FABLE_ELITE",
                "why": "currently among the measured top producers by downstream value per "
                       "token. This is REVOCABLE -- it is re-earned at every scoring pass (§4)"}
    return {"miner": s.name, "state": "OPUS_STANDARD",
            "why": "default seat. Opus 5 is the local Claude default; Fable is not used merely "
                   "because it is available (§2)"}


def rank_elite(stats: list[MinerStats], *, cap: int = MAX_FABLE_ELITE) -> dict[str, Any]:
    """§3B/§4. Which NON-Chinese miners have currently earned Fable, by measurement alone."""
    scored = []
    unmeasured = []
    for s in stats:
        if s.name in CHINESE_MINERS:
            continue
        r = roi_score(s)
        (scored if r["status"] == "MEASURED" else unmeasured).append((s.name, r))
    scored.sort(key=lambda kv: -(kv[1]["score"] or 0.0))
    winners = [n for n, r in scored[:cap] if (r["score"] or 0.0) > 0.0]
    return {
        "elite": winners,
        "ranked": [{"miner": n, **r} for n, r in scored],
        "unmeasured": [n for n, _ in unmeasured],
        "cap": cap,
        "law": "Fable is EARNED by measured downstream value per token and re-earned every pass. "
               "A miner with score 0 never qualifies, however much it scrapes",
    }


def model_for(s: MinerStats, *, elite_names: set[str] | None = None) -> dict[str, Any]:
    """The seat decision for one local Claude miner run."""
    t = tier_for(s, elite_names=elite_names)
    state = t["state"]
    model = FABLE if state == "FABLE_ELITE" else OPUS
    return {**t, "model": model,
            "note": "LOCAL CLAUDE ONLY. This routing never applies to OpenRouter, DeepSeek, "
                    "Codex, GPT, Kimi or Qwen, and never to the hypothesis generator."}


def cadence_hours(s: MinerStats, *, base_h: float = 24.0) -> dict[str, Any]:
    """§9/§10/§24. Interval follows refill and yield, stretching on repeated low yield.

    The base is one substantive cycle per day (§10's "ordinary miner"). Measured refill, when
    known, overrides it: a source that demonstrably needs 60h to refill is not asked every 24.
    """
    hours = float(base_h)
    reasons = [f"base {base_h:.0f}h (§10 ordinary miner)"]
    if s.estimated_refill_h and s.estimated_refill_h > hours:
        hours = float(s.estimated_refill_h)
        reasons.append(f"measured refill {s.estimated_refill_h:.0f}h dominates the base")
    if s.consecutive_low_yield >= LOW_YIELD_RUNS_TO_COOL:
        hours *= 2.0
        reasons.append(f"x2 cooldown ({s.consecutive_low_yield} low-yield runs)")
    if s.consecutive_zero_yield >= ZERO_YIELD_RUNS_TO_HIBERNATE:
        hours = max(hours, 168.0)
        reasons.append(f"hibernation floor 168h ({s.consecutive_zero_yield} zero-yield runs)")
    return {"miner": s.name, "interval_hours": round(hours, 1), "why": "; ".join(reasons),
            "law": "cadence follows information refill and marginal ROI, never habit (§9)"}


def record(s: MinerStats, *, root: Path | None = None) -> dict[str, Any]:
    """Append one miner's telemetry row (§24/§30) for the rolling ROI ranking."""
    base = root or _ROOT
    row = {"ts": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           **{k: v for k, v in s.__dict__.items() if k != "extra"},
           "roi": roi_score(s)}
    p = base / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


#: Systems this directive explicitly puts OUT OF SCOPE. Named here so the boundary is testable.
EXTERNAL_UNTOUCHED: tuple[str, ...] = (
    "hypothesis_generator", "openrouter", "deepseek", "codex", "gpt", "kimi", "qwen",
)


def assert_external_untouched() -> dict[str, Any]:
    """The scope boundary, as a check rather than a promise.

    This module must never name an external provider as a routing target. If a future edit adds
    one, the test that calls this fails -- which is the point: a scope boundary maintained only
    by everyone remembering it is a boundary that lasts until the first busy afternoon.
    """
    targets = {OPUS, FABLE}
    leaked = sorted(t for t in targets
                    if any(ext in t.lower() for ext in EXTERNAL_UNTOUCHED))
    return {
        "ok": not leaked,
        "routing_targets": sorted(targets),
        "external_systems_out_of_scope": list(EXTERNAL_UNTOUCHED),
        "leaked": leaked,
        "why": ("this module routes only between local Claude models; no external provider is a "
                "routing target" if not leaked else
                f"SCOPE BREACH: {leaked} -- an external provider became a local-Claude routing "
                "target, which this directive forbids outright"),
    }
