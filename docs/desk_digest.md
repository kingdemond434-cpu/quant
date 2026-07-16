# Desk digest (auto-generated daily -- do not hand-edit)
_updated 2026-07-16T08:01Z · companion to [[institutional_knowledge]]_

## Book
- Molded net: **$-16.73** | funding **$75.16** | run-rate APR 31.7% | day 14.11
- Root cause: **unknown_novel** (pause_and_page) | tracking error $-195.39

## Validation clocks
- **carry (DEPLOYED)**: 19/90d | bt 3.27 fwd 10.1
- **perp L/S**: 12/90d | bt 0.48 fwd 4.31
- **trend**: 12/90d | bt 1.41 fwd -10.92
- **trend regime-gated**: 7/90d | bt 1.36 fwd 0.0
- **OI/LS data**: 17/40d
- **stablecoin data**: 14/40d

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

## Executive KPI snapshot
- CRO: {"hypotheses_tested_lifetime": 20, "validated_survivors": 1, "survivor_note": "cash-carry (fwd 8/90); trend candidate gauntlet-passed (fwd 1/90); all else graveyarded", "survival_r
- CEO binding constraint: validation calendar-time + data breadth (NOT engineering; backlog empty)

_Full state: decision_ledger.json · executive_kpis.json · data_registry.json_