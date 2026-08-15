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

from libs.execution.wallet import WALLETS
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
    # 9600s (2026-08-12): run_ci now bounds each of its OWN steps, summing to 8700s worst case
    # (pytest honestly runs 60-80min under --cov, so its inner budget rose to 7200s), and this
    # outer bound must lose that race -- an outer kill produces no [HUNG] line and no
    # red CI marker, which is precisely the stale-green blindness the inner bounds exist to end.
    # This is a ceiling reached only when the gate is wedged, so the
    # rise costs nothing on a healthy day and buys a NAMED failure on a bad one. The ordering is
    # asserted by tests/ops/test_ci_gate_timeouts.py against run_ci.STEP_BUDGET_TOTAL_S.
    ("ci_gate",           "scripts/run_ci.py",             9600),
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
    # THE MONEY PATH, IN THE PIPELINE THAT PROVABLY RUNS. Measured 2026-08-15: the spot book, the
    # discretionary sleeve and the leaderboard panel were all wired into ops/run_research_cycle.sh,
    # which is driven by a USER systemd unit -- and user units do not fire at all unless lingering
    # is enabled for the account. This list is invoked by the 2am root crontab, which is the only
    # daily schedule on this box with observed firings behind it.
    #
    # RUNNING IN BOTH IS SAFE AND DELIBERATE. run_spot_executor trades the DELTA against live
    # holdings, so a second pass the same day sees the book already at target and skips every leg
    # under the venue minimum; client order IDs are keyed to the UTC date, so a genuine duplicate
    # is rejected by the venue rather than filled twice. Duplication costs one API call. The
    # alternative -- a money path that only runs if a user timer happens to be enabled -- costs the
    # day's rebalance, silently, and that is III.16 on the one capability that touches capital.
    # THE PROMOTION PATH, SAME REASONING. run_auto_promotion is the VERB on research-to-capital --
    # auto_promotion.decide() had zero callers until it was written -- and it too lived only in the
    # shell cycle. Armed but unscheduled is indistinguishable from unarmed in every artifact the
    # desk produces. The ladder runs FIRST because promotion must see the Stage-B rows the ladder
    # just published; a promotion decided from a pre-ladder read cites figures the dashboard never
    # showed, which makes it unauditable after the fact.
    # WHY A SEAT IS UNJUDGEABLE, named per slot. The displacement plan correctly refuses to
    # reclaim what it cannot see and then stops, which leaves the item unactionable -- and the
    # queue is the binding constraint on breadth, so an unusable seat is the most expensive
    # object on the desk. Reports only; it never reclaims.
    ("slot_diagnosis",    "scripts/diagnose_forward_slots.py", 120),
    # HOW MANY INDEPENDENT BETS ARE HELD, which is the number every return target rests on and the
    # one nothing else on the desk publishes. "15 sleeves" and "1.2 effective bets" are the same
    # book in every strategy count; k_eff = n/(1+(n-1)rho) separates them. Also the daily caller
    # for the family partition -- seats are per-family or the queue rations breadth globally.
    ("breadth_ledger",    "scripts/report_breadth.py",         120),
    # WHERE THE NEXT RETURN COMES FROM, RANKED -- and it had no daily caller. The census scores
    # every mechanism class by plausibility x orthogonality x data-feasibility x depth-deficit and
    # names, per class, WHO IS FORCED TO TRADE against the desk and which datasets are missing. It
    # is the desk's reading list for breadth, it is the artifact `report_mechanism_supply` consumes,
    # and it ran only when somebody remembered it existed (III.16). Top gaps as of 2026-08-15 are
    # all NO-CANDIDATE: index_reconstitution_flow 0.48, estate_liquidation_distribution 0.45,
    # treasury_cost_base_liquidation 0.42 -- three forced-seller mechanisms the desk has never
    # screened, every one of them FREE-ACQUIRABLE.
    ("mechanism_census",  "scripts/run_mechanism_census.py",   300),
    # THE mechanical_supply_release CHAIN, all four steps of which existed and none of which ran.
    # Vesting cliffs and emissions are a forced seller on an IMMUTABLE schedule -- the same shape as
    # carry, and the highest-orthogonality class whose data the census records as already on disk.
    # The screen honestly reports UNMEASURED while its inputs are missing; running it daily is what
    # turns "we never got to it" into a named, dated deficit that accrues.
    ("unlock_calendar",   "scripts/collect_unlock_calendar.py", 180),
    ("circulating_supply", "scripts/collect_circulating_supply.py", 180),
    ("supply_screen",     "scripts/screen_unlock_supply_series.py", 240),
    ("supply_report",     "scripts/report_mechanism_supply.py", 120),
    ("live_ladder",       "scripts/run_live_ladder.py",      600),
    ("auto_promotion",    "scripts/run_auto_promotion.py --capital 200 --min-notional 10", 300),
    ("golive_preflight",  "scripts/run_golive_preflight.py --capital 200", 120),
    ("spot_targets",      "scripts/run_spot_momentum.py --equity 200 --min-notional 10", 300),
    ("spot_orders",       "scripts/run_spot_executor.py --equity auto --quote USDC --place --reserve-frac 0.3 --wallet {WALLET}", 300),
    # --place: the eleven playbook rules now TRADE, each entry carrying a venue-held stop placed
    # through the same primitive the momentum book uses. --spot-only refuses every short they call
    # and journals the refusal, which on a spot account IS the measurement for H1/H7/H11.
    ("discretionary",     "scripts/run_discretionary_live.py --equity auto --spot-only "
                          "--quote USDC --place --min-notional 5 --wallet {WALLET}", 600),
    # THE LEVERED PATH. Inert without data/MARGIN_ENABLE and without capital in the margin wallet,
    # both of which are the principal's acts. The leverage is COMPUTED every run -- no flag -- so a
    # thin edge borrows nothing and the same line is correct at any Sharpe.
    ("margin_orders",     "scripts/run_margin_executor.py --quote USDC --place", 300),
    # THE MECHANISM SLEEVES, running under a DECLARED SUSPENSION of L1.6 recorded in
    # docs/research/LIVE_EXCEPTION_LEDGER.json. Both steps fail closed without that ledger row, so
    # revoking the exception is one field and binds on the next cycle. They trade as a SEPARATE
    # book with their own target artifact -- merging them into the momentum weights would produce
    # a set no organ published, sized against a Sharpe describing neither.
    ("mechanism_sleeves", "scripts/run_mechanism_sleeves.py", 300),
    ("mechanism_orders",  "scripts/run_margin_executor.py --quote USDC --place "
                          "--targets data/mechanism_sleeve_targets.json", 300),
    ("leaderboards",      "scripts/collect_leaderboards.py", 300),
    ("copytrading_panel", "scripts/screen_copytrading.py",   300),
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
    # THE THIRD COST BASIS, and it runs IMMEDIATELY AFTER the book walk on purpose: it publishes
    # the two side by side, so reading a stale cost_model.json here would compare today's prints
    # against yesterday's depth and call the difference a finding (L1.44 at the read site).
    # 1500s: the first full 3-venue 24h pass measured 11m34s wall, and bybit's batched-trade
    # partitions are the growing half. A timeout sized AT the measurement is a timeout that starts
    # killing the step the week the tape thickens (R0146, the stale-consumer class).
    ("print_impact",      "scripts/fit_print_impact.py",   1500),  # L1.45 3rd basis: others' fills
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
    # THE WALLET IS SUBSTITUTED HERE, NOT HARDCODED IN THE STEP TABLE. Binance treats spot and
    # cross-margin as separate balances, so the day the principal moves capital between them, every
    # sleeve pointed at the old one keeps running perfectly and places nothing. An env var means
    # that move is one line on the box rather than a code change -- and the executors additionally
    # name the other wallet at runtime when it holds the money (`wallet.misplaced_capital`), so a
    # cycle left on the wrong setting reports it instead of going quiet.
    # ENV FIRST, THEN A REPO FILE. `/etc/environment` needs root, and the principal running the
    # desk is not root on this box -- a control surface that requires sudo to change is one that
    # gets left wrong. `data/DESK_WALLET` sits beside the other arming markers, is gitignored so it
    # cannot travel into a clone, and is writable by the account that actually moves the capital.
    desk_wallet = (os.environ.get("DESK_WALLET") or "").strip().lower()
    if not desk_wallet:
        try:
            desk_wallet = (_ROOT / "data" / "DESK_WALLET").read_text("utf-8").strip().lower()
        except OSError:
            desk_wallet = "spot"
    desk_wallet = desk_wallet or "spot"
    if desk_wallet not in WALLETS:
        raise SystemExit(f"DESK_WALLET={desk_wallet!r} is not one of {WALLETS}. Refusing to "
                         "default: a typo that silently trades the wrong wallet is the failure "
                         "this substitution exists to prevent")
    for label, script, timeout in _STEPS:
        steps[label] = _run(script.replace("{WALLET}", desk_wallet), timeout)
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
