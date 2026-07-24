#!/usr/bin/env python3
"""WEEKLY DEEP COLD AUDIT (principal-ratified v2, 2026-07-24) -- the autonomous VPS equivalent
of the parallel 6-agent ceiling audit, upgraded to the full framework. Eight SEQUENTIAL cold
auditors (fresh context each = independence; the box cannot fan out parallel agents) + a
synthesis lead that builds the capability map, prioritizes the portfolio, and recursively
improves the audit itself. Max effort, quota-unconstrained (Max plan). Weekly, Sunday 04:00Z.

OUTCOME-ASSERTED: any report < 2500 bytes is recorded as a FAILED auditor (the quota-stub
class) -- the audit that hunts config-vs-outcome must never itself be config-vs-outcome.
"""
from __future__ import annotations

import contextlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
OUT = ROOT / "docs/research/deep_sweep"
CORE = (ROOT / "prompts/deep_sweep_core.txt").read_text("utf-8")

SUBSYSTEMS = {
    "alpha-discovery": "Hypothesis diversity, unexplored market behaviors, crowded themes, "
        "neglected regimes, cross-asset transfer, temporal-resolution gaps, feature-interaction "
        "and higher-order opportunities, regime-conditioned hypotheses, causal-vs-correlational "
        "assumptions, hypothesis redundancy, negative-result reuse, abandoned-idea reassessment, "
        "falsification quality. What markets/public-info are we ignoring? Which signals can't be "
        "tested for missing data?",
    "data-intelligence": "Every dataset: quality/coverage/latency/history/cost AND collection "
        "architecture, redundancy, vendor concentration, survivorship, timestamp consistency, "
        "entity resolution, schema evolution, repair automation, backfill capability, metadata, "
        "versioning, lineage, reproducibility. Hunt derived/synthetic datasets, weak-labels, "
        "cross-source enrichment, alt-language sources, gov publications, archives.",
    "data-moat": "NOT 'what data do we have' but 'what information can only exist because of "
        "how WE combine data': proprietary transformations, hierarchical/composed features, "
        "graph reps, embeddings, event reconstruction, market-state fingerprints, research "
        "memory, experiment lineage, feature ancestry, alpha genealogy. These are more "
        "defensible than raw data.",
    "infrastructure": "Every service across correctness/latency/throughput/availability/"
        "resilience/recoverability/scaling/cost/fault-tolerance/deployment+rollback safety/"
        "test-depth/observability/alert-quality/tech-debt/upgrade-readiness. Security + "
        "operational resilience (outages hit research continuity). Organizational entropy: "
        "duplicated code/prompts/datasets, dead infra, orphaned automation.",
    "execution-growth": "Every execution pathway challenged: info leaks, latency accumulation, "
        "retries hiding problems, sync failures, broker-behavior bias, fills vs expectation, "
        "regime-varying slippage, commission-vs-strategy interaction, fragile logic, "
        "reconciliation failures, emergency-procedure gaps. MEASURED not configured (maker "
        "fill-rate, BNB balance, carry harvest vs fees). Gate-0 readiness + compounding levers.",
    "validation-stats": "Selection bias, multiple testing, parameter sensitivity, sample "
        "dependence, walk-forward + CV methodology, regime robustness, distributional "
        "assumptions, uncertainty propagation, capacity/cost modeling, simulation realism, MC "
        "design, bootstrap quality, structural breaks. Which gates accept/reject ~100pct (zero "
        "information)? What rigorous methods sit as DEAD CODE? Is the DSR bar OPTIMAL -- neither "
        "so high real alphas die nor so low noise passes? Challenge as if the authors are gone.",
    "research-engine": "The engine that makes future discoveries (highest-return section): "
        "hypothesis generation, experiment scheduling, prioritization, AI prompting, "
        "literature/repo/forum mining, translation, knowledge reuse, dedup, automation, "
        "turnaround, research-memory + knowledge-graph quality, search strategy, cross-domain "
        "synthesis, failed-experiment learning, throughput, bottlenecks. Research FRICTION "
        "(waiting/searching/cleaning/manual/duplicate/context-switch) and INFORMATION ENTROPY "
        "(knowledge forgotten, experiments lost, ideas rediscovered).",
    "meta-and-blindspots": "The layer above: which research ASSUMPTIONS have never been tested? "
        "Which workflows persist by habit? Which metrics could mislead? BLIND-SPOT TRANSFER -- "
        "scan one field outside crypto-quant expertise (optimization/control-theory/signal-"
        "processing/information-theory/network-science/OR/causal-inference/anomaly-detection/RL) "
        "for ideas that widen the hypothesis space. INSTITUTIONAL CURIOSITY: what stopped "
        "surprising us, which rejected ideas deserve re-look given new capability. Research "
        "TRAJECTORY: is each cycle making the next stronger (velocity/quality/robustness trend)?",
}


