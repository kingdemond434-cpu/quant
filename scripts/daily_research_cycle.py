"""Daily institutional research cycle -- the CRO everyday loop.

ONE complete cycle, run daily by Task Scheduler:
  1. run_daily_research.py   -- forward-accumulating pipeline: candidate generation + validation +
                                data archiving (feeds the research system for testing)
  2. research_cycle.py       -- regenerate the 3 state files, ROI reprioritization, calibration
  3. run_leverage_opt.py     -- recompute growth-optimal leverage per sleeve + joint
  4. run_live_combined.py    -- refresh the molded book
Then it appends a DATED entry to data/cro_cycle_log.json (bottleneck, next highest-ROI task,
deployed metrics, calibration, candidates tested) and prints the next action. Continuous process:
no terminal state except the absence of positive expected-Research-ROI work.

Each step is isolated -- one failure never aborts the cycle. Idempotent + safe to re-run.

    python scripts/daily_research_cycle.py
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)
_LOG = _ROOT / "data" / "cro_cycle_log.json"
# R0258: steps_ok in the cycle log had ZERO consumers, so a failed step was invisible. Every
# cycle now also drops this artifact for run_alerts.py, which pages when it carries failures.
_STATUS = _ROOT / "data" / "research_chain_status.json"

# ordered pipeline; (label, script, timeout_s). Heavy research first, then bookkeeping.
_STEPS = [
    # 1200s: the whole-tree gate (2026-07-25) runs ~8min; the old 300s was sized for the 4-file
    # gate and silently killed this step by timeout every run since (R0146, stale-consumer class).
    # 3900s (2026-08-05): run_ci now bounds each of its OWN steps, summing to 3300s worst case,
    # and this outer bound must lose that race -- an outer kill produces no [HUNG] line and no
    # red CI marker, which is precisely the stale-green blindness the inner bounds exist to end.
    # This is a ceiling reached only when the gate is wedged (normal run is still ~8min), so the
    # rise costs nothing on a healthy day and buys a NAMED failure on a bad one. The ordering is
    # asserted by tests/ops/test_ci_gate_timeouts.py against run_ci.STEP_BUDGET_TOTAL_S.
    ("ci_gate",           "scripts/run_ci.py",             3900),
    ("recorder_watch",    "scripts/ensure_recorder.py",      60),  # data moat must never sleep
    ("stablecoin_flows",  "scripts/run_stablecoin_flows.py", 180),  # daily on-chain clock tick
    ("fred_macro",        "scripts/collect_fred_macro.py",   120),  # free US-macro (key-gated)
    ("walcl_clock",       "scripts/derive_walcl_clock.py",    60),  # R0031 forward clock, reads
    #                      the fred archive the previous step just refreshed (phase = cadence)
    ("naver_krsearch",    "scripts/collect_naver_krsearch.py", 60),  # KR attention (key-gated)
    ("root_cause",        "scripts/run_root_cause.py",       120),  # classify losses pre-reaction
    ("desk_digest",       "scripts/render_desk_digest.py",    60),  # Obsidian-readable daily brief
    ("micro_audit",       "scripts/run_micro_audit.py",      480),  # 3 cold LLMs on 24h delta
    ("cadence",           "scripts/run_cadence.py",          900),  # stage-aware review scheduler
    ("research_feed",     "scripts/collect_research_feed.py", 120),  # arXiv q-fin -> vault inbox
    ("growth_audit",      "scripts/run_growth_audit.py",       60),  # under-utilization = defect
    ("research_pipeline", "scripts/run_daily_research.py",  7200),
    ("autodiscovery",     "scripts/run_crypto_research.py", 1800),  # industrialized crypto factory
    # the research-coordination engines: rank the agenda queue, screen novelty against the
    # do-not-repeat list, assess crowding/capacity, and flag candidates that duplicate a
    # deployed sleeve. 17 of 21 alpha_factory modules had no caller before this.
    ("alpha_factory",     "scripts/run_alpha_factory.py",   180),
    ("state_files",       "scripts/research_cycle.py",      300),
    ("trade_forensics",   "scripts/run_trade_forensics.py",  60),  # class-bleed probe (daily)
    ("nav_attest",        "scripts/run_nav_attest.py",       60),  # hash-chained track record
    # gap-2 §3-§6: the ONE production caller for the S1 rails (naked-position reconcile, pager
    # de-risk ladder, 6h canary, numeric ramp gate, stage machine). Inert at S0/without keys --
    # but it must run daily from S0 so the rails are exercised BEFORE they are load-bearing,
    # rather than executing for the first time on the day real money is behind them.
    ("live_guard",        "scripts/run_live_guard.py",       120),
    ("listing_watch",     "scripts/run_listing_watch.py",    60),  # gap-53 data clock
    # §42(6): the CONSUMER for that clock. Collection without a promotion path is acquisition the
    # desk can never convert, so the study runs on the same cadence as the collector rather than
    # waiting for someone to remember it exists.
    ("event_study",       "scripts/run_event_study.py",     300),
    # §42: cross-venue funding on the THIN tail -- where a small book is not the worst-capitalised
    # participant. The liquid names are already screened; this starts the clock on the other end.
    ("tail_funding",      "scripts/collect_tail_funding_divergence.py", 120),
    ("kimchi_premium",    "scripts/collect_kimchi_premium.py", 90),  # gap-74 forward clock
    ("onchain_activity",  "scripts/collect_onchain_activity.py", 120),
    # licence-clean Glassnode/Coin-Metrics replacement (facts reconstructed from chain)
    ("onchain_metrics",   "scripts/collect_onchain_metrics.py", 180),  # on-chain throughput
    ("stablecoin_supply", "scripts/collect_stablecoin_supply.py", 120),  # supply momentum clock
    ("breadth_expander", "scripts/breadth_expander.py", 420),  # external-LLM breadth scout (Stage-A only)
    ("signal_halflife",  "scripts/signal_halflife.py", 180),  # signal ageing/decay tracker
    ("measurement_gate",  "scripts/measurement_gate.py", 120),  # inputs must be verified before any optimisation
    ("exec_bottleneck",   "scripts/execution_bottleneck.py", 60),  # live book vs live gate
    ("collector_monitor","scripts/collector_monitor.py", 90),  # G3 zero-trust sensor kill-switch
    ("stage_a_exec",       "scripts/stage_a_executor.py", 120),  # RUN the ranked queue, not order it
    ("defi_axis",          "scripts/build_defi_axis.py", 60),  # pool rows -> daily z20 axis feed
    ("conversion",        "scripts/conversion_engine.py", 90),  # mined data -> ranked experiments, every cycle
    ("enforce_proof",     "scripts/prove_future.py", 90),  # adversarial: guards must FAIL on planted violations
    ("principle_audit",   "scripts/principle_audit.py", 30),  # STRICT: all 15 principles must reach models
    ("blindspot_max",     "scripts/blindspot_max.py", 120),  # 4 classes of mechanical unknown-unknown
    ("doctrine_guard",      "scripts/doctrine.py", 30),  # STRICT: fails if any LLM caller runs without doctrine
    ("doctrine_diff",       "scripts/check_doctrine_diff.py", 30),  # R0093: principal order -> blind-spot row
    ("unobserved",          "scripts/unobserved.py", 90),  # unknown-unknowns we already own and never read
    ("module_justify",      "scripts/module_justification.py", 120),  # would I build this today -- merit audit of existing code
    ("coverage_audit",      "scripts/coverage_audit.py", 60),  # one honest coverage number per surface
    ("knowledge_engine",   "scripts/knowledge_engine.py", 90),  # memory + causal graph + genome + revival
    ("dependency_graph",   "scripts/dependency_graph.py", 60),  # impact analysis: what is poisoned now
    ("data_vitals",         "scripts/data_vitals.py", 90),  # live collector DQS + provenance
    ("alpha_lifecycle",     "scripts/alpha_lifecycle.py", 90),  # failure patterns + transfer pipeline + novelty + anomalies
    ("research_cio",        "scripts/research_cio.py", 90),  # info advantage + blind spots + north star + scheduler
    ("hedge_integrity",     "scripts/hedge_integrity.py", 60),  # venue-truth hedge invariant
    ("feature_library",     "scripts/feature_library.py", 90),  # feature assets + construction coverage
    ("leakage_detector",    "scripts/leakage_detector.py", 60),  # self-validating leakage contract
    ("experiment_registry", "scripts/experiment_registry.py", 90),  # harvest experiments -> permanent objects
    ("desk_brief",          "scripts/research_exchange.py brief", 60),  # daily research board / external-LLM brief
    # --- installed 2026-07-29 (closure cycle). Every one of these is an organ that would
    # otherwise be built-but-idle, which L2.9 counts as a defect. Cheap, read-only, no risk path.
    ("ratchets",            "scripts/check_ratchets.py --ratchet", 60),  # L1.0: every metric toward 100%, floors only rise
    ("execution_intel",     "scripts/run_execution_intel.py", 60),  # cross-feed cost-DRIFT (recommend-only)
    ("reality_gap",         "scripts/run_reality_gap.py", 60),  # L2.10: backtest->shadow->live->venue-truth
    ("miner_runway",        "scripts/check_miner_runway.py --report-only", 60),  # why a seat never produced
    ("scheduler_manifest",  "scripts/check_scheduler_manifest.py --report-only", 60),  # DR floor + live drift
    ("mypy_ratchet",        "scripts/check_mypy_ratchet.py --report-only", 900),  # type backlog is a ceiling
    ("contributor_score",   "scripts/research_exchange.py score", 60),  # which intelligence source earns allocation
    ("claim_verifier",    "scripts/claim_verifier.py", 90),  # verify every published claim vs source
    ("claim_escalate",    "scripts/claim_escalate.py", 60),  # escalate false claims to pager + Gate-0
    ("data_sanity",       "scripts/data_sanity.py", 120),  # implausibility scan (2 artifacts today)
    ("hurdle_rate",       "scripts/hurdle_rate.py", 90),  # is the desk beating T-bills/BTC?
    ("negative_knowledge", "scripts/negative_knowledge.py", 60),  # revival triggers on dead ideas
    ("research_autopsy",  "scripts/research_autopsy.py", 60),  # failure-mode taxonomy + lessons
    ("research_erv",      "scripts/research_erv.py", 60),  # rank hypotheses before spending slots
    ("mechanism_board",   "scripts/mechanism_board.py", 60),  # mechanism kills + portfolio + gate
    ("screen_auditor",    "scripts/screen_auditor.py", 60),  # missing-rail audit on screens
    ("cny_premium",       "scripts/collect_cny_premium.py", 60),  # USDT/CNY P2P premium (#76)
    ("axis_shadows",      "scripts/run_axis_shadows.py",     120),  # Stage-B forward eval
    ("reject_rescore",    "scripts/run_rejection_rescore.py", 300),  # feed near-miss reject scores
    ("rejection_shadow",  "scripts/run_rejection_shadow.py",  60),  # gate-leak recovery audit
    ("cost_model",        "scripts/run_cost_model.py",      600),  # measured exec costs (daily)
    ("shadow_8h",         "scripts/run_shadow_8h.py",       420),  # 3x-obs challenger shadow
    ("leverage_opt",      "scripts/run_leverage_opt.py",    120),
    ("molded_refresh",    "scripts/run_live_combined.py",   120),
    # the self-improvement queue: derive review dates so decisions can MATURE, and publish
    # the matured-and-unscored worklist. Never writes an outcome -- scoring is a judgement.
    ("decision_review",   "scripts/run_decision_review.py",  60),
    # what the DESK costs, vs what a trade costs -- the hurdle it must clear to stand still
    ("desk_economics",    "scripts/run_desk_economics.py",   30),
    ("git_snapshot",      "scripts/git_snapshot.py",        120),  # daily forensic code history
]


def _run(script: str, timeout: int) -> dict[str, object]:
    try:
        # R0094: entries may carry args ("research_exchange.py brief", "--report-only").
        # Passing the whole string as one argv element made python treat it as a filename
        # containing a space -> rc=2 every run, swallowed by the best-effort chain.
        r = subprocess.run([_PY, *shlex.split(script)], cwd=str(_ROOT), timeout=timeout,
                           capture_output=True, text=True, check=False)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        return {"ok": r.returncode == 0, "rc": r.returncode, "tail": tail[0][:160]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": "timeout", "tail": f"timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "rc": "error", "tail": repr(e)[:160]}


def _write_status(steps: dict[str, dict[str, object]]) -> None:
    """R0258: atomic failed-steps artifact for the pager (same-dir tmp + os.replace, the
    run_deadman_switch.py idiom) -- run_alerts.py reads it each tick and pages on failures.
    Written on EVERY cycle (empty failed list included) so a later clean run resolves the
    alert. Best-effort: a status-write failure must never abort the cycle."""
    failed = [{"step": k, "rc": v.get("rc"), "tail": str(v.get("tail", ""))[:400]}
              for k, v in steps.items() if not v.get("ok")]
    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "runner": "daily_research_cycle",
        "steps_total": len(steps),
        "failed": failed,
    }
    try:
        _STATUS.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATUS.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), "utf-8")
        os.replace(tmp, _STATUS)
    except OSError as e:
        print(f"[status-write-failed] {e!r}"[:160])


def _load(p: Path, d: object) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def _nav_equity() -> dict[str, object]:
    """E-12/R0095: equity for the cycle log comes from the NAV attestation chain, the desk's
    single hash-chained equity record. web/portfolio.json was a THIRD source of truth and the
    two had already diverged. The chain row carries `mode` (PAPER until Gate-0), so a consumer
    can never mistake a paper sleeve for live capital."""
    try:
        last = (_ROOT / "data" / "nav_attestation.jsonl").read_text("utf-8").strip().splitlines()[-1]
        rec = json.loads(last)
        return {"equity": rec.get("equity_marked"), "equity_date": rec.get("date"),
                "mode": rec.get("mode"), "n_carries": rec.get("n_carries"),
                "source": "nav_attestation_chain"}
    except (OSError, IndexError, json.JSONDecodeError) as e:
        # honest absence beats a silent fallback to the source this exists to retire
        return {"equity": None, "source": f"nav-chain-unreadable: {e!r:.100}"}


def main() -> None:
    steps: dict[str, dict[str, object]] = {}
    for label, script, timeout in _STEPS:
        steps[label] = _run(script, timeout)
        print(f"[{label}] {steps[label]}")
    _write_status(steps)  # R0258: pager artifact, before any bookkeeping below can raise

    # read resulting institutional state for the dated cycle log
    eng = _load(_ROOT / "engineering_backlog.json", {})
    state = _load(_ROOT / "research_state.json", {})
    port = _load(_ROOT / "web" / "portfolio.json", {}).get("deployed", {})
    cal = _load(_ROOT / "web" / "calibration.json", {})
    disc = _load(_ROOT / "web" / "discovery.json", {})
    nxt = eng.get("next_action")

    entry = {
        "date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        "ts": datetime.now(tz=UTC).isoformat(),
        "steps_ok": {k: v.get("ok") for k, v in steps.items()},
        "binding_constraint": state.get("binding_constraint"),
        "next_highest_roi_task": ({"id": nxt.get("id"), "roi": nxt.get("roi")} if nxt else None),
        "open_backlog": [i.get("id") for i in eng.get("open", [])],
        # equity from the NAV chain (E-12); portfolio.json survives only for the sleeve
        # ratios it alone computes -- it is no longer an equity source here.
        "deployed": {**_nav_equity(),
                     **{k: port.get(k) for k in ("net_pnl", "days_live", "deployed_sharpe")}},
        "calibration": {k: cal.get(k) for k in ("n_resolved", "brier", "bias_label")},
        "data_clocks": [p.get("status") for p in disc.get("pending", [])],
    }
    log = _load(_LOG, [])
    if not isinstance(log, list):
        log = []
    log.append(entry)
    _LOG.write_text(json.dumps(log[-400:], indent=2), "utf-8")

    print(f"CRO cycle {entry['date']}: next-ROI={entry['next_highest_roi_task']} "
          f"| constraint={entry['binding_constraint']}")
    if nxt is None:
        print("  no positive-ROI engineering task -> research capital = WAIT on data clocks "
              "+ scope next orthogonal free-data stream (see research_agenda.json).")


if __name__ == "__main__":
    sys.exit(main())
