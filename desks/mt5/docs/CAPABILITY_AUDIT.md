# Capability-vs-Code Audit

_Standing audit: every mandate requirement classified REAL+WIRED / PARTIAL / STUB /
DOC-ONLY / MISSING. Updated continuously. CODE + TESTS + WIRING > README CLAIMS._

Legend: **REAL+WIRED** = implemented, running, producing data. **PARTIAL** = exists
but incomplete or advisory-only. **STUB** = interface/placeholder, no pipeline.
**DOC-ONLY** = mandated/described, not in code. **MISSING** = not present anywhere.

## Research factory

| Requirement | Status | Evidence |
|---|---|---|
| Survivor production pipeline (hunts 5-16) | REAL+WIRED | run_hunt5/6/9/12/13/15/16; battery gates (t>2, n>60, PF>1.05, maxDD>−30R, 3-fold WF, 2× stress) |
| Family-level multiplicity (deflated t) | REAL+WIRED | E_max family haircuts in every battery; multiplicity.py gate_ds |
| Chronological walk-forward OOS | REAL+WIRED | wf_oos in battery (3 folds all>0) |
| Parameter neighborhood stability | PARTIAL | hunt13 component ablation; no systematic perturbation sweep |
| Session/entry perturbation | PARTIAL | exit_study, window quarantine |
| Cost stress (2×/5×) | REAL+WIRED | battery 2×; validate_fusion cost audit |
| Latency/fill realism | PARTIAL | engine: next-bar-open entries, intrabar trigger fills, costs inside; no latency model |
| Cross-engine truth (independent engine) | MISSING | Fincept steal queued |
| Block bootstrap | REAL+WIRED | portfolio_bootstrap (5d/21d/252d) |
| PBO/CPCV | DOC-ONLY | mandated in MANDATE_RESEARCH_FACTORY; not implemented |
| Placebo/null pipeline | REAL+WIRED | placebo_test.py (bar-return null; fixed 2026-08-17) |
| Graveyard mining | PARTIAL | hunt9 dead-levels report; trade_path; no systematic failure taxonomy |
| Economic failure labels | DOC-ONLY | gold-desk has reference_labeling (that brain); mt5 side none |
| Researcher/miner leaderboard | MISSING | — |
| Idea-to-result latency KPI | MISSING | — |

## Survivor governance

| Requirement | Status | Evidence |
|---|---|---|
| Auto-promotion (shadow→challenger→promoted→scale) | REAL+WIRED | shadow_forward (50 trades/14d verdict) → promoter → sleeves.json → gateway |
| Champion margin / kill rules | REAL+WIRED | XAUUSD challengers must beat armed exp −0.02; JPY promote directly |
| Auto-retire / decay monitors | REAL+WIRED | roll20 exp≤0 / maxDD<−25R / n≥50 exp<0.05 → RETIRED |
| Regime hibernation (gold book) | REAL+WIRED | regime_hibernate + regime_monitor maxDD rule |
| Forward ledger (append-only, frozen) | REAL+WIRED | live_ledger.jsonl + shadow_forward separate |
| Live-vs-research isolation (immutable champions) | REAL+WIRED | gateway deterministic loop; research never writes live state |
| Edge Hardness / durability scores | DOC-ONLY | rubric in frontier mandate; advisory, no code |
| Directional specialization (L/S organisms) | REAL+WIRED | hunt16 LONG/SHORT separate cells |
| Dynamic allocation (posterior E[log W]) | PARTIAL | allocation.py advisory; equal-weight default; no auto reallocation |
| Capacity modeling | DOC-ONLY | EUR-400 guard + lot ramp; no impact model |

## Data

| Requirement | Status | Evidence |
|---|---|---|
| Universe + parquet lake | REAL+WIRED | data/universe (H1 parquets), universe.json costs, data_registry.json |
| Free-data frontier | REAL+WIRED | free_data_frontier.json; cot, cot_tff, states |
| Paid→free proxy reconstruction | PARTIAL | fetch_triangle, states synthesis; institutional proxies queued |
| Private-data compounding | PARTIAL | live_ledger, trade_path MAE/MFE; no systematic decision/quote DB yet |
| Microstructure features (OBI, book, toxicity) | MISSING | queued (Fincept) |
| Dividend durability / slow macro factors | MISSING | iREIT source logged, queued |
| Market-plumbing data (auctions, repo, basis) | MISSING | queued per mandate |

## Operations / infrastructure

| Requirement | Status | Evidence |
|---|---|---|
| Gateway loop (Startup, restart-on-death) | REAL+WIRED | MT5Gateway.cmd loop; watchdog exemption (cwd-based) |
| Broker abstraction (venue-independent strategies) | PARTIAL | MetaTrader5 only; validate_fusion prepares Fusion; no adapter layer |
| Fail-closed (stale/invalid → no order) | REAL+WIRED | GATEWAY_PAUSED, gateway_paused(), spread gates, arm/stop bracket discipline |
| DataHub (one-fetch-many-subscribers) | MISSING | queued (Fincept); currently per-script fetch |
| Miner checkpointing / resume | PARTIAL | hunts resumable via partial JSON; no general task state |
| Universal tool registry / MCP | MISSING | queued (Fincept) |
| Hourly cycle (health + mining + validation + sync) | MISSING | building (research/hourly_cycle.py) |
| Hourly sync to VPS brains | MISSING | building (MT5Sync.cmd + bundle) |
| Daily frontier report | MISSING | building (hourly_cycle writes reports/frontier.json) |

## Mandates coverage

| Mandate doc | Coverage |
|---|---|
| MANDATE_FREE_DATA_SUPREMACY | PARTIAL (free frontier live; reconstruction growing) |
| MANDATE_RESEARCH_FACTORY | PARTIAL (core validation live; PBO/latency/leaderboard missing) |
| MANDATE_INSTITUTIONAL_ADVANTAGE | PARTIAL (moat hierarchy documented; proxies queued) |
| MANDATE_UNIVERSE | REAL+WIRED (sweep live) |
| MANDATE_MECHANISM_RE | REAL+WIRED (hunt13 component decomposition) |
| MANDATE_AUTONOMOUS_FRONTIER | PARTIAL (loop live; allocation/hardness doc-only) |
| MANDATE_EXTERNAL_INTELLIGENCE | PARTIAL (provenance registry live; mining loop building) |
| MANDATE_GLOBAL_MINER | PARTIAL (absorbed sources live: Davidd hunt16, Fincept queued, iREIT queued; video/multi-language mining MISSING) |

## Immediate gap-closure queue (by expected marginal ROI)

1. Hourly cycle + sync (this build) — makes everything self-maintaining and shared.
2. Bar-null placebo verdicts → correct SUSPECT flags (in flight).
3. Cross-engine truth (independent replay engine for champions) — Fincept steal.
4. Miner checkpointing generalization.
5. Broker adapter layer (Fusion second venue).
6. PBO/CPCV on the survivor population once universe sweep completes.
7. Edge-hardness scoring as code (advisory fields in survivor records).
8. Daily frontier report as standing artifact.