def _run(prompt: str, timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c",
         'source ops/brain_env.sh && brain_auth_check && '
         'claude --effort max --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def run_auditor(key: str, brief: str, stamp: str) -> bool:
    report = OUT / f"{stamp}_{key}.md"
    prompt = (
        f"{CORE}\n\n=== YOUR SUBSYSTEM THIS SWEEP: {key} ===\n{brief}\n\n"
        f"Work from /home/quant/quant-platform, READ-ONLY (run read/inspect commands freely; "
        f"do NOT modify code/state/cron/git). Apply ALL SIX perspectives and the five-things "
        f"search and the negative-space sweep. WRITE your full report to {report} in the "
        f"four-output structure, every claim carrying its proving command output. Be "
        f"exhaustive; token cost is not a constraint."
    )
    try:
        r = _run(prompt, 2700)
    except subprocess.TimeoutExpired:
        r = None
    ok = report.exists() and report.stat().st_size >= 2500
    if not ok:
        tail = ((r.stdout or "")[-900:] + "\n--stderr--\n" + (r.stderr or "")[-400:]) \
            if r else "TIMEOUT"
        report.write_text(f"# AUDITOR FAILED ({key})\n{tail}\n", "utf-8")
    return ok


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    results = []
    for key, brief in SUBSYSTEMS.items():
        print(f"[deep-sweep] auditor: {key}", flush=True)
        ok = run_auditor(key, brief, stamp)
        results.append((key, ok))
        print(f"[deep-sweep] {key}: {'OK' if ok else 'FAILED (recorded)'}", flush=True)

    good = [f"{stamp}_{k}.md" for k, ok in results if ok]
    synth = OUT / f"{stamp}_SYNTHESIS.md"
    if good:
        sp = (
            f"{CORE}\n\n=== YOU ARE THE SYNTHESIS LEAD ===\nRead every auditor report in "
            f"docs/research/deep_sweep/ dated {stamp}: {', '.join(good)}. Produce the honest "
            f"ceiling map to {synth}:\n"
            "(A) Overall verdict + per-subsystem ceiling table (current pct, practical ceiling, "
            "opportunity cost 1y).\n"
            "(B) CAPABILITY MAP: for the desk's capabilities, which MISSING capability unlocks "
            "the most downstream capabilities (highest-ROI multiplier)? Which existing capability "
            "is the biggest bottleneck / greatest systemic risk if it fails?\n"
            "(C) TOP OPPORTUNITIES as a PRIORITIZED PORTFOLIO: rank by expected total long-term "
            "contribution (direct + enabling/cascade effects + optionality + compounding) / "
            "(engineering effort x maintenance x opportunity-cost). Flag compounding multipliers. "
            "Do NOT rank by raw score alone -- they compete for scarce implementation capacity.\n"
            "(D) HARD WALLS listed separately (do not confuse with headroom).\n"
            "(E) AUDITOR DISAGREEMENTS adjudicated with evidence.\n"
            "(F) RECURSIVE META: which of the 8 subsystem-audits produced the most value this "
            "week, which produced little, what NEW audit section should exist next week, which "
            "audit question is no longer discriminative. Improve the audit itself.\n"
            "(G) RESEARCH CAPABILITY CAGR: a rough composite index (experiment throughput, "
            "hypothesis quality, validation quality, automation, knowledge reuse, implementation "
            "velocity, data coverage) -- is the ENGINE getting stronger week over week?\n"
            "THEN: append the top portfolio items as dated entries to "
            "docs/research/improvement_inbox.md (each: exactly-what + evidence + fix + ROI + "
            "dependencies + retirement condition), and add ONE line to data/PRINCIPAL_ACTION.md "
            "ONLY if a human decision/spend is required. Blunt; portfolio-prioritized, never "
            "'implement everything'; nothing high-value lost to neglect."
        )
        with contextlib.suppress(subprocess.TimeoutExpired):
            _run(sp, 2400)
    n_ok = sum(1 for _, ok in results if ok)
    print(f"[deep-sweep] done: {n_ok}/{len(results)} produced; "
          f"synthesis={'yes' if synth.exists() else 'NO'}", flush=True)


if __name__ == "__main__":
    main()
