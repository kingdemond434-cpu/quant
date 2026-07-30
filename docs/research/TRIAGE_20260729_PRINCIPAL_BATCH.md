# TRIAGE — principal directive batch, 2026-07-29 (items 102–131)

Principal order (verbatim intent): *"approve or reject… if these things are all already in the
system then don't add, just improve and max fully… If capability exists, upgrade it to maximum
validated effectiveness. If missing, build it. If duplicated, merge it. If unused, activate it
or retire it."*

Same verdicts as the 07-27 triage: **BUILT** (exists — named artifact), **UPGRADED-THIS-CYCLE**
(existed, maximised today), **BUILD** (approved, in flight), **QUEUE** (blocker named),
**REJECT** (with reason, standing). Numbering continues from TRIAGE_ADDENDUM.md (#101).

## The headline rule applied

Of the ~30 capabilities requested, **21 already exist** in this repo under other names, **4 were
already queued with named blockers**, **3 were already rejected with reasons that still hold**,
and **the genuinely new remainder is small**: an execution-intelligence consolidation, a
reality-gap report, a weekly gap-max sweep, and four constitutional doctrines. That is exactly
the outcome the principal's own anti-bloat rule predicts.

| # | Requested capability | Verdict | Where it lives / blocker / reason |
|---|---|---|---|
| 102 | 24/7 Execution monitoring agent ("fixes and maxes execution") | **BUILD (approved, amended)** | Approved as the principal's own corrected design: monitor→diagnose→recommend→adjust-within-approved-limits, NEVER autonomous live-logic edits. Consolidates what exists: `hedge_integrity.py`, executor TCA fields, `execution_bottleneck.py`, venue-divergence sampler, daily integrity watch, churn rails. Delta = one consolidated report + alert wiring (`run_execution_intel`), not a new agent. |
| 103 | Statistical Validation Agent | **BUILT + UPGRADED-THIS-CYCLE** | The gauntlet (`libs/autodiscovery/validation.py`), `axis_screen` (power-aware), `leakage_detector`. Upgraded today: gap #87 per-candidate PBO/Romano-Wolf flip applied at every call site (principal-ruled); mutation testing installed (first measured scores — gap #53); pre-filter stage (HYPOTHESIS_MAX #1). |
| 104 | Alpha Decay Agent | **QUEUE (standing)** | Triage #34 + register #24 (deadline 08-15): the branch logic exists (fill-ratio × realized-vol discriminator); blocked on >0 deployed alphas to monitor. `revalidate_clocks.py` already covers the forward clocks. |
| 105 | Research Allocation Agent | **BUILT-partial + QUEUE** | ERV ranking (`research_erv.py` + `mechanism_board.py`) IS the allocator. The learning half is triage #38, blocked on per-mechanism n (2/10 vs 0/10 = one coin flip). Not self-unblockable; calendar + experiments. |
| 106 | Data Quality Guardian | **BUILT** | `measurement_gate.py` (fail-closed, 5 contracts) + DQS (commit 91ed648) + dependency graph Tier-0 kill-rail (commit c05da93/122d95b — caught a 34-day error). |
| 107 | Unknown-Unknown Explorer | **QUEUE (402)** | Triage #25. Blocked on the ~$25-50 OpenRouter top-up (register #89: ONE purchase blocks 8 defects). The free half (blind-spot battery, negative-space sweeps, blindrediscovery digs) is BUILT and constitutional (L1.9). |
| 108 | Complexity Auditor | **BUILT** | `meta_architect.py` simplifier + module justification sweep (commits 590d3a4/ef1dbf3: 90/243 modules measured INERT). Principal's "shouldn't be timid though" noted: the sweep's own rule is measured-inertness, not taste. |
| 109 | Market Regime Intelligence | **BUILT / REJECT stands as prediction machine** | `classify_regime.py` + `libs/regime/` (HMM live). Triage #77's rejection of a regime *prediction machine* stands. |
| 110 | Strategy Attribution Agent | **QUEUE (>0 deployed)** | `signal_engine/attribution` exists (orphaned); autopsy (`research_autopsy.py`) covers deaths. Activates with deployed alphas — attribution of a zero-alpha book is arithmetic on noise. |
| 111 | Capital Efficiency Agent | **BUILT** | Utilisation closed end-to-end (commit 0d482b0), growth-audit numerics, `capacity_policy` single source, §42 capacity quotas. |
| 112 | Research Reproducibility Agent | **BUILT** | `experiment_registry.py` — 369 experiments, commit-pinned lineage. |
| 113 | Data Acquisition Strategy Agent | **BUILT** | §33 conversion protocol + `data_axis_watchlist` + `paid_dataset_targets` (§39) + free-frontier axiom. Scoring upgrade = triage #17 (Information Advantage Score), approved BUILD. |
| 114 | Market Impact / Capacity Agent | **QUEUE (TCA accrual)** | Triage #46 — needs live fills to accumulate (now logging). Static capacity gate already in the gauntlet. |
| 115 | Cybersecurity / Op-Resilience Agent | **BUILD-partial (approved)** | Exists: key hygiene plan (GO_LIVE_CHECKLIST), triple-guard arming, capability whitelist AST test. Approved delta: failure-injection drills (venue 5xx, stale tape, partial fills) folded into the connector verification bar (#2) — chaos engineering AT the go-live gate, not a standing agent. |
| 116 | Governance Audit Agent | **BUILT** | `scripts/max_audit.py` (~40 mechanical fences, daily, 48h auto-escalation) IS the requested "Mechanical Enforcement Layer / Capability Audit Loop". Every new organ this cycle lands WITH its fence (L2.2). |
| 117 | Decision Quality Audit / AI Decision Performance Ledger | **BUILT** | `data/decision_ledger.json` (~190 entries: reasoning, expected impact, reversal conditions) + recommendation ledger (R00xx, forced disposition §41) + outcome-scoring cadence (first scoring pass ~08-03 when entries mature 30d). |
| 118 | Adversarial pressure ("every strategy has an enemy") | **BUILT + QUEUE** | L1.7 constitutional; mechanism_board 4-question gate; 13-seat panel; graveyard. The LLM red-team half is triage #22 (402). |
| 119 | Bayesian Belief Updating Engine | **REJECT stands** | Triage #69: multiplies unmeasured priors. The measurable version EXISTS: decision-outcome calibration scoring + family kills updating generation weights (negative knowledge). |
| 120 | Opportunity Cost Engine | **BUILT** | Constitutional L1.14 (no recommendation complete without the best alternative) + ERV ranking enforcing Expected Impact × Confidence ÷ Cost. |
| 121 | Research Portfolio Manager | **QUEUE (>1 validated alpha)** | Triage #30/#31 class. A portfolio of one validated edge has no allocation problem. |
| 122 | Counterfactual Intelligence | **BUILT (doctrine)** | L2.7 decision template requires alternatives + opportunity cost on every recommendation; §36 forces the do-nothing exit to be explicit. |
| 123 | Strategic Horizon Manager | **REJECT (as module)** | Same class as triage #75: a document, not a system. Horizons already separated mechanically: register deadlines (short), §33 dates (medium), quarterly reviews + moat (long). |
| 124 | External Reality Benchmarking | **BUILT-blocked** | `oss_benchmark.md` + 7 frontier miners + prospector/litminer. BLOCKED operationally: 6/7 miners have never run (credentials+cron on the box — human step, `check_miner_runway` ships this cycle to page it). |
| 125 | Strategic Stopping Rule / Sufficient Improvement | **BUILT** | L2.8 default-stability + §36 three-exits discipline (implement / defer with date / retire with reason). |
| 126 | AI Self-Calibration Score | **BUILT (accruing)** | Panel seat scorecards + decision-outcome scoring (matures ~08-03). Cannot be rushed: calibration needs resolved outcomes. |
| 127 | Reality Gap Detection Engine | **BUILD (approved)** | Exists in pieces: L1.4 (reality outranks simulation), shadow-vs-prediction daily checks, venue-divergence sampler, cost predicted-vs-realized (7.75x finding was EXACTLY this engine firing by hand). Approved delta: one consolidated predicted-vs-realised report across backtest→shadow→paper→live chains. |
| 128 | Distribution Shift Monitoring | **BUILD (approved, merged)** | Merge into `revalidate_clocks.py` + regime engine (not a new agent): feature/vol/liquidity drift flags on the live axes, action = revalidate + confidence haircut. |
| 129 | Causal Mechanism Validation | **BUILT** | mechanism_board 4-question gate (who creates it / incentive / persistence / destroyer) + `economic_mechanism` gate in the gauntlet + MEASUREMENT_DOCTRINE. Register #71(4) adds empirical-Bayes on the desk's own tail. |
| 130 | Independent Replication Gate | **BUILD (approved as S1→S2 rider)** | Challenger pattern + held-out OOS harness exist. Approved: promotion S1→S2 requires an independent re-implementation match (different code path, same numbers) — recorded in staging gate docs; zero candidates pending, so this costs nothing until it binds. |
| 131 | Weekly full gap-max sweep (this session, recurring, autonomous) | **BUILD (approved — shipped this cycle)** | New L4 weekly duty + scheduled autonomous session (see WEEKLY_MAX_CYCLE.md). The desk-side half rides the existing weekly deep cold audit; the builder half is the scheduled session. |

## Dispositions requiring nothing (already dead, stays dead)

- "More LLM agents / dashboards for their own sake" — triage #81 rejection re-affirmed by the
  principal's own anti-bloat wording in this directive.
- Confidence Propagation / Uncertainty Budget — triage #68/#70 rejections stand (unmeasured priors).

## The honest bottom line, unchanged from 07-27

The constitution and architecture are not the constraint. The constraint is: **miners without
credentials, one $25-50 funding blocker, collectors, and calendar time to the first forward
verdict (~09-01)**. Everything buildable in this batch was built or wired this cycle; everything
blocked carries its blocker in the register where it escalates.
