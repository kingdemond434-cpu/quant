#!/usr/bin/env python3
"""WEEKLY DEEP COLD AUDIT (principal-ratified v2, 2026-07-24) -- the autonomous VPS equivalent
of the parallel 6-agent ceiling audit, upgraded to the full framework. Eight SEQUENTIAL cold
auditors (fresh context each = independence; the box cannot fan out parallel agents) + a
synthesis lead that builds the capability map, prioritizes the portfolio, and recursively
improves the audit itself. Max effort, quota-unconstrained (Max plan). Weekly, Sunday 04:00Z.

OUTCOME-ASSERTED: an auditor is graded COMPLETE only when its report carries the
`STATUS: COMPLETE` sentinel the auditor flips as its final act (plus a 1200-byte floor
against empty stubs). Bytes alone are NOT completion: on 2026-07-30 two auditors died
after writing their ~1.8KB skeletons and the old size-only gate graded both OK, skipped
them on every resume, and handed the synthesis lead two empty files as evidence (R0055)
-- the audit that hunts config-vs-outcome must never itself be config-vs-outcome.
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
    # 9th seat, the 07-31 synthesis's own (F) recommendation made real the same week: the
    # execution-growth seat found the launch-day money-path cluster days before keys arrive, so
    # launch-readiness gets an EXPLICIT seat while the stakes are highest. RETIREMENT CONDITION:
    # after Gate-0 passes AND the first live week completes clean, fold this brief back into
    # execution-growth (record the retirement in the synthesis that does it).
    "launch-readiness": "ACTIVE UNTIL GATE-0 + FIRST CLEAN LIVE WEEK. The money path AS WIRED, "
        "not as designed: walk every command and code path that fires on launch day and in week "
        "one (deposit recording, capital events, equity sources, ruin-rail arming/re-entry, "
        "stop placement, connector order paths, guard consumers, kill switches, reconciliation) "
        "and prove each reads/writes what actually exists -- phantom files, $0-equity paths, "
        "zero-caller safety code are the defect classes with proven instances. Board-vs-reality: "
        "does every gate0/readiness board line trace to a real artifact a real writer maintains? "
        "Drill coverage: which launch-day failures have never been drilled? Assume the launch "
        "happens TOMORROW and hunt what fires exactly once, that day, wrong.",
}


def _run(prompt: str, timeout: int) -> subprocess.CompletedProcess[str]:
    # DUAL-POOL (2026-07-26): try the fable metered pool FIRST, fall through to the Max seat.
    # Each auditor is its own invocation with its own brain_auth_check, so the 8 auditors
    # AUTO-LOAD-BALANCE across both pools -- the first ones drain fable, the rest land on opus-5.
    # The sweep lost every auditor at 04:00 racing the cycle and diggers for a single seat.
    return subprocess.run(
        ["bash", "-c",
         # The chain comes from brain_env.sh -> ops/model_chain.env (single source, 2026-07-30).
         # It used to be re-exported here as a literal, which would have pinned the sweep to
         # yesterday's models the moment run_model_upgrade.py adopted a newer flagship.
         'source ops/brain_env.sh && '
         # a silent short-circuit here is what made today's four failures
         # undiagnosable: no model answered, claude never ran, both streams empty
         'brain_auth_check || { echo "BRAIN_AUTH_FAILED: no model in '
         '_BRAIN_MODEL_CHAIN answered -- pool drained or session limit"; '
         'exit 90; } && '
         'claude --effort max --append-system-prompt "$_DOCTRINE" -p "$0" '
         '--dangerously-skip-permissions', prompt],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout)


_SENTINEL = "STATUS: COMPLETE"
# Reports written before the sentinel convention existed are grandfathered on the byte
# floor alone -- without this, the first post-fix resume would re-run every real report
# from earlier the same day (6 x 30min of quota re-buying evidence that already exists).
_SENTINEL_BORN = datetime(2026, 7, 31, tzinfo=UTC).timestamp()


def _complete(report: Path) -> bool:
    """COMPLETION is the auditor's own final act, not a byte count.

    The 2026-07-30 sweep graded two ~1.8KB skeletons OK on `st_size >= 1200` -- a
    doctrine-conforming skeleton clears any sane byte floor, so an auditor that dies
    after writing its headings is invisible to a size gate forever (R0055). The 1200b
    floor stays only to reject empty/binary stubs; the grade is the sentinel."""
    if not report.exists() or report.stat().st_size < 1200:
        return False
    if _SENTINEL in report.read_text("utf-8", errors="replace"):
        return True
    return report.stat().st_mtime < _SENTINEL_BORN


def run_auditor(key: str, brief: str, stamp: str) -> bool:
    report = OUT / f"{stamp}_{key}.md"
    prompt = (
        f"{CORE}\n\n=== YOUR SUBSYSTEM THIS SWEEP: {key} ===\n{brief}\n\n"
        f"Work from /home/quant/quant-platform, READ-ONLY (run read/inspect commands freely; "
        f"do NOT modify code/state/cron/git). Apply ALL SIX perspectives and the five-things "
        f"search and the negative-space sweep. WRITE your full report to {report} in the "
        f"four-output structure, every claim carrying its proving command output. Put "
        f"`STATUS: IN PROGRESS` near the top of the file when you create it and flip it to "
        f"`STATUS: COMPLETE` as your FINAL edit -- the runner grades completion by that "
        f"sentinel and a report never flipped re-runs on the next window. Be "
        f"exhaustive; token cost is not a constraint."
    )
    try:
        r = _run(prompt, 1800)
    except subprocess.TimeoutExpired:
        r = None
    ok = _complete(report)
    if not ok:
        # NAME THE STAGE. "Failed with two empty streams" is what today's four auditors
        # recorded, and it cost the reason entirely. Exit 90 is our own auth sentinel; any
        # other non-zero came from claude itself; None means the 1800s budget ran out.
        if r is None:
            why = ("TIMEOUT after the 1800s budget -- this auditor's brief is too broad for one "
                   "window; split it rather than raising the timeout")
        elif r.returncode == 90:
            why = ("BRAIN_AUTH_FAILED -- no model in the chain answered (pool drained or session "
                   "limit). This is RETRYABLE: the catch-up re-fires the sweep and the resume "
                   "logic skips every COMPLETE report, so only the failures re-run")
        else:
            why = f"claude exited {r.returncode}"
        streams = (f"\n--stdout(tail)--\n{(r.stdout or '')[-900:]}"
                   f"\n--stderr(tail)--\n{(r.stderr or '')[-600:]}") if r else ""
        partial = report.stat().st_size if report.exists() else 0
        # Sidecar, NEVER the report itself: the old code overwrote the partial report with
        # this stub, destroying the only evidence of how far the auditor got -- in direct
        # contradiction of the completion contract it enforces. A partial report is the
        # deliverable; the next window's auditor continues over it.
        (OUT / f"{stamp}_{key}.md.FAILED").write_text(
            f"# AUDITOR FAILED ({key})\n\nWHY: {why}\n"
            f"partial report bytes preserved in place: {partial} "
            f"(re-runs on resume until its {_SENTINEL} sentinel appears)\n{streams}\n", "utf-8")
    return ok


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    results = []
    # SEAT ROTATION (E-20, 07-31 synthesis): the dict order ran verbatim every window, so when a
    # window died mid-sweep the SAME tail seats starved every time (position 8 produced nothing
    # for days while position 1 re-ran fine). Rotate the starting seat by date -- deterministic
    # (resume within a day sees the same order) and fair across days: every seat is first once
    # per cycle through the list.
    seats = list(SUBSYSTEMS.items())
    offset = int(stamp) % len(seats)
    seats = seats[offset:] + seats[:offset]
    for key, brief in seats:
        # RESUMABLE (2026-07-26): a real report for TODAY means this auditor is done -- skip it,
        # so a sweep killed halfway is CONTINUED by the next invocation (organ_catchup re-fires
        # reset-aware) instead of restarting at auditor one and re-losing the same seat race.
        done = OUT / f"{stamp}_{key}.md"
        if _complete(done):
            print(f"[deep-sweep] {key}: already COMPLETE today -- skipping (resume)", flush=True)
            results.append((key, True))
            continue
        print(f"[deep-sweep] auditor: {key}", flush=True)
        ok = run_auditor(key, brief, stamp)
        results.append((key, ok))
        print(f"[deep-sweep] {key}: {'OK' if ok else 'FAILED (recorded)'}", flush=True)

    good = [f"{stamp}_{k}.md" for k, ok in results if ok]
    synth = OUT / f"{stamp}_SYNTHESIS.md"
    if _complete(synth):
        # Synthesis had NO resume check: the 2026-07-30 22:45 window re-launched a full
        # synthesis seat five hours after the 17:00 one wrote STATUS: COMPLETE.
        print("[deep-sweep] synthesis: already COMPLETE today -- skipping (resume)", flush=True)
    elif good:
        sp = (
            f"{CORE}\n\n=== YOU ARE THE SYNTHESIS LEAD ===\nRead every auditor report in "
            f"docs/research/deep_sweep/ dated {stamp}: {', '.join(good)}. Produce the honest "
            f"ceiling map to {synth}:\n"
            "(A) Overall verdict + per-subsystem ceiling table (current pct, practical ceiling, "
            "opportunity cost 1y) -- AND re-grade docs/research/TIER1_BENCHMARK.md in the same "
            "session: where auditor evidence moves a layer's tier against the motive-similar "
            "cohort (RenTech/Medallion always cited fully as the ceiling exemplar), edit the "
            "register's row and say why; the register and this table must never disagree "
            "silently.\n"
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
            "THEN -- LEDGER FIRST (R0056; the desk's own record proves improvement_inbox.md is "
            "write-only): row each top portfolio item into the section-42 ledger via "
            "`.venv/bin/python scripts/recommendations.py add --source deep_sweep --summary "
            "'...' --roi-bps N` -- DEDUP against open rows first (`recommendations.py report`) "
            "and cite the existing row id instead of re-adding; then append ONE short pointer "
            "entry to docs/research/improvement_inbox.md naming the row ids; and add ONE line to "
            "data/PRINCIPAL_ACTION.md ONLY if a human decision/spend is required. Blunt; "
            "portfolio-prioritized, never 'implement everything'; nothing high-value lost to "
            "neglect. L1.28b applies to your own output: an un-rowed recommendation is a finding "
            "already leaking."
        )
        with contextlib.suppress(subprocess.TimeoutExpired):
            _run(sp, 1800)
    # SECOND FAMILY (L1.33 / R0114, shared helper libs/llm/second_opinion.py): all nine seats and
    # the synthesis lead think in the same model family's priors -- the meta-and-blindspots seat
    # included, which is the defect it audits for, applied to itself. Ask the independent family
    # which SUBSYSTEM/seat this sweep cannot see, and record the verdict beside the reports --
    # SOLO when the seat is dark, and a dark partner never breaks the sweep's exit-0 cadence.
    try:
        import sys
        root = str(Path(__file__).resolve().parent.parent)   # __file__, so it also works off-VPS
        if root not in sys.path:
            sys.path.insert(0, root)        # run as `python scripts/...`: root is not on sys.path
        from libs.llm.second_opinion import consult_second_family
        consult_second_family(
            "deep_sweep",
            {"stamp": stamp,
             "auditors": {k: ("COMPLETE" if ok else "FAILED") for k, ok in results},
             "synthesis": "COMPLETE" if _complete(synth) else "MISSING"},
            artifact=OUT / f"{stamp}_second_family.json")
    except Exception as exc:  # the partner must never break the organ
        print(f"  second family: SKIPPED ({exc})")
    n_ok = sum(1 for _, ok in results if ok)
    print(f"[deep-sweep] done: {n_ok}/{len(results)} COMPLETE; "
          f"synthesis={'yes' if _complete(synth) else 'NO'}", flush=True)


if __name__ == "__main__":
    main()
