# Desk digest (auto-generated daily -- do not hand-edit)
_updated 2026-07-18T08:01Z · companion to [[institutional_knowledge]]_

## Book
- Molded net: **$-73.76** | funding **$84.52** | run-rate APR 20.5% | day 16.11
- Root cause: **expected_variance** (monitor_only) | tracking error $-147.78

## Validation clocks
- **carry (DEPLOYED)**: 22/90d | bt 3.28 fwd 10.26
- **perp L/S**: 15/90d | bt 0.81 fwd -0.82
- **trend**: 15/90d | bt 1.3 fwd -11.58
- **trend regime-gated**: 10/90d | bt 1.28 fwd 0.0
- **OI/LS data**: 20/40d
- **stablecoin data**: 16/40d

## Open decisions (ledger)
- `2026-07-04-cashcarry-top10-4500` -- review 2026-08-04: funding/day rises ~50% without new drift losses by 2026-08-04
- `2026-07-04-levered-lab-3x` -- review 2026-10-02: by day 90: sim vs real comparison decisively answers the leverage question
- `2026-07-04-trend-promotion` -- review 2026-10-02: forward Sharpe >= 0.7 (>=0.5x backtest) at day 90
- `2026-07-04-reconcile-limit-fallback` -- review 2026-08-04: zero stranded orphans > 24h by 2026-08-04
- `2026-07-09-trend-unblend-and-regime-challenger` -- review 2026-10-07: challenger fwd Sharpe > incumbent fwd Sharpe AND >=0.5 at day 90
- `2026-07-09-carry-accounting-symmetric-realized` -- review ?: net_pnl ~= funding - fees +- basis drift as closes accumulate
- `2026-07-09-income-pagination` -- review ?: income totals stable vs manual venue export
- `2026-07-09-carry-hysteresis-hold-while-positive` -- review ?: closes/day < 3 and commissions < 20% of funding by 2026-07-23
- `2026-07-09-liquidation-source-swap-binance-to-bybit` -- review 2026-07-12: data/liquidations.parquet shows events > 0 within 72h and a steady accumulation rate there
- `2026-07-09-duplicate-live-executor-killed` -- review 2026-07-10: No further Python312-rooted process appears in Get-CimInstance Win32_Process going forward
- `2026-07-09-live-autodeploy-preauthorization` -- review at live connect + 60d: first auto-deployed sleeve reaches step-2 (10%) without gate breach
- `2026-07-09-adaptive-validation-windows` -- review first fast-track + 30d: first fast-tracked sleeve survives its first 30 live days without demotion
- `2026-07-10-max-growth-mandate-discovery-engine` -- review 2026-08-10: 0 unresolved NONE-defects older than 1 cycle; >=90 hypotheses scored by 2026-08-10 with gr
- `2026-07-11-rail-autonomy-tiers` -- review first rail move + 30d: first Tier-1/2 rail move is evidence-clean at its 30d review
- `2026-07-12-external-review-fixes` -- review ?: zero false dead-man fires in 90d; first promotion decision uses NW t + regime evidence; li
- `2026-07-12-first-inversion-rule-declined` -- review ?: first live inversion episode: realized DD <= 2x model expectation
- `2026-07-12-first-inversion-rule-adopted` -- review ?: first live inversion episode DD <= model expectation at capped size; cap lifts correctly o
- `2026-07-12-round2-review-fixes` -- review ?: carry day-40 gate evaluates with regime evidence available; no false dead-man events; CI g
- `2026-07-12-deadman-false-fire-incident` -- review ?: zero deadman false fires; single pid-stamped writer verified after every daemon deploy
- `2026-07-12-multi-model-advisory-panel` -- review ?: first automated panel run produces >=1 QUEUE-or-better finding; provider hit-rate measurab
- `2026-07-12-vps-migration-complete` -- review ?: 7 continuous days of clean VPS heartbeats -> live connector enable gate opens
- `2026-07-12-panel-max-roi-upgrade` -- review ?: first generate-mission produces >=1 EV-gate-QUEUE hypothesis; first data-mission surfaces 
- `2026-07-12-monthly-tier1-panel` -- review ?: first monthly tier1 review produces >=1 EV-positive achievable move implemented or queued
- `2026-07-12-panel-roster-refresh-and-memory` -- review ?: roster stays >=10 distinct labs with zero dead IDs; no rejected finding re-triaged after i
- `2026-07-16-nom-thin-book-sizing-fix` -- review ?: 30d post-restart: zero opens >35% of book capital, zero thin-book fills, and dead-man equi
- `2026-07-16-level5-factory-prompt-triage` -- review ?: by pilot day-30 (~2026-08-15): scale-or-not decided from survivors-per-1000 evidence; zero
- `2026-07-16-audit-max-roi-upgrade` -- review ?: 30d: >=1 micro-audit finding leads to a verified fix or a logged ruling; brain_down pager 
- `2026-07-16-pager-silent-death-backoff-fix` -- review ?: test page received by principal; alert state shows successful pushes resuming
- `2026-07-16-gap-elimination-override-adoption` -- review ?: 14d: >=1 benchmark-mission plan or micro-audit missing-action survives code verification a
- `2026-07-16-fred-macro-collector-wired` -- review ?: first pre-registered macro-crypto hypothesis clears or fails the gauntlet honestly within 
- `2026-07-16-leverage-optimizer-runaway` -- review ?: brain root-causes the confidence jump within 3 cycles; no position ever exceeds cap_frac x
- `2026-07-16-v8-master-blueprint-triage` -- review ?: external heartbeat pings green within 48h of operator signup; live-connector spec review i
- `2026-07-17-tier1-scorecard-rider` -- review ?: first two tier1 runs produce >=7 validly-cited dimension scores per model; scores correlat
- `2026-07-17-data-triggered-generation` -- review ?: first matured family (OI/LS ~07-29) gets its scoped generate run within 2 cycles
- `2026-07-17-cadence-engine` -- review ?: 4 weeks: panels fired 7.0+-0.5d apart with zero brain involvement; no double-fires
- `2026-07-17-no-change-cap-principal-order` -- review ?: 30d: zero change-induced incidents despite unrestricted velocity
- `2026-07-17-throughput-amendment-and-connector-spec` -- review ?: connector built to spec + breaker-tested before 2026-08-05; zero same-subsystem collision 
- `2026-07-17-shadow-clock-contamination-ruling` -- review ?: no future cycle re-litigates this contamination question without new code/market evidence
- `2026-07-17-carry-crowding-monitor` -- review ?: web/crowding.json refreshes daily without error; monthly governance references it at least
- `2026-07-17-reconciler-silent-failure-counter` -- review ?: next time a hedge order is persistently rejected, a RECONCILE-FAIL line appears within 3 c
- `2026-07-17-growth-audit-capital-utilization-deferral` -- review ?: once GAP#14 is root-caused and GAP#15 is resolved (trim or natural close), capital utiliza
- `2026-07-17-weekly-architecture-review` -- review ?: next weekly architecture review (within 7 cycles) finds the same conclusion or identifies 
- `2026-07-17-hwm-contamination-false-fire` -- review ?: post-reset baseline forms on clean wallet; no fourth false fire from stale references
- `2026-07-17-spec-prebuild-standing-rule` -- review ?: next 3 implemented register items each had a complete spec before their build began
- `2026-07-17-research-pack-triage` -- review ?: decay-lab spec complete before monthly window; clustering live before next factory expansi
- `2026-07-17-master-expansion-package-triage` -- review ?: 5 specs complete within 5 cycles; liquidation-cascade hypothesis pre-registered within 2 w
- `2026-07-17-deadman-reset-2-principal-approved` -- review ?: 48h: no deadman breach counts; positions ~$300-450/name; measured eq stable vs new HW
- `2026-07-18-prospector-seat-adopted` -- review ?: >=1 provenance-SEMI-or-better card reaching pre-registration within 2 runs; watchlist aliv
- `2026-07-18-execution-lockdown-and-recorder-live` -- review ?: 7 consecutive days of gap-free hourly partitions for 5 symbols; recorder survives a cycle 
- `2026-07-18-literature-deep-miner` -- review ?: >=1 mechanism card surviving to pre-registration within 3 sessions
- `2026-07-18-digging-doctrine-and-autopsy-spec` -- review ?: first dossier produces >=1 new monitored indicator + >=1 drill scenario
- `2026-07-18-digging-cadence-biweekly` -- review ?: all coverage families visited >=1x within 6 weeks; connector progress unimpeded
- `2026-07-18-full-panel-event-rules` -- review ?: Gate-0 pre-mortem produces >=1 finding worth addressing before keys
- `2026-07-18-growth-audit-denominator-fix` -- review ?: zero growth_defect pages while book is fully deployed at authorized size
- `2026-07-18-digging-breadth-all-improvement-classes` -- review ?: within 2 dig cycles, >=1 non-alpha improvement finding captured and spec-queued
- `2026-07-18-ai-methods-digging-gap-closed` -- review ?: within 2 literature cycles, >=1 concrete engine/prompt/eval improvement captured
- `2026-07-18-digger-coverage-self-audit` -- review ?: first coverage audit adds >=1 genuinely missing family OR credibly confirms completeness
- `2026-07-18-youtube-transcript-reality` -- review ?: Prospector cites >=1 video-sourced mechanism via text mirror within 2 runs
- `2026-07-18-ex-solo-quant-priority` -- review ?: within 3 Prospector runs, >=1 card sourced from an ex/solo-quant long-form piece
- `2026-07-18-source-yield-learning` -- review ?: by the 2nd coverage audit, budget measurably shifted toward a proven-productive family

## Executive KPI snapshot
- CRO: {"hypotheses_tested_lifetime": 20, "validated_survivors": 1, "survivor_note": "cash-carry (fwd 8/90); trend candidate gauntlet-passed (fwd 1/90); all else graveyarded", "survival_r
- CEO binding constraint: validation calendar-time + data breadth (NOT engineering; backlog empty)

_Full state: decision_ledger.json · executive_kpis.json · data_registry.json